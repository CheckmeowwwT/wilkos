from __future__ import annotations

import colorsys
import math
import random
from collections import deque

import pygame

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

    def _canvas_rebuild_selection_surface(self) -> None:
        self._canvas_sel_preview_cache_key = None
        self._canvas_sel_preview_surf = None
        self._canvas_sel_rotate_cache_key = None
        self._canvas_sel_rotate_cache_surf = None
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
        elif self.canvas_surface is not None:
            self.canvas_clipboard = {
                (px, py): tuple(self.canvas_surface.get_at((px, py)))  # type: ignore[arg-type]
                for px, py in self.canvas_selection_pixels
            }
        else:
            self.status = "Nothing selected to copy."
            return
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
        self.canvas_sel_drag_start = None
        self.canvas_sel_drag_mode = ""
        self.canvas_sel_restore_on_cancel = True
        self.canvas_sel_auto_commit = auto_commit
        self.canvas_sel_push_undo_on_commit = False
        self._canvas_rebuild_selection_surface()
        self._mark_canvas_changed()
        mode_labels = {"move": "M — drag to move  Enter=commit  Esc=cancel",
                       "rotate": "R — drag to rotate  Enter=commit  Esc=cancel",
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
        self.canvas_sel_drag_start = None
        self.canvas_sel_drag_mode = ""
        self.canvas_sel_restore_on_cancel = False
        self.canvas_sel_auto_commit = True
        self.canvas_sel_push_undo_on_commit = True
        self._canvas_rebuild_selection_surface()
        self.status = "Pasted selection — drag to move or use handles to resize."

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
            self.canvas_selection_pixels = self._canvas_apply_surface_selection(
                self.canvas_sel_surface,
                (int(round(min_x + ox)), int(round(min_y + oy))),
            )
        elif self.canvas_sel_transform == "scale" and self.canvas_sel_surface is not None and self.canvas_sel_scale_rect is not None:
            left, top, right, bottom = self.canvas_sel_scale_rect
            target_w = max(1, int(round(right - left)))
            target_h = max(1, int(round(bottom - top)))
            scaled = pygame.transform.scale(self.canvas_sel_surface, (target_w, target_h))
            self.canvas_selection_pixels = self._canvas_apply_surface_selection(
                scaled,
                (int(round(left)), int(round(top))),
            )
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
        self.canvas_sel_lift = {}
        self.canvas_sel_transform = None
        self.canvas_sel_drag_start = None
        self.canvas_sel_drag_mode = ""
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
        self._mark_canvas_changed()
        self.status = "Transform cancelled."

    def _draw_smudge(self, prev: tuple[int, int], curr: tuple[int, int]) -> None:
        """Drag pixels from prev toward curr — classic smear effect."""
        if self.canvas_surface is None:
            return
        sw, sh = self.canvas_surface.get_size()
        size = max(1, self.canvas_brush_size)
        strength = 0.7
        for ox in range(-size, size + 1):
            for oy in range(-size, size + 1):
                if ox * ox + oy * oy > size * size:
                    continue
                sx, sy = prev[0] + ox, prev[1] + oy
                tx, ty = curr[0] + ox, curr[1] + oy
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
        self._canvas_patch_render_region(self._canvas_dirty_rect_from_points([prev, curr], size))

    # ── Vanishing point tool ─────────────────────────────────────────────

    def _draw_vpoint_line(self, start: tuple[int, int], color: tuple[int, int, int, int]) -> None:
        """Draw a line from start through (or toward) the vanishing point,
        extending to canvas edges in both directions."""
        if self.canvas_surface is None or self.canvas_vp is None:
            return
        sw, sh = self.canvas_surface.get_size()
        vx, vy = self.canvas_vp
        sx, sy = start
        dx, dy = vx - sx, vy - sy
        if dx == 0 and dy == 0:
            return
        size = max(1, self.canvas_brush_size)
        # Extend the line in both directions until it leaves the canvas
        def _clip_t(p: float, d: float, lo: float, hi: float) -> tuple[float, float]:
            if d == 0:
                return (-1e9, 1e9)
            return ((lo - p) / d, (hi - p) / d)
        tx_lo, tx_hi = _clip_t(sx, dx, 0, sw - 1)
        ty_lo, ty_hi = _clip_t(sy, dy, 0, sh - 1)
        t_min = max(min(tx_lo, tx_hi), min(ty_lo, ty_hi))
        t_max = min(max(tx_lo, tx_hi), max(ty_lo, ty_hi))
        if t_max < t_min:
            return
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
        if tool == "line":
            self._draw_canvas_pixel_line(start, end, color, size)
        elif tool == "circle":
            rx = abs(end[0] - start[0])
            ry = abs(end[1] - start[1])
            cx, cy = start
            rect = pygame.Rect(cx - rx, cy - ry, rx * 2, ry * 2)
            pygame.draw.ellipse(self.canvas_surface, color, rect, 0 if self.canvas_fill_shapes else size)
        elif tool == "square":
            x0, y0 = min(start[0], end[0]), min(start[1], end[1])
            x1, y1 = max(start[0], end[0]), max(start[1], end[1])
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
        target = self.canvas_surface.get_at(start)
        if target == fill_color:
            return
        q: deque[tuple[int, int]] = deque([start])
        seen: set[tuple[int, int]] = {start}
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
                    self.canvas_tool = name
                    if name not in {"select", "rectselect", "move"}:
                        self.canvas_selection_pixels.clear()
                    tool_label = dict(self._CANVAS_TOOLS).get(name, name.title())
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
        elif tool in {"pencil", "brush", "eraser", "spray", "blend", "smudge"}:
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
        if self.canvas_sel_transform and self.canvas_sel_drag_start:
            dx = pos[0] - self.canvas_sel_drag_start[0]
            dy = pos[1] - self.canvas_sel_drag_start[1]
            zoom = max(self.canvas_zoom, 0.001)
            if self.canvas_sel_transform == "move":
                self.canvas_sel_offset = (int(dx / zoom), int(dy / zoom))
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


