from __future__ import annotations

import colorsys
import math
import random
from pathlib import Path

import pygame

try:
    from ..constants import CANVAS_PALETTE
    from ..core.utils import input_display_text, parse_int
except ImportError:
    from constants import CANVAS_PALETTE  # type: ignore[no-redef]
    from core.utils import input_display_text, parse_int  # type: ignore[no-redef]


class UIRenderMixin:
    def _draw_tool_icon(self, surf: pygame.Surface, name: str, rect: pygame.Rect, col: tuple) -> None:
        """Draw a small programmatic icon so we're not font-glyph-dependent."""
        cx, cy = rect.centerx, rect.centery
        s = 5  # half-size
        c = col

        if name == "select":
            # Dashed selection rectangle
            r = pygame.Rect(cx - s, cy - s, s * 2, s * 2)
            for i in range(0, r.width + 1, 3):
                x = r.x + min(i, r.width - 1)
                pygame.draw.rect(surf, c, (x, r.y, 2, 1))
                pygame.draw.rect(surf, c, (x, r.bottom, 2, 1))
            for i in range(0, r.height + 1, 3):
                y = r.y + min(i, r.height - 1)
                pygame.draw.rect(surf, c, (r.x, y, 1, 2))
                pygame.draw.rect(surf, c, (r.right, y, 1, 2))

        elif name == "rectselect":
            r = pygame.Rect(cx - s, cy - s, s * 2, s * 2)
            pygame.draw.rect(surf, c, r, 1)
            inner = r.inflate(-4, -4)
            if inner.width > 0 and inner.height > 0:
                pygame.draw.rect(surf, c, inner, 1)

        elif name == "eyedropper":
            # Circle crosshair (targeting sight)
            pygame.draw.circle(surf, c, (cx, cy), s - 1, 1)
            pygame.draw.circle(surf, c, (cx, cy), 2)

        elif name == "move":
            # Cross with 4 arrowheads
            pygame.draw.line(surf, c, (cx - s, cy), (cx + s, cy), 1)
            pygame.draw.line(surf, c, (cx, cy - s), (cx, cy + s), 1)
            pygame.draw.polygon(surf, c, [(cx - s, cy), (cx - s + 3, cy - 2), (cx - s + 3, cy + 2)])
            pygame.draw.polygon(surf, c, [(cx + s, cy), (cx + s - 3, cy - 2), (cx + s - 3, cy + 2)])
            pygame.draw.polygon(surf, c, [(cx, cy - s), (cx - 2, cy - s + 3), (cx + 2, cy - s + 3)])
            pygame.draw.polygon(surf, c, [(cx, cy + s), (cx - 2, cy + s - 3), (cx + 2, cy + s - 3)])

        elif name == "pencil":
            # Diagonal stroke with tip
            pygame.draw.line(surf, c, (cx + s - 1, cy - s + 1), (cx - s + 1, cy + s - 1), 2)
            pygame.draw.circle(surf, c, (cx - s + 1, cy + s - 1), 1)

        elif name == "brush":
            # Filled circle
            pygame.draw.circle(surf, c, (cx, cy), s - 1)

        elif name == "eraser":
            # Filled wide rectangle
            pygame.draw.rect(surf, c, (cx - s, cy - 3, s * 2, 6))

        elif name == "bucket":
            # Filled downward triangle (bucket pouring)
            pygame.draw.polygon(surf, c, [(cx, cy + s), (cx - s, cy - s + 1), (cx + s, cy - s + 1)])

        elif name == "line":
            # Thick diagonal line
            pygame.draw.line(surf, c, (cx - s, cy + s - 1), (cx + s, cy - s + 1), 2)

        elif name == "circle":
            # Circle outline
            pygame.draw.circle(surf, c, (cx, cy), s, 1)

        elif name == "square":
            # Square outline
            pygame.draw.rect(surf, c, (cx - s, cy - s, s * 2 + 1, s * 2 + 1), 1)

        elif name == "spray":
            # Cluster of dots
            _rng = random.Random(42)
            for _ in range(7):
                dx = _rng.randint(-s, s)
                dy = _rng.randint(-s, s)
                pygame.draw.circle(surf, c, (cx + dx, cy + dy), 1)

        elif name == "blend":
            # Two overlapping circle outlines
            pygame.draw.circle(surf, c, (cx - 2, cy), s - 2, 1)
            pygame.draw.circle(surf, c, (cx + 2, cy), s - 2, 1)

        elif name == "smudge":
            # Wavy line (sine curve)
            pts = [(cx - s + i, cy + int(2 * math.sin(i * 1.1))) for i in range(s * 2 + 1)]
            for i in range(len(pts) - 1):
                pygame.draw.line(surf, c, pts[i], pts[i + 1], 2)

        elif name == "vpoint":
            # Converging lines to vanishing point
            pygame.draw.circle(surf, c, (cx, cy), 2)
            pygame.draw.line(surf, c, (cx, cy), (cx - s, cy + s), 1)
            pygame.draw.line(surf, c, (cx, cy), (cx + s, cy + s), 1)
            pygame.draw.line(surf, c, (cx, cy), (cx, cy - s), 1)

        elif name == "rotate3d":
            # Three tiny rotation rings.
            pygame.draw.ellipse(surf, c, pygame.Rect(cx - s, cy - s, s * 2, s * 2), 1)
            pygame.draw.ellipse(surf, c, pygame.Rect(cx - s, cy - 3, s * 2, 6), 1)
            pygame.draw.ellipse(surf, c, pygame.Rect(cx - 3, cy - s, 6, s * 2), 1)

        elif name == "colorkey":
            # Swatch with a diagonal strike-through (remove this color).
            rect_inner = pygame.Rect(cx - s, cy - s + 1, s * 2, s * 2 - 1)
            pygame.draw.rect(surf, c, rect_inner, 1)
            pygame.draw.line(surf, c, rect_inner.topleft, rect_inner.bottomright, 2)

        elif name == "light":
            mode = getattr(self, "canvas_light_mode", "bulb")
            if mode == "fire":
                # Flame torch: teardrop body with inner flame highlight.
                outer = [
                    (cx, cy - s - 1),
                    (cx - 3, cy - s + 3),
                    (cx - s, cy),
                    (cx - 3, cy + s - 1),
                    (cx, cy + s),
                    (cx + 3, cy + s - 1),
                    (cx + s, cy),
                    (cx + 3, cy - s + 3),
                ]
                pygame.draw.polygon(surf, c, outer, 1)
                inner = [
                    (cx, cy - s + 3),
                    (cx - 2, cy + 1),
                    (cx, cy + s - 2),
                    (cx + 2, cy + 1),
                ]
                pygame.draw.polygon(surf, c, inner, 1)
            else:
                # Light bulb: round glass top + screw base lines + radiating ticks.
                pygame.draw.circle(surf, c, (cx, cy - 1), s - 1, 1)
                pygame.draw.line(surf, c, (cx - 2, cy + s - 2), (cx + 2, cy + s - 2), 1)
                pygame.draw.line(surf, c, (cx - 2, cy + s),     (cx + 2, cy + s),     1)
                for ang in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
                    ex = int(cx + math.cos(ang) * (s + 2))
                    ey = int(cy - 1 + math.sin(ang) * (s + 2))
                    ix = int(cx + math.cos(ang) * (s + 0))
                    iy = int(cy - 1 + math.sin(ang) * (s + 0))
                    pygame.draw.line(surf, c, (ix, iy), (ex, ey), 1)

        else:
            # Fallback: render short text
            pass  # caller can fall back to text

    def _draw_canvas_preview_box(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        small: pygame.font.Font,
        *,
        label: str,
        frame_idx: int | None = None,
    ) -> None:
        pygame.draw.rect(screen, (16, 16, 20), rect)
        pygame.draw.rect(screen, (58, 58, 68), rect, 1)
        if rect.width <= 12 or rect.height <= 12:
            return
        preview_idx = self._canvas_preview_frame_idx(pygame.time.get_ticks()) if frame_idx is None else frame_idx
        preview_comp = self._canvas_composited_frame(preview_idx) if self.canvas_doc.frames else None
        if preview_comp is not None:
            pw, ph = preview_comp.get_size()
            inner_w = max(1, rect.width - 10)
            inner_h = max(1, rect.height - 22)
            scale = min(inner_w / max(pw, 1), inner_h / max(ph, 1))
            draw_w = max(1, int(pw * scale))
            draw_h = max(1, int(ph * scale))
            checker = pygame.Surface((draw_w, draw_h))
            checker.fill((62, 62, 68))
            tile = max(4, min(12, max(draw_w // max(pw, 1), draw_h // max(ph, 1))))
            for row in range(0, draw_h, tile):
                for col in range(0, draw_w, tile):
                    if ((row // tile) + (col // tile)) % 2 == 1:
                        checker.fill((46, 46, 52), (col, row, tile, tile))
            target = pygame.Rect(0, 0, draw_w, draw_h)
            target.center = (rect.centerx, rect.centery + 6)
            screen.blit(checker, target.topleft)
            scaled = self._canvas_scaled_frame_surface(preview_idx, (draw_w, draw_h))
            screen.blit(scaled, target.topleft)
        else:
            msg = small.render("No preview", True, (92, 92, 108))
            screen.blit(msg, msg.get_rect(center=rect.center))
            preview_idx = 0
        caption = f"{label}  {'Playing' if self.canvas_preview_playing and len(self.canvas_doc.frames) > 1 else 'Paused'}  F{preview_idx + 1}/{max(1, len(self.canvas_doc.frames))}"
        screen.blit(small.render(caption, True, (170, 190, 230)), (rect.x + 6, rect.y + 6))

    def _draw_shadowed_panel(self, screen: pygame.Surface, rect: pygame.Rect, fill: tuple[int, int, int], border: tuple[int, int, int], radius: int = 0) -> None:  # noqa: ARG002
        pygame.draw.rect(screen, fill, rect)
        pygame.draw.rect(screen, border, rect, 1)

    def _draw_checkerboard(self, screen: pygame.Surface, rect: pygame.Rect, tile: int = 32) -> None:
        color_a = (48, 48, 52)
        color_b = (38, 38, 42)
        cols = (rect.width + tile - 1) // tile
        rows = (rect.height + tile - 1) // tile
        for row in range(rows):
            for col in range(cols):
                color = color_a if (row + col) % 2 == 0 else color_b
                cell = pygame.Rect(rect.x + col * tile, rect.y + row * tile, tile, tile)
                pygame.draw.rect(screen, color, cell)

    def _draw_rotation_gizmo(self, screen: pygame.Surface) -> None:
        if not self.rotation_gizmo_enabled or self.dialog_mode is not None or self.dropdown_open is not None:
            return
        center = self._rotation_gizmo_center_screen()
        metrics = self._rotation_gizmo_metrics()
        if center is None or metrics is None:
            return
        cx, cy = int(center[0]), int(center[1])
        radius, x_ry, y_rx = metrics
        ring_rect_z = pygame.Rect(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))
        ring_rect_x = pygame.Rect(int(cx - radius), int(cy - x_ry), int(radius * 2), int(x_ry * 2))
        ring_rect_y = pygame.Rect(int(cx - y_rx), int(cy - radius), int(y_rx * 2), int(radius * 2))

        colors = {"x": (214, 106, 106), "y": (108, 188, 120), "z": (220, 220, 224)}
        widths = {"x": 1, "y": 1, "z": 1}
        if self.rotation_gizmo_axis in widths:
            widths[self.rotation_gizmo_axis] = 2

        pygame.draw.ellipse(screen, colors["z"], ring_rect_z, widths["z"])
        pygame.draw.ellipse(screen, colors["x"], ring_rect_x, widths["x"])
        pygame.draw.ellipse(screen, colors["y"], ring_rect_y, widths["y"])
        pygame.draw.circle(screen, (232, 232, 236), (cx, cy), 3)

    def _draw_canvas_3d_rotation_gizmo(self, screen: pygame.Surface, draw_rect: pygame.Rect) -> None:
        center = self._canvas_3d_gizmo_center_screen(draw_rect)
        metrics = self._canvas_3d_gizmo_metrics(draw_rect)
        if center is None or metrics is None:
            return
        cx, cy = int(center[0]), int(center[1])
        radius, x_ry, y_rx = metrics
        ring_rect_z = pygame.Rect(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))
        ring_rect_x = pygame.Rect(int(cx - radius), int(cy - x_ry), int(radius * 2), int(x_ry * 2))
        ring_rect_y = pygame.Rect(int(cx - y_rx), int(cy - radius), int(y_rx * 2), int(radius * 2))
        colors = {"x": (236, 96, 96), "y": (94, 208, 118), "z": (232, 232, 238)}
        widths = {"x": 1, "y": 1, "z": 1}
        if self.canvas_sel_3d_axis in widths:
            widths[self.canvas_sel_3d_axis] = 2
        pygame.draw.ellipse(screen, colors["z"], ring_rect_z, widths["z"])
        pygame.draw.ellipse(screen, colors["x"], ring_rect_x, widths["x"])
        pygame.draw.ellipse(screen, colors["y"], ring_rect_y, widths["y"])
        pygame.draw.circle(screen, (246, 246, 250), (cx, cy), 3)

    def _draw_scene_board(self, screen: pygame.Surface, font: pygame.font.Font, small: pygame.font.Font) -> None:
        self._draw_shadowed_panel(screen, self.board_rect, (30, 30, 34), (84, 84, 90), radius=0)
        toolbar = self._scene_toolbar_rect()
        viewport = self._scene_viewport_rect()
        pygame.draw.rect(screen, (45, 45, 50), toolbar)
        pygame.draw.rect(screen, (70, 70, 76), toolbar, 1)
        title = f"{self.active_scene.name}"
        meta = f"{self.active_scene.board_width} x {self.active_scene.board_height}px"
        zoom_text = f"Zoom {int(self.zoom * 100)}%"
        screen.blit(font.render(title, True, (236, 236, 240)), (toolbar.x + 8, toolbar.y + 6))
        screen.blit(small.render(meta, True, (180, 180, 186)), (toolbar.x + 132, toolbar.y + 9))
        screen.blit(small.render(zoom_text, True, (180, 180, 186)), (toolbar.right - 130, toolbar.y + 9))

        focus_rect = self._scene_focus_toggle_rect()
        active = self.scene_focus_mode
        pygame.draw.rect(screen, (50, 80, 130) if active else (40, 40, 48), focus_rect)
        pygame.draw.rect(screen, (100, 150, 220) if active else (72, 72, 82), focus_rect, 1)
        inner = focus_rect.inflate(-10, -10)
        pygame.draw.rect(screen, (220, 230, 242) if active else (170, 170, 180), inner, 1)

        self._clamp_camera()
        _, origin_x, origin_y = self._scene_world_origin_on_screen()
        scene_x = int(origin_x)
        scene_y = int(origin_y)
        scene_w = max(1, int(self.active_scene.board_width * self.zoom))
        scene_h = max(1, int(self.active_scene.board_height * self.zoom))
        scene_rect = pygame.Rect(scene_x, scene_y, scene_w, scene_h)

        pygame.draw.rect(screen, (24, 24, 28), viewport)
        previous_clip = screen.get_clip()
        screen.set_clip(viewport)
        tile_size = max(8, int(32 * self.zoom))
        self._draw_checkerboard(screen, scene_rect, tile=tile_size)
        pygame.draw.rect(screen, (150, 150, 156), scene_rect, 1)

        for sprite in self.active_scene.sprites:
            sprite_rect = self._sprite_screen_rect(sprite)
            transformed = self._sprite_screen_surface(sprite, pygame.time.get_ticks())
            if transformed is None:
                pygame.draw.rect(screen, (90, 60, 62), sprite_rect)
                pygame.draw.rect(screen, (180, 130, 136), sprite_rect, 1)
            else:
                transformed_rect = transformed.get_rect(center=sprite_rect.center)
                screen.blit(transformed, transformed_rect)

            if sprite.sprite_id in self.selected_sprite_ids or (
                not self.selected_sprite_ids and sprite.sprite_id == self.selected_sprite_id
            ):
                outline = sprite_rect.inflate(6, 6)
                pygame.draw.rect(screen, (224, 224, 228), outline, 1)

        selection_rect = self._selection_screen_rect()
        if selection_rect is not None:
            pygame.draw.rect(screen, (232, 232, 236), selection_rect, 1)
            for handle_rect in self._selected_resize_handles().values():
                pygame.draw.rect(screen, (242, 242, 246), handle_rect)
                pygame.draw.rect(screen, (70, 70, 76), handle_rect, 1)
            self._draw_rotation_gizmo(screen)

        if self.marquee_selecting:
            marquee = self._marquee_rect()
            pygame.draw.rect(screen, (210, 210, 214), marquee, 1)
            if marquee.width > 0 and marquee.height > 0:
                fill = pygame.Surface((marquee.width, marquee.height), pygame.SRCALPHA)
                fill.fill((210, 210, 214, 30))
                screen.blit(fill, marquee.topleft)

        screen.set_clip(previous_clip)
        pygame.draw.rect(screen, (68, 68, 74), viewport, 1)

    def _draw_canvas_workspace(self, screen: pygame.Surface, font: pygame.font.Font, small: pygame.font.Font) -> None:
        panel = self._canvas_workspace_panel_rect()
        self._draw_shadowed_panel(screen, panel, (22, 22, 26), (60, 60, 66), radius=0)

        # ── Header bar ──────────────────────────────────────────────
        if self.canvas_focus_mode:
            focus_bar = pygame.Rect(panel.x, panel.y, panel.width, 30)
            pygame.draw.rect(screen, (30, 30, 36), focus_bar)
            pygame.draw.rect(screen, (54, 54, 62), focus_bar, 1)
            if self.canvas_surface is not None:
                sw, sh = self.canvas_surface.get_size()
                meta = f"{sw}x{sh}  |  {int(self.canvas_zoom * 100)}%"
            else:
                meta = "Canvas"
            screen.blit(small.render(meta, True, (180, 210, 255)), (focus_bar.x + 10, focus_bar.y + 8))
            toggle_rect = self._canvas_focus_toggle_rect(panel)
            pygame.draw.rect(screen, (40, 40, 48), toggle_rect)
            pygame.draw.rect(screen, (90, 140, 220), toggle_rect, 1)
            inset = toggle_rect.inflate(-10, -10)
            pygame.draw.rect(screen, (220, 230, 242), inset, 1)
        else:
            header = pygame.Rect(panel.x, panel.y, panel.width, 44)
            pygame.draw.rect(screen, (30, 30, 36), header)
            pygame.draw.rect(screen, (54, 54, 62), header, 1)
            screen.blit(font.render("Canvas", True, (220, 220, 226)), (header.x + 12, header.y + 6))
            for idx, rect in self._canvas_header_tab_rects(panel):
                active = idx == self.canvas_tab_idx
                fill = (48, 76, 126) if active else (38, 38, 46)
                border = (100, 150, 220) if active else (72, 72, 82)
                pygame.draw.rect(screen, fill, rect)
                pygame.draw.rect(screen, border, rect, 1)
                label = self._canvas_tab_name(idx)
                txt = small.render(label, True, (220, 232, 248) if active else (188, 194, 208))
                text_rect = txt.get_rect(center=rect.center)
                if text_rect.width > rect.width - 10:
                    text_rect.x = rect.x + 6
                    text_rect.centery = rect.centery
                screen.blit(txt, text_rect)

            active_tool_label = dict(self._CANVAS_TOOLS).get(self.canvas_tool, self.canvas_tool.title())
            tool_label = f"{active_tool_label}  {self.canvas_brush_size}px"
            tl = small.render(tool_label, True, (180, 210, 255))
            screen.blit(tl, (header.right - tl.get_width() - 12, header.y + 14))

            # ── In-canvas toolbar (New / Save / Fit / Onion / BG) ───────
            toolbar = self._canvas_toolbar_rect(panel)
            pygame.draw.rect(screen, (28, 28, 34), toolbar)
            pygame.draw.rect(screen, (50, 50, 58), toolbar, 1)
            toggle_labels = {
                "new": "New", "fit": "Fit",
                "onion": ("Onion●" if self.canvas_onion_skin else "Onion"),
                "bgmode": ("Light" if self.canvas_bg_light else "Dark"),
                "delete": "Delete",
            }
            for name, rect in self._canvas_workspace_toolbar_buttons(panel).items():
                if name == "focus":
                    fill = (50, 80, 130) if self.canvas_focus_mode else (40, 40, 48)
                    border = (100, 150, 220) if self.canvas_focus_mode else (72, 72, 82)
                    pygame.draw.rect(screen, fill, rect)
                    pygame.draw.rect(screen, border, rect, 1)
                    inset = rect.inflate(-10, -10)
                    pygame.draw.rect(screen, (220, 230, 242), inset, 1)
                    continue
                tog_on = (name == "onion" and self.canvas_onion_skin) or (name == "bgmode" and self.canvas_bg_light)
                destructive = name == "delete"
                fill = (88, 52, 52) if destructive else ((50, 80, 130) if tog_on else (40, 40, 48))
                border = (160, 92, 92) if destructive else ((100, 150, 220) if tog_on else (72, 72, 82))
                pygame.draw.rect(screen, fill, rect)
                pygame.draw.rect(screen, border, rect, 1)
                ls = small.render(toggle_labels.get(name, name), True,
                                  (255, 228, 228) if destructive else ((180, 220, 255) if tog_on else (220, 220, 230)))
                screen.blit(ls, ls.get_rect(center=rect.center))

        # ── Canvas view area ─────────────────────────────────────────
        view = self._canvas_view_rect(panel)
        pygame.draw.rect(screen, (18, 18, 22), view)
        pygame.draw.rect(screen, (44, 44, 52), view, 1)

        if self.canvas_surface is None:
            lines = [
                "No canvas open.",
                'Click "New" to create a blank canvas,',
                "or select a PNG/JPG/BMP from the asset browser below.",
            ]
            cy = view.centery - len(lines) * 13
            for line in lines:
                ls = small.render(line, True, (90, 90, 100))
                screen.blit(ls, ls.get_rect(centerx=view.centerx, y=cy))
                cy += 26
            return

        draw_rect = self._canvas_draw_rect(view, self.canvas_surface)
        prev_clip = screen.get_clip()
        screen.set_clip(view)
        sw, sh = self.canvas_surface.get_size()
        visible_patch = self._canvas_visible_source_dest_rects(draw_rect, view, (sw, sh))
        visible_px_bounds = self._canvas_visible_pixel_bounds(draw_rect, view, (sw, sh))

        # ── Background: build a checker at canvas resolution once, scale per frame ──
        if visible_patch is not None:
            src_rect, dst_rect = visible_patch
            base_key = (sw, sh, self.canvas_bg_light)
            if self._canvas_checker_base_key != base_key:
                if self.canvas_bg_light:
                    ca, cb = (255, 255, 255), (210, 210, 215)
                else:
                    ca, cb = (68, 68, 72), (48, 48, 52)
                base = pygame.Surface((sw, sh))
                base.fill(ca)
                row_even = pygame.Surface((sw, 1))
                row_even.fill(ca)
                for x in range(1, sw, 2):
                    row_even.fill(cb, (x, 0, 1, 1))
                row_odd = pygame.Surface((sw, 1))
                row_odd.fill(ca)
                for x in range(0, sw, 2):
                    row_odd.fill(cb, (x, 0, 1, 1))
                for y in range(sh):
                    base.blit(row_odd if (y % 2) else row_even, (0, y))
                self._canvas_checker_base = base
                self._canvas_checker_base_key = base_key
                self._canvas_checker_cache = None
                self._canvas_checker_surf = None
            cache_key = (
                sw,
                sh,
                src_rect.x,
                src_rect.y,
                src_rect.width,
                src_rect.height,
                dst_rect.width,
                dst_rect.height,
                self.canvas_bg_light,
            )
            if self._canvas_checker_cache != cache_key and self._canvas_checker_base is not None:
                patch = self._canvas_checker_base.subsurface(src_rect)
                self._canvas_checker_surf = pygame.transform.scale(
                    patch, (dst_rect.width, dst_rect.height)
                )
                self._canvas_checker_cache = cache_key
            if self._canvas_checker_surf is not None:
                screen.blit(self._canvas_checker_surf, dst_rect.topleft)

        # ── Onion skin: previous frame ghost ────────────────────────
        if self.canvas_onion_skin and self.canvas_doc.frame_idx > 0:
            onion = self._canvas_scaled_visible_frame_surface(
                self.canvas_doc.frame_idx - 1,
                draw_rect,
                view,
                alpha=60,
            )
            if onion is not None:
                onion_surf, _, onion_dst = onion
                screen.blit(onion_surf, onion_dst.topleft)
        if self.canvas_onion_skin and self.canvas_doc.frame_idx < len(self.canvas_doc.frames) - 1:
            onion_n = self._canvas_scaled_visible_frame_surface(
                self.canvas_doc.frame_idx + 1,
                draw_rect,
                view,
                alpha=40,
            )
            if onion_n is not None:
                onion_surf_n, _, onion_dst_n = onion_n
                screen.blit(onion_surf_n, onion_dst_n.topleft)

        # ── Composited frame (all visible layers) ────────────────────
        scaled = self._canvas_scaled_visible_frame_surface(
            self.canvas_doc.frame_idx,
            draw_rect,
            view,
        )
        if scaled is not None:
            scaled_surf, _, scaled_dst = scaled
            screen.blit(scaled_surf, scaled_dst.topleft)

        # Border around canvas
        pygame.draw.rect(screen, (70, 110, 170), draw_rect, 1)

        # ── Pixel grid when zoomed in enough ─────────────────────────
        if self.canvas_zoom >= 6 and visible_patch is not None:
            src_rect, dst_rect = visible_patch
            grid_key = (
                sw,
                sh,
                src_rect.x,
                src_rect.y,
                src_rect.width,
                src_rect.height,
                dst_rect.width,
                dst_rect.height,
                int(round(self.canvas_zoom * 100)),
            )
            if self._canvas_grid_cache != grid_key:
                grid = pygame.Surface((dst_rect.width, dst_rect.height), pygame.SRCALPHA)
                for gx in range(src_rect.x + 1, src_rect.right):
                    sx = int(round((gx - src_rect.x) * dst_rect.width / src_rect.width))
                    pygame.draw.line(grid, (255, 255, 255, 22), (sx, 0), (sx, dst_rect.height))
                for gy in range(src_rect.y + 1, src_rect.bottom):
                    sy = int(round((gy - src_rect.y) * dst_rect.height / src_rect.height))
                    pygame.draw.line(grid, (255, 255, 255, 22), (0, sy), (dst_rect.width, sy))
                self._canvas_grid_surf = grid
                self._canvas_grid_cache = grid_key
            if self._canvas_grid_surf is not None:
                screen.blit(self._canvas_grid_surf, dst_rect.topleft)

        # ── Vanishing point crosshair ─────────────────────────────────
        if self.canvas_tool == "vpoint" and self.canvas_vp is not None:
            vpx = draw_rect.x + int(self.canvas_vp[0] * self.canvas_zoom)
            vpy = draw_rect.y + int(self.canvas_vp[1] * self.canvas_zoom)
            pygame.draw.line(screen, (255, 80, 80), (vpx - 8, vpy), (vpx + 8, vpy), 1)
            pygame.draw.line(screen, (255, 80, 80), (vpx, vpy - 8), (vpx, vpy + 8), 1)
            pygame.draw.circle(screen, (255, 80, 80), (vpx, vpy), 4, 1)

        # ── Selection highlight ──────────────────────────────────────
        if self.canvas_selection_pixels and not self.canvas_sel_transform and visible_px_bounds is not None:
            pzw = max(1, int(self.canvas_zoom))
            pzh = max(1, int(self.canvas_zoom))
            min_vx, min_vy, max_vx, max_vy = visible_px_bounds
            for px, py in self.canvas_selection_pixels:
                if px < min_vx or px > max_vx or py < min_vy or py > max_vy:
                    continue
                sx = int(px * self.canvas_zoom)
                sy = int(py * self.canvas_zoom)
                pygame.draw.rect(screen, (80, 140, 255, 80), (draw_rect.x + sx, draw_rect.y + sy, pzw, pzh))
                pygame.draw.rect(screen, (120, 180, 255, 180), (draw_rect.x + sx, draw_rect.y + sy, pzw, pzh), 1)

            sel_box = self._canvas_selection_screen_rect(draw_rect)
            if sel_box is not None:
                pygame.draw.rect(screen, (214, 226, 255), sel_box, 2)
                for handle_rect in self._canvas_selection_handle_rects(draw_rect).values():
                    pygame.draw.ellipse(screen, (248, 248, 250), handle_rect)
                    pygame.draw.ellipse(screen, (40, 40, 46), handle_rect, 2)

        # ── Paste preview ────────────────────────────────────────────
        if self.canvas_paste_active and self.canvas_paste_pixels and visible_px_bounds is not None:
            ox, oy = self.canvas_paste_origin
            pzw = max(1, int(self.canvas_zoom))
            pzh = max(1, int(self.canvas_zoom))
            min_vx, min_vy, max_vx, max_vy = visible_px_bounds
            for (px, py), color in self.canvas_paste_pixels.items():
                tx = px + ox
                ty = py + oy
                if tx < min_vx or tx > max_vx or ty < min_vy or ty > max_vy:
                    continue
                sx = int(tx * self.canvas_zoom)
                sy = int(ty * self.canvas_zoom)
                pygame.draw.rect(screen, (*color[:3], 180), (draw_rect.x + sx, draw_rect.y + sy, pzw, pzh))
            # Bounding box
            if self.canvas_paste_pixels:
                min_px = min(p[0] for p in self.canvas_paste_pixels) + ox
                min_py = min(p[1] for p in self.canvas_paste_pixels) + oy
                max_px = max(p[0] for p in self.canvas_paste_pixels) + ox
                max_py = max(p[1] for p in self.canvas_paste_pixels) + oy
                bx = draw_rect.x + int(min_px * self.canvas_zoom)
                by = draw_rect.y + int(min_py * self.canvas_zoom)
                bw = int((max_px - min_px + 1) * self.canvas_zoom)
                bh = int((max_py - min_py + 1) * self.canvas_zoom)
                pygame.draw.rect(screen, (255, 220, 80), (bx, by, bw, bh), 1)

        # ── Lasso path while drawing ─────────────────────────────────
        if self.canvas_lasso_active and len(self.canvas_lasso_pixels) > 1:
            # canvas_lasso_pixels are already screen-space coords
            pygame.draw.lines(screen, (120, 200, 255), False, self.canvas_lasso_pixels, 1)
        if self.canvas_rect_select_active and self.canvas_rect_select_start and self.canvas_rect_select_end:
            x0, y0 = self.canvas_rect_select_start
            x1, y1 = self.canvas_rect_select_end
            left = draw_rect.x + int(min(x0, x1) * self.canvas_zoom)
            top = draw_rect.y + int(min(y0, y1) * self.canvas_zoom)
            right = draw_rect.x + int((max(x0, x1) + 1) * self.canvas_zoom)
            bottom = draw_rect.y + int((max(y0, y1) + 1) * self.canvas_zoom)
            pygame.draw.rect(screen, (120, 200, 255), (left, top, max(1, right - left), max(1, bottom - top)), 1)

        # ── Shape / VP preview ────────────────────────────────────────
        if self.canvas_preview_start:
            s = self.canvas_preview_start
            zoom = self.canvas_zoom
            def to_screen(p: tuple[int, int]) -> tuple[int, int]:
                return (draw_rect.x + int(p[0] * zoom), draw_rect.y + int(p[1] * zoom))
            ss = to_screen(s)
            pcol = self.canvas_color[:3]
            w = max(1, int(self.canvas_brush_size * zoom))
            if self.canvas_preview_end:
                e = self.canvas_preview_end
                se = to_screen(e)
                if self.canvas_tool == "line":
                    preview_pixels = self._canvas_line_pixels(s, e, max(1, self.canvas_brush_size))
                    pw = max(1, int(zoom))
                    ph = max(1, int(zoom))
                    for px, py in preview_pixels:
                        if visible_px_bounds is not None:
                            min_vx, min_vy, max_vx, max_vy = visible_px_bounds
                            if px < min_vx or px > max_vx or py < min_vy or py > max_vy:
                                continue
                        sx = draw_rect.x + int(px * zoom)
                        sy = draw_rect.y + int(py * zoom)
                        pygame.draw.rect(screen, pcol, (sx, sy, pw, ph))
                elif self.canvas_tool == "circle":
                    rx = abs(se[0] - ss[0])
                    ry = abs(se[1] - ss[1])
                    cr = pygame.Rect(ss[0] - rx, ss[1] - ry, rx * 2, ry * 2)
                    if cr.width > 0 and cr.height > 0:
                        pygame.draw.ellipse(screen, pcol, cr, 0 if self.canvas_fill_shapes else w)
                elif self.canvas_tool == "square":
                    rx0, ry0 = min(ss[0], se[0]), min(ss[1], se[1])
                    rx1, ry1 = max(ss[0], se[0]), max(ss[1], se[1])
                    r = pygame.Rect(rx0, ry0, max(1, rx1 - rx0), max(1, ry1 - ry0))
                    pygame.draw.rect(screen, pcol, r, 0 if self.canvas_fill_shapes else w)
                elif self.canvas_tool == "vpoint" and self.canvas_vp:
                    # Preview: dashed line from start through VP to canvas edge
                    vpx_s = draw_rect.x + int(self.canvas_vp[0] * zoom)
                    vpy_s = draw_rect.y + int(self.canvas_vp[1] * zoom)
                    pygame.draw.line(screen, (255, 100, 80), ss, (vpx_s, vpy_s), 1)

        screen.set_clip(prev_clip)

        # ── Selection transform gizmo overlay ────────────────────
        if self.canvas_sel_transform and self.canvas_sel_lift:
            import math
            zoom = self.canvas_zoom
            if self.canvas_sel_surface is not None:
                if self.canvas_sel_transform == "move" and self.canvas_sel_base_bbox is not None:
                    min_x, min_y, _, _ = self.canvas_sel_base_bbox
                    ox, oy = self.canvas_sel_offset
                    preview_rect = pygame.Rect(
                        draw_rect.x + int((min_x + ox) * zoom),
                        draw_rect.y + int((min_y + oy) * zoom),
                        max(1, int(self.canvas_sel_surface.get_width() * zoom)),
                        max(1, int(self.canvas_sel_surface.get_height() * zoom)),
                    )
                    preview = self._canvas_scaled_selection_preview("move", preview_rect.size)
                    if preview is not None:
                        screen.blit(preview, preview_rect.topleft)
                elif self.canvas_sel_transform == "scale" and self.canvas_sel_scale_rect is not None:
                    left, top, right, bottom = self.canvas_sel_scale_rect
                    preview_rect = pygame.Rect(
                        draw_rect.x + int(left * zoom),
                        draw_rect.y + int(top * zoom),
                        max(1, int((right - left) * zoom)),
                        max(1, int((bottom - top) * zoom)),
                    )
                    preview = self._canvas_scaled_selection_preview("scale", preview_rect.size)
                    if preview is not None:
                        screen.blit(preview, preview_rect.topleft)
                elif self.canvas_sel_transform == "rotate" and self.canvas_sel_base_bbox is not None:
                    rotated = self._canvas_rotated_selection_preview(self.canvas_sel_angle, zoom)
                    if rotated is not None:
                        min_x, min_y, max_x, max_y = self.canvas_sel_base_bbox
                        center_x = draw_rect.x + int(round(((min_x + max_x + 1) / 2.0) * zoom))
                        center_y = draw_rect.y + int(round(((min_y + max_y + 1) / 2.0) * zoom))
                        preview_rect = rotated.get_rect(center=(center_x, center_y))
                        screen.blit(rotated, preview_rect.topleft)
                elif self.canvas_sel_transform == "rotate3d" and self.canvas_sel_base_bbox is not None:
                    projected = self._canvas_3d_selection_preview()
                    if projected is not None:
                        projected_surface, offset = projected
                        min_x, min_y, max_x, max_y = self.canvas_sel_base_bbox
                        center_x = (min_x + max_x + 1) / 2.0
                        center_y = (min_y + max_y + 1) / 2.0
                        preview_rect = pygame.Rect(
                            draw_rect.x + int(round((center_x + offset[0]) * zoom)),
                            draw_rect.y + int(round((center_y + offset[1]) * zoom)),
                            max(1, int(round(projected_surface.get_width() * zoom))),
                            max(1, int(round(projected_surface.get_height() * zoom))),
                        )
                        preview = pygame.transform.scale(projected_surface, preview_rect.size)
                        screen.blit(preview, preview_rect.topleft)
                else:
                    for (px, py), col in self.canvas_sel_lift.items():
                        bbox = self._canvas_sel_bbox()
                        if bbox:
                            min_x, min_y, max_x, max_y = bbox
                            cxf = (min_x + max_x) / 2.0
                            cyf = (min_y + max_y) / 2.0
                            dx = (px - cxf) * self.canvas_sel_scale
                            dy = (py - cyf) * self.canvas_sel_scale
                            angle_rad = math.radians(self.canvas_sel_angle)
                            cos_a = math.cos(angle_rad)
                            sin_a = math.sin(angle_rad)
                            npx = cxf + dx * cos_a - dy * sin_a
                            npy = cyf + dx * sin_a + dy * cos_a
                            spx = draw_rect.x + int(npx * zoom)
                            spy = draw_rect.y + int(npy * zoom)
                        else:
                            continue
                        pw = max(1, int(zoom))
                        r, g, b, a = col
                        pygame.draw.rect(screen, (r, g, b), (spx, spy, pw, pw))
            # Draw gizmo handles
            bbox2 = self._canvas_sel_bbox()
            if bbox2:
                min_x2, min_y2, max_x2, max_y2 = bbox2
                if self.canvas_sel_transform == "move":
                    ox, oy = self.canvas_sel_offset
                    bsx = draw_rect.x + int((min_x2 + ox) * zoom)
                    bsy = draw_rect.y + int((min_y2 + oy) * zoom)
                    bex = draw_rect.x + int((max_x2 + ox + 1) * zoom)
                    bey = draw_rect.y + int((max_y2 + oy + 1) * zoom)
                    move_box = pygame.Rect(bsx, bsy, max(1, bex - bsx), max(1, bey - bsy))
                    pygame.draw.rect(screen, (214, 226, 255), move_box, 2)
                    for handle_rect in self._canvas_selection_handle_rects(draw_rect).values():
                        pygame.draw.ellipse(screen, (248, 248, 250), handle_rect)
                        pygame.draw.ellipse(screen, (40, 40, 46), handle_rect, 2)
                elif self.canvas_sel_transform == "scale":
                    scale_box = self._canvas_selection_screen_rect(draw_rect)
                    if scale_box is not None:
                        pygame.draw.rect(screen, (255, 220, 120), scale_box, 2)
                        for handle_rect in self._canvas_selection_handle_rects(draw_rect).values():
                            pygame.draw.ellipse(screen, (248, 248, 250), handle_rect)
                            pygame.draw.ellipse(screen, (40, 40, 46), handle_rect, 2)
                elif self.canvas_sel_transform == "rotate":
                    rotate_box = self._canvas_selection_screen_rect(draw_rect)
                    if rotate_box is not None:
                        pygame.draw.rect(screen, (100, 255, 180), rotate_box, 2)
                        handle_rect = self._canvas_rotation_handle_rect(draw_rect)
                        if handle_rect is not None:
                            pygame.draw.line(screen, (100, 255, 180), (rotate_box.centerx, rotate_box.top), handle_rect.center, 1)
                            pygame.draw.ellipse(screen, (248, 248, 250), handle_rect)
                            pygame.draw.ellipse(screen, (40, 80, 56), handle_rect, 2)
                elif self.canvas_sel_transform == "rotate3d":
                    rotate3d_box = self._canvas_3d_selection_screen_rect(draw_rect)
                    if rotate3d_box is not None:
                        pygame.draw.rect(screen, (135, 220, 255), rotate3d_box, 2)
                    self._draw_canvas_3d_rotation_gizmo(screen, draw_rect)
        # ── Resize-tool handles ─────────────────────────────────────
        if self.canvas_tool == "resize" and self.canvas_surface is not None:
            panel2 = self._canvas_workspace_panel_rect()
            view2 = self._canvas_view_rect(panel2)
            dr = self._canvas_draw_rect(view2, self.canvas_surface)
            hs = 8
            for hx, hy in [(dr.right, dr.bottom), (dr.x, dr.bottom),
                           (dr.right, dr.y), (dr.x, dr.y)]:
                pygame.draw.rect(screen, (255, 200, 60), (hx - hs // 2, hy - hs // 2, hs, hs))
                pygame.draw.rect(screen, (220, 160, 20), (hx - hs // 2, hy - hs // 2, hs, hs), 1)

    def _draw_inspector(self, screen: pygame.Surface, font: pygame.font.Font, small: pygame.font.Font) -> None:
        panel = self._canvas_tools_panel_rect() if self.workspace_mode == "canvas" else self._inspector_rect()
        if self.workspace_mode == "canvas":
            self._draw_shadowed_panel(screen, panel, (24, 24, 28), (58, 58, 66), radius=0)
            header = pygame.Rect(panel.x, panel.y, panel.width, 38)
            pygame.draw.rect(screen, (32, 32, 38), header)
            pygame.draw.rect(screen, (56, 56, 64), header, 1)
            screen.blit(font.render("Canvas Tools", True, (216, 216, 224)), (header.x + 8, header.y + 9))

            # ── Tool grid (icon buttons + hover tooltip) ─────────
            hover_tool_name: str | None = None
            for name, rect in self._canvas_toolbar_buttons(panel).items():
                active = self.canvas_tool == name
                hovered = rect.collidepoint(self.drag_pos)
                transform_active = (name == "select" and self.canvas_sel_transform is not None)
                fill = (52, 90, 155) if (active or transform_active) else (48, 60, 80) if hovered else (38, 38, 46)
                border = (90, 140, 220) if (active or transform_active) else (100, 120, 160) if hovered else (64, 64, 74)
                pygame.draw.rect(screen, fill, rect)
                pygame.draw.rect(screen, border, rect, 1)
                icon_col = (220, 235, 255) if (active or transform_active) else (190, 190, 205)
                self._draw_tool_icon(screen, name, rect, icon_col)
                if hovered:
                    hover_tool_name = dict(self._CANVAS_TOOLS).get(name, name.title())
            # Tooltip for hovered tool
            if hover_tool_name:
                tip_text = font.render(hover_tool_name, True, (240, 240, 248))
                mx, my = self.drag_pos
                tr = pygame.Rect(mx + 14, my - 6, tip_text.get_width() + 10, tip_text.get_height() + 6)
                # Keep tooltip within right panel
                if tr.right > panel.right - 2:
                    tr.x = mx - tr.width - 6
                pygame.draw.rect(screen, (22, 28, 48), tr)
                pygame.draw.rect(screen, (80, 100, 160), tr, 1)
                screen.blit(tip_text, (tr.x + 5, tr.y + 3))
            # Show active transform mode next to Select tool label
            if self.canvas_sel_transform and self.canvas_selection_pixels:
                sel_r = self._canvas_toolbar_buttons(panel).get("select")
                if sel_r:
                    tm_lbl = small.render(self.canvas_sel_transform[0].upper(), True, (255, 200, 80))
                    screen.blit(tm_lbl, (sel_r.right + 2, sel_r.y + 1))

            # ── Brush size ──────────────────────────────────────
            minus, field, plus = self._canvas_size_input_rects(panel)
            screen.blit(small.render("Size", True, (110, 110, 122)), (panel.x + 8, minus.y - 14))
            for btn, lbl in [(minus, "-"), (plus, "+")]:
                pygame.draw.rect(screen, (46, 46, 56), btn)
                pygame.draw.rect(screen, (80, 80, 92), btn, 1)
                ls = small.render(lbl, True, (200, 200, 212))
                screen.blit(ls, ls.get_rect(center=btn.center))
            pygame.draw.rect(screen, (20, 20, 24), field)
            pygame.draw.rect(screen, (100, 140, 210) if self.canvas_brush_size_focus else (72, 72, 84), field, 1)
            disp = input_display_text(self.canvas_brush_size_input, self.canvas_brush_size_focus, "1")
            ls = small.render(disp + "px", True, (210, 220, 240))
            screen.blit(ls, ls.get_rect(center=field.center))

            # ── Fill toggle (for circle/square) ────────────────
            fill_rect = self._canvas_fill_toggle_rect(panel)
            fill_active = self.canvas_fill_shapes
            pygame.draw.rect(screen, (38, 38, 46), fill_rect)
            pygame.draw.rect(screen, (72, 72, 84), fill_rect, 1)
            cb = pygame.Rect(fill_rect.x + 4, fill_rect.centery - 7, 14, 14)
            pygame.draw.rect(screen, (20, 20, 24), cb)
            pygame.draw.rect(screen, (90, 140, 210) if fill_active else (72, 72, 84), cb, 1)
            if fill_active:
                pygame.draw.line(screen, (100, 180, 255), (cb.x + 2, cb.centery), (cb.centerx, cb.bottom - 3), 2)
                pygame.draw.line(screen, (100, 180, 255), (cb.centerx, cb.bottom - 3), (cb.right - 2, cb.y + 2), 2)
            ls = small.render("Fill shapes", True, (180, 180, 195))
            screen.blit(ls, (fill_rect.x + 22, fill_rect.y + 3))

            # ── Mirror toggles ──────────────────────────────────
            mh_rect, mv_rect = self._canvas_mirror_toggle_rects(panel)
            for btn, label, active in [
                (mh_rect, "Mir H", self.canvas_mirror_h),
                (mv_rect, "Mir V", self.canvas_mirror_v),
            ]:
                fill = (40, 80, 120) if active else (38, 38, 46)
                border = (80, 160, 230) if active else (64, 64, 74)
                pygame.draw.rect(screen, fill, btn)
                pygame.draw.rect(screen, border, btn, 1)
                ls = small.render(label, True, (160, 220, 255) if active else (160, 160, 175))
                screen.blit(ls, ls.get_rect(center=btn.center))

            # ── Blend strength ──────────────────────────────────
            bm, bf, bp = self._canvas_blend_input_rects(panel)
            screen.blit(small.render("Blend%", True, (110, 110, 122)), (panel.x + 8, bm.y - 14))
            for btn, lbl in [(bm, "-"), (bp, "+")]:
                pygame.draw.rect(screen, (46, 46, 56), btn)
                pygame.draw.rect(screen, (80, 80, 92), btn, 1)
                ls = small.render(lbl, True, (200, 200, 212))
                screen.blit(ls, ls.get_rect(center=btn.center))
            pygame.draw.rect(screen, (20, 20, 24), bf)
            pygame.draw.rect(screen, (100, 140, 210) if self.canvas_blend_focus else (72, 72, 84), bf, 1)
            bdisp = input_display_text(self.canvas_blend_input, self.canvas_blend_focus, "50")
            ls = small.render(bdisp + "%", True, (210, 220, 240))
            screen.blit(ls, ls.get_rect(center=bf.center))

            # ── Color Key input (R,G,B to wipe from current layer) ─
            ck = self._canvas_colorkey_input_rect(panel)
            is_colorkey_tool = self.canvas_tool == "colorkey"
            label = "Remove R,G,B (Enter)" if is_colorkey_tool else "Remove R,G,B"
            label_col = (200, 220, 240) if is_colorkey_tool else (110, 110, 122)
            screen.blit(small.render(label, True, label_col), (panel.x + 8, ck.y - 14))
            pygame.draw.rect(screen, (20, 20, 24), ck)
            ck_border = (
                (255, 180, 90) if (is_colorkey_tool and self.canvas_colorkey_focus)
                else (100, 140, 210) if self.canvas_colorkey_focus
                else (72, 72, 84)
            )
            pygame.draw.rect(screen, ck_border, ck, 1)
            ck_disp = input_display_text(
                self.canvas_colorkey_input,
                self.canvas_colorkey_focus,
                "255,255,255",
            )
            ls = small.render(ck_disp, True, (210, 220, 240) if is_colorkey_tool else (140, 140, 152))
            screen.blit(ls, ls.get_rect(midleft=(ck.x + 6, ck.centery)))
            # Preview swatch on the right edge so the user can confirm the color.
            parsed = self._parse_colorkey_input(self.canvas_colorkey_input)
            if parsed is not None:
                pr, pg, pb = parsed
                sw_rect = pygame.Rect(ck.right - 22, ck.y + 4, 16, ck.height - 8)
                pygame.draw.rect(screen, (pr, pg, pb), sw_rect)
                pygame.draw.rect(screen, (40, 40, 46), sw_rect, 1)

            # ── Color picker launcher ───────────────────────────
            color_rect = self._canvas_color_button_rect(panel)
            screen.blit(small.render("Color", True, (110, 110, 122)), (panel.x + 8, color_rect.y - 14))
            pygame.draw.rect(screen, (28, 28, 34), color_rect)
            pygame.draw.rect(screen, (72, 72, 84), color_rect, 1)
            preview_rect = pygame.Rect(color_rect.x + 8, color_rect.y + 7, 28, 28)
            pygame.draw.rect(screen, self.canvas_color[:3], preview_rect)
            pygame.draw.rect(screen, (100, 140, 210), preview_rect, 1)
            screen.blit(small.render(self._canvas_color_hex(), True, (214, 224, 244)), (preview_rect.right + 10, color_rect.y + 7))
            hint = "Open wheel picker"
            screen.blit(small.render(hint, True, (136, 150, 176)), (preview_rect.right + 10, color_rect.y + 22))

            quick_palette = self._canvas_quick_palette()
            for idx, swatch_rect in enumerate(self._canvas_quick_palette_rects(panel)):
                swatch_color = quick_palette[idx] if idx < len(quick_palette) else CANVAS_PALETTE[idx % len(CANVAS_PALETTE)]
                active = swatch_color == self.canvas_color
                pygame.draw.rect(screen, swatch_color[:3], swatch_rect)
                pygame.draw.rect(screen, (110, 170, 240) if active else (72, 72, 84), swatch_rect, 2 if active else 1)
                slot_label = small.render(str(idx + 1), True, (238, 242, 250))
                screen.blit(slot_label, (swatch_rect.x + 6, swatch_rect.y + 3))

            # ── Selection transform buttons ──────────────────────
            has_sel = bool(self.canvas_selection_pixels)
            action_labels = {
                "rot_ccw": "↺90", "rot_cw": "↻90",
                "flip_h": "FlipH", "flip_v": "FlipV",
                "scale_dn": "Sc-", "scale_up": "Sc+",
                "bright_dn": "Br-", "bright_up": "Br+",
            }
            for key, rect in self._canvas_selection_action_rects(panel).items():
                active = has_sel
                fill = (42, 60, 90) if active else (30, 30, 36)
                border = (80, 120, 180) if active else (50, 50, 58)
                pygame.draw.rect(screen, fill, rect)
                pygame.draw.rect(screen, border, rect, 1)
                ls = small.render(action_labels.get(key, key), True,
                                  (180, 210, 255) if active else (80, 80, 90))
                screen.blit(ls, ls.get_rect(center=rect.center))

            # ── Extra info below action buttons (only if they fit) ───────
            action_rects = self._canvas_selection_action_rects(panel)
            info_y = max((r.bottom for r in action_rects.values()), default=panel.y + 400) + 8
            if self.canvas_tool == "vpoint" and info_y + 16 <= panel.bottom:
                vp_str = f"VP: {self.canvas_vp}" if self.canvas_vp else "VP: click to place"
                vt = small.render(vp_str, True, (255, 120, 90))
                screen.blit(vt, (panel.x + 8, info_y))
                info_y += 18
            if self.canvas_selection_pixels and info_y + 16 <= panel.bottom:
                sel_lbl = small.render(f"Sel: {len(self.canvas_selection_pixels)}px", True, (160, 210, 255))
                screen.blit(sel_lbl, (panel.x + 8, info_y))
                info_y += 18
            if self.canvas_doc.asset_rel is not None and info_y + 16 <= panel.bottom:
                nt = small.render(Path(self.canvas_doc.asset_rel).name[:22], True, (110, 140, 180))
                screen.blit(nt, (panel.x + 8, info_y))
            left_handle = self._canvas_inspector_left_handle_rect()
            top_handle = self._canvas_inspector_top_handle_rect()
            pygame.draw.rect(screen, (58, 58, 66), left_handle)
            pygame.draw.rect(screen, (92, 92, 104), left_handle, 1)
            pygame.draw.rect(screen, (58, 58, 66), top_handle)
            pygame.draw.rect(screen, (92, 92, 104), top_handle, 1)
            return

        self._draw_shadowed_panel(screen, panel, (30, 30, 34), (84, 84, 90), radius=0)
        header = pygame.Rect(panel.x, panel.y, panel.width, 30)
        pygame.draw.rect(screen, (45, 45, 50), header)
        pygame.draw.rect(screen, (70, 70, 76), header, 1)
        screen.blit(font.render("Inspector", True, (236, 236, 240)), (header.x + 8, header.y + 6))
        y = panel.y + 40
        selected = self._selected_sprite()
        if selected is None:
            screen.blit(small.render("No asset selected", True, (182, 182, 188)), (panel.x + 8, y))
            return
        selected_count = len(self._selected_sprites())
        lines = [
            f"Selection: {selected_count} asset(s)",
            f"Primary: {Path(selected.asset_path).name}",
            f"Pos: {int(selected.x)}, {int(selected.y)}",
            f"Size: {selected.width} x {selected.height}",
            f"Rotation: X {int(selected.rotation_x)} / Y {int(selected.rotation_y)} / Z {int(selected.rotation_z)}",
            "Drag in viewport to move selection",
            "Drag corners to resize as group",
            "R: toggle X/Y/Z ring gizmo",
            "Drag ring to rotate active axis",
            "D then drag: duplicate selected asset",
            "V paste, M merge",
            "Ctrl+E export scene PNG",
            "Delete to remove",
        ]
        for line in lines:
            screen.blit(small.render(line, True, (188, 188, 194)), (panel.x + 8, y))
            y += 22

    def _draw_asset_browser(self, screen: pygame.Surface, font: pygame.font.Font, small: pygame.font.Font) -> None:
        # In canvas mode the bottom panel shows frames+layers unless the user opened the asset browser
        if self.workspace_mode == "canvas" and not self.canvas_assets_open:
            self._draw_canvas_bottom_panel(screen, font, small)
            return

        panel = self._asset_panel_rect()
        self._draw_shadowed_panel(screen, panel, (28, 28, 32), (86, 86, 92), radius=0)

        current_rel = self.asset_library.current_dir.relative_to(self.asset_root).as_posix()
        current_label = "assets/" if current_rel == "." else f"assets/{current_rel}/"
        header = pygame.Rect(panel.x, panel.y, panel.width, 28)
        pygame.draw.rect(screen, (44, 44, 48), header)
        pygame.draw.rect(screen, (70, 70, 76), header, 1)
        screen.blit(font.render("Assets", True, (236, 236, 240)), (panel.x + 8, panel.y + 4))

        # Collapse toggle button
        collapse_rect = self._asset_collapse_button_rect()
        pygame.draw.rect(screen, (56, 56, 62), collapse_rect)
        pygame.draw.rect(screen, (100, 100, 106), collapse_rect, 1)
        arrow = "▲ Show" if self.asset_panel_collapsed else "▼ Hide"
        ct = small.render(arrow, True, (210, 210, 216))
        screen.blit(ct, ct.get_rect(center=collapse_rect.center))

        if self.asset_panel_collapsed:
            return

        screen.blit(small.render(current_label, True, (184, 184, 190)), (panel.x + 8, panel.y + 34))
        page_label = f"Page {self.asset_library.page + 1}/{self._max_asset_page() + 1}"
        screen.blit(small.render(page_label, True, (176, 176, 182)), (panel.x + 150, panel.y + 34))
        tip = "Drop PNGs or GIFs onto the window to import them into the open folder."
        screen.blit(small.render(tip, True, (172, 172, 178)), (panel.x + 8, panel.y + 52))

        handle = self._asset_resize_handle_rect()
        pygame.draw.rect(screen, (58, 58, 62), handle)
        grip = pygame.Rect(handle.centerx - 18, handle.centery - 2, 36, 4)
        pygame.draw.rect(screen, (148, 148, 154), grip)

        for name, rect in self._toolbar_buttons().items():
            pygame.draw.rect(screen, (50, 50, 56), rect)
            pygame.draw.rect(screen, (124, 124, 130), rect, 1)
            label = {
                "up": "Up",
                "prev": "Prev",
                "next": "Next",
                "import": "Import",
                "delete": "Delete",
                "new_folder": "New Folder",
                "refresh": "Refresh",
            }[name]
            text = small.render(label, True, (236, 236, 240))
            screen.blit(text, text.get_rect(center=rect.center))

        entries = self._visible_asset_entries()
        if not entries:
            empty = "This folder is empty. Create folders here or drop a PNG or GIF into the window."
            screen.blit(small.render(empty, True, (188, 188, 194)), (panel.x + 18, panel.y + 104))
            return

        for entry, rect in entries:
            frame = pygame.Rect(rect.x, rect.y, rect.width, rect.height)
            selected = entry.rel_path == self.selected_asset_rel
            pygame.draw.rect(screen, (54, 72, 108) if selected else (42, 42, 48), frame)
            pygame.draw.rect(screen, (140, 176, 232) if selected else (126, 126, 132), frame, 1)
            screen.blit(entry.preview, (frame.x + 8, frame.y + 8))
            label = f"[{entry.name}]" if entry.is_dir else entry.name
            screen.blit(small.render(label[:14], True, (224, 224, 230)), (frame.x, frame.bottom + 8))

    def _draw_canvas_focus_layers_panel(self, screen: pygame.Surface, font: pygame.font.Font, small: pygame.font.Font) -> None:
        panel = self._canvas_focus_layer_panel_rect()
        self._draw_shadowed_panel(screen, panel, (22, 22, 28), (58, 58, 66), radius=0)
        header = pygame.Rect(panel.x, panel.y, panel.width, 28)
        pygame.draw.rect(screen, (34, 34, 40), header)
        pygame.draw.rect(screen, (62, 62, 72), header, 1)
        screen.blit(font.render("Layers", True, (216, 216, 224)), (header.x + 10, header.y + 4))

        active_layer_visible = bool(
            self.canvas_doc.frames
            and self.canvas_doc.frame_idx < len(self.canvas_doc.layer_visible)
            and self.canvas_doc.layer_idx < len(self.canvas_doc.layer_visible[self.canvas_doc.frame_idx])
            and self.canvas_doc.layer_visible[self.canvas_doc.frame_idx][self.canvas_doc.layer_idx]
        )
        labels = {
            "layer_add": "+",
            "layer_dup": "Dup",
            "layer_merge": f"Merge {len(self._canvas_selected_layer_indices())}" if len(self._canvas_selected_layer_indices()) > 1 else "Merge",
            "layer_vis": "Hide" if active_layer_visible else "Show",
            "layer_up": "Up",
            "layer_down": "Dn",
            "layer_ren": "Name",
            "layer_del": "Del",
        }
        for key, rect in self._canvas_focus_layer_button_rects().items():
            if key == "layer_add":
                col = (42, 82, 58)
            elif key == "layer_del":
                col = (88, 52, 52)
            elif key == "layer_vis":
                col = (46, 90, 132) if active_layer_visible else (60, 56, 44)
            else:
                col = (40, 40, 52)
            pygame.draw.rect(screen, col, rect)
            pygame.draw.rect(screen, (72, 72, 84), rect, 1)
            bt = small.render(labels[key], True, (220, 230, 242))
            screen.blit(bt, bt.get_rect(center=rect.center))

        rows_rect = self._canvas_focus_layer_rows_rect()
        pygame.draw.rect(screen, (18, 18, 24), rows_rect)
        pygame.draw.rect(screen, (54, 54, 64), rows_rect, 1)
        if self.canvas_doc.frames:
            fi = self.canvas_doc.frame_idx
            frame_layers = self.canvas_doc.frames[fi] if fi < len(self.canvas_doc.frames) else []
            nl = len(frame_layers)
            row_y = rows_rect.y + 6
            row_h = 20
            visible_rows = max(1, rows_rect.height // row_h)
            max_scroll = max(0, nl - visible_rows)
            self.canvas_layer_scroll = max(0, min(self.canvas_layer_scroll, max_scroll))
            start = max(0, nl - 1 - self.canvas_layer_scroll)
            stop = max(-1, start - visible_rows)
            selected_layers = set(self._canvas_selected_layer_indices())
            for li in range(start, stop, -1):
                if row_y + 18 > rows_rect.bottom - 2:
                    break
                row_r = pygame.Rect(rows_rect.x + 4, row_y, rows_rect.width - 8, 18)
                sel = li == self.canvas_doc.layer_idx
                multi_sel = li in selected_layers
                vis = self.canvas_doc.layer_visible[fi][li] if fi < len(self.canvas_doc.layer_visible) else True
                fill = (50, 78, 130) if sel else (40, 62, 96) if multi_sel else (32, 32, 40)
                border = (80, 120, 200) if sel else (96, 144, 198) if multi_sel else (52, 52, 62)
                pygame.draw.rect(screen, fill, row_r)
                pygame.draw.rect(screen, border, row_r, 1)
                pygame.draw.circle(screen, (140, 200, 140) if vis else (70, 70, 80), (row_r.x + 8, row_r.centery), 5)
                nm = (self.canvas_doc.layer_names[fi][li] if fi < len(self.canvas_doc.layer_names) else f"Layer {li + 1}")
                lc = (210, 228, 255) if (sel or multi_sel) else (150, 150, 170)
                screen.blit(small.render(nm[:18], True, lc), (row_r.x + 18, row_r.y + 2))
                row_y += row_h
            if max_scroll > 0:
                track = pygame.Rect(rows_rect.right - 6, rows_rect.y + 2, 4, rows_rect.height - 4)
                pygame.draw.rect(screen, (34, 34, 42), track)
                thumb_h = max(12, int(track.height * (visible_rows / max(nl, 1))))
                thumb_y = track.y + int((track.height - thumb_h) * (self.canvas_layer_scroll / max(max_scroll, 1)))
                pygame.draw.rect(screen, (110, 126, 154), (track.x, thumb_y, track.width, thumb_h))

    def _draw_canvas_bottom_panel(self, screen: pygame.Surface, font: pygame.font.Font, small: pygame.font.Font) -> None:
        """Bottom panel shown in canvas mode: frame strip (left) + layer list (right)."""
        if self.canvas_bottom_collapsed:
            # Thin strip docked at the very bottom of the screen
            strip_y = self.screen_height - self.gutter - 28
            strip = pygame.Rect(self.gutter, strip_y, self.screen_width - self.gutter * 2, 28)
            pygame.draw.rect(screen, (22, 22, 28), strip)
            pygame.draw.rect(screen, (48, 48, 58), strip, 1)
            toggle_r = self._canvas_bottom_toggle_rect()
            pygame.draw.rect(screen, (42, 42, 52), toggle_r)
            pygame.draw.rect(screen, (80, 80, 95), toggle_r, 1)
            at = small.render("▲ Show", True, (180, 190, 210))
            screen.blit(at, at.get_rect(center=toggle_r.center))
            return

        panel = self._asset_panel_rect()

        # ── Collapse toggle tab (above the full panel) ─────────────────
        toggle_r = self._canvas_bottom_toggle_rect()
        pygame.draw.rect(screen, (32, 32, 40), toggle_r)
        pygame.draw.rect(screen, (60, 60, 72), toggle_r, 1)
        at = small.render("▼ Hide", True, (180, 180, 196))
        screen.blit(at, at.get_rect(center=toggle_r.center))

        self._draw_shadowed_panel(screen, panel, (20, 20, 24), (54, 54, 62), radius=0)

        mid_x = self._canvas_bottom_mid_x(panel)
        split_handle = self._canvas_bottom_split_handle_rect(panel)
        resize_handle = self._asset_resize_handle_rect()
        pygame.draw.rect(screen, (58, 58, 62), resize_handle)
        grip = pygame.Rect(resize_handle.centerx - 18, resize_handle.centery - 2, 36, 4)
        pygame.draw.rect(screen, (148, 148, 154), grip)

        # ── LEFT: Frame strip ─────────────────────────────────────────────
        pygame.draw.rect(screen, (18, 18, 22), pygame.Rect(panel.x, panel.y, mid_x - panel.x, panel.height))
        screen.blit(small.render("Frames", True, (100, 130, 180)), (panel.x + 6, panel.y + 4))

        # Onion + BG toggles
        tog_x = panel.x + 6
        tog_y = panel.y + 20
        for tog_lbl, tog_val in [
            (("Onion●" if self.canvas_onion_skin else "Onion"), self.canvas_onion_skin),
            (("Light" if self.canvas_bg_light else "Dark"), self.canvas_bg_light),
        ]:
            tog_r = pygame.Rect(tog_x, tog_y, 52, 18)
            pygame.draw.rect(screen, (50, 80, 130) if tog_val else (34, 34, 42), tog_r)
            pygame.draw.rect(screen, (90, 130, 210) if tog_val else (58, 58, 68), tog_r, 1)
            screen.blit(small.render(tog_lbl, True, (180, 210, 255) if tog_val else (150, 150, 165)), (tog_x + 3, tog_y + 2))
            tog_x += 57

        # Frame thumbnails
        n = len(self.canvas_doc.frames)
        frame_area_x = panel.x + 6
        frame_area_y = panel.y + 42
        frame_buttons = self._canvas_bottom_frame_button_rects(panel)
        frame_button_left = min((rect.x for rect in frame_buttons.values()), default=mid_x - 6)
        large_preview_rect = self._canvas_bottom_large_preview_rect(panel)
        frame_right_limit = (large_preview_rect.x - 8) if large_preview_rect is not None else frame_button_left - 6
        frame_area_w = max(40, frame_right_limit - frame_area_x)
        frame_area_h = panel.height - 48
        if n == 0:
            screen.blit(small.render("No frames", True, (70, 70, 82)), (frame_area_x, frame_area_y + 4))
        else:
            thumb_w = min(68, max(36, (frame_area_w - 4 * max(n - 1, 0)) // max(n, 1)))
            thumb_h = frame_area_h - 18
            for i in range(n):
                fx = frame_area_x + i * (thumb_w + 4)
                if fx + thumb_w > frame_area_x + frame_area_w:
                    break
                fr = pygame.Rect(fx, frame_area_y, thumb_w, thumb_h)
                active = (i == self.canvas_doc.frame_idx)
                pygame.draw.rect(screen, (50, 80, 140) if active else (32, 32, 38), fr)
                pygame.draw.rect(screen, (90, 140, 220) if active else (58, 58, 68), fr, 1)
                th = self._canvas_scaled_frame_surface(i, (max(1, fr.width - 4), max(1, fr.height - 14)))
                if th is not None:
                    screen.blit(th, (fr.x + 2, fr.y + 2))
                lbl = small.render(str(i + 1), True, (200, 220, 255) if active else (110, 110, 130))
                screen.blit(lbl, (fr.x + 2, fr.bottom - 13))
            # Frame buttons: add, duplicate, move left/right, delete
            labels = {
                "frame_add": "+",
                "frame_dup": "Dup",
                "frame_prev": "<",
                "frame_next": ">",
                "fps_dn": "-",
                "fps_val": f"{self.canvas_preview_fps}fps",
                "fps_up": "+",
                "preview_play": "Pause" if self.canvas_preview_playing and len(self.canvas_doc.frames) > 1 else "Play",
                "frame_del": "Del",
            }
            for key, br in frame_buttons.items():
                label = labels[key]
                if key == "frame_add":
                    col = (42, 82, 58)
                elif key == "frame_del":
                    col = (88, 52, 52)
                elif key == "preview_play" and self.canvas_preview_playing and len(self.canvas_doc.frames) > 1:
                    col = (46, 90, 132)
                elif key == "fps_val":
                    col = (38, 52, 78)
                else:
                    col = (42, 42, 52)
                pygame.draw.rect(screen, col, br)
                pygame.draw.rect(screen, (72, 72, 84), br, 1)
                bt = small.render(label, True, (220, 230, 242))
                screen.blit(bt, bt.get_rect(center=br.center))
            if large_preview_rect is not None:
                self._draw_canvas_preview_box(screen, large_preview_rect, small, label="Preview")

        # ── RIGHT: Layer list ─────────────────────────────────────────────
        layer_x = mid_x + 4
        layer_w = panel.right - layer_x - 6
        pygame.draw.rect(screen, (22, 22, 28), pygame.Rect(mid_x, panel.y, panel.right - mid_x, panel.height))
        screen.blit(small.render("Preview / Layers", True, (100, 130, 180)), (layer_x, panel.y + 4))
        pygame.draw.rect(screen, (60, 60, 72), split_handle)
        pygame.draw.rect(screen, (96, 96, 110), split_handle, 1)

        preview_rect = self._canvas_bottom_preview_rect(panel)
        self._draw_canvas_preview_box(screen, preview_rect, small, label="Mini")

        # Layer control buttons: +, Dup, Name, Up, Dn, Del
        layer_button_rects = self._canvas_bottom_layer_button_rects(panel)
        active_layer_visible = bool(
            self.canvas_doc.frames
            and self.canvas_doc.frame_idx < len(self.canvas_doc.layer_visible)
            and self.canvas_doc.layer_idx < len(self.canvas_doc.layer_visible[self.canvas_doc.frame_idx])
            and self.canvas_doc.layer_visible[self.canvas_doc.frame_idx][self.canvas_doc.layer_idx]
        )
        layer_button_labels = {
            "layer_add": "+",
            "layer_dup": "Dup",
            "layer_ren": "Name",
            "layer_merge": f"Merge {len(self._canvas_selected_layer_indices())}" if len(self._canvas_selected_layer_indices()) > 1 else "Merge",
            "layer_up": "↑",
            "layer_down": "↓",
            "layer_vis": "Hide" if active_layer_visible else "Show",
            "layer_del": "Del",
        }
        for key, br in layer_button_rects.items():
            if key == "layer_add":
                col = (42, 82, 58)
            elif key == "layer_del":
                col = (88, 52, 52)
            elif key == "layer_vis":
                col = (46, 90, 132) if active_layer_visible else (60, 56, 44)
            else:
                col = (40, 40, 52)
            pygame.draw.rect(screen, col, br)
            pygame.draw.rect(screen, (72, 72, 84), br, 1)
            bt = small.render(layer_button_labels[key], True, (220, 230, 242))
            screen.blit(bt, bt.get_rect(center=br.center))

        # Layer rows
        if self.canvas_doc.frames:
            fi = self.canvas_doc.frame_idx
            frame_layers = self.canvas_doc.frames[fi] if fi < len(self.canvas_doc.frames) else []
            nl = len(frame_layers)
            row_y, visible_rows, scroll, max_scroll = self._canvas_layer_row_metrics(panel)
            start = max(0, nl - 1 - scroll)
            stop = max(-1, start - visible_rows)
            selected_layers = set(self._canvas_selected_layer_indices())
            for li in range(start, stop, -1):
                if row_y + 18 > panel.bottom - 2:
                    break
                sel = (li == self.canvas_doc.layer_idx)
                multi_sel = li in selected_layers
                vis = self.canvas_doc.layer_visible[fi][li] if fi < len(self.canvas_doc.layer_visible) else True
                row_r = pygame.Rect(layer_x, row_y, layer_w, 18)
                fill = (50, 78, 130) if sel else (40, 62, 96) if multi_sel else (32, 32, 40)
                border = (80, 120, 200) if sel else (96, 144, 198) if multi_sel else (52, 52, 62)
                pygame.draw.rect(screen, fill, row_r)
                pygame.draw.rect(screen, border, row_r, 1)
                # Eye dot
                pygame.draw.circle(screen, (140, 200, 140) if vis else (70, 70, 80), (row_r.x + 8, row_r.centery), 5)
                nm = (self.canvas_doc.layer_names[fi][li] if fi < len(self.canvas_doc.layer_names) else f"Layer {li+1}")
                lc = (210, 228, 255) if (sel or multi_sel) else (150, 150, 170)
                screen.blit(small.render(nm[:16], True, lc), (row_r.x + 18, row_r.y + 2))
                row_y += 20
            if max_scroll > 0:
                rows_rect = self._canvas_layer_rows_rect(panel)
                track = pygame.Rect(rows_rect.right - 6, rows_rect.y, 4, rows_rect.height)
                pygame.draw.rect(screen, (34, 34, 42), track)
                thumb_h = max(12, int(rows_rect.height * (visible_rows / max(nl, 1))))
                thumb_y = track.y + int((track.height - thumb_h) * (scroll / max(max_scroll, 1)))
                pygame.draw.rect(screen, (110, 126, 154), (track.x, thumb_y, track.width, thumb_h))

    def _draw_topbar(self, screen: pygame.Surface, font: pygame.font.Font, small: pygame.font.Font) -> None:
        topbar = pygame.Rect(0, 0, self.screen_width, self.topbar_h)
        self._draw_shadowed_panel(screen, topbar, (28, 28, 32), (72, 72, 78), radius=0)
        screen.blit(font.render("Scene Editor", True, (236, 236, 240)), (topbar.x + 12, topbar.y + 15))

        labels = {"file": "File", "scene": "Scene", "canvas": "Canvas", "assets": "Assets"}
        for name, rect in self._menu_buttons().items():
            assets_active = name == "assets" and self.canvas_assets_open and self.workspace_mode == "canvas"
            active = self.dropdown_open == name or (name == self.workspace_mode and name in {"scene", "canvas"}) or assets_active
            fill = (76, 76, 82) if active else (44, 44, 48)
            border = (140, 140, 146) if active else (94, 94, 100)
            pygame.draw.rect(screen, fill, rect)
            pygame.draw.rect(screen, border, rect, 1)
            text = small.render(labels[name], True, (234, 234, 238))
            screen.blit(text, text.get_rect(center=rect.center))

        if self.workspace_mode == "canvas":
            if self.canvas_doc.asset_rel is None:
                chip_text = "Canvas: no asset selected"
            else:
                active_tool_label = dict(self._CANVAS_TOOLS).get(self.canvas_tool, self.canvas_tool.title())
                chip_text = f"Canvas: {Path(self.canvas_doc.asset_rel).name} • {active_tool_label}"
        else:
            selected = self._selected_sprite()
            if selected is None:
                chip_text = "No asset selected"
            else:
                count = len(self._selected_sprites())
                chip_text = (
                    f"Selected: {count} • {Path(selected.asset_path).name} • "
                    f"X{int(selected.rotation_x)} Y{int(selected.rotation_y)} Z{int(selected.rotation_z)}"
                )
        chip = small.render(chip_text, True, (224, 224, 230))
        chip_rect = pygame.Rect(topbar.right - chip.get_width() - 20, topbar.y + 12, chip.get_width() + 14, 28)
        pygame.draw.rect(screen, (44, 44, 48), chip_rect)
        pygame.draw.rect(screen, (96, 96, 102), chip_rect, 1)
        screen.blit(chip, (chip_rect.x + 8, chip_rect.y + 7))

    def _draw_dropdowns(self, screen: pygame.Surface, small: pygame.font.Font) -> None:
        if self.dropdown_open is None:
            return
        panel = self._menu_dropdown_rect(self.dropdown_open)
        pygame.draw.rect(screen, (30, 30, 34), panel)
        pygame.draw.rect(screen, (112, 112, 118), panel, 1)
        for label, rect in self._menu_items(self.dropdown_open):
            pygame.draw.rect(screen, (46, 46, 50), rect)
            pygame.draw.rect(screen, (88, 88, 94), rect, 1)
            text = small.render(label, True, (236, 236, 240))
            screen.blit(text, (rect.x + 10, rect.y + 7))

    def _draw_tabs(self, screen: pygame.Surface, small: pygame.font.Font) -> None:
        tabs_rect = pygame.Rect(0, self.topbar_h, self.screen_width, self.tabs_h)
        self._draw_shadowed_panel(screen, tabs_rect, (26, 26, 30), (72, 72, 78), radius=0)
        if self.workspace_mode != "scene":
            export_rect = self._canvas_export_rect()
            active = self.dropdown_open == "canvas_export"
            fill = (70, 70, 76) if active else (42, 42, 46)
            border = (138, 138, 144) if active else (90, 90, 96)
            pygame.draw.rect(screen, fill, export_rect)
            pygame.draw.rect(screen, border, export_rect, 1)
            label = small.render("Export", True, (234, 234, 238))
            screen.blit(label, label.get_rect(center=export_rect.center))
            return
        for index, rect, close_rect in self._tab_layouts():
            scene = self.scenes[index]
            active = index == self.active_scene_idx
            fill = (70, 70, 76) if active else (42, 42, 46)
            border = (138, 138, 144) if active else (90, 90, 96)
            pygame.draw.rect(screen, fill, rect)
            pygame.draw.rect(screen, border, rect, 1)
            label = f"{scene.name} • {scene.board_width}x{scene.board_height}"
            text = small.render(label[:28], True, (236, 236, 240))
            screen.blit(text, (rect.x + 12, rect.y + 8))
            close_fill = (104, 104, 110) if active else (60, 60, 66)
            close_border = (160, 160, 166) if active else (108, 108, 114)
            pygame.draw.rect(screen, close_fill, close_rect)
            pygame.draw.rect(screen, close_border, close_rect, 1)
            cx, cy = close_rect.center
            pygame.draw.line(screen, (234, 234, 238), (cx - 3, cy - 3), (cx + 3, cy + 3), 1)
            pygame.draw.line(screen, (234, 234, 238), (cx + 3, cy - 3), (cx - 3, cy + 3), 1)

    def _draw_status(self, screen: pygame.Surface, small: pygame.font.Font) -> None:
        # Hide status bar in canvas focus mode and when the animation panel is collapsed.
        if self.workspace_mode == "canvas" and self.canvas_focus_mode:
            return
        if self.workspace_mode == "canvas" and self.canvas_bottom_collapsed:
            return
        text = small.render(self.status[:170], True, (220, 220, 226))
        rect = pygame.Rect(self.board_rect.x + 8, self.board_rect.bottom - 30, self.board_rect.width - 16, 24)
        pygame.draw.rect(screen, (40, 40, 44), rect)
        pygame.draw.rect(screen, (86, 86, 92), rect, 1)
        screen.blit(text, (rect.x + 8, rect.y + 4))

    def _draw_dialog(self, screen: pygame.Surface, font: pygame.font.Font, small: pygame.font.Font) -> None:
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((6, 10, 16, 170))
        screen.blit(overlay, (0, 0))

        if self.dialog_mode == "new_scene":
            panel, options, width_rect, height_rect, create_rect, cancel_rect = self._new_scene_dialog_layout()
            self._draw_shadowed_panel(screen, panel, (34, 34, 38), (132, 132, 138), radius=0)
            screen.blit(font.render("New Scene", True, (242, 242, 246)), (panel.x + 22, panel.y + 20))
            subtitle = "Pick a preset or type custom width and height in pixels."
            screen.blit(small.render(subtitle, True, (186, 186, 192)), (panel.x + 22, panel.y + 52))
            for size, rect in options:
                selected = size == self.pending_scene_size
                fill = (92, 92, 98) if selected else (56, 56, 62)
                border = (186, 186, 192) if selected else (128, 128, 134)
                pygame.draw.rect(screen, fill, rect)
                pygame.draw.rect(screen, border, rect, 1)
                label = font.render(f"{size[0]} x {size[1]}", True, (236, 236, 240))
                screen.blit(label, label.get_rect(center=rect.center))

            screen.blit(small.render("Custom Width", True, (188, 188, 194)), (width_rect.x, width_rect.y - 20))
            screen.blit(small.render("Custom Height", True, (188, 188, 194)), (height_rect.x, height_rect.y - 20))
            width_active = self.scene_size_focus == "width"
            height_active = self.scene_size_focus == "height"
            pygame.draw.rect(screen, (22, 22, 26), width_rect)
            pygame.draw.rect(screen, (182, 182, 188) if width_active else (114, 114, 120), width_rect, 1)
            pygame.draw.rect(screen, (22, 22, 26), height_rect)
            pygame.draw.rect(screen, (182, 182, 188) if height_active else (114, 114, 120), height_rect, 1)
            width_value = input_display_text(self.custom_scene_width_input, width_active, "0")
            height_value = input_display_text(self.custom_scene_height_input, height_active, "0")
            screen.blit(font.render(width_value, True, (236, 236, 240)), (width_rect.x + 10, width_rect.y + 8))
            screen.blit(font.render(height_value, True, (236, 236, 240)), (height_rect.x + 10, height_rect.y + 8))

            for rect, label in [(create_rect, "Create"), (cancel_rect, "Cancel")]:
                pygame.draw.rect(screen, (58, 58, 64), rect)
                pygame.draw.rect(screen, (136, 136, 142), rect, 1)
                text = small.render(label, True, (236, 236, 240))
                screen.blit(text, text.get_rect(center=rect.center))
            return

        if self.dialog_mode == "new_canvas":
            panel, presets, w_rect, h_rect, create_rect, cancel_rect = self._new_canvas_dialog_layout()
            self._draw_shadowed_panel(screen, panel, (28, 28, 32), (90, 90, 96), radius=0)
            screen.blit(font.render("New Canvas", True, (220, 220, 226)), (panel.x + 20, panel.y + 18))
            screen.blit(small.render("Pick a preset or enter a custom size.", True, (150, 150, 158)), (panel.x + 20, panel.y + 48))
            cur_w = parse_int(self.canvas_new_width_input)
            cur_h = parse_int(self.canvas_new_height_input)
            for sz, rect in presets:
                sel = sz == (cur_w, cur_h)
                fill = (60, 90, 150) if sel else (44, 44, 52)
                border = (110, 160, 230) if sel else (80, 80, 90)
                pygame.draw.rect(screen, fill, rect)
                pygame.draw.rect(screen, border, rect, 1)
                lbl = small.render(f"{sz[0]}x{sz[1]}", True, (220, 230, 255) if sel else (190, 190, 200))
                screen.blit(lbl, lbl.get_rect(center=rect.center))
            screen.blit(small.render("Width", True, (160, 160, 168)), (w_rect.x, w_rect.y - 18))
            screen.blit(small.render("Height", True, (160, 160, 168)), (h_rect.x, h_rect.y - 18))
            for rect, focus_key, val in [(w_rect, "width", self.canvas_new_width_input), (h_rect, "height", self.canvas_new_height_input)]:
                active = self.canvas_new_focus == focus_key
                pygame.draw.rect(screen, (18, 18, 22), rect)
                pygame.draw.rect(screen, (140, 180, 230) if active else (80, 80, 90), rect, 1)
                screen.blit(font.render(input_display_text(val, active, "0"), True, (220, 220, 226)), (rect.x + 10, rect.y + 8))
            for rect, label, accent in [(create_rect, "Create", True), (cancel_rect, "Cancel", False)]:
                pygame.draw.rect(screen, (48, 80, 140) if accent else (50, 50, 58), rect)
                pygame.draw.rect(screen, (100, 150, 220) if accent else (90, 90, 100), rect, 1)
                ls = small.render(label, True, (220, 230, 255) if accent else (200, 200, 210))
                screen.blit(ls, ls.get_rect(center=rect.center))
            return

        if self.dialog_mode == "new_folder":
            panel, input_rect, create_rect, cancel_rect = self._new_folder_dialog_layout()
            self._draw_shadowed_panel(screen, panel, (34, 34, 38), (132, 132, 138), radius=22)
            screen.blit(font.render("New Folder", True, (246, 248, 255)), (panel.x + 22, panel.y + 20))
            subtitle = "Create a folder anywhere inside assets/. Nested paths like props/trees are allowed."
            screen.blit(small.render(subtitle, True, (186, 186, 192)), (panel.x + 22, panel.y + 52))
            pygame.draw.rect(screen, (12, 18, 28), input_rect)
            pygame.draw.rect(screen, (132, 132, 138), input_rect, 1)
            value = input_display_text(self.folder_name_input, True, "")
            color = (244, 248, 255) if self.folder_name_input else (180, 180, 186)
            screen.blit(font.render(value, True, color), (input_rect.x + 12, input_rect.y + 9))
            for rect, label in [(create_rect, "Create"), (cancel_rect, "Cancel")]:
                pygame.draw.rect(screen, (58, 58, 64), rect)
                pygame.draw.rect(screen, (136, 136, 142), rect, 1)
                text = small.render(label, True, (240, 246, 255))
                screen.blit(text, text.get_rect(center=rect.center))
            return

        if self.dialog_mode == "save_scene":
            panel, input_rect, save_rect, cancel_rect = self._save_scene_dialog_layout()
            self._draw_shadowed_panel(screen, panel, (34, 34, 38), (132, 132, 138), radius=22)
            screen.blit(font.render("Save Scene", True, (246, 248, 255)), (panel.x + 22, panel.y + 20))
            subtitle = "Name the scene. A preview PNG goes to assets/scenes and the editable data goes to json_scenes."
            screen.blit(small.render(subtitle, True, (186, 186, 192)), (panel.x + 22, panel.y + 52))
            pygame.draw.rect(screen, (12, 18, 28), input_rect)
            pygame.draw.rect(screen, (132, 132, 138), input_rect, 1)
            value = input_display_text(self.scene_name_input, True, "")
            color = (244, 248, 255) if self.scene_name_input else (180, 180, 186)
            screen.blit(font.render(value, True, color), (input_rect.x + 12, input_rect.y + 9))
            for rect, label in [(save_rect, "Save"), (cancel_rect, "Cancel")]:
                pygame.draw.rect(screen, (58, 58, 64), rect)
                pygame.draw.rect(screen, (136, 136, 142), rect, 1)
                text = small.render(label, True, (240, 246, 255))
                screen.blit(text, text.get_rect(center=rect.center))
            return

        if self.dialog_mode == "canvas_rename":
            panel, input_rect, save_rect, cancel_rect = self._canvas_rename_dialog_layout()
            self._draw_shadowed_panel(screen, panel, (34, 34, 38), (132, 132, 138), radius=22)
            kind = "Layer" if self.canvas_rename_kind == "layer" else "Frame"
            screen.blit(font.render(f"Rename {kind}", True, (246, 248, 255)), (panel.x + 22, panel.y + 20))
            subtitle = f"Give the current {kind.lower()} a clearer name."
            screen.blit(small.render(subtitle, True, (186, 186, 192)), (panel.x + 22, panel.y + 52))
            pygame.draw.rect(screen, (12, 18, 28), input_rect)
            pygame.draw.rect(screen, (132, 132, 138), input_rect, 1)
            value = input_display_text(self.canvas_name_input, True, "")
            color = (244, 248, 255) if self.canvas_name_input else (180, 180, 186)
            screen.blit(font.render(value, True, color), (input_rect.x + 12, input_rect.y + 9))
            for rect, label in [(save_rect, "Save"), (cancel_rect, "Cancel")]:
                pygame.draw.rect(screen, (58, 58, 64), rect)
                pygame.draw.rect(screen, (136, 136, 142), rect, 1)
                text = small.render(label, True, (240, 246, 255))
                screen.blit(text, text.get_rect(center=rect.center))
            return

        if self.dialog_mode == "color_picker":
            panel, wheel_rect, value_rect, preview_rect, alpha_rect, apply_rect, cancel_rect = self._canvas_color_picker_layout()
            self._draw_shadowed_panel(screen, panel, (26, 26, 30), (92, 92, 102), radius=0)
            screen.blit(font.render("Canvas Color", True, (236, 236, 242)), (panel.x + 22, panel.y + 18))
            subtitle = "Drag wheel for hue/sat, value slider for brightness, bottom slider for opacity."
            screen.blit(small.render(subtitle, True, (162, 162, 174)), (panel.x + 22, panel.y + 44))

            wheel = self._canvas_color_wheel_surface(wheel_rect.width)
            screen.blit(wheel, wheel_rect.topleft)
            pygame.draw.circle(screen, (82, 82, 92), wheel_rect.center, wheel_rect.width // 2, 1)

            gradient = pygame.Surface((value_rect.width, value_rect.height))
            steps = max(1, value_rect.height - 1)
            top_r, top_g, top_b = colorsys.hsv_to_rgb(self.canvas_color_hue, self.canvas_color_sat, 1.0)
            top_color = (int(top_r * 255), int(top_g * 255), int(top_b * 255))
            for y in range(value_rect.height):
                mix = 1.0 - (y / steps)
                color = (
                    int(top_color[0] * mix),
                    int(top_color[1] * mix),
                    int(top_color[2] * mix),
                )
                pygame.draw.line(gradient, color, (0, y), (value_rect.width, y))
            screen.blit(gradient, value_rect.topleft)
            pygame.draw.rect(screen, (82, 82, 92), value_rect, 1)

            radius = wheel_rect.width / 2.0
            marker_x = int(wheel_rect.centerx + math.cos(self.canvas_color_hue * math.tau) * radius * self.canvas_color_sat)
            marker_y = int(wheel_rect.centery + math.sin(self.canvas_color_hue * math.tau) * radius * self.canvas_color_sat)
            pygame.draw.circle(screen, (255, 255, 255), (marker_x, marker_y), 7, 2)
            slider_y = value_rect.y + int((1.0 - self.canvas_color_val) * value_rect.height)
            pygame.draw.rect(screen, (255, 255, 255), (value_rect.x - 3, slider_y - 2, value_rect.width + 6, 4))

            pygame.draw.rect(screen, (32, 32, 38), preview_rect)
            pygame.draw.rect(screen, (76, 76, 88), preview_rect, 1)
            swatch = pygame.Rect(preview_rect.x + 12, preview_rect.y + 12, preview_rect.width - 24, 30)
            swatch_surf = pygame.Surface((swatch.width, swatch.height), pygame.SRCALPHA)
            cs = 5
            for sy in range(0, swatch.height, cs):
                for sx in range(0, swatch.width, cs):
                    c = (180, 180, 180) if (sx // cs + sy // cs) % 2 == 0 else (240, 240, 240)
                    pygame.draw.rect(swatch_surf, c, (sx, sy, cs, cs))
            pygame.draw.rect(swatch_surf, self.canvas_color, (0, 0, swatch.width, swatch.height))
            screen.blit(swatch_surf, swatch.topleft)
            pygame.draw.rect(screen, (120, 150, 210), swatch, 1)
            screen.blit(small.render(self._canvas_color_hex(), True, (220, 226, 244)), (preview_rect.x + 12, preview_rect.y + 52))
            rgb_label = f"RGB {self.canvas_color[0]},{self.canvas_color[1]},{self.canvas_color[2]}  A:{self.canvas_color[3]}"
            screen.blit(small.render(rgb_label, True, (158, 168, 188)), (preview_rect.x + 12, preview_rect.y + 70))

            # Alpha slider
            alpha_check = pygame.Surface((alpha_rect.width, alpha_rect.height), pygame.SRCALPHA)
            acs = 4
            for ay in range(0, alpha_rect.height, acs):
                for ax in range(0, alpha_rect.width, acs):
                    c = (180, 180, 180) if (ax // acs + ay // acs) % 2 == 0 else (240, 240, 240)
                    pygame.draw.rect(alpha_check, c, (ax, ay, acs, acs))
            ar, ag, ab = self.canvas_color[:3]
            for ax in range(alpha_rect.width):
                a_val = int(ax / max(alpha_rect.width - 1, 1) * 255)
                pygame.draw.line(alpha_check, (ar, ag, ab, a_val), (ax, 0), (ax, alpha_rect.height - 1))
            screen.blit(alpha_check, alpha_rect.topleft)
            pygame.draw.rect(screen, (82, 82, 92), alpha_rect, 1)
            alpha_x = alpha_rect.x + int(self.canvas_color[3] / 255.0 * alpha_rect.width)
            pygame.draw.rect(screen, (255, 255, 255), (alpha_x - 2, alpha_rect.y - 3, 4, alpha_rect.height + 6))

            for rect, label, accent in [(apply_rect, "Apply", True), (cancel_rect, "Cancel", False)]:
                pygame.draw.rect(screen, (46, 82, 138) if accent else (52, 52, 60), rect)
                pygame.draw.rect(screen, (100, 150, 220) if accent else (92, 92, 102), rect, 1)
                text = small.render(label, True, (236, 242, 255) if accent else (220, 220, 228))
                screen.blit(text, text.get_rect(center=rect.center))
            return
