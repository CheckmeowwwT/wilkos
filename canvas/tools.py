from __future__ import annotations

import colorsys
import math
import random
from collections import deque

import pygame
from PIL import Image as PILImage

try:
    from ..constants import CANVAS_PALETTE
except ImportError:
    from constants import CANVAS_PALETTE  # type: ignore[no-redef]


class CanvasToolsMixin:
    def _update_canvas_focus_tools_hover(self) -> None:
        if not (self.workspace_mode == "canvas" and self.canvas_focus_mode):
            self.canvas_focus_tools_open = False
            self.canvas_focus_tools_progress = 0.0
            return
        width = max(220, self.canvas_inspector_width)
        panel_rect = pygame.Rect(
            self.screen_width - self.gutter - width,
            self.gutter,
            width,
            self.screen_height - self.gutter * 2,
        )
        vert_ok = panel_rect.y <= self.drag_pos[1] <= panel_rect.bottom
        edge_hot = vert_ok and self.drag_pos[0] >= self.screen_width - 2
        if self.canvas_focus_tools_open:
            stay_open = vert_ok and self.drag_pos[0] >= panel_rect.left
            self.canvas_focus_tools_open = stay_open or edge_hot
        else:
            self.canvas_focus_tools_open = edge_hot
        target = 1.0 if self.canvas_focus_tools_open else 0.0
        speed = 0.18
        if self.canvas_focus_tools_progress < target:
            self.canvas_focus_tools_progress = min(target, self.canvas_focus_tools_progress + speed)
        elif self.canvas_focus_tools_progress > target:
            self.canvas_focus_tools_progress = max(target, self.canvas_focus_tools_progress - speed)

    # ── Canvas right-panel layout helpers ──────────────────────────────

    _CANVAS_TOOLS = [
        ("select",     "Lasso Select"),
        ("rectselect", "Square Select"),
        ("eyedropper", "Pick"),
        ("move",       "Move"),
        ("pencil",     "Pencil"),
        ("brush",      "Brush"),
        ("eraser",     "Eraser"),
        ("bucket",     "Bucket"),
        ("line",       "Line"),
        ("circle",     "Circle"),
        ("square",     "Square"),
        ("spray",      "Spray"),
        ("blend",      "Blend"),
        ("smudge",     "Smudge"),
        ("vpoint",     "VP"),
        ("light",      "Light"),
    ]

    # Unicode icons rendered in tool buttons (1-2 chars each)
    _CANVAS_TOOL_ICONS: dict[str, str] = {
        "select":     "◇",
        "rectselect": "▣",
        "eyedropper": "⊙",
        "move":       "⊕",
        "pencil":     "╱",
        "brush":      "○",
        "eraser":     "□",
        "bucket":     "▽",
        "line":       "—",
        "circle":     "◯",
        "square":     "▭",
        "spray":      "∷",
        "blend":      "≈",
        "smudge":     "∼",
        "vpoint":     "◁",
        "light":      "Lt",
    }

    def _canvas_selection_screen_rect(self, draw_rect: pygame.Rect) -> pygame.Rect | None:
        bbox = self.canvas_sel_base_bbox if self.canvas_sel_transform and self.canvas_sel_base_bbox else self._canvas_sel_bbox()
        if bbox is None or self.canvas_surface is None:
            return None
        min_x, min_y, max_x, max_y = bbox
        if self.canvas_sel_transform == "move" and self.canvas_sel_lift:
            ox, oy = self.canvas_sel_offset
            left_f = min_x + ox
            top_f = min_y + oy
            right_f = max_x + 1 + ox
            bottom_f = max_y + 1 + oy
        elif self.canvas_sel_transform == "scale" and self.canvas_sel_scale_rect is not None:
            left_f, top_f, right_f, bottom_f = self.canvas_sel_scale_rect
        else:
            left_f, top_f = float(min_x), float(min_y)
            right_f, bottom_f = float(max_x + 1), float(max_y + 1)
        left = draw_rect.x + int(left_f * self.canvas_zoom)
        top = draw_rect.y + int(top_f * self.canvas_zoom)
        right = draw_rect.x + int(right_f * self.canvas_zoom)
        bottom = draw_rect.y + int(bottom_f * self.canvas_zoom)
        return pygame.Rect(left, top, max(1, right - left), max(1, bottom - top))

    def _canvas_selection_handle_rects(self, draw_rect: pygame.Rect) -> dict[str, pygame.Rect]:
        box = self._canvas_selection_screen_rect(draw_rect)
        if box is None:
            return {}
        hs = 16
        centers = {
            "tl": box.topleft,
            "tm": (box.centerx, box.top),
            "tr": box.topright,
            "ml": (box.left, box.centery),
            "mr": (box.right, box.centery),
            "bl": box.bottomleft,
            "bm": (box.centerx, box.bottom),
            "br": box.bottomright,
        }
        return {
            key: pygame.Rect(cx - hs // 2, cy - hs // 2, hs, hs)
            for key, (cx, cy) in centers.items()
        }

    def _canvas_selection_overlay_action_rects(self, draw_rect: pygame.Rect) -> dict[str, pygame.Rect]:
        return {}

    def _canvas_sprite_model_match(self) -> dict | None:
        """Return the stored 3D sprite model if the current selection is the same sprite."""
        model = getattr(self, "canvas_sprite_model", None)
        if not isinstance(model, dict):
            return None
        sel = self.canvas_selection_pixels
        if not sel:
            return None
        model_pixels = model.get("pixels")
        if not model_pixels:
            return None
        inter = len(sel & model_pixels)
        union = len(sel | model_pixels)
        if union == 0:
            return None
        if inter / union >= 0.6:
            return model
        return None

    def _canvas_invalidate_sprite_model(self) -> None:
        self.canvas_sprite_model = None

    def _canvas_save_sprite_model(
        self,
        original_surface: pygame.Surface,
        origin_min: tuple[int, int],
        rot: tuple[float, float, float],
        painted_pixels: set[tuple[int, int]],
    ) -> None:
        self.canvas_sprite_model = {
            "surface": original_surface.copy(),
            "origin_min": (int(origin_min[0]), int(origin_min[1])),
            "rot": (float(rot[0]), float(rot[1]), float(rot[2])),
            "pixels": set(painted_pixels),
        }

    def _canvas_rebuild_selection_surface(self) -> None:
        self._canvas_sel_preview_cache_key = None
        self._canvas_sel_preview_surf = None
        self._canvas_sel_rotate_cache_key = None
        self._canvas_sel_rotate_cache_surf = None
        self._canvas_clear_3d_selection_cache()
        if not self.canvas_sel_lift:
            self.canvas_sel_surface = None
            self.canvas_sel_base_bbox = None
            self.canvas_sel_scale_rect = None
            return
        xs = [p[0] for p in self.canvas_sel_lift]
        ys = [p[1] for p in self.canvas_sel_lift]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        surf = pygame.Surface((max_x - min_x + 1, max_y - min_y + 1), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        for (px, py), color in self.canvas_sel_lift.items():
            surf.set_at((px - min_x, py - min_y), color)
        self.canvas_sel_surface = surf
        self.canvas_sel_base_bbox = (min_x, min_y, max_x, max_y)
        self.canvas_sel_scale_rect = (float(min_x), float(min_y), float(max_x + 1), float(max_y + 1))

    def _canvas_apply_surface_selection(
        self,
        surf: pygame.Surface,
        top_left: tuple[int, int],
    ) -> set[tuple[int, int]]:
        if self.canvas_surface is None:
            return set()
        sw, sh = self.canvas_surface.get_size()
        ox, oy = top_left
        selected: set[tuple[int, int]] = set()
        for sy in range(surf.get_height()):
            for sx in range(surf.get_width()):
                color = surf.get_at((sx, sy))
                if color.a <= 0:
                    continue
                tx = ox + sx
                ty = oy + sy
                if 0 <= tx < sw and 0 <= ty < sh:
                    self.canvas_surface.set_at((tx, ty), color)
                    selected.add((tx, ty))
        return selected

    def _canvas_move_selection_immediate(self, dx: int, dy: int) -> bool:
        if self.canvas_surface is None or not self.canvas_selection_pixels or (dx == 0 and dy == 0):
            return False
        # Refuse to nudge while another transform is active — entering "move"
        # here would re-lift pixels already cleared by the in-flight transform
        # and the subsequent commit would erase the selection.
        if self.canvas_sel_transform not in (None, "move"):
            return False
        if self.canvas_sel_transform == "move" and self.canvas_sel_lift:
            ox, oy = self.canvas_sel_offset
            self.canvas_sel_offset = (ox + dx, oy + dy)
        else:
            self._canvas_enter_sel_transform("move", auto_commit=False)
            self.canvas_sel_offset = (dx, dy)
        self._canvas_commit_sel_transform()
        self.status = "Selection moved."
        return True

    def _canvas_draw_rect(self, view: pygame.Rect, surface: pygame.Surface) -> pygame.Rect:
        sw, sh = surface.get_size()
        if sw <= 0 or sh <= 0:
            return pygame.Rect(view.x, view.y, 1, 1)
        w = max(1, int(sw * self.canvas_zoom))
        h = max(1, int(sh * self.canvas_zoom))
        cx = view.centerx + int(self.canvas_offset_x)
        cy = view.centery + int(self.canvas_offset_y)
        return pygame.Rect(cx - w // 2, cy - h // 2, w, h)

    def _canvas_pixel_at(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        if self.canvas_surface is None:
            return None
        panel = self._canvas_workspace_panel_rect()
        view = self._canvas_view_rect(panel)
        draw = self._canvas_draw_rect(view, self.canvas_surface)
        if not draw.collidepoint(pos):
            return None
        sx, sy = self.canvas_surface.get_size()
        px = int((pos[0] - draw.x) / max(self.canvas_zoom, 0.001))
        py = int((pos[1] - draw.y) / max(self.canvas_zoom, 0.001))
        px = max(0, min(px, sx - 1))
        py = max(0, min(py, sy - 1))
        return (px, py)

    def _canvas_fit(self) -> None:
        if self.canvas_surface is None:
            self.canvas_zoom = 4.0
            self.canvas_offset_x = 0.0
            self.canvas_offset_y = 0.0
            return
        panel = self._canvas_workspace_panel_rect()
        view = self._canvas_view_rect(panel)
        sw, sh = self.canvas_surface.get_size()
        if sw <= 0 or sh <= 0:
            return
        self.canvas_zoom = max(1.0, min(view.width / sw, view.height / sh))
        self.canvas_offset_x = 0.0
        self.canvas_offset_y = 0.0

    def _canvas_zoom_at(self, screen_pos: tuple[int, int], delta: int) -> None:
        if self.canvas_surface is None:
            return
        panel = self._canvas_workspace_panel_rect()
        view = self._canvas_view_rect(panel)
        old_zoom = self.canvas_zoom
        factor = 1.15 if delta > 0 else (1 / 1.15)
        self.canvas_zoom = max(0.5, min(self.canvas_zoom * factor, 20.0))
        if abs(self.canvas_zoom - old_zoom) < 1e-6:
            return
        # Zoom toward mouse position
        mx = screen_pos[0] - view.centerx - self.canvas_offset_x
        my = screen_pos[1] - view.centery - self.canvas_offset_y
        scale = self.canvas_zoom / max(old_zoom, 1e-6)
        self.canvas_offset_x += mx - mx * scale
        self.canvas_offset_y += my - my * scale

    def _sync_canvas_hsv_from_color(self, color: tuple[int, int, int, int]) -> None:
        r, g, b, _ = color
        hue, sat, val = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        self.canvas_color_hue = hue
        self.canvas_color_sat = sat
        self.canvas_color_val = val

    def _set_canvas_color(self, color: tuple[int, int, int, int]) -> None:
        self.canvas_color = tuple(max(0, min(255, int(channel))) for channel in color)  # type: ignore[assignment]
        self._sync_canvas_hsv_from_color(self.canvas_color)
        self._record_canvas_color_use(self.canvas_color, weight=1)

    def _record_canvas_color_use(self, color: tuple[int, int, int, int], weight: int = 1) -> None:
        if len(color) < 4 or color[3] <= 0 or weight <= 0:
            return
        normalized = tuple(max(0, min(255, int(channel))) for channel in color[:4])
        self.canvas_color_usage[normalized] = self.canvas_color_usage.get(normalized, 0) + weight

    def _canvas_quick_palette(self) -> list[tuple[int, int, int, int]]:
        ranked = sorted(
            self.canvas_color_usage.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2], item[0][3]),
        )
        palette = [color for color, _ in ranked[:5]]
        for fallback in CANVAS_PALETTE:
            if len(palette) >= 5:
                break
            if fallback not in palette:
                palette.append(fallback)
        current = self.canvas_color
        if current not in palette:
            palette = [current] + palette[:4]
        return palette[:5]

    def _canvas_apply_quick_palette_slot(self, slot_idx: int) -> bool:
        palette = self._canvas_quick_palette()
        if not (0 <= slot_idx < len(palette)):
            return False
        self._set_canvas_color(palette[slot_idx])
        self.status = f"Quick color {slot_idx + 1}: {self._canvas_color_hex()}."
        return True

    @staticmethod
    def _canvas_dirty_rect_from_points(
        points: list[tuple[int, int]],
        pad: int = 0,
    ) -> pygame.Rect:
        if not points:
            return pygame.Rect(0, 0, 0, 0)
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x = min(xs) - pad
        min_y = min(ys) - pad
        max_x = max(xs) + pad
        max_y = max(ys) + pad
        return pygame.Rect(min_x, min_y, (max_x - min_x) + 1, (max_y - min_y) + 1)

    def _canvas_scaled_selection_preview(
        self,
        mode_key: str,
        size: tuple[int, int],
    ) -> pygame.Surface | None:
        if self.canvas_sel_surface is None:
            return None
        width = max(1, int(size[0]))
        height = max(1, int(size[1]))
        source = self.canvas_sel_surface
        cache_key = (mode_key, id(source), source.get_width(), source.get_height(), width, height)
        if self._canvas_sel_preview_cache_key != cache_key or self._canvas_sel_preview_surf is None:
            self._canvas_sel_preview_surf = pygame.transform.scale(source, (width, height))
            self._canvas_sel_preview_cache_key = cache_key
        return self._canvas_sel_preview_surf

    def _canvas_rotated_selection_preview(self, angle: float, zoom: float = 1.0) -> pygame.Surface | None:
        if self.canvas_sel_surface is None:
            return None
        source = self.canvas_sel_surface
        angle_key = int(round(angle * 10.0))
        zoom_key = int(round(max(0.01, zoom) * 100.0))
        cache_key = ("rotate", id(source), source.get_width(), source.get_height(), angle_key, zoom_key)
        if self._canvas_sel_rotate_cache_key != cache_key or self._canvas_sel_rotate_cache_surf is None:
            rotated = pygame.transform.rotate(source, -angle)
            target_size = (
                max(1, int(round(rotated.get_width() * max(0.01, zoom)))),
                max(1, int(round(rotated.get_height() * max(0.01, zoom)))),
            )
            self._canvas_sel_rotate_cache_surf = pygame.transform.scale(rotated, target_size)
            self._canvas_sel_rotate_cache_key = cache_key
        return self._canvas_sel_rotate_cache_surf

    def _canvas_clear_3d_selection_cache(self) -> None:
        self._canvas_sel_3d_cache_key = None
        self._canvas_sel_3d_cache_surf = None
        self._canvas_sel_3d_cache_offset = (0.0, 0.0)

    @staticmethod
    def _canvas_solve_linear_system(
        matrix: list[list[float]],
        values: list[float],
    ) -> list[float] | None:
        n = len(values)
        rows = [matrix[i][:] + [values[i]] for i in range(n)]
        for col in range(n):
            pivot = max(range(col, n), key=lambda row: abs(rows[row][col]))
            if abs(rows[pivot][col]) < 1e-9:
                return None
            if pivot != col:
                rows[col], rows[pivot] = rows[pivot], rows[col]
            pivot_value = rows[col][col]
            for item_col in range(col, n + 1):
                rows[col][item_col] /= pivot_value
            for row in range(n):
                if row == col:
                    continue
                factor = rows[row][col]
                if abs(factor) < 1e-12:
                    continue
                for item_col in range(col, n + 1):
                    rows[row][item_col] -= factor * rows[col][item_col]
        return [rows[row][n] for row in range(n)]

    @classmethod
    def _canvas_homography(
        cls,
        src: list[tuple[float, float]],
        dst: list[tuple[float, float]],
    ) -> tuple[float, float, float, float, float, float, float, float, float] | None:
        if len(src) != 4 or len(dst) != 4:
            return None
        matrix: list[list[float]] = []
        values: list[float] = []
        for (x, y), (u, v) in zip(src, dst):
            matrix.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
            values.append(u)
            matrix.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
            values.append(v)
        solved = cls._canvas_solve_linear_system(matrix, values)
        if solved is None:
            return None
        return (
            solved[0], solved[1], solved[2],
            solved[3], solved[4], solved[5],
            solved[6], solved[7], 1.0,
        )

    @staticmethod
    def _canvas_apply_homography(
        matrix: tuple[float, float, float, float, float, float, float, float, float],
        x: float,
        y: float,
    ) -> tuple[float, float] | None:
        h0, h1, h2, h3, h4, h5, h6, h7, h8 = matrix
        denom = (h6 * x) + (h7 * y) + h8
        if abs(denom) < 1e-9:
            return None
        return (
            ((h0 * x) + (h1 * y) + h2) / denom,
            ((h3 * x) + (h4 * y) + h5) / denom,
        )

    def _canvas_project_3d_corners(
        self,
        width: int,
        height: int,
        rot_x: float,
        rot_y: float,
        rot_z: float,
    ) -> list[tuple[float, float]]:
        return [
            self._canvas_project_3d_point(width, height, u, v, 0.0, rot_x, rot_y, rot_z)[:2]
            for u, v in ((0.0, 0.0), (float(width), 0.0), (float(width), float(height)), (0.0, float(height)))
        ]

    def _canvas_project_3d_point(
        self,
        width: int,
        height: int,
        u: float,
        v: float,
        local_z: float,
        rot_x: float,
        rot_y: float,
        rot_z: float,
    ) -> tuple[float, float, float]:
        def avoid_edge_on(angle: float) -> float:
            normalized = angle % 360.0
            for edge in (90.0, 270.0):
                if abs(normalized - edge) < 0.35:
                    return angle + (0.35 if normalized >= edge else -0.35)
            return angle

        rot_x = avoid_edge_on(rot_x)
        rot_y = avoid_edge_on(rot_y)
        rx = math.radians(rot_x)
        ry = math.radians(rot_y)
        rz = math.radians(rot_z)
        cos_x, sin_x = math.cos(rx), math.sin(rx)
        cos_y, sin_y = math.cos(ry), math.sin(ry)
        cos_z, sin_z = math.cos(rz), math.sin(rz)
        half_w = width / 2.0
        half_h = height / 2.0
        distance = max(float(width), float(height), 16.0) * 4.0
        x = u - half_w
        y = v - half_h
        z = local_z

        y, z = (y * cos_x) - (z * sin_x), (y * sin_x) + (z * cos_x)
        x, z = (x * cos_y) + (z * sin_y), (-x * sin_y) + (z * cos_y)
        x, y = (x * cos_z) - (y * sin_z), (x * sin_z) + (y * cos_z)

        denom = max(distance + z, distance * 0.2)
        perspective = distance / denom
        return x * perspective, y * perspective, z

    @staticmethod
    def _canvas_abs_normalized_angle(angle: float) -> float:
        normalized = angle % 360.0
        return min(normalized, 360.0 - normalized)

    def _canvas_3d_rotation_is_identity(self, tolerance: float = 1.5) -> bool:
        return all(
            self._canvas_abs_normalized_angle(angle) <= tolerance
            for angle in (self.canvas_sel_3d_x, self.canvas_sel_3d_y, self.canvas_sel_3d_z)
        )

    @staticmethod
    def _canvas_darken_rgba(color: pygame.Color | tuple[int, int, int, int], factor: float) -> tuple[int, int, int, int]:
        r, g, b, a = color
        factor = max(0.0, min(1.0, factor))
        return (int(r * factor), int(g * factor), int(b * factor), int(a))

    @staticmethod
    def _canvas_rotate_3d_vector(
        x: float,
        y: float,
        z: float,
        rot_x: float,
        rot_y: float,
        rot_z: float,
    ) -> tuple[float, float, float]:
        rx = math.radians(rot_x)
        ry = math.radians(rot_y)
        rz = math.radians(rot_z)
        cos_x, sin_x = math.cos(rx), math.sin(rx)
        cos_y, sin_y = math.cos(ry), math.sin(ry)
        cos_z, sin_z = math.cos(rz), math.sin(rz)
        y, z = (y * cos_x) - (z * sin_x), (y * sin_x) + (z * cos_x)
        x, z = (x * cos_y) + (z * sin_y), (-x * sin_y) + (z * cos_y)
        x, y = (x * cos_z) - (y * sin_z), (x * sin_z) + (y * cos_z)
        length = max(1e-6, math.sqrt((x * x) + (y * y) + (z * z)))
        return x / length, y / length, z / length

    def _canvas_3d_face_normal(
        self,
        face: str,
        rot_x: float,
        rot_y: float,
        rot_z: float,
    ) -> tuple[float, float, float]:
        normals = {
            "front": (0.0, 0.0, -1.0),
            "back": (0.0, 0.0, 1.0),
            "left": (-1.0, 0.0, 0.0),
            "right": (1.0, 0.0, 0.0),
            "top": (0.0, -1.0, 0.0),
            "bottom": (0.0, 1.0, 0.0),
        }
        return self._canvas_rotate_3d_vector(*normals[face], rot_x, rot_y, rot_z)

    @staticmethod
    def _canvas_3d_face_visibility(normal: tuple[float, float, float]) -> float:
        return max(0.0, -normal[2])

    @staticmethod
    def _canvas_apply_light_rgba(
        color: pygame.Color | tuple[int, int, int, int],
        factor: float,
        *,
        cool_shadow: float = 0.0,
    ) -> tuple[int, int, int, int]:
        r, g, b, a = color
        factor = max(0.0, min(1.45, factor))
        if factor >= 1.0:
            lift = min(0.38, (factor - 1.0) * 0.6)
            r = int(r + (255 - r) * lift)
            g = int(g + (255 - g) * lift)
            b = int(b + (255 - b) * lift)
        else:
            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)
            if cool_shadow > 0.0:
                b = min(255, int(b + 18 * cool_shadow))
                g = min(255, int(g + 6 * cool_shadow))
        return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)), int(a))

    def _canvas_3d_shade_for_normal(
        self,
        normal: tuple[float, float, float],
        *,
        base: str,
    ) -> float:
        light = (-0.42, -0.62, -0.66)
        light_len = math.sqrt(sum(component * component for component in light))
        lx, ly, lz = (component / light_len for component in light)
        diffuse = max(0.0, (normal[0] * lx) + (normal[1] * ly) + (normal[2] * lz))
        camera = self._canvas_3d_face_visibility(normal)
        if base == "front":
            return max(0.58, min(1.18, 0.58 + diffuse * 0.34 + camera * 0.22))
        if base == "back":
            return max(0.30, min(0.78, 0.28 + diffuse * 0.24 + camera * 0.18))
        rim = max(0.0, abs(normal[0]) * 0.08 + max(0.0, -normal[1]) * 0.08)
        return max(0.34, min(1.12, 0.34 + diffuse * 0.48 + camera * 0.24 + rim))

    def _canvas_inferred_edge_color(
        self,
        source: pygame.Surface,
        alpha_mask: list[list[bool]],
        x: int,
        y: int,
        edge: str,
    ) -> tuple[int, int, int, int]:
        width, height = source.get_size()
        inward = {
            "left": (1, 0),
            "right": (-1, 0),
            "top": (0, 1),
            "bottom": (0, -1),
        }[edge]
        tangent = (0, 1) if edge in {"left", "right"} else (1, 0)
        samples: list[tuple[int, int, int, int, int]] = []
        for step, weight in ((0, 5), (1, 3), (2, 1)):
            for side in (-1, 0, 1):
                sx = x + inward[0] * step + tangent[0] * side
                sy = y + inward[1] * step + tangent[1] * side
                if not (0 <= sx < width and 0 <= sy < height):
                    continue
                if not alpha_mask[sy][sx]:
                    continue
                color = source.get_at((sx, sy))
                samples.append((color.r, color.g, color.b, color.a, weight if side == 0 else max(1, weight - 1)))
        if not samples:
            color = source.get_at((x, y))
            return color.r, color.g, color.b, color.a
        total = sum(weight for *_, weight in samples)
        r = sum(red * weight for red, _, _, _, weight in samples) / total
        g = sum(green * weight for _, green, _, _, weight in samples) / total
        b = sum(blue * weight for _, _, blue, _, weight in samples) / total
        a = sum(alpha * weight for _, _, _, alpha, weight in samples) / total
        return int(r), int(g), int(b), int(a)

    def _canvas_inferred_surface_color(
        self,
        source: pygame.Surface,
        alpha_mask: list[list[bool]],
        x: int,
        y: int,
    ) -> tuple[int, int, int, int]:
        width, height = source.get_size()
        samples: list[tuple[int, int, int, int, int]] = []
        for sy in range(max(0, y - 1), min(height, y + 2)):
            for sx in range(max(0, x - 1), min(width, x + 2)):
                if not alpha_mask[sy][sx]:
                    continue
                color = source.get_at((sx, sy))
                weight = 5 if (sx, sy) == (x, y) else 1
                samples.append((color.r, color.g, color.b, color.a, weight))
        if not samples:
            color = source.get_at((x, y))
            return color.r, color.g, color.b, color.a
        total = sum(weight for *_, weight in samples)
        r = sum(red * weight for red, _, _, _, weight in samples) / total
        g = sum(green * weight for _, green, _, _, weight in samples) / total
        b = sum(blue * weight for _, _, blue, _, weight in samples) / total
        a = sum(alpha * weight for _, _, _, alpha, weight in samples) / total
        return int(r), int(g), int(b), int(a)

    @staticmethod
    def _canvas_draw_projected_quad(
        output: pygame.Surface,
        points: list[tuple[float, float, float]],
        color: tuple[int, int, int, int],
        bounds_offset: tuple[float, float],
    ) -> None:
        if color[3] <= 0:
            return
        ox, oy = bounds_offset
        pts2 = [(px - ox, py - oy) for px, py, _ in points]
        min_x = math.floor(min(px for px, _ in pts2))
        min_y = math.floor(min(py for _, py in pts2))
        max_x = math.ceil(max(px for px, _ in pts2))
        max_y = math.ceil(max(py for _, py in pts2))
        if max_x < 0 or max_y < 0 or min_x >= output.get_width() or min_y >= output.get_height():
            return
        if max_x - min_x <= 1 and max_y - min_y <= 1:
            cx = int(round(sum(px for px, _ in pts2) / len(pts2)))
            cy = int(round(sum(py for _, py in pts2) / len(pts2)))
            if 0 <= cx < output.get_width() and 0 <= cy < output.get_height():
                output.set_at((cx, cy), color)
            return
        cx = sum(px for px, _ in pts2) / len(pts2)
        cy = sum(py for _, py in pts2) / len(pts2)
        expanded: list[tuple[int, int]] = []
        for px, py in pts2:
            dx = px - cx
            dy = py - cy
            length = math.hypot(dx, dy)
            if length > 1e-6:
                px += (dx / length) * 0.12
                py += (dy / length) * 0.12
            expanded.append((int(round(px)), int(round(py))))
        pygame.draw.polygon(output, color, expanded)

    @staticmethod
    def _canvas_surface_to_pil(surface: pygame.Surface) -> PILImage.Image:
        raw = pygame.image.tobytes(surface, "RGBA", False)
        return PILImage.frombytes("RGBA", surface.get_size(), raw)

    @staticmethod
    def _canvas_pil_to_surface(image: PILImage.Image) -> pygame.Surface:
        return pygame.image.frombytes(image.tobytes(), image.size, "RGBA")

    def _canvas_warp_face(
        self,
        face_source: pygame.Surface,
        dst_corners: list[tuple[float, float]],
        output_size: tuple[int, int],
    ) -> pygame.Surface | None:
        width, height = face_source.get_size()
        if width <= 0 or height <= 0:
            return None
        out_w, out_h = output_size
        if out_w <= 0 or out_h <= 0:
            return None
        inverse = self._canvas_homography(
            dst_corners,
            [(0.0, 0.0), (float(width), 0.0), (float(width), float(height)), (0.0, float(height))],
        )
        if inverse is None:
            return None
        coeffs = inverse[:8]
        warped = self._canvas_surface_to_pil(face_source).transform(
            (out_w, out_h),
            PILImage.Transform.PERSPECTIVE,
            coeffs,
            resample=PILImage.Resampling.NEAREST,
            fillcolor=(0, 0, 0, 0),
        )
        return self._canvas_pil_to_surface(warped)

    def _canvas_preshade_front_surface(
        self,
        source: pygame.Surface,
        *,
        shade: float,
        cool_shadow: float,
    ) -> pygame.Surface:
        width, height = source.get_size()
        out = pygame.Surface((width, height), pygame.SRCALPHA)
        out.fill((0, 0, 0, 0))
        for y in range(height):
            for x in range(width):
                color = source.get_at((x, y))
                if color.a <= 0:
                    continue
                shaded = self._canvas_apply_light_rgba(
                    (color.r, color.g, color.b, color.a),
                    shade,
                    cool_shadow=cool_shadow,
                )
                out.set_at((x, y), shaded)
        return out

    def _canvas_preshade_back_surface(
        self,
        source: pygame.Surface,
        alpha_mask: list[list[bool]],
        *,
        shade: float,
        cool_shadow: float,
    ) -> pygame.Surface:
        width, height = source.get_size()
        out = pygame.Surface((width, height), pygame.SRCALPHA)
        out.fill((0, 0, 0, 0))
        for y in range(height):
            for x in range(width):
                if not alpha_mask[y][x]:
                    continue
                rgba = self._canvas_inferred_surface_color(source, alpha_mask, x, y)
                shaded = self._canvas_apply_light_rgba(rgba, shade, cool_shadow=cool_shadow)
                out.set_at((x, y), shaded)
        return out

    def _canvas_project_surface_3d(
        self,
        source: pygame.Surface,
        rot_x: float,
        rot_y: float,
        rot_z: float,
    ) -> tuple[pygame.Surface, tuple[float, float]] | None:
        width, height = source.get_size()
        if width <= 0 or height <= 0:
            return None
        if all(self._canvas_abs_normalized_angle(angle) <= 1.5 for angle in (rot_x, rot_y, rot_z)):
            return source.copy(), (-width / 2.0, -height / 2.0)
        depth = max(1.25, min(14.0, min(width, height) * 0.35))
        front_z = 0.0
        back_z = depth
        bound_points = [
            self._canvas_project_3d_point(width, height, u, v, z, rot_x, rot_y, rot_z)
            for z in (front_z, back_z)
            for u, v in ((0.0, 0.0), (float(width), 0.0), (float(width), float(height)), (0.0, float(height)))
        ]
        min_x = math.floor(min(point[0] for point in bound_points))
        min_y = math.floor(min(point[1] for point in bound_points))
        max_x = math.ceil(max(point[0] for point in bound_points))
        max_y = math.ceil(max(point[1] for point in bound_points))
        out_w = max(1, int(max_x - min_x))
        out_h = max(1, int(max_y - min_y))

        output = pygame.Surface((out_w, out_h), pygame.SRCALPHA)
        output.fill((0, 0, 0, 0))
        alpha_mask = [
            [source.get_at((x, y)).a > 0 for x in range(width)]
            for y in range(height)
        ]

        face_normals = {
            face: self._canvas_3d_face_normal(face, rot_x, rot_y, rot_z)
            for face in ("front", "back", "left", "right", "top", "bottom")
        }
        face_visibility = {
            face: self._canvas_3d_face_visibility(normal)
            for face, normal in face_normals.items()
        }
        face_shades = {
            face: self._canvas_3d_shade_for_normal(
                normal,
                base="front" if face == "front" else "back" if face == "back" else "side",
            )
            for face, normal in face_normals.items()
        }

        def project_face_corners(z: float) -> list[tuple[float, float]]:
            corners = [
                self._canvas_project_3d_point(width, height, u, v, z, rot_x, rot_y, rot_z)[:2]
                for u, v in (
                    (0.0, 0.0),
                    (float(width), 0.0),
                    (float(width), float(height)),
                    (0.0, float(height)),
                )
            ]
            return [(c[0] - min_x, c[1] - min_y) for c in corners]

        # ── Back face: inverse-mapped warp ─────────────────────────────
        if face_visibility["back"] > 0.02:
            back_source = self._canvas_preshade_back_surface(
                source,
                alpha_mask,
                shade=face_shades["back"],
                cool_shadow=max(0.0, 1.0 - face_shades["back"]),
            )
            warped_back = self._canvas_warp_face(
                back_source,
                project_face_corners(back_z),
                (out_w, out_h),
            )
            if warped_back is not None:
                output.blit(warped_back, (0, 0))

        # ── Side strips: per-edge scatter (1px-thin, no visible destruction) ──
        def edge_quad(x: int, y: int, edge: str) -> list[tuple[float, float, float]]:
            if edge == "left":
                a, b = (float(x), float(y)), (float(x), float(y + 1))
            elif edge == "right":
                a, b = (float(x + 1), float(y)), (float(x + 1), float(y + 1))
            elif edge == "top":
                a, b = (float(x), float(y)), (float(x + 1), float(y))
            else:
                a, b = (float(x), float(y + 1)), (float(x + 1), float(y + 1))
            return [
                self._canvas_project_3d_point(width, height, a[0], a[1], front_z, rot_x, rot_y, rot_z),
                self._canvas_project_3d_point(width, height, b[0], b[1], front_z, rot_x, rot_y, rot_z),
                self._canvas_project_3d_point(width, height, b[0], b[1], back_z, rot_x, rot_y, rot_z),
                self._canvas_project_3d_point(width, height, a[0], a[1], back_z, rot_x, rot_y, rot_z),
            ]

        side_faces: list[tuple[float, list[tuple[float, float, float]], tuple[int, int, int, int]]] = []
        for y in range(height):
            for x in range(width):
                if not alpha_mask[y][x]:
                    continue
                neighbors = {
                    "left": x == 0 or not alpha_mask[y][x - 1],
                    "right": x == width - 1 or not alpha_mask[y][x + 1],
                    "top": y == 0 or not alpha_mask[y - 1][x],
                    "bottom": y == height - 1 or not alpha_mask[y + 1][x],
                }
                for edge, visible in neighbors.items():
                    if not visible:
                        continue
                    if face_visibility[edge] <= 0.02:
                        continue
                    side_quad = edge_quad(x, y, edge)
                    side_color = self._canvas_inferred_edge_color(source, alpha_mask, x, y, edge)
                    side_faces.append((
                        sum(point[2] for point in side_quad) / 4.0,
                        side_quad,
                        self._canvas_apply_light_rgba(
                            side_color,
                            face_shades[edge],
                            cool_shadow=max(0.0, 1.0 - face_shades[edge]),
                        ),
                    ))

        offset = (float(min_x), float(min_y))
        for _, quad, color in sorted(side_faces, key=lambda item: item[0], reverse=True):
            self._canvas_draw_projected_quad(output, quad, color, offset)

        # ── Front face: inverse-mapped warp (lays on top of sides/back) ──
        if face_visibility["front"] > 0.02:
            front_source = self._canvas_preshade_front_surface(
                source,
                shade=face_shades["front"],
                cool_shadow=max(0.0, 1.0 - face_shades["front"]) * 0.4,
            )
            warped_front = self._canvas_warp_face(
                front_source,
                project_face_corners(front_z),
                (out_w, out_h),
            )
            if warped_front is not None:
                output.blit(warped_front, (0, 0))

        return output, offset

    def _canvas_3d_selection_preview(self) -> tuple[pygame.Surface, tuple[float, float]] | None:
        if self.canvas_sel_surface is None:
            return None
        source = self.canvas_sel_surface
        cache_key = (
            id(source),
            source.get_width(),
            source.get_height(),
            int(round(self.canvas_sel_3d_x * 10.0)),
            int(round(self.canvas_sel_3d_y * 10.0)),
            int(round(self.canvas_sel_3d_z * 10.0)),
        )
        if self._canvas_sel_3d_cache_key != cache_key or self._canvas_sel_3d_cache_surf is None:
            projected = self._canvas_project_surface_3d(
                source,
                self.canvas_sel_3d_x,
                self.canvas_sel_3d_y,
                self.canvas_sel_3d_z,
            )
            if projected is None:
                return None
            self._canvas_sel_3d_cache_surf, self._canvas_sel_3d_cache_offset = projected
            self._canvas_sel_3d_cache_key = cache_key
        return self._canvas_sel_3d_cache_surf, self._canvas_sel_3d_cache_offset

    def _canvas_3d_selection_screen_rect(self, draw_rect: pygame.Rect) -> pygame.Rect | None:
        if self.canvas_sel_base_bbox is None:
            return None
        preview = self._canvas_3d_selection_preview()
        if preview is None:
            return None
        surface, offset = preview
        min_x, min_y, max_x, max_y = self.canvas_sel_base_bbox
        center_x = (min_x + max_x + 1) / 2.0
        center_y = (min_y + max_y + 1) / 2.0
        left = draw_rect.x + int(round((center_x + offset[0]) * self.canvas_zoom))
        top = draw_rect.y + int(round((center_y + offset[1]) * self.canvas_zoom))
        width = max(1, int(round(surface.get_width() * self.canvas_zoom)))
        height = max(1, int(round(surface.get_height() * self.canvas_zoom)))
        return pygame.Rect(left, top, width, height)

    def _canvas_3d_gizmo_center_screen(self, draw_rect: pygame.Rect) -> tuple[float, float] | None:
        if self.canvas_sel_base_bbox is None:
            return None
        min_x, min_y, max_x, max_y = self.canvas_sel_base_bbox
        center_x = (min_x + max_x + 1) / 2.0
        center_y = (min_y + max_y + 1) / 2.0
        return (
            draw_rect.x + center_x * self.canvas_zoom,
            draw_rect.y + center_y * self.canvas_zoom,
        )

    def _canvas_3d_gizmo_metrics(self, draw_rect: pygame.Rect) -> tuple[float, float, float] | None:
        base_rect = self._canvas_3d_selection_screen_rect(draw_rect) or self._canvas_selection_screen_rect(draw_rect)
        if base_rect is None:
            return None
        radius = max(34.0, min(150.0, max(base_rect.width, base_rect.height) * 0.72))
        x_ry = max(10.0, radius * 0.34)
        y_rx = max(10.0, radius * 0.34)
        return radius, x_ry, y_rx

    def _canvas_3d_gizmo_hit_axis(self, pos: tuple[int, int], draw_rect: pygame.Rect) -> str | None:
        center = self._canvas_3d_gizmo_center_screen(draw_rect)
        metrics = self._canvas_3d_gizmo_metrics(draw_rect)
        if center is None or metrics is None:
            return None
        cx, cy = center
        radius, x_ry, y_rx = metrics
        dx = pos[0] - cx
        dy = pos[1] - cy
        tol = max(0.10, 9.0 / max(radius, 1.0))
        z_val = (dx * dx + dy * dy) / max(radius * radius, 1e-6)
        x_val = (dx * dx) / max(radius * radius, 1e-6) + (dy * dy) / max(x_ry * x_ry, 1e-6)
        y_val = (dx * dx) / max(y_rx * y_rx, 1e-6) + (dy * dy) / max(radius * radius, 1e-6)
        candidates = [
            ("z", abs(z_val - 1.0) / tol),
            ("x", abs(x_val - 1.0) / tol),
            ("y", abs(y_val - 1.0) / tol),
        ]
        axis, score = min(candidates, key=lambda item: item[1])
        return axis if score <= 1.0 else None

    def _canvas_3d_gizmo_param_angle(
        self,
        axis: str,
        pos: tuple[int, int],
        draw_rect: pygame.Rect,
    ) -> float:
        center = self._canvas_3d_gizmo_center_screen(draw_rect)
        metrics = self._canvas_3d_gizmo_metrics(draw_rect)
        if center is None or metrics is None:
            return 0.0
        cx, cy = center
        radius, x_ry, y_rx = metrics
        dx = pos[0] - cx
        dy = pos[1] - cy
        if axis == "z":
            return math.degrees(math.atan2(dy, dx))
        if axis == "x":
            return math.degrees(math.atan2(dy / max(x_ry, 1e-6), dx / max(radius, 1e-6)))
        return math.degrees(math.atan2(dy / max(radius, 1e-6), dx / max(y_rx, 1e-6)))

    @staticmethod
    def _canvas_3d_function_axis_for_ring(axis: str) -> str:
        if axis == "x":
            return "y"
        if axis == "y":
            return "x"
        return axis

    @staticmethod
    def _canvas_normalize_angle_delta(delta: float) -> float:
        while delta > 180.0:
            delta -= 360.0
        while delta < -180.0:
            delta += 360.0
        return delta

    def _canvas_start_3d_gizmo_drag(self, axis: str, pos: tuple[int, int], draw_rect: pygame.Rect) -> None:
        self.canvas_sel_3d_axis = axis
        self.canvas_sel_3d_start_angle = self._canvas_3d_gizmo_param_angle(axis, pos, draw_rect)
        self.canvas_sel_3d_last_angle = self.canvas_sel_3d_start_angle
        self.canvas_sel_3d_start_values = (self.canvas_sel_3d_x, self.canvas_sel_3d_y, self.canvas_sel_3d_z)
        function_axis = self._canvas_3d_function_axis_for_ring(axis)
        label = "free tilt" if axis == "free" else f"{function_axis.upper()} axis"
        self.status = f"3D rotating on {label}. Enter commits."

    def _canvas_update_3d_gizmo_drag(self, pos: tuple[int, int], draw_rect: pygame.Rect) -> None:
        axis = self.canvas_sel_3d_axis
        if axis is None:
            return
        current = self._canvas_3d_gizmo_param_angle(axis, pos, draw_rect)
        delta = self._canvas_normalize_angle_delta(current - self.canvas_sel_3d_last_angle)
        self.canvas_sel_3d_last_angle = current
        base_x, base_y, base_z = self.canvas_sel_3d_start_values
        function_axis = self._canvas_3d_function_axis_for_ring(axis)
        if function_axis == "free" and self.canvas_sel_drag_start is not None:
            dx = (pos[0] - self.canvas_sel_drag_start[0]) / max(self.canvas_zoom, 0.001)
            dy = (pos[1] - self.canvas_sel_drag_start[1]) / max(self.canvas_zoom, 0.001)
            self.canvas_sel_3d_x = (base_x - dy * 3.0) % 360.0
            self.canvas_sel_3d_y = (base_y + dx * 3.0) % 360.0
        elif function_axis == "x":
            self.canvas_sel_3d_x = (self.canvas_sel_3d_x + delta) % 360.0
        elif function_axis == "y":
            self.canvas_sel_3d_y = (self.canvas_sel_3d_y + delta) % 360.0
        else:
            self.canvas_sel_3d_z = (self.canvas_sel_3d_z + delta) % 360.0

    def _canvas_select_opaque_region(self, start: tuple[int, int]) -> bool:
        if self.canvas_surface is None:
            return False
        sw, sh = self.canvas_surface.get_size()
        if not (0 <= start[0] < sw and 0 <= start[1] < sh):
            return False
        if self.canvas_surface.get_at(start).a <= 8:
            return False
        selected: set[tuple[int, int]] = set()
        queue: deque[tuple[int, int]] = deque([start])
        selected.add(start)
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in selected or not (0 <= nx < sw and 0 <= ny < sh):
                    continue
                if self.canvas_surface.get_at((nx, ny)).a <= 8:
                    continue
                selected.add((nx, ny))
                queue.append((nx, ny))
        self.canvas_selection_pixels = selected
        self.status = f"Selected {len(selected)} connected pixel(s) for 3D rotate."
        return bool(selected)

    def _canvas_select_all_opaque(self) -> bool:
        if self.canvas_surface is None:
            return False
        sw, sh = self.canvas_surface.get_size()
        selected = {
            (x, y)
            for y in range(sh)
            for x in range(sw)
            if self.canvas_surface.get_at((x, y)).a > 8
        }
        self.canvas_selection_pixels = selected
        if selected:
            self.status = f"Selected {len(selected)} opaque pixel(s) for 3D rotate."
            return True
        return False

    def _canvas_rotation_handle_rect(self, draw_rect: pygame.Rect) -> pygame.Rect | None:
        box = self._canvas_selection_screen_rect(draw_rect)
        if box is None:
            return None
        handle_size = 16
        cx = box.centerx
        cy = box.top - 26
        return pygame.Rect(cx - handle_size // 2, cy - handle_size // 2, handle_size, handle_size)

    def _apply_canvas_hsv_color(self) -> None:
        r, g, b = colorsys.hsv_to_rgb(self.canvas_color_hue, self.canvas_color_sat, self.canvas_color_val)
        self.canvas_color = (
            int(round(r * 255)),
            int(round(g * 255)),
            int(round(b * 255)),
            self.canvas_color[3],
        )

    def _canvas_color_hex(self) -> str:
        r, g, b, _ = self.canvas_color
        return f"#{r:02X}{g:02X}{b:02X}"

    def _open_canvas_color_picker(self) -> None:
        self.canvas_color_before_picker = self.canvas_color
        self.canvas_color_picker_drag = None
        self.dialog_mode = "color_picker"
        self.dropdown_open = None
        self.status = "Pick a canvas color."

    def _close_canvas_color_picker(self, *, apply: bool) -> None:
        if not apply:
            self._set_canvas_color(self.canvas_color_before_picker)
            self.status = "Color picker cancelled."
        else:
            self.status = f"Canvas color set to {self._canvas_color_hex()}."
        self.canvas_color_picker_drag = None
        self.dialog_mode = None

    def _canvas_color_wheel_surface(self, diameter: int) -> pygame.Surface:
        key = (diameter, int(round(self.canvas_color_val * 255)))
        cached = self.canvas_color_wheel_cache.get(key)
        if cached is not None:
            return cached
        if len(self.canvas_color_wheel_cache) > 16:
            self.canvas_color_wheel_cache.clear()
        wheel = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        radius = diameter / 2.0
        for y in range(diameter):
            for x in range(diameter):
                dx = x - radius + 0.5
                dy = y - radius + 0.5
                distance = math.hypot(dx, dy)
                if distance > radius:
                    continue
                hue = (math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0
                sat = min(1.0, distance / max(radius, 1.0))
                r, g, b = colorsys.hsv_to_rgb(hue / 360.0, sat, self.canvas_color_val)
                wheel.set_at((x, y), (int(r * 255), int(g * 255), int(b * 255), 255))
        self.canvas_color_wheel_cache[key] = wheel
        return wheel

    def _update_canvas_color_picker(self, pos: tuple[int, int]) -> None:
        _, wheel, value, _, alpha_rect, _, _ = self._canvas_color_picker_layout()
        if self.canvas_color_picker_drag == "wheel":
            dx = pos[0] - wheel.centerx
            dy = pos[1] - wheel.centery
            radius = wheel.width / 2.0
            self.canvas_color_sat = max(0.0, min(1.0, math.hypot(dx, dy) / max(radius, 1.0)))
            self.canvas_color_hue = ((math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0) / 360.0
            self._apply_canvas_hsv_color()
        elif self.canvas_color_picker_drag == "value":
            ratio = (pos[1] - value.y) / max(value.height, 1)
            self.canvas_color_val = 1.0 - max(0.0, min(1.0, ratio))
            self._apply_canvas_hsv_color()
        elif self.canvas_color_picker_drag == "alpha":
            ratio = (pos[0] - alpha_rect.x) / max(alpha_rect.width, 1)
            alpha = int(round(max(0.0, min(1.0, ratio)) * 255))
            self.canvas_color = self.canvas_color[:3] + (alpha,)

    def _open_canvas_rename_dialog(self, kind: str) -> None:
        if kind == "layer":
            if not self.canvas_doc.frames:
                return
            self.canvas_rename_kind = "layer"
            self.canvas_rename_index = self.canvas_doc.layer_idx
            fi = self.canvas_doc.frame_idx
            self.canvas_name_input = self.canvas_doc.layer_names[fi][self.canvas_doc.layer_idx]
        elif kind == "frame":
            if not self.canvas_doc.frames:
                return
            self.canvas_rename_kind = "frame"
            self.canvas_rename_index = self.canvas_doc.frame_idx
            self.canvas_name_input = self._canvas_frame_name(self.canvas_doc.frame_idx)
        elif kind == "tab":
            if not self.canvas_tabs:
                return
            self.canvas_rename_kind = "tab"
            self.canvas_rename_index = self.canvas_tab_idx
            self.canvas_name_input = self._canvas_tab_name(self.canvas_tab_idx)
        else:
            return
        self.dialog_mode = "canvas_rename"
        self.dropdown_open = None
        self.status = f"Rename {kind}."

    def _confirm_canvas_rename(self) -> None:
        name = self.canvas_name_input.strip()
        if not name or self.canvas_rename_kind is None:
            self.status = "Name cannot be empty."
            return
        if self.canvas_rename_kind == "layer":
            fi = self.canvas_doc.frame_idx
            li = self.canvas_rename_index
            if fi < len(self.canvas_doc.layer_names) and li < len(self.canvas_doc.layer_names[fi]):
                self.canvas_doc.layer_names[fi][li] = name
                self.status = f"Layer renamed to {name}."
        elif self.canvas_rename_kind == "frame":
            idx = self.canvas_rename_index
            if idx < len(self.canvas_doc.frame_names):
                self.canvas_doc.frame_names[idx] = name
                self.status = f"Frame renamed to {name}."
        elif self.canvas_rename_kind == "tab":
            idx = self.canvas_rename_index
            if 0 <= idx < len(self.canvas_tabs):
                self.canvas_tabs[idx]["name"] = name
                self.status = f"Canvas tab renamed to {name}."
        self.dialog_mode = None
        self.canvas_rename_kind = None

    def _open_new_canvas_dialog(self) -> None:
        if len(self.canvas_tabs) >= self._max_canvas_tabs():
            self.status = f"Canvas tab limit reached ({self._max_canvas_tabs()}). Delete one to add another."
            return
        self.canvas_new_width_input = "64"
        self.canvas_new_height_input = "64"
        self.canvas_new_focus = "width"
        self.canvas_focus_mode = False
        self.canvas_focus_tools_open = False
        self.canvas_focus_tools_progress = 0.0
        self.dialog_mode = "new_canvas"
        self.dropdown_open = None
        self.status = "Choose a size for the new canvas."

    def _confirm_new_canvas(self) -> None:
        if len(self.canvas_tabs) >= self._max_canvas_tabs():
            self.dialog_mode = None
            self.status = f"Canvas tab limit reached ({self._max_canvas_tabs()}). Delete one to add another."
            return
        try:
            w = max(1, min(int(self.canvas_new_width_input.strip() or "0"), 4096))
            h = max(1, min(int(self.canvas_new_height_input.strip() or "0"), 4096))
        except ValueError:
            self.status = "Canvas size must be whole numbers (1–4096)."
            return
        self._save_active_canvas_tab_state()
        new_state = self._new_canvas_doc_state(w, h)
        if self._canvas_tab_is_placeholder(self.canvas_tab_idx):
            tab_name = self._canvas_tab_name(self.canvas_tab_idx)
            self.canvas_tabs[self.canvas_tab_idx]["state"] = new_state
        else:
            tab_name = self._next_canvas_tab_name()
            self.canvas_tabs.append({"name": tab_name, "state": new_state})
            self.canvas_tab_idx = len(self.canvas_tabs) - 1
        self._canvas_apply_doc_state(new_state)
        self.canvas_focus_mode = False
        self.canvas_focus_tools_open = False
        self.canvas_focus_tools_progress = 0.0
        self.dialog_mode = None
        self._canvas_fit()
        self._save_active_canvas_tab_state()
        self.status = f"New {w}×{h} canvas ready in {tab_name}."

    def _canvas_copy_selection(self) -> None:
        if not self.canvas_selection_pixels:
            self.status = "Nothing selected to copy."
            return
        if self.canvas_sel_transform and self.canvas_sel_lift:
            bbox = self._canvas_sel_bbox()
            if bbox is None:
                self.status = "Nothing selected to copy."
                return
            min_x, min_y, _, _ = bbox
            copied: dict[tuple[int, int], tuple[int, int, int, int]] = {}
            if self.canvas_sel_transform == "move":
                ox, oy = self.canvas_sel_offset
                for (px, py), color in self.canvas_sel_lift.items():
                    copied[(px + ox - min_x, py + oy - min_y)] = color
            else:
                for (px, py), color in self.canvas_sel_lift.items():
                    copied[(px - min_x, py - min_y)] = color
            self.canvas_clipboard = copied
        else:
            source = self._canvas_composited_frame(self.canvas_doc.frame_idx) if self.canvas_doc.frames else None
            if source is None:
                source = self.canvas_surface
            if source is None:
                self.status = "Nothing selected to copy."
                return
            sw, sh = source.get_size()
            self.canvas_clipboard = {
                (px, py): tuple(source.get_at((px, py)))  # type: ignore[arg-type]
                for px, py in self.canvas_selection_pixels
                if 0 <= px < sw and 0 <= py < sh
            }
        self.status = f"Copied {len(self.canvas_clipboard)} pixel(s)."

    def _canvas_paste_start(self) -> None:
        self._canvas_begin_paste_transform()

    def _canvas_paste_commit(self) -> None:
        if not self.canvas_paste_active or self.canvas_surface is None:
            return
        self._canvas_push_undo()
        ox, oy = self.canvas_paste_origin
        sw, sh = self.canvas_surface.get_size()
        for (px, py), color in self.canvas_paste_pixels.items():
            nx, ny = px + ox, py + oy
            if 0 <= nx < sw and 0 <= ny < sh:
                self.canvas_surface.set_at((nx, ny), color)
        self._mark_canvas_changed()
        self.canvas_paste_active = False
        self.status = "Pasted."

    # ── Selection transforms ────────────────────────────────────────────

    def _canvas_rotate_selection(self, cw: bool = True) -> None:
        if self.canvas_surface is None or not self.canvas_selection_pixels:
            return
        pixels = {
            (px, py): tuple(self.canvas_surface.get_at((px, py)))  # type: ignore[arg-type]
            for px, py in self.canvas_selection_pixels
        }
        min_x = min(p[0] for p in pixels)
        max_x = max(p[0] for p in pixels)
        min_y = min(p[1] for p in pixels)
        max_y = max(p[1] for p in pixels)
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        new_pixels: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        for (px, py), color in pixels.items():
            rx, ry = px - cx, py - cy
            if cw:
                nx, ny = -ry, rx
            else:
                nx, ny = ry, -rx
            new_pixels[(int(round(cx + nx)), int(round(cy + ny)))] = color  # type: ignore[assignment]
        self._canvas_push_undo()
        sw, sh = self.canvas_surface.get_size()
        for px, py in self.canvas_selection_pixels:
            self.canvas_surface.set_at((px, py), (0, 0, 0, 0))
        for (px, py), color in new_pixels.items():
            if 0 <= px < sw and 0 <= py < sh:
                self.canvas_surface.set_at((px, py), color)
        self.canvas_selection_pixels = {p for p in new_pixels if 0 <= p[0] < sw and 0 <= p[1] < sh}
        self._mark_canvas_changed()
        self.status = f"Rotated {'CW' if cw else 'CCW'} 90°."

    def _canvas_flip_selection(self, horizontal: bool) -> None:
        if self.canvas_surface is None or not self.canvas_selection_pixels:
            return
        pixels = {
            (px, py): tuple(self.canvas_surface.get_at((px, py)))  # type: ignore[arg-type]
            for px, py in self.canvas_selection_pixels
        }
        min_x = min(p[0] for p in pixels)
        max_x = max(p[0] for p in pixels)
        min_y = min(p[1] for p in pixels)
        max_y = max(p[1] for p in pixels)
        new_pixels: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        for (px, py), color in pixels.items():
            if horizontal:
                new_pixels[(max_x - (px - min_x), py)] = color  # type: ignore[assignment]
            else:
                new_pixels[(px, max_y - (py - min_y))] = color  # type: ignore[assignment]
        self._canvas_push_undo()
        sw, sh = self.canvas_surface.get_size()
        for px, py in self.canvas_selection_pixels:
            self.canvas_surface.set_at((px, py), (0, 0, 0, 0))
        for (px, py), color in new_pixels.items():
            if 0 <= px < sw and 0 <= py < sh:
                self.canvas_surface.set_at((px, py), color)
        self.canvas_selection_pixels = {p for p in new_pixels if 0 <= p[0] < sw and 0 <= p[1] < sh}
        self._mark_canvas_changed()
        self.status = f"Flipped {'horizontal' if horizontal else 'vertical'}."

    def _canvas_scale_selection(self, factor: float) -> None:
        if self.canvas_surface is None or not self.canvas_selection_pixels:
            return
        pixels = {
            (px, py): tuple(self.canvas_surface.get_at((px, py)))  # type: ignore[arg-type]
            for px, py in self.canvas_selection_pixels
        }
        min_x = min(p[0] for p in pixels)
        max_x = max(p[0] for p in pixels)
        min_y = min(p[1] for p in pixels)
        max_y = max(p[1] for p in pixels)
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        new_pixels: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        for (px, py), color in pixels.items():
            nx = int(round(cx + (px - cx) * factor))
            ny = int(round(cy + (py - cy) * factor))
            new_pixels[(nx, ny)] = color  # type: ignore[assignment]
        self._canvas_push_undo()
        sw, sh = self.canvas_surface.get_size()
        for px, py in self.canvas_selection_pixels:
            self.canvas_surface.set_at((px, py), (0, 0, 0, 0))
        for (px, py), color in new_pixels.items():
            if 0 <= px < sw and 0 <= py < sh:
                self.canvas_surface.set_at((px, py), color)
        self.canvas_selection_pixels = {p for p in new_pixels if 0 <= p[0] < sw and 0 <= p[1] < sh}
        self._mark_canvas_changed()
        self.status = f"Scaled selection {'up' if factor > 1 else 'down'}."

    def _canvas_adjust_brightness(self, delta: float) -> None:
        if self.canvas_surface is None or not self.canvas_selection_pixels:
            return
        self._canvas_push_undo()
        step = int(delta * 255)
        for px, py in self.canvas_selection_pixels:
            r, g, b, a = self.canvas_surface.get_at((px, py))
            r = max(0, min(255, r + step))
            g = max(0, min(255, g + step))
            b = max(0, min(255, b + step))
            self.canvas_surface.set_at((px, py), (r, g, b, a))
        self._mark_canvas_changed()
        self.status = f"Brightness {'increased' if delta > 0 else 'decreased'}."

    # ── Mirror helper ───────────────────────────────────────────────────

    def _mirror_positions(self, px: int, py: int) -> list[tuple[int, int]]:
        """Return all pixel positions to paint when mirror modes are active."""
        if self.canvas_surface is None:
            return [(px, py)]
        sw, sh = self.canvas_surface.get_size()
        pts = [(px, py)]
        if self.canvas_mirror_h:
            pts.append((sw - 1 - px, py))
        if self.canvas_mirror_v:
            pts.append((px, sh - 1 - py))
        if self.canvas_mirror_h and self.canvas_mirror_v:
            pts.append((sw - 1 - px, sh - 1 - py))
        return list(dict.fromkeys(pts))

    def _mirror_point_pairs(
        self,
        a: tuple[int, int],
        b: tuple[int, int],
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """Return all (start, end) pairs for stroke-style ops with mirror modes active."""
        a_pts = self._mirror_positions(a[0], a[1])
        b_pts = self._mirror_positions(b[0], b[1])
        return list(dict.fromkeys(zip(a_pts, b_pts)))

    # ── Spray / blend drawing ───────────────────────────────────────────

    def _draw_spray(self, pixel: tuple[int, int], color: tuple[int, int, int, int]) -> None:
        if self.canvas_surface is None:
            return
        sw, sh = self.canvas_surface.get_size()
        size = max(1, self.canvas_brush_size)
        density = max(4, size * 3)
        centers = self._mirror_positions(pixel[0], pixel[1])
        for center in centers:
            for _ in range(density):
                angle = random.uniform(0, 2 * math.pi)
                r = random.uniform(0, size)
                x = int(round(center[0] + r * math.cos(angle)))
                y = int(round(center[1] + r * math.sin(angle)))
                if 0 <= x < sw and 0 <= y < sh:
                    self.canvas_surface.set_at((x, y), color)
        self._canvas_patch_render_region(self._canvas_dirty_rect_from_points(centers, size))

    def _draw_blend(self, pixel: tuple[int, int], color: tuple[int, int, int, int]) -> None:
        if self.canvas_surface is None:
            return
        sw, sh = self.canvas_surface.get_size()
        size = max(1, self.canvas_brush_size)
        strength = max(0.0, min(1.0, self.canvas_blend_strength))
        cr, cg, cb, ca = color
        centers = self._mirror_positions(pixel[0], pixel[1])
        for center in centers:
            for dx in range(-size, size + 1):
                for dy in range(-size, size + 1):
                    if dx * dx + dy * dy <= size * size:
                        x, y = center[0] + dx, center[1] + dy
                        if 0 <= x < sw and 0 <= y < sh:
                            er, eg, eb, ea = self.canvas_surface.get_at((x, y))
                            self.canvas_surface.set_at((x, y), (
                                int(er + (cr - er) * strength),
                                int(eg + (cg - eg) * strength),
                                int(eb + (cb - eb) * strength),
                                int(ea + (ca - ea) * strength),
                            ))
        self._canvas_patch_render_region(self._canvas_dirty_rect_from_points(centers, size))

    # ── Smudge tool ─────────────────────────────────────────────────────

    def _canvas_sel_bbox(self) -> tuple[int, int, int, int] | None:
        """Return (min_x, min_y, max_x, max_y) of selection, or None if empty."""
        if not self.canvas_selection_pixels:
            return None
        xs = [p[0] for p in self.canvas_selection_pixels]
        ys = [p[1] for p in self.canvas_selection_pixels]
        return min(xs), min(ys), max(xs), max(ys)

    def _finalize_rect_selection(self) -> None:
        if self.canvas_surface is None or self.canvas_rect_select_start is None or self.canvas_rect_select_end is None:
            self.canvas_rect_select_active = False
            self.canvas_rect_select_start = None
            self.canvas_rect_select_end = None
            return
        sw, sh = self.canvas_surface.get_size()
        x0, y0 = self.canvas_rect_select_start
        x1, y1 = self.canvas_rect_select_end
        min_x, max_x = sorted((max(0, min(sw - 1, x0)), max(0, min(sw - 1, x1))))
        min_y, max_y = sorted((max(0, min(sh - 1, y0)), max(0, min(sh - 1, y1))))
        selected = {
            (px, py)
            for px in range(min_x, max_x + 1)
            for py in range(min_y, max_y + 1)
        }
        self.canvas_selection_pixels = selected
        self.canvas_rect_select_active = False
        self.canvas_rect_select_start = None
        self.canvas_rect_select_end = None
        self.status = f"Selected {len(self.canvas_selection_pixels)} pixel(s)."

    def _canvas_enter_sel_transform(self, mode: str, *, auto_commit: bool = False) -> None:
        """Lift the selection pixels off the canvas and enter a transform mode."""
        if not self.canvas_selection_pixels or self.canvas_surface is None:
            return
        self._canvas_push_undo()
        # Snapshot selected pixel colors and erase them from canvas
        self.canvas_sel_lift = {}
        for px, py in self.canvas_selection_pixels:
            try:
                col = self.canvas_surface.get_at((px, py))
                self.canvas_sel_lift[(px, py)] = (col.r, col.g, col.b, col.a)
                self.canvas_surface.set_at((px, py), (0, 0, 0, 0))
            except IndexError:
                pass
        self.canvas_sel_transform = mode
        self.canvas_sel_offset = (0, 0)
        self.canvas_sel_angle = 0.0
        self.canvas_sel_scale = 1.0
        self.canvas_sel_3d_x = 0.0
        self.canvas_sel_3d_y = 0.0
        self.canvas_sel_3d_z = 0.0
        self.canvas_sel_3d_axis = None
        self.canvas_sel_3d_start_angle = 0.0
        self.canvas_sel_3d_last_angle = 0.0
        self.canvas_sel_3d_start_values = (0.0, 0.0, 0.0)
        self.canvas_sel_drag_start = None
        self.canvas_sel_drag_mode = ""
        self.canvas_sel_restore_on_cancel = True
        self.canvas_sel_auto_commit = auto_commit
        self.canvas_sel_push_undo_on_commit = False
        self._canvas_rebuild_selection_surface()
        if mode == "rotate3d":
            matched = self._canvas_sprite_model_match()
            if matched is not None and self.canvas_sel_surface is not None:
                self.canvas_sel_surface = matched["surface"].copy()
                ox, oy = matched["origin_min"]
                sw_m, sh_m = self.canvas_sel_surface.get_size()
                self.canvas_sel_base_bbox = (ox, oy, ox + sw_m - 1, oy + sh_m - 1)
                self.canvas_sel_3d_x, self.canvas_sel_3d_y, self.canvas_sel_3d_z = matched["rot"]
                self._canvas_clear_3d_selection_cache()
        self._mark_canvas_changed()
        mode_labels = {"move": "M — drag to move  Enter=commit  Esc=cancel",
                       "rotate": "R — drag to rotate  Enter=commit  Esc=cancel",
                       "rotate3d": "R 3D — drag X/Y/Z rings  Enter=commit  Esc=cancel",
                       "scale": "S — drag corners to scale  Enter=commit  Esc=cancel"}
        self.status = mode_labels.get(mode, f"{mode} mode")

    def _canvas_begin_paste_transform(self) -> None:
        if not self.canvas_clipboard or self.canvas_surface is None:
            self.status = "Clipboard is empty."
            return
        sw, sh = self.canvas_surface.get_size()
        min_x = min(p[0] for p in self.canvas_clipboard)
        min_y = min(p[1] for p in self.canvas_clipboard)
        max_x = max(p[0] for p in self.canvas_clipboard)
        max_y = max(p[1] for p in self.canvas_clipboard)
        pw = max_x - min_x + 1
        ph = max_y - min_y + 1
        target_bbox = self._canvas_sel_bbox()
        if target_bbox is not None:
            target_min_x, target_min_y, _, _ = target_bbox
            ox = target_min_x - min_x
            oy = target_min_y - min_y
        else:
            ox = sw // 2 - pw // 2 - min_x
            oy = sh // 2 - ph // 2 - min_y
        self.canvas_paste_active = False
        self.canvas_paste_pixels = {}
        self.canvas_paste_origin = (0, 0)
        self.canvas_sel_lift = {}
        self.canvas_selection_pixels = set()
        for (px, py), color in self.canvas_clipboard.items():
            nx, ny = px + ox, py + oy
            self.canvas_sel_lift[(nx, ny)] = color
            self.canvas_selection_pixels.add((nx, ny))
        self.canvas_sel_transform = "move"
        self.canvas_sel_offset = (0, 0)
        self.canvas_sel_angle = 0.0
        self.canvas_sel_scale = 1.0
        self.canvas_sel_3d_x = 0.0
        self.canvas_sel_3d_y = 0.0
        self.canvas_sel_3d_z = 0.0
        self.canvas_sel_3d_axis = None
        self.canvas_sel_3d_start_angle = 0.0
        self.canvas_sel_3d_last_angle = 0.0
        self.canvas_sel_3d_start_values = (0.0, 0.0, 0.0)
        self.canvas_sel_drag_start = None
        self.canvas_sel_drag_mode = ""
        self.canvas_sel_restore_on_cancel = False
        self.canvas_sel_auto_commit = False
        self.canvas_sel_push_undo_on_commit = True
        self._canvas_rebuild_selection_surface()
        self.status = "Pasted selection — drag to position, Enter to commit, Esc to cancel."

    def _canvas_commit_sel_transform(self) -> None:
        """Paint the lifted+transformed pixels back onto the canvas."""
        if self.canvas_surface is None or not self.canvas_sel_lift:
            self.canvas_sel_transform = None
            return
        if self.canvas_sel_push_undo_on_commit:
            self._canvas_push_undo()
        if self.canvas_sel_transform == "move" and self.canvas_sel_surface is not None and self.canvas_sel_base_bbox is not None:
            min_x, min_y, _, _ = self.canvas_sel_base_bbox
            ox, oy = self.canvas_sel_offset
            surf_to_apply = self.canvas_sel_surface
            surf_w = surf_to_apply.get_width()
            surf_h = surf_to_apply.get_height()
            sw, sh = self.canvas_surface.get_size()
            # Scale-to-fit if the surface is bigger than the canvas, so every pixel
            # survives the commit instead of being clipped at the edges.
            if surf_w > sw or surf_h > sh:
                fit_scale = min(sw / max(1, surf_w), sh / max(1, surf_h))
                if fit_scale < 1.0:
                    new_w = max(1, int(round(surf_w * fit_scale)))
                    new_h = max(1, int(round(surf_h * fit_scale)))
                    surf_to_apply = pygame.transform.scale(surf_to_apply, (new_w, new_h))
                    surf_w = new_w
                    surf_h = new_h
            top_x = int(round(min_x + ox))
            top_y = int(round(min_y + oy))
            # Snap into bounds — guaranteed possible now because surf fits in canvas.
            top_x = max(0, min(top_x, sw - surf_w))
            top_y = max(0, min(top_y, sh - surf_h))
            self.canvas_selection_pixels = self._canvas_apply_surface_selection(
                surf_to_apply,
                (top_x, top_y),
            )
            model = getattr(self, "canvas_sprite_model", None)
            if isinstance(model, dict):
                shift_x = top_x - int(round(min_x))
                shift_y = top_y - int(round(min_y))
                model_pixels = {(px + shift_x, py + shift_y) for (px, py) in model["pixels"]}
                m_origin = (model["origin_min"][0] + shift_x, model["origin_min"][1] + shift_y)
                self.canvas_sprite_model = {
                    "surface": model["surface"],
                    "origin_min": m_origin,
                    "rot": model["rot"],
                    "pixels": model_pixels,
                }
        elif self.canvas_sel_transform == "scale" and self.canvas_sel_surface is not None and self.canvas_sel_scale_rect is not None:
            left, top, right, bottom = self.canvas_sel_scale_rect
            target_w = max(1, int(round(right - left)))
            target_h = max(1, int(round(bottom - top)))
            scaled = pygame.transform.scale(self.canvas_sel_surface, (target_w, target_h))
            self.canvas_selection_pixels = self._canvas_apply_surface_selection(
                scaled,
                (int(round(left)), int(round(top))),
            )
            self._canvas_invalidate_sprite_model()
        elif self.canvas_sel_transform == "rotate" and self.canvas_sel_surface is not None and self.canvas_sel_base_bbox is not None:
            rotated = self._canvas_rotated_selection_preview(self.canvas_sel_angle)
            if rotated is not None:
                min_x, min_y, max_x, max_y = self.canvas_sel_base_bbox
                center_x = (min_x + max_x + 1) / 2.0
                center_y = (min_y + max_y + 1) / 2.0
                top_left = (
                    int(round(center_x - (rotated.get_width() / 2.0))),
                    int(round(center_y - (rotated.get_height() / 2.0))),
                )
                self.canvas_selection_pixels = self._canvas_apply_surface_selection(rotated, top_left)
            self._canvas_invalidate_sprite_model()
        elif self.canvas_sel_transform == "rotate3d" and self.canvas_sel_surface is not None and self.canvas_sel_base_bbox is not None:
            min_x, min_y, max_x, max_y = self.canvas_sel_base_bbox
            original_surface = self.canvas_sel_surface
            origin_min = (int(min_x), int(min_y))
            committed_rot = (self.canvas_sel_3d_x, self.canvas_sel_3d_y, self.canvas_sel_3d_z)
            if self._canvas_3d_rotation_is_identity():
                self.canvas_selection_pixels = self._canvas_apply_surface_selection(
                    self.canvas_sel_surface,
                    (int(min_x), int(min_y)),
                )
            else:
                projected = self._canvas_3d_selection_preview()
                if projected is None:
                    projected = (self.canvas_sel_surface, (-self.canvas_sel_surface.get_width() / 2.0, -self.canvas_sel_surface.get_height() / 2.0))
                projected_surface, offset = projected
                center_x = (min_x + max_x + 1) / 2.0
                center_y = (min_y + max_y + 1) / 2.0
                top_left = (
                    int(round(center_x + offset[0])),
                    int(round(center_y + offset[1])),
                )
                self.canvas_selection_pixels = self._canvas_apply_surface_selection(projected_surface, top_left)
            self._canvas_save_sprite_model(
                original_surface,
                origin_min,
                committed_rot,
                self.canvas_selection_pixels,
            )
        self.canvas_sel_lift = {}
        self.canvas_sel_transform = None
        self.canvas_sel_drag_start = None
        self.canvas_sel_drag_mode = ""
        self.canvas_sel_3d_axis = None
        self.canvas_sel_3d_start_angle = 0.0
        self.canvas_sel_3d_last_angle = 0.0
        self.canvas_sel_3d_start_values = (0.0, 0.0, 0.0)
        self.canvas_sel_restore_on_cancel = True
        self.canvas_sel_auto_commit = False
        self.canvas_sel_push_undo_on_commit = False
        self.canvas_sel_surface = None
        self.canvas_sel_base_bbox = None
        self.canvas_sel_scale_rect = None
        self._canvas_sel_preview_cache_key = None
        self._canvas_sel_preview_surf = None
        self._canvas_sel_rotate_cache_key = None
        self._canvas_sel_rotate_cache_surf = None
        self._canvas_clear_3d_selection_cache()
        self._mark_canvas_changed()
        self.status = "Transform committed."

    def _canvas_cancel_sel_transform(self) -> None:
        """Paint lifted pixels back at original position (cancel transform)."""
        if self.canvas_surface is not None and self.canvas_sel_restore_on_cancel:
            sw, sh = self.canvas_surface.get_size()
            for (px, py), col in self.canvas_sel_lift.items():
                if 0 <= px < sw and 0 <= py < sh:
                    self.canvas_surface.set_at((px, py), col)
        elif not self.canvas_sel_restore_on_cancel:
            self.canvas_selection_pixels.clear()
        self.canvas_sel_lift = {}
        self.canvas_sel_transform = None
        self.canvas_sel_drag_start = None
        self.canvas_sel_drag_mode = ""
        self.canvas_sel_3d_axis = None
        self.canvas_sel_3d_start_angle = 0.0
        self.canvas_sel_3d_last_angle = 0.0
        self.canvas_sel_3d_start_values = (0.0, 0.0, 0.0)
        self.canvas_sel_restore_on_cancel = True
        self.canvas_sel_auto_commit = False
        self.canvas_sel_push_undo_on_commit = False
        self.canvas_sel_surface = None
        self.canvas_sel_base_bbox = None
        self.canvas_sel_scale_rect = None
        self._canvas_sel_preview_cache_key = None
        self._canvas_sel_preview_surf = None
        self._canvas_sel_rotate_cache_key = None
        self._canvas_sel_rotate_cache_surf = None
        self._canvas_clear_3d_selection_cache()
        self._mark_canvas_changed()
        self.status = "Transform cancelled."

    def _draw_smudge(self, prev: tuple[int, int], curr: tuple[int, int]) -> None:
        """Drag pixels from prev toward curr — classic smear effect."""
        if self.canvas_surface is None:
            return
        sw, sh = self.canvas_surface.get_size()
        size = max(1, self.canvas_brush_size)
        strength = 0.7
        dirty: list[tuple[int, int]] = []
        for prev_m, curr_m in self._mirror_point_pairs(prev, curr):
            dirty.extend((prev_m, curr_m))
            for ox in range(-size, size + 1):
                for oy in range(-size, size + 1):
                    if ox * ox + oy * oy > size * size:
                        continue
                    sx, sy = prev_m[0] + ox, prev_m[1] + oy
                    tx, ty = curr_m[0] + ox, curr_m[1] + oy
                    if not (0 <= sx < sw and 0 <= sy < sh):
                        continue
                    if not (0 <= tx < sw and 0 <= ty < sh):
                        continue
                    sr, sg, sb, sa = self.canvas_surface.get_at((sx, sy))
                    er, eg, eb, ea = self.canvas_surface.get_at((tx, ty))
                    self.canvas_surface.set_at((tx, ty), (
                        int(er + (sr - er) * strength),
                        int(eg + (sg - eg) * strength),
                        int(eb + (sb - eb) * strength),
                        int(ea + (sa - ea) * strength),
                    ))
        self._canvas_patch_render_region(self._canvas_dirty_rect_from_points(dirty, size))

    # ── Vanishing point tool ─────────────────────────────────────────────

    def _draw_vpoint_line(self, start: tuple[int, int], color: tuple[int, int, int, int]) -> None:
        """Draw a line from start through (or toward) the vanishing point,
        extending to canvas edges in both directions."""
        if self.canvas_surface is None or self.canvas_vp is None:
            return
        sw, sh = self.canvas_surface.get_size()
        size = max(1, self.canvas_brush_size)

        def _clip_t(p: float, d: float, lo: float, hi: float) -> tuple[float, float]:
            if d == 0:
                return (-1e9, 1e9)
            return ((lo - p) / d, (hi - p) / d)

        for s_m, vp_m in self._mirror_point_pairs(start, self.canvas_vp):
            sx, sy = s_m
            vx, vy = vp_m
            dx, dy = vx - sx, vy - sy
            if dx == 0 and dy == 0:
                continue
            tx_lo, tx_hi = _clip_t(sx, dx, 0, sw - 1)
            ty_lo, ty_hi = _clip_t(sy, dy, 0, sh - 1)
            t_min = max(min(tx_lo, tx_hi), min(ty_lo, ty_hi))
            t_max = min(max(tx_lo, tx_hi), max(ty_lo, ty_hi))
            if t_max < t_min:
                continue
            p1 = (int(sx + dx * t_min), int(sy + dy * t_min))
            p2 = (int(sx + dx * t_max), int(sy + dy * t_max))
            pygame.draw.line(self.canvas_surface, color, p1, p2, size)
        self._mark_canvas_changed()

    # ── Frame / layer management ─────────────────────────────────────────

    def _draw_canvas_line(self, start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int, int], *, tool: str | None = None) -> None:
        if self.canvas_surface is None:
            return
        used_tool = tool or self.canvas_tool
        size = max(1, self.canvas_brush_size)
        # Build list of (start, end) pairs including mirrors
        pairs = [(start, end)]
        if self.canvas_mirror_h or self.canvas_mirror_v:
            sw, sh = self.canvas_surface.get_size()
            extras: list[tuple[tuple[int, int], tuple[int, int]]] = []
            if self.canvas_mirror_h:
                ms = (sw - 1 - start[0], start[1])
                me = (sw - 1 - end[0], end[1])
                extras.append((ms, me))
            if self.canvas_mirror_v:
                ms2 = (start[0], sh - 1 - start[1])
                me2 = (end[0], sh - 1 - end[1])
                extras.append((ms2, me2))
            if self.canvas_mirror_h and self.canvas_mirror_v:
                ms3 = (sw - 1 - start[0], sh - 1 - start[1])
                me3 = (sw - 1 - end[0], sh - 1 - end[1])
                extras.append((ms3, me3))
            pairs.extend(extras)
        dirty_points: list[tuple[int, int]] = []
        for s, e in pairs:
            dirty_points.extend((s, e))
            if used_tool == "brush":
                for cx, cy in self._bresenham_line(s[0], s[1], e[0], e[1]):
                    self._draw_canvas_brush_dab((cx, cy), color, size)
            else:
                pygame.draw.line(self.canvas_surface, color, s, e, size)
                if size > 1:
                    half = max(1, size // 2)
                    pygame.draw.circle(self.canvas_surface, color, s, half)
                    pygame.draw.circle(self.canvas_surface, color, e, half)
        pad = max(1, int(math.ceil(size / 2.0))) + 1
        self._canvas_patch_render_region(self._canvas_dirty_rect_from_points(dirty_points, pad))

    def _commit_shape(self, start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int, int]) -> None:
        """Commit line/circle/square to canvas_surface."""
        if self.canvas_surface is None:
            return
        self._canvas_push_undo()
        size = max(1, self.canvas_brush_size)
        tool = self.canvas_tool
        for s, e in self._mirror_point_pairs(start, end):
            if tool == "line":
                self._draw_canvas_pixel_line(s, e, color, size)
            elif tool == "circle":
                rx = abs(e[0] - s[0])
                ry = abs(e[1] - s[1])
                cx, cy = s
                rect = pygame.Rect(cx - rx, cy - ry, rx * 2, ry * 2)
                pygame.draw.ellipse(self.canvas_surface, color, rect, 0 if self.canvas_fill_shapes else size)
            elif tool == "square":
                x0, y0 = min(s[0], e[0]), min(s[1], e[1])
                x1, y1 = max(s[0], e[0]), max(s[1], e[1])
                rect = pygame.Rect(x0, y0, max(1, x1 - x0), max(1, y1 - y0))
                pygame.draw.rect(self.canvas_surface, color, rect, 0 if self.canvas_fill_shapes else size)
        self._mark_canvas_changed()

    @staticmethod
    def _bresenham_line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
        """Return all integer points on the line segment (x0,y0)→(x1,y1)."""
        pts: list[tuple[int, int]] = []
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x1 > x0 else -1
        sy = 1 if y1 > y0 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            pts.append((x, y))
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
        return pts

    def _canvas_line_pixels(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        size: int,
    ) -> set[tuple[int, int]]:
        cache_key = (start, end, max(1, size))
        if self._canvas_line_preview_cache_key == cache_key:
            return self._canvas_line_preview_pixels
        pixels: set[tuple[int, int]] = set()
        half = max(0, cache_key[2] // 2)
        for cx, cy in self._bresenham_line(start[0], start[1], end[0], end[1]):
            for dy in range(-half, half + 1):
                for dx in range(-half, half + 1):
                    pixels.add((cx + dx, cy + dy))
        self._canvas_line_preview_cache_key = cache_key
        self._canvas_line_preview_pixels = pixels
        return pixels

    def _draw_canvas_pixel_line(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        color: tuple[int, int, int, int],
        size: int,
    ) -> None:
        if self.canvas_surface is None:
            return
        sw, sh = self.canvas_surface.get_size()
        for px, py in self._canvas_line_pixels(start, end, size):
            if 0 <= px < sw and 0 <= py < sh:
                self.canvas_surface.set_at((px, py), color)

    def _draw_canvas_brush_dab(
        self,
        center: tuple[int, int],
        color: tuple[int, int, int, int],
        diameter: int,
    ) -> None:
        if self.canvas_surface is None:
            return
        sw, sh = self.canvas_surface.get_size()
        if diameter <= 1:
            if 0 <= center[0] < sw and 0 <= center[1] < sh:
                self._blend_canvas_pixel(center, color, 0.72)
            return
        radius = max(1.0, diameter / 2.0)
        radius_sq = radius * radius
        span = int(math.ceil(radius))
        cx, cy = center
        for dy in range(-span, span + 1):
            py = cy + dy
            if py < 0 or py >= sh:
                continue
            for dx in range(-span, span + 1):
                px = cx + dx
                if px < 0 or px >= sw:
                    continue
                dist_sq = (dx * dx) + (dy * dy)
                if dist_sq <= radius_sq:
                    dist = math.sqrt(dist_sq)
                    falloff = max(0.0, 1.0 - (dist / max(radius, 0.001)))
                    opacity = 0.18 + falloff * 0.42
                    if dist <= radius * 0.45:
                        opacity += 0.12
                    self._blend_canvas_pixel((px, py), color, min(0.85, opacity))

    def _blend_canvas_pixel(
        self,
        pos: tuple[int, int],
        color: tuple[int, int, int, int],
        opacity: float,
    ) -> None:
        if self.canvas_surface is None:
            return
        opacity = max(0.0, min(1.0, opacity))
        if opacity <= 0.0:
            return
        er, eg, eb, ea = self.canvas_surface.get_at(pos)
        sr, sg, sb, sa = color
        src_alpha = (sa / 255.0) * opacity
        dst_alpha = ea / 255.0
        out_alpha = src_alpha + dst_alpha * (1.0 - src_alpha)
        if out_alpha <= 0.0:
            self.canvas_surface.set_at(pos, (0, 0, 0, 0))
            return
        out_r = int(round((sr * src_alpha + er * dst_alpha * (1.0 - src_alpha)) / out_alpha))
        out_g = int(round((sg * src_alpha + eg * dst_alpha * (1.0 - src_alpha)) / out_alpha))
        out_b = int(round((sb * src_alpha + eb * dst_alpha * (1.0 - src_alpha)) / out_alpha))
        out_a = int(round(out_alpha * 255))
        self.canvas_surface.set_at(pos, (out_r, out_g, out_b, out_a))

    def _lighten_canvas_pixel(
        self,
        pos: tuple[int, int],
        color: tuple[int, int, int, int],
        opacity: float,
    ) -> None:
        """Brighten the destination pixel toward `color` (additive-leaning)."""
        if self.canvas_surface is None:
            return
        sw, sh = self.canvas_surface.get_size()
        if not (0 <= pos[0] < sw and 0 <= pos[1] < sh):
            return
        opacity = max(0.0, min(1.0, opacity))
        cr, cg, cb, _ = color
        dr, dg, db, da = self.canvas_surface.get_at(pos)
        nr = min(255, int(dr + (cr - dr) * opacity + cr * opacity * 0.30))
        ng = min(255, int(dg + (cg - dg) * opacity + cg * opacity * 0.30))
        nb = min(255, int(db + (cb - db) * opacity + cb * opacity * 0.30))
        na = min(255, int(da + (255 - da) * opacity))
        self.canvas_surface.set_at(pos, (nr, ng, nb, na))

    def _build_bulb_glow_template(
        self,
        size: int,
        color: tuple[int, int, int, int],
        peak: float,
    ) -> pygame.Surface:
        """Build a square Gaussian glow sprite: bright core, smooth radial falloff."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        half = size / 2.0
        sigma = size / 5.5
        inv_2sigma_sq = 1.0 / (2.0 * sigma * sigma)
        cr, cg, cb = color[0], color[1], color[2]
        peak = max(0.0, min(1.0, peak))
        for py in range(size):
            dy = py - half
            dy2 = dy * dy
            for px in range(size):
                dx = px - half
                dist_sq = dx * dx + dy2
                if dist_sq * inv_2sigma_sq > 14.0:
                    continue
                falloff = math.exp(-dist_sq * inv_2sigma_sq)
                opacity = falloff * peak
                if opacity < 0.003:
                    continue
                ga = int(round(255.0 * opacity))
                gr = int(round(cr * opacity))
                gg = int(round(cg * opacity))
                gb = int(round(cb * opacity))
                surf.set_at((px, py), (gr, gg, gb, ga))
        return surf

    def _draw_light_bulb(
        self,
        centers: list[tuple[int, int]],
        brush_size: int,
        color: tuple[int, int, int, int],
    ) -> None:
        """Soft additive bulb glow. Masked to the active selection if one exists;
        otherwise masked to the layer's drawn (opaque) pixels so the glow
        illuminates the artwork rather than painting empty canvas."""
        if self.canvas_surface is None:
            return
        sw, sh = self.canvas_surface.get_size()
        peak = 0.18 + min(1.0, max(1, brush_size) / 96.0) * 0.44
        diameter = max(48, max(sw, sh) * 3)
        template = self._build_bulb_glow_template(96, color, peak)
        glow = pygame.transform.smoothscale(template, (diameter, diameter))
        half = diameter // 2

        # Compose all centers' glows into a single canvas-sized buffer.
        buffer = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for cx, cy in centers:
            buffer.blit(glow, (int(cx - half), int(cy - half)))

        selection = self.canvas_selection_pixels
        if selection:
            # Mask the buffer to the user's explicit selection.
            for px, py in selection:
                if not (0 <= px < sw and 0 <= py < sh):
                    continue
                gp = buffer.get_at((px, py))
                if gp.a == 0:
                    continue
                cp = self.canvas_surface.get_at((px, py))
                self.canvas_surface.set_at(
                    (px, py),
                    (
                        min(255, cp.r + gp.r),
                        min(255, cp.g + gp.g),
                        min(255, cp.b + gp.b),
                        min(255, cp.a + gp.a),
                    ),
                )
            return

        # No selection: mask to the layer's opaque pixels using pygame's C-side mask.
        canvas_mask = pygame.mask.from_surface(self.canvas_surface, threshold=0)
        if canvas_mask.count() == 0:
            # Empty layer — keep the whole-canvas behavior so a fresh canvas can still glow.
            self.canvas_surface.blit(buffer, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            return
        mask_surface = canvas_mask.to_surface(
            setcolor=(255, 255, 255, 255),
            unsetcolor=(0, 0, 0, 0),
        )
        # Multiply: keep glow only where mask is white (opaque), zero elsewhere.
        buffer.blit(mask_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.canvas_surface.blit(buffer, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    @staticmethod
    def _fire_palette_from_color(
        color: tuple[int, int, int, int],
    ) -> tuple[
        tuple[int, int, int, int],
        tuple[int, int, int, int],
        tuple[int, int, int, int],
        tuple[int, int, int, int],
    ]:
        """Derive a four-stop flame palette tinted by the active swatch.

        Hot core lifts toward white; outer stops darken toward black so any color
        produces a believable flame gradient — red gives orange-red fire, blue
        gives blue-white fire, green gives ghostly green fire, and so on.
        """
        r, g, b, _ = color
        def lift(channel: int, amount: float) -> int:
            return max(0, min(255, int(channel + (255 - channel) * amount)))
        def darken(channel: int, amount: float) -> int:
            return max(0, min(255, int(channel * amount)))
        core = (lift(r, 0.85), lift(g, 0.85), lift(b, 0.85), 255)
        bright = (lift(r, 0.30), lift(g, 0.30), lift(b, 0.30), 255)
        mid = (darken(r, 0.85), darken(g, 0.85), darken(b, 0.85), 255)
        dark = (darken(r, 0.40), darken(g, 0.40), darken(b, 0.40), 255)
        return (core, bright, mid, dark)

    def _draw_light_fire(
        self,
        centers: list[tuple[int, int]],
        radius: int,
        color: tuple[int, int, int, int],
    ) -> None:
        if self.canvas_surface is None:
            return
        sw, sh = self.canvas_surface.get_size()
        radius = max(2, radius)
        radius_f = float(radius)
        flame_palette = self._fire_palette_from_color(color)
        for cx, cy in centers:
            for dy in range(-radius - 2, radius + 2):
                py = cy + dy
                if py < 0 or py >= sh:
                    continue
                # Tongues stretch upward (negative dy in screen space)
                stretch_y = float(dy) if dy < 0 else dy * 0.55
                for dx in range(-radius, radius + 1):
                    px = cx + dx
                    if px < 0 or px >= sw:
                        continue
                    d = math.hypot(dx, stretch_y)
                    jitter = random.uniform(0.85, 1.18)
                    if d * jitter > radius_f:
                        continue
                    t = min(1.0, d / radius_f)
                    if t < 0.20:
                        flame = flame_palette[0]
                    elif t < 0.50:
                        flame = flame_palette[1]
                    elif t < 0.80:
                        flame = flame_palette[2]
                    else:
                        flame = flame_palette[3]
                    falloff = (1.0 - t) ** 1.4
                    opacity = falloff * 0.55 * random.uniform(0.65, 1.15)
                    if opacity < 0.02:
                        continue
                    self._lighten_canvas_pixel((px, py), flame, opacity)

    def _draw_light(self, pixel: tuple[int, int], color: tuple[int, int, int, int]) -> None:
        if self.canvas_surface is None:
            return
        radius = max(2, self.canvas_brush_size)
        centers = self._mirror_positions(pixel[0], pixel[1])
        if self.canvas_light_mode == "fire":
            self._draw_light_fire(centers, radius, color)
            self._canvas_patch_render_region(self._canvas_dirty_rect_from_points(centers, radius * 2))
        else:
            self._draw_light_bulb(centers, radius, color)
            # Bulb modifies every pixel on the canvas; invalidate the whole frame
            # so the cached composite/scaled views fully refresh.
            self._mark_canvas_changed()

    def _finalize_lasso_selection(self) -> None:
        screen_pts = self.canvas_lasso_pixels
        if self.canvas_surface is None or len(screen_pts) < 3:
            self.canvas_lasso_pixels = []
            self.canvas_lasso_active = False
            return

        sw, sh = self.canvas_surface.get_size()

        # 1. Convert screen-space path to canvas pixel outline via Bresenham
        #    between consecutive points (already 1-2px apart in screen space,
        #    but mapping may compress them further, so Bresenham closes any gaps).
        outline: set[tuple[int, int]] = set()

        def screen_to_canvas(p: tuple[int, int]) -> tuple[int, int] | None:
            return self._canvas_pixel_at(p)

        # Interpolate at 1-px screen steps between consecutive points so that
        # fast mouse movement (which may leave large jumps) is covered.
        interpolated: list[tuple[int, int]] = []
        for i in range(len(screen_pts) - 1):
            ax, ay = screen_pts[i]
            bx, by = screen_pts[i + 1]
            steps = max(abs(bx - ax), abs(by - ay), 1)
            for t in range(steps):
                ix = ax + (bx - ax) * t // steps
                iy = ay + (by - ay) * t // steps
                interpolated.append((ix, iy))
        interpolated.append(screen_pts[-1])

        # Convert each interpolated screen point to a canvas pixel
        canvas_path: list[tuple[int, int]] = []
        prev: tuple[int, int] | None = None
        for sp in interpolated:
            cp = screen_to_canvas(sp)
            if cp is None:
                continue
            cpx = max(0, min(sw - 1, cp[0]))
            cpy = max(0, min(sh - 1, cp[1]))
            cp = (cpx, cpy)
            if cp != prev:
                canvas_path.append(cp)
                prev = cp

        if len(canvas_path) < 3:
            self.canvas_lasso_pixels = []
            self.canvas_lasso_active = False
            return

        # 2. Rasterize the closed outline using Bresenham between canvas pixels
        for i in range(len(canvas_path)):
            x0, y0 = canvas_path[i]
            x1, y1 = canvas_path[(i + 1) % len(canvas_path)]
            for pt in self._bresenham_line(x0, y0, x1, y1):
                if 0 <= pt[0] < sw and 0 <= pt[1] < sh:
                    outline.add(pt)

        # 3. Find centroid of canvas_path and BFS flood fill inward from there
        cx = sum(p[0] for p in canvas_path) // len(canvas_path)
        cy = sum(p[1] for p in canvas_path) // len(canvas_path)
        seed = (cx, cy)

        # If centroid lands on the outline itself, nudge until we find interior
        if seed in outline:
            found_seed = False
            for r in range(1, max(sw, sh)):
                for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r),
                               (r, r), (-r, r), (r, -r), (-r, -r)):
                    s = (cx + dx, cy + dy)
                    if 0 <= s[0] < sw and 0 <= s[1] < sh and s not in outline:
                        seed = s
                        found_seed = True
                        break
                if found_seed:
                    break

        interior: set[tuple[int, int]] = set()
        if seed not in outline and 0 <= seed[0] < sw and 0 <= seed[1] < sh:
            q: deque[tuple[int, int]] = deque([seed])
            visited: set[tuple[int, int]] = {seed}
            while q:
                x, y = q.popleft()
                interior.add((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if (nx, ny) in visited or (nx, ny) in outline:
                        continue
                    if 0 <= nx < sw and 0 <= ny < sh:
                        visited.add((nx, ny))
                        q.append((nx, ny))

        selected = outline | interior
        self.canvas_selection_pixels = selected
        self.canvas_lasso_pixels = []
        self.canvas_lasso_active = False
        self.status = f"Selected {len(selected)} pixel(s). Delete to erase, Esc to deselect."

    def _bucket_fill(self, start: tuple[int, int], fill_color: tuple[int, int, int, int]) -> None:
        if self.canvas_surface is None:
            return
        self._canvas_push_undo()
        width, height = self.canvas_surface.get_size()
        starts = self._mirror_positions(start[0], start[1])
        # Capture each mirror start's target color before any fill mutates the canvas
        seeds: list[tuple[tuple[int, int], pygame.Color]] = []
        for s in starts:
            if 0 <= s[0] < width and 0 <= s[1] < height:
                seeds.append((s, self.canvas_surface.get_at(s)))
        for seed, target in seeds:
            if self.canvas_surface.get_at(seed) != target:
                continue
            if target == fill_color:
                continue
            q: deque[tuple[int, int]] = deque([seed])
            seen: set[tuple[int, int]] = {seed}
            while q:
                x, y = q.popleft()
                if self.canvas_surface.get_at((x, y)) != target:
                    continue
                self.canvas_surface.set_at((x, y), fill_color)
                if x > 0:
                    p = (x - 1, y)
                    if p not in seen:
                        seen.add(p)
                        q.append(p)
                if x + 1 < width:
                    p = (x + 1, y)
                    if p not in seen:
                        seen.add(p)
                        q.append(p)
                if y > 0:
                    p = (x, y - 1)
                    if p not in seen:
                        seen.add(p)
                        q.append(p)
                if y + 1 < height:
                    p = (x, y + 1)
                    if p not in seen:
                        seen.add(p)
                        q.append(p)
        self._mark_canvas_changed()

    def _handle_canvas_click(self, pos: tuple[int, int]) -> bool:
        if self.workspace_mode != "canvas":
            return False
        panel = self._canvas_tools_panel_rect()
        board = self._canvas_workspace_panel_rect()

        # ── Right-panel: tools / size input / fill toggle / palette ───
        if panel.collidepoint(pos):
            for name, rect in self._canvas_toolbar_buttons(panel).items():
                if rect.collidepoint(pos):
                    if name == "light" and self.canvas_tool == "light":
                        self.canvas_light_mode = "fire" if self.canvas_light_mode == "bulb" else "bulb"
                        self.status = f"Light: {self.canvas_light_mode.title()} mode."
                        return True
                    self.canvas_tool = name
                    if name not in {"select", "rectselect", "move", "rotate3d"}:
                        self.canvas_selection_pixels.clear()
                    entered_transform = False
                    if name == "rotate3d" and self.canvas_sel_transform:
                        self.status = "Finish the current transform with Enter or Esc first."
                        return True
                    if name == "rotate3d" and self.canvas_selection_pixels:
                        self._canvas_enter_sel_transform("rotate3d")
                        entered_transform = True
                    tool_label = dict(self._CANVAS_TOOLS).get(name, name.title())
                    if name == "light":
                        self.status = f"Canvas tool: Light ({self.canvas_light_mode}). Click Light again to switch mode."
                        return True
                    if not entered_transform:
                        self.status = f"Canvas tool: {tool_label}."
                    return True
            minus, field, plus = self._canvas_size_input_rects(panel)
            if minus.collidepoint(pos):
                self.canvas_brush_size = max(1, self.canvas_brush_size - 1)
                self.canvas_brush_size_input = str(self.canvas_brush_size)
                self.status = f"Brush size: {self.canvas_brush_size}px."
                return True
            if plus.collidepoint(pos):
                self.canvas_brush_size = min(128, self.canvas_brush_size + 1)
                self.canvas_brush_size_input = str(self.canvas_brush_size)
                self.status = f"Brush size: {self.canvas_brush_size}px."
                return True
            if field.collidepoint(pos):
                self.canvas_brush_size_focus = True
                self.canvas_blend_focus = False
                return True
            fill_rect = self._canvas_fill_toggle_rect(panel)
            if fill_rect.collidepoint(pos):
                self.canvas_fill_shapes = not self.canvas_fill_shapes
                self.status = f"Shape fill: {'on' if self.canvas_fill_shapes else 'off'}."
                return True
            mh_rect, mv_rect = self._canvas_mirror_toggle_rects(panel)
            if mh_rect.collidepoint(pos):
                self.canvas_mirror_h = not self.canvas_mirror_h
                self.status = f"Mirror horizontal: {'on' if self.canvas_mirror_h else 'off'}."
                return True
            if mv_rect.collidepoint(pos):
                self.canvas_mirror_v = not self.canvas_mirror_v
                self.status = f"Mirror vertical: {'on' if self.canvas_mirror_v else 'off'}."
                return True
            bm, bf, bp = self._canvas_blend_input_rects(panel)
            if bm.collidepoint(pos):
                self.canvas_blend_strength = max(0.0, round(self.canvas_blend_strength - 0.05, 2))
                self.canvas_blend_input = str(int(self.canvas_blend_strength * 100))
                self.status = f"Blend strength: {int(self.canvas_blend_strength * 100)}%."
                return True
            if bp.collidepoint(pos):
                self.canvas_blend_strength = min(1.0, round(self.canvas_blend_strength + 0.05, 2))
                self.canvas_blend_input = str(int(self.canvas_blend_strength * 100))
                self.status = f"Blend strength: {int(self.canvas_blend_strength * 100)}%."
                return True
            if bf.collidepoint(pos):
                self.canvas_blend_focus = True
                self.canvas_brush_size_focus = False
                return True
            for key, rect in self._canvas_selection_action_rects(panel).items():
                if rect.collidepoint(pos):
                    if key == "rot_cw":
                        self._canvas_rotate_selection(cw=True)
                    elif key == "rot_ccw":
                        self._canvas_rotate_selection(cw=False)
                    elif key == "flip_h":
                        self._canvas_flip_selection(horizontal=True)
                    elif key == "flip_v":
                        self._canvas_flip_selection(horizontal=False)
                    elif key == "scale_up":
                        self._canvas_scale_selection(1.25)
                    elif key == "scale_dn":
                        self._canvas_scale_selection(0.8)
                    elif key == "bright_up":
                        self._canvas_adjust_brightness(0.1)
                    elif key == "bright_dn":
                        self._canvas_adjust_brightness(-0.1)
                    return True
            self.canvas_brush_size_focus = False
            self.canvas_blend_focus = False
            for idx, swatch_rect in enumerate(self._canvas_quick_palette_rects(panel)):
                if swatch_rect.collidepoint(pos):
                    self._canvas_apply_quick_palette_slot(idx)
                    return True
            if self._canvas_color_button_rect(panel).collidepoint(pos):
                self._open_canvas_color_picker()
                return True
            return True

        if not board.collidepoint(pos):
            self.canvas_brush_size_focus = False
            self.canvas_blend_focus = False
            return False

        # ── In-canvas toolbar (New / Save / Fit / Onion / BG) ─────────
        if self.canvas_focus_mode:
            if self._canvas_focus_toggle_rect(board).collidepoint(pos):
                self.canvas_focus_mode = False
                self.dropdown_open = None
                self.status = "Canvas focus mode off."
                return True
        else:
            for idx, rect in self._canvas_header_tab_rects(board):
                if rect.collidepoint(pos):
                    if idx == self.canvas_tab_idx:
                        self._open_canvas_rename_dialog("tab")
                    else:
                        self._switch_canvas_tab(idx)
                    return True
            for name, rect in self._canvas_workspace_toolbar_buttons(board).items():
                if rect.collidepoint(pos):
                    if name == "new":
                        self._open_new_canvas_dialog()
                    elif name == "fit":
                        self._canvas_fit()
                        self.status = "Canvas fitted to view."
                    elif name == "onion":
                        self.canvas_onion_skin = not self.canvas_onion_skin
                        self.status = f"Onion skin: {'on' if self.canvas_onion_skin else 'off'}."
                    elif name == "bgmode":
                        self.canvas_bg_light = not self.canvas_bg_light
                        self.status = f"Background: {'light' if self.canvas_bg_light else 'dark'}."
                    elif name == "delete":
                        self._delete_current_canvas_tab()
                    elif name == "focus":
                        self.canvas_focus_mode = not self.canvas_focus_mode
                        self.dropdown_open = None
                        self.status = "Canvas focus mode " + ("on." if self.canvas_focus_mode else "off.")
                    return True

        # ── Drawing view ───────────────────────────────────────────────
        view = self._canvas_view_rect(board)
        if not view.collidepoint(pos):
            return True
        if self.canvas_surface is None:
            return True
        draw_rect = self._canvas_draw_rect(view, self.canvas_surface)

        overlay_actions = self._canvas_selection_overlay_action_rects(draw_rect)
        for key, rect in overlay_actions.items():
            if rect.collidepoint(pos):
                if key == "copy":
                    self._canvas_copy_selection()
                elif key == "paste":
                    self._canvas_paste_start()
                elif key == "move" and self.canvas_selection_pixels:
                    self._canvas_enter_sel_transform("move", auto_commit=True)
                return True

        if self.canvas_sel_transform == "rotate3d" and self.canvas_selection_pixels:
            axis = self._canvas_3d_gizmo_hit_axis(pos, draw_rect)
            if axis is not None:
                self.canvas_sel_drag_start = pos
                self._canvas_start_3d_gizmo_drag(axis, pos, draw_rect)
                self.canvas_drawing = True
                return True
            rotate3d_rect = self._canvas_3d_selection_screen_rect(draw_rect)
            if rotate3d_rect is not None and rotate3d_rect.collidepoint(pos):
                self.canvas_sel_drag_start = pos
                self._canvas_start_3d_gizmo_drag("free", pos, draw_rect)
                self.canvas_drawing = True
                return True
            return True

        if self.canvas_sel_transform == "rotate" and self.canvas_selection_pixels:
            rotate_handle = self._canvas_rotation_handle_rect(draw_rect)
            if rotate_handle is not None and rotate_handle.collidepoint(pos):
                self.canvas_sel_drag_start = pos
                self.canvas_drawing = True
                return True
            rotate_box = self._canvas_selection_screen_rect(draw_rect)
            if rotate_box is not None and rotate_box.collidepoint(pos):
                self.canvas_sel_drag_start = pos
                self.canvas_drawing = True
                return True

        handle_rects = self._canvas_selection_handle_rects(draw_rect)
        for handle_name, handle_rect in handle_rects.items():
            if handle_rect.collidepoint(pos) and self.canvas_selection_pixels:
                if self.canvas_sel_transform != "scale" or not self.canvas_sel_lift:
                    self._canvas_enter_sel_transform("scale", auto_commit=True)
                self.canvas_sel_drag_start = pos
                self.canvas_sel_drag_mode = handle_name
                self.canvas_drawing = True
                return True

        sel_rect = self._canvas_selection_screen_rect(draw_rect)
        if sel_rect is not None and sel_rect.collidepoint(pos) and self.canvas_selection_pixels:
            if self.canvas_sel_transform != "move" or not self.canvas_sel_lift:
                self._canvas_enter_sel_transform("move", auto_commit=True)
            self.canvas_sel_drag_start = pos
            self.canvas_drawing = True
            return True

        # Commit paste if active and clicking canvas area
        if self.canvas_paste_active:
            self._canvas_paste_commit()
            return True

        # Click outside the paste/move selection while a non-auto-committing
        # paste is live → commit so the user doesn't have to find the Enter key.
        if (
            self.canvas_sel_transform == "move"
            and self.canvas_sel_lift
            and not self.canvas_sel_auto_commit
        ):
            self._canvas_commit_sel_transform()
            return True

        pixel = self._canvas_pixel_at(pos)
        tool = self.canvas_tool
        color = (0, 0, 0, 0) if tool == "eraser" else self.canvas_color

        # ── Transform gizmo drag initiation ──────────────────────
        if self.canvas_sel_transform:
            self.canvas_sel_drag_start = pos
            self.canvas_drawing = True
            if self.canvas_sel_transform == "scale":
                # Detect which corner was clicked
                bbox3 = self._canvas_sel_bbox()
                if bbox3:
                    min_x3, min_y3, max_x3, max_y3 = bbox3
                    zoom3 = self.canvas_zoom
                    panel3 = self._canvas_workspace_panel_rect()
                    view3 = self._canvas_view_rect(panel3)
                    dr3 = self._canvas_draw_rect(view3, self.canvas_surface) if self.canvas_surface else draw_rect
                    corners3 = {
                        "tl": (dr3.x + int(min_x3 * zoom3), dr3.y + int(min_y3 * zoom3)),
                        "tr": (dr3.x + int((max_x3+1) * zoom3), dr3.y + int(min_y3 * zoom3)),
                        "bl": (dr3.x + int(min_x3 * zoom3), dr3.y + int((max_y3+1) * zoom3)),
                        "br": (dr3.x + int((max_x3+1) * zoom3), dr3.y + int((max_y3+1) * zoom3)),
                    }
                    self.canvas_sel_drag_mode = ""
                    for cname, (chx, chy) in corners3.items():
                        if abs(pos[0] - chx) < 12 and abs(pos[1] - chy) < 12:
                            self.canvas_sel_drag_mode = cname
                            break
            return True

        if tool == "rotate3d":
            if self.canvas_selection_pixels:
                self._canvas_enter_sel_transform("rotate3d")
            elif pixel and self._canvas_select_opaque_region(pixel):
                self._canvas_enter_sel_transform("rotate3d")
            else:
                self.status = "Click opaque pixels or make a selection, then press R for 3D rotate."
            return True

        if tool == "eyedropper":
            if pixel and self.canvas_surface is not None:
                sampled = self.canvas_surface.get_at(pixel)
                self._set_canvas_color((sampled.r, sampled.g, sampled.b, 255))
                self.status = f"Picked {self._canvas_color_hex()}."
        elif tool == "bucket":
            if pixel:
                self._record_canvas_color_use(self.canvas_color, weight=2)
                self._bucket_fill(pixel, self.canvas_color)
        elif tool == "select":
            self.canvas_selection_pixels.clear()
            self.canvas_lasso_pixels = [pos]
            self.canvas_lasso_active = True
            self.canvas_drawing = True
        elif tool == "rectselect":
            if pixel:
                self.canvas_selection_pixels.clear()
                self.canvas_rect_select_start = pixel
                self.canvas_rect_select_end = pixel
                self.canvas_rect_select_active = True
                self.canvas_drawing = True
        elif tool == "vpoint":
            if pixel:
                if self.canvas_vp is None:
                    # First click sets the VP
                    self.canvas_vp = pixel
                    self.status = f"VP set at {pixel}. Click+drag to draw lines toward it."
                else:
                    # Subsequent clicks start a VP-line drag
                    self.canvas_preview_start = pixel
                    self.canvas_drawing = True
        elif tool in {"line", "circle", "square"}:
            if pixel:
                self._record_canvas_color_use(color, weight=2)
                self.canvas_preview_start = pixel
                self.canvas_preview_end = pixel
                self.canvas_preview_active = True
                self.canvas_drawing = True
        elif tool in {"pencil", "brush", "eraser", "spray", "blend", "smudge", "light"}:
            if pixel:
                if tool != "eraser":
                    self._record_canvas_color_use(color, weight=2)
                self._canvas_push_undo()
                self.canvas_drawing = True
                self.canvas_smudge_prev = pixel
                self.canvas_last_pixel = pixel
                if tool == "spray":
                    self._draw_spray(pixel, color)
                elif tool == "blend":
                    self._draw_blend(pixel, color)
                elif tool == "light":
                    self._draw_light(pixel, color)
                elif tool != "smudge":
                    self._draw_canvas_line(pixel, pixel, color)
        elif tool == "move":
            if self.canvas_selection_pixels:
                if self.canvas_sel_transform != "move" or not self.canvas_sel_lift:
                    self._canvas_enter_sel_transform("move", auto_commit=True)
                self.canvas_sel_drag_start = pos
                self.canvas_drawing = True
            else:
                # Move tool: drag pans the canvas view
                self.canvas_move_dragging = True
                self.canvas_move_last = pos
                self.canvas_drawing = True
        elif tool == "resize":
            # Resize tool: check if clicking a corner handle
            if self.canvas_surface is not None:
                sw, sh = self.canvas_surface.get_size()
                panel2 = self._canvas_workspace_panel_rect()
                view2 = self._canvas_view_rect(panel2)
                dr = self._canvas_draw_rect(view2, self.canvas_surface)
                hs = 10
                corners = {
                    "br": (dr.right, dr.bottom),
                    "bl": (dr.x,     dr.bottom),
                    "tr": (dr.right, dr.y),
                    "tl": (dr.x,     dr.y),
                }
                for anchor, (hx, hy) in corners.items():
                    if abs(pos[0] - hx) < hs and abs(pos[1] - hy) < hs:
                        self.canvas_resize_dragging = True
                        self.canvas_resize_anchor = anchor
                        self.canvas_drawing = True
                        break
        elif tool == "rotate":
            # Rotate: click rotates canvas 90° CW; right-click handled in mouse up
            if self.canvas_surface is not None:
                self._canvas_push_undo()
                rotated = pygame.transform.rotate(self.canvas_surface, -90)
                self.canvas_surface = rotated
                self._mark_canvas_changed()
                self.status = "Canvas rotated 90° CW."
        return True

    def _handle_canvas_motion(self, pos: tuple[int, int]) -> bool:
        if self.workspace_mode != "canvas":
            return False
        if self.canvas_panning:
            dx = pos[0] - self.canvas_pan_anchor[0]
            dy = pos[1] - self.canvas_pan_anchor[1]
            self.canvas_offset_x = self.canvas_pan_origin[0] + dx
            self.canvas_offset_y = self.canvas_pan_origin[1] + dy
            return True
        # Move tool drag → pan canvas view
        if self.canvas_move_dragging:
            dx = pos[0] - self.canvas_move_last[0]
            dy = pos[1] - self.canvas_move_last[1]
            self.canvas_offset_x += dx
            self.canvas_offset_y += dy
            self.canvas_move_last = pos
            return True
        # Resize tool drag → resize canvas
        if self.canvas_resize_dragging and self.canvas_surface is not None:
            panel2 = self._canvas_workspace_panel_rect()
            view2 = self._canvas_view_rect(panel2)
            dr = self._canvas_draw_rect(view2, self.canvas_surface)
            zoom = max(self.canvas_zoom, 0.001)
            anchor = self.canvas_resize_anchor
            if anchor == "br":
                new_w = max(1, int((pos[0] - dr.x) / zoom))
                new_h = max(1, int((pos[1] - dr.y) / zoom))
            elif anchor == "bl":
                new_w = max(1, int((dr.right - pos[0]) / zoom))
                new_h = max(1, int((pos[1] - dr.y) / zoom))
            elif anchor == "tr":
                new_w = max(1, int((pos[0] - dr.x) / zoom))
                new_h = max(1, int((dr.bottom - pos[1]) / zoom))
            else:  # tl
                new_w = max(1, int((dr.right - pos[0]) / zoom))
                new_h = max(1, int((dr.bottom - pos[1]) / zoom))
            new_w = max(1, min(new_w, 2048))
            new_h = max(1, min(new_h, 2048))
            if (new_w, new_h) != self.canvas_surface.get_size():
                new_surf = pygame.Surface((new_w, new_h), pygame.SRCALPHA)
                new_surf.fill((0, 0, 0, 0))
                new_surf.blit(self.canvas_surface, (0, 0))
                self.canvas_surface = new_surf
                self._mark_canvas_changed()
            return True
        # ── Transform gizmo drag update ──────────────────────────
        if self.canvas_sel_transform and self.canvas_sel_drag_start and self.canvas_drawing:
            dx = pos[0] - self.canvas_sel_drag_start[0]
            dy = pos[1] - self.canvas_sel_drag_start[1]
            zoom = max(self.canvas_zoom, 0.001)
            if self.canvas_sel_transform == "move":
                self.canvas_sel_offset = (int(dx / zoom), int(dy / zoom))
            elif self.canvas_sel_transform == "rotate3d":
                panel4 = self._canvas_workspace_panel_rect()
                view4 = self._canvas_view_rect(panel4)
                dr4 = self._canvas_draw_rect(view4, self.canvas_surface) if self.canvas_surface else None
                if dr4 is not None:
                    if self.canvas_sel_3d_axis is None:
                        self._canvas_start_3d_gizmo_drag("z", self.canvas_sel_drag_start, dr4)
                    self._canvas_update_3d_gizmo_drag(pos, dr4)
            elif self.canvas_sel_transform == "rotate":
                import math
                bbox4 = self.canvas_sel_base_bbox or self._canvas_sel_bbox()
                if bbox4:
                    panel4 = self._canvas_workspace_panel_rect()
                    view4 = self._canvas_view_rect(panel4)
                    dr4 = self._canvas_draw_rect(view4, self.canvas_surface) if self.canvas_surface else None
                    if dr4:
                        min_x4, min_y4, max_x4, max_y4 = bbox4
                        cx4 = dr4.x + ((min_x4 + max_x4) / 2.0) * zoom
                        cy4 = dr4.y + ((min_y4 + max_y4) / 2.0) * zoom
                        self.canvas_sel_angle = math.degrees(math.atan2(pos[1] - cy4, pos[0] - cx4))
            elif self.canvas_sel_transform == "scale" and self.canvas_sel_drag_mode:
                bbox5 = self.canvas_sel_base_bbox or self._canvas_sel_bbox()
                if bbox5:
                    min_x5, min_y5, max_x5, max_y5 = bbox5
                    left = float(min_x5)
                    top = float(min_y5)
                    right = float(max_x5 + 1)
                    bottom = float(max_y5 + 1)
                    dx_canvas = dx / zoom
                    dy_canvas = dy / zoom
                    mode = self.canvas_sel_drag_mode
                    if "l" in mode:
                        left += dx_canvas
                    if "r" in mode:
                        right += dx_canvas
                    if "t" in mode:
                        top += dy_canvas
                    if "b" in mode:
                        bottom += dy_canvas
                    if mode == "tm":
                        top += dy_canvas
                    elif mode == "bm":
                        bottom += dy_canvas
                    elif mode == "ml":
                        left += dx_canvas
                    elif mode == "mr":
                        right += dx_canvas
                    min_size = 1.0
                    if right - left < min_size:
                        if mode in {"tl", "bl", "ml"}:
                            left = right - min_size
                        else:
                            right = left + min_size
                    if bottom - top < min_size:
                        if mode in {"tl", "tr", "tm"}:
                            top = bottom - min_size
                        else:
                            bottom = top + min_size
                    self.canvas_sel_scale_rect = (left, top, right, bottom)
            return True

        if not self.canvas_drawing or self.canvas_surface is None:
            return False
        pixel = self._canvas_pixel_at(pos)
        tool = self.canvas_tool
        color = (0, 0, 0, 0) if tool == "eraser" else self.canvas_color

        if tool == "select" and self.canvas_lasso_active:
            if not self.canvas_lasso_pixels or (
                abs(pos[0] - self.canvas_lasso_pixels[-1][0]) > 1
                or abs(pos[1] - self.canvas_lasso_pixels[-1][1]) > 1
            ):
                self.canvas_lasso_pixels.append(pos)
        elif tool == "rectselect" and self.canvas_rect_select_active:
            if pixel:
                self.canvas_rect_select_end = pixel
        elif tool in {"line", "circle", "square"} and self.canvas_preview_active:
            if pixel:
                self.canvas_preview_end = pixel
        elif tool == "vpoint" and self.canvas_drawing:
            if pixel:
                self.canvas_preview_end = pixel  # reuse preview to show VP line
        elif tool in {"pencil", "brush", "eraser"}:
            if pixel:
                last = self.canvas_last_pixel or pixel
                self._draw_canvas_line(last, pixel, color)
                self.canvas_last_pixel = pixel
        elif tool == "spray":
            if pixel:
                self._draw_spray(pixel, color)
        elif tool == "blend":
            if pixel:
                self._draw_blend(pixel, color)
        elif tool == "light":
            # Fire mode is a brush stroke; bulb is a one-shot bucket-style glow.
            if pixel and self.canvas_light_mode == "fire":
                self._draw_light(pixel, color)
        elif tool == "smudge":
            if pixel:
                prev = self.canvas_smudge_prev or pixel
                if prev != pixel:
                    self._draw_smudge(prev, pixel)
                self.canvas_smudge_prev = pixel
        return True

    def _handle_canvas_mouse_up(self) -> None:
        tool = self.canvas_tool
        color = (0, 0, 0, 0) if tool == "eraser" else self.canvas_color
        if tool == "select" and self.canvas_lasso_active:
            self._finalize_lasso_selection()
        elif tool == "rectselect" and self.canvas_rect_select_active:
            self._finalize_rect_selection()
        elif tool in {"line", "circle", "square"} and self.canvas_preview_active:
            if self.canvas_preview_start and self.canvas_preview_end and self.canvas_surface:
                self._commit_shape(self.canvas_preview_start, self.canvas_preview_end, color)
        elif tool == "vpoint" and self.canvas_drawing:
            # Commit VP line: from canvas_preview_start toward vanishing point
            if self.canvas_preview_start and self.canvas_vp and self.canvas_surface:
                self._canvas_push_undo()
                self._draw_vpoint_line(self.canvas_preview_start, color)
        if self.canvas_sel_transform and self.canvas_sel_drag_start is not None and self.canvas_sel_auto_commit:
            self._canvas_commit_sel_transform()
        self.canvas_sel_3d_axis = None
        if self.canvas_sel_transform == "rotate3d":
            self.canvas_sel_drag_start = None
        self.canvas_drawing = False
        self.canvas_last_pixel = None
        self.canvas_smudge_prev = None
        self.canvas_panning = False
        self.canvas_move_dragging = False
        self.canvas_resize_dragging = False
        self.canvas_preview_active = False
        self.canvas_preview_start = None
        self.canvas_preview_end = None
        self.canvas_lasso_active = False
        self.canvas_rect_select_active = False
