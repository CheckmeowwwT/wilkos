from __future__ import annotations

import pygame

try:
    from ..constants import SCENE_SIZE_PRESETS
except ImportError:
    from constants import SCENE_SIZE_PRESETS  # type: ignore[no-redef]


class UILayoutMixin:
    def _menu_buttons(self) -> dict[str, pygame.Rect]:
        topbar = pygame.Rect(0, 0, self.screen_width, self.topbar_h)
        button_y = topbar.y + (topbar.height - 28) // 2
        start_x = topbar.x + 176
        return {
            "file":   pygame.Rect(start_x,       button_y, 82, 28),
            "scene":  pygame.Rect(start_x + 90,  button_y, 92, 28),
            "canvas": pygame.Rect(start_x + 188, button_y, 102, 28),
            "assets": pygame.Rect(start_x + 298, button_y, 84, 28),
        }

    def _menu_dropdown_rect(self, menu_name: str) -> pygame.Rect:
        if menu_name == "canvas_export":
            base = self._canvas_export_rect()
            item_count = 1 if len(self.canvas_doc.frames) <= 1 else 3
            return pygame.Rect(base.x, base.bottom + 2, 220, item_count * 36 + 10)

        buttons = self._menu_buttons()
        base = buttons[menu_name]
        if menu_name == "file":
            item_count = 5
        elif menu_name == "scene":
            item_count = 2
        else:
            item_count = 0
        return pygame.Rect(base.x, self.topbar_h + 2, 190, item_count * 36 + 10)

    def _menu_items(self, menu_name: str) -> list[tuple[str, pygame.Rect]]:
        if menu_name == "file":
            names = ["New", "Open", "Save", "Export PNG", "Export GIF"]
        elif menu_name == "scene":
            names = ["New Scene", "Save Scene"]
        elif menu_name == "canvas_export":
            names = ["Export PNG"]
            if len(self.canvas_doc.frames) > 1:
                names.extend(["Export as Spritesheet", "Export as GIF"])
        else:
            names = []
        panel = self._menu_dropdown_rect(menu_name)
        items: list[tuple[str, pygame.Rect]] = []
        for index, name in enumerate(names):
            rect = pygame.Rect(panel.x + 6, panel.y + 6 + index * 36, panel.width - 12, 30)
            items.append((name, rect))
        return items

    def _tab_layouts(self) -> list[tuple[int, pygame.Rect, pygame.Rect]]:
        tabs_rect = pygame.Rect(0, self.topbar_h, self.screen_width, self.tabs_h)
        x = tabs_rect.x + 10
        y = tabs_rect.y + 4
        layouts: list[tuple[int, pygame.Rect, pygame.Rect]] = []
        for index, scene in enumerate(self.scenes):
            width = 176 if len(scene.name) < 11 else min(270, 104 + len(scene.name) * 7)
            tab_rect = pygame.Rect(x, y, width, self.tabs_h - 8)
            close_rect = pygame.Rect(tab_rect.right - 22, tab_rect.y + 4, 14, 14)
            layouts.append((index, tab_rect, close_rect))
            x += width + 8
        return layouts

    def _canvas_export_rect(self) -> pygame.Rect:
        tabs_rect = pygame.Rect(0, self.topbar_h, self.screen_width, self.tabs_h)
        return pygame.Rect(tabs_rect.x + 10, tabs_rect.y + 4, 108, tabs_rect.height - 8)

    def _canvas_bottom_mid_x(self, panel: pygame.Rect) -> int:
        split = max(0.45, min(0.82, self.canvas_bottom_split))
        self.canvas_bottom_split = split
        return panel.x + int(panel.width * split)

    def _canvas_bottom_split_handle_rect(self, panel: pygame.Rect) -> pygame.Rect:
        mid_x = self._canvas_bottom_mid_x(panel)
        return pygame.Rect(mid_x - 3, panel.y + 6, 6, panel.height - 12)

    def _canvas_layer_row_metrics(self, panel: pygame.Rect) -> tuple[int, int, int, int]:
        row_y = self._canvas_bottom_layer_top(panel)
        visible_rows = max(1, (panel.bottom - 4 - row_y) // 20)
        fi = self.canvas_doc.frame_idx
        nl = len(self.canvas_doc.frames[fi]) if self.canvas_doc.frames and fi < len(self.canvas_doc.frames) else 0
        max_scroll = max(0, nl - visible_rows)
        self.canvas_layer_scroll = max(0, min(self.canvas_layer_scroll, max_scroll))
        return row_y, visible_rows, self.canvas_layer_scroll, max_scroll

    def _canvas_layer_rows_rect(self, panel: pygame.Rect) -> pygame.Rect:
        mid_x = self._canvas_bottom_mid_x(panel)
        row_y, visible_rows, _, _ = self._canvas_layer_row_metrics(panel)
        return pygame.Rect(mid_x + 4, row_y, panel.right - mid_x - 10, max(18, visible_rows * 20))

    def _canvas_inspector_left_handle_rect(self) -> pygame.Rect:
        panel = self._canvas_tools_panel_rect()
        return pygame.Rect(panel.x - 4, panel.y + 8, 8, max(32, panel.height - 16))

    def _canvas_inspector_top_handle_rect(self) -> pygame.Rect:
        panel = self._canvas_tools_panel_rect()
        return pygame.Rect(panel.x + 8, panel.y - 4, max(32, panel.width - 16), 8)

    def _save_scene_dialog_layout(self) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
        panel = pygame.Rect(0, 0, 520, 196)
        panel.center = (self.screen_width // 2, self.screen_height // 2)
        input_rect = pygame.Rect(panel.x + 20, panel.y + 82, panel.width - 40, 40)
        save_rect = pygame.Rect(panel.right - 222, panel.bottom - 52, 96, 36)
        cancel_rect = pygame.Rect(panel.right - 114, panel.bottom - 52, 96, 36)
        return panel, input_rect, save_rect, cancel_rect

    def _canvas_toolbar_buttons(self, panel: pygame.Rect) -> dict[str, pygame.Rect]:
        cols = 4
        gap = 4
        x0 = panel.x + 8
        y0 = panel.y + 44
        avail_w = panel.width - 16
        btn_w = max(40, (avail_w - gap * (cols - 1)) // cols)
        btn_h = 24
        buttons: dict[str, pygame.Rect] = {}
        for i, (key, _) in enumerate(self._CANVAS_TOOLS):
            row, col = divmod(i, cols)
            rect = pygame.Rect(x0 + col * (btn_w + gap), y0 + row * (btn_h + gap), btn_w, btn_h)
            buttons[key] = rect
        return buttons

    def _canvas_tool_grid_bottom(self, panel: pygame.Rect) -> int:
        buttons = self._canvas_toolbar_buttons(panel)
        return max((rect.bottom for rect in buttons.values()), default=panel.y + 44)

    def _canvas_size_input_rects(self, panel: pygame.Rect) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        """Returns (minus_btn, text_field, plus_btn)."""
        y = self._canvas_tool_grid_bottom(panel) + 20
        x = panel.x + 8
        return (
            pygame.Rect(x, y, 24, 24),
            pygame.Rect(x + 28, y, panel.width - 60, 24),
            pygame.Rect(panel.x + panel.width - 24, y, 24, 24),
        )

    def _canvas_fill_toggle_rect(self, panel: pygame.Rect) -> pygame.Rect:
        minus, _, _ = self._canvas_size_input_rects(panel)
        return pygame.Rect(panel.x + 8, minus.bottom + 8, panel.width - 16, 22)

    def _canvas_mirror_toggle_rects(self, panel: pygame.Rect) -> tuple[pygame.Rect, pygame.Rect]:
        """Returns (mirror_h_btn, mirror_v_btn) side by side."""
        fill_rect = self._canvas_fill_toggle_rect(panel)
        y = fill_rect.bottom + 8
        mid = panel.x + panel.width // 2
        return (
            pygame.Rect(panel.x + 8, y, mid - panel.x - 12, 24),
            pygame.Rect(mid + 2, y, panel.right - mid - 10, 24),
        )

    def _canvas_blend_input_rects(self, panel: pygame.Rect) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        """Returns (minus_btn, text_field, plus_btn) for blend strength."""
        mh_rect, _ = self._canvas_mirror_toggle_rects(panel)
        y = mh_rect.bottom + 20
        x = panel.x + 8
        return (
            pygame.Rect(x, y, 24, 24),
            pygame.Rect(x + 28, y, panel.width - 60, 24),
            pygame.Rect(panel.x + panel.width - 24, y, 24, 24),
        )

    def _canvas_selection_action_rects(self, panel: pygame.Rect) -> dict[str, pygame.Rect]:
        """Selection transform buttons stacked below the color picker."""
        palette_rects = self._canvas_quick_palette_rects(panel)
        anchor_rect = palette_rects[0] if palette_rects else self._canvas_color_button_rect(panel)
        y0 = anchor_rect.bottom + 14
        y1 = y0 + 28
        gap = 4
        avail = panel.width - 16
        btn_w = max(30, (avail - gap * 3) // 4)
        x = panel.x + 8
        keys = [
            ("rot_ccw", "↺90"), ("rot_cw", "↻90"),
            ("flip_h",  "FlipH"), ("flip_v",  "FlipV"),
            ("scale_dn","Sc-"), ("scale_up","Sc+"),
            ("bright_dn","Br-"), ("bright_up","Br+"),
        ]
        rects: dict[str, pygame.Rect] = {}
        for i, (key, _) in enumerate(keys):
            row, col = divmod(i, 4)
            y = y0 if row == 0 else y1
            rects[key] = pygame.Rect(x + col * (btn_w + gap), y, btn_w, 24)
        return rects

    def _canvas_color_button_rect(self, panel: pygame.Rect) -> pygame.Rect:
        bm, _, _ = self._canvas_blend_input_rects(panel)
        return pygame.Rect(panel.x + 8, bm.bottom + 12, panel.width - 16, 42)

    def _canvas_quick_palette_rects(self, panel: pygame.Rect) -> list[pygame.Rect]:
        color_rect = self._canvas_color_button_rect(panel)
        gap = 4
        swatch_w = max(24, (color_rect.width - gap * 4) // 5)
        return [
            pygame.Rect(color_rect.x + idx * (swatch_w + gap), color_rect.bottom + 8, swatch_w, 22)
            for idx in range(5)
        ]

    def _canvas_view_rect(self, panel: pygame.Rect) -> pygame.Rect:
        if self.workspace_mode == "canvas" and self.canvas_focus_mode:
            top = panel.y + 34
        else:
            # Header (44) + toolbar (34) = 80px reserved at top; 4px margin at bottom
            top = panel.y + 80
        if self.canvas_bottom_collapsed:
            # Extend canvas to fill most of the screen; thin strip docks at bottom
            strip_h = 28
            bottom = self.screen_height - self.gutter - strip_h - 4
        else:
            bottom = panel.bottom - 4
        return pygame.Rect(
            panel.x + 4, top,
            panel.width - 8,
            max(1, bottom - top),
        )

    def _canvas_toolbar_rect(self, panel: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(panel.x + 4, panel.y + 44, panel.width - 8, 34)

    def _canvas_focus_toggle_rect(self, panel: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(panel.right - 34, panel.y + 8, 26, 26)

    def _scene_focus_toggle_rect(self) -> pygame.Rect:
        toolbar = self._scene_toolbar_rect()
        return pygame.Rect(toolbar.right - 32, toolbar.y + 2, 26, 26)

    def _canvas_color_picker_layout(
        self,
    ) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
        panel = pygame.Rect(0, 0, 430, 380)
        panel.center = (self.screen_width // 2, self.screen_height // 2)
        wheel = pygame.Rect(panel.x + 24, panel.y + 62, 220, 220)
        value = pygame.Rect(wheel.right + 16, wheel.y, 24, wheel.height)
        preview = pygame.Rect(value.right + 20, wheel.y, 126, 86)
        alpha_rect = pygame.Rect(panel.x + 24, wheel.bottom + 14, panel.width - 48, 16)
        apply_rect = pygame.Rect(panel.right - 208, panel.bottom - 48, 92, 34)
        cancel_rect = pygame.Rect(panel.right - 104, panel.bottom - 48, 92, 34)
        return panel, wheel, value, preview, alpha_rect, apply_rect, cancel_rect

    def _canvas_rename_dialog_layout(self) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
        panel = pygame.Rect(0, 0, 520, 196)
        panel.center = (self.screen_width // 2, self.screen_height // 2)
        input_rect = pygame.Rect(panel.x + 20, panel.y + 82, panel.width - 40, 40)
        save_rect = pygame.Rect(panel.right - 222, panel.bottom - 52, 96, 36)
        cancel_rect = pygame.Rect(panel.right - 114, panel.bottom - 52, 96, 36)
        return panel, input_rect, save_rect, cancel_rect

    def _new_canvas_dialog_layout(self) -> tuple[pygame.Rect, list[tuple[tuple[int, int], pygame.Rect]], pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
        panel = pygame.Rect(0, 0, 500, 300)
        panel.center = (self.screen_width // 2, self.screen_height // 2)
        presets: list[tuple[tuple[int, int], pygame.Rect]] = []
        sizes = [(8, 8), (16, 16), (32, 32), (64, 64), (128, 128), (256, 256)]
        bw, bh, gap = 120, 38, 10
        sx = panel.x + 20
        sy = panel.y + 72
        for i, sz in enumerate(sizes):
            row, col = divmod(i, 3)
            presets.append((sz, pygame.Rect(sx + col * (bw + gap), sy + row * (bh + gap), bw, bh)))
        w_rect = pygame.Rect(panel.x + 20, panel.y + 208, 200, 36)
        h_rect = pygame.Rect(panel.x + 260, panel.y + 208, 200, 36)
        create = pygame.Rect(panel.right - 216, panel.bottom - 48, 96, 34)
        cancel = pygame.Rect(panel.right - 110, panel.bottom - 48, 96, 34)
        return panel, presets, w_rect, h_rect, create, cancel

    def _canvas_workspace_toolbar_buttons(self, panel: pygame.Rect) -> dict[str, pygame.Rect]:
        toolbar = self._canvas_toolbar_rect(panel)
        x = toolbar.x + 6
        y = toolbar.y + 3
        buttons: dict[str, pygame.Rect] = {}
        for name, w in [("new", 46), ("fit", 36), ("onion", 48), ("bgmode", 44), ("delete", 50)]:
            buttons[name] = pygame.Rect(x, y, w, 26)
            x += w + 5
        buttons["focus"] = pygame.Rect(toolbar.right - 32, y, 26, 26)
        return buttons

    def _new_scene_dialog_layout(
        self,
    ) -> tuple[
        pygame.Rect,
        list[tuple[tuple[int, int], pygame.Rect]],
        pygame.Rect,
        pygame.Rect,
        pygame.Rect,
        pygame.Rect,
    ]:
        panel = pygame.Rect(0, 0, 560, 338)
        panel.center = (self.screen_width // 2, self.screen_height // 2)
        options: list[tuple[tuple[int, int], pygame.Rect]] = []
        start_x = panel.x + 22
        start_y = panel.y + 82
        button_w = 244
        button_h = 50
        gap = 14
        for index, size in enumerate(SCENE_SIZE_PRESETS):
            row = index // 2
            col = index % 2
            rect = pygame.Rect(
                start_x + col * (button_w + gap),
                start_y + row * (button_h + gap),
                button_w,
                button_h,
            )
            options.append((size, rect))
        width_rect = pygame.Rect(panel.x + 22, panel.y + 206, 240, 38)
        height_rect = pygame.Rect(panel.x + 282, panel.y + 206, 240, 38)
        create_rect = pygame.Rect(panel.right - 222, panel.bottom - 52, 96, 36)
        cancel_rect = pygame.Rect(panel.right - 114, panel.bottom - 52, 96, 36)
        return panel, options, width_rect, height_rect, create_rect, cancel_rect

    def _new_folder_dialog_layout(self) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
        panel = pygame.Rect(0, 0, 520, 196)
        panel.center = (self.screen_width // 2, self.screen_height // 2)
        input_rect = pygame.Rect(panel.x + 20, panel.y + 82, panel.width - 40, 40)
        create_rect = pygame.Rect(panel.right - 222, panel.bottom - 52, 96, 36)
        cancel_rect = pygame.Rect(panel.right - 114, panel.bottom - 52, 96, 36)
        return panel, input_rect, create_rect, cancel_rect

    def _canvas_bottom_toggle_rect(self) -> pygame.Rect:
        """Rect for the Show/Hide toggle button."""
        if self.canvas_bottom_collapsed:
            # Thin strip docked at screen bottom — toggle lives inside it
            strip_y = self.screen_height - self.gutter - 28
            strip_right = self.screen_width - self.gutter
            return pygame.Rect(strip_right - 76, strip_y + 4, 68, 20)
        else:
            panel = self._asset_panel_rect()
            return pygame.Rect(panel.right - 76, panel.y - 22, 68, 20)

    def _canvas_bottom_frame_button_rects(self, panel: pygame.Rect) -> dict[str, pygame.Rect]:
        """Bottom-panel frame action buttons shown to the right of the strip."""
        mid_x = self._canvas_bottom_mid_x(panel)
        y = panel.y + 42
        gap = 4
        specs = [
            ("frame_add", "+", 24),
            ("frame_dup", "Dup", 34),
            ("frame_prev", "<", 24),
            ("frame_next", ">", 24),
            ("fps_dn", "-", 20),
            ("fps_val", "FPS", 42),
            ("fps_up", "+", 20),
            ("preview_play", "Play", 40),
            ("frame_del", "Del", 34),
        ]
        total_w = sum(width for _, _, width in specs) + gap * (len(specs) - 1)
        x = mid_x - 6 - total_w
        rects: dict[str, pygame.Rect] = {}
        for key, _, width in specs:
            rects[key] = pygame.Rect(x, y, width, 20)
            x += width + gap
        return rects

    def _canvas_bottom_preview_rect(self, panel: pygame.Rect) -> pygame.Rect:
        mid_x = self._canvas_bottom_mid_x(panel)
        layer_x = mid_x + 4
        layer_w = panel.right - layer_x - 6
        return pygame.Rect(layer_x, panel.y + 20, layer_w, 56)

    def _canvas_bottom_large_preview_rect(self, panel: pygame.Rect) -> pygame.Rect | None:
        mid_x = self._canvas_bottom_mid_x(panel)
        frame_buttons = self._canvas_bottom_frame_button_rects(panel)
        column_x = min((rect.x for rect in frame_buttons.values()), default=mid_x - 160)
        preview_x = max(panel.x + 168, column_x)
        preview_rect = pygame.Rect(preview_x, panel.y + 68, mid_x - preview_x - 6, panel.height - 74)
        if preview_rect.width < 120 or preview_rect.height < 70:
            return None
        return preview_rect

    def _canvas_bottom_layer_button_rects(self, panel: pygame.Rect) -> dict[str, pygame.Rect]:
        mid_x = self._canvas_bottom_mid_x(panel)
        layer_x = mid_x + 4
        layer_w = panel.right - layer_x - 6
        btn_w = max(34, (layer_w - 12) // 4)
        top = self._canvas_bottom_preview_rect(panel).bottom + 8
        rects: dict[str, pygame.Rect] = {}
        top_keys = ("layer_add", "layer_dup", "layer_ren", "layer_merge")
        bottom_keys = ("layer_up", "layer_down", "layer_vis", "layer_del")
        for idx, key in enumerate(top_keys):
            rects[key] = pygame.Rect(layer_x + idx * (btn_w + 4), top, btn_w, 18)
        for idx, key in enumerate(bottom_keys):
            rects[key] = pygame.Rect(layer_x + idx * (btn_w + 4), top + 22, btn_w, 18)
        return rects

    def _canvas_bottom_layer_top(self, panel: pygame.Rect) -> int:
        buttons = self._canvas_bottom_layer_button_rects(panel)
        return max((rect.bottom for rect in buttons.values()), default=self._canvas_bottom_preview_rect(panel).bottom) + 6

    def _canvas_focus_layer_button_rects(self) -> dict[str, pygame.Rect]:
        panel = self._canvas_focus_layer_panel_rect()
        gap = 4
        cols = 2
        btn_w = max(72, (panel.width - 24 - gap) // cols)
        x0 = panel.x + 10
        y0 = panel.y + 36
        keys = [
            ("layer_add", "+"),
            ("layer_dup", "Dup"),
            ("layer_merge", "Merge"),
            ("layer_vis", "Show"),
            ("layer_up", "Up"),
            ("layer_down", "Dn"),
            ("layer_ren", "Name"),
            ("layer_del", "Del"),
        ]
        rects: dict[str, pygame.Rect] = {}
        for i, (key, _) in enumerate(keys):
            row, col = divmod(i, cols)
            rects[key] = pygame.Rect(x0 + col * (btn_w + gap), y0 + row * 24, btn_w, 20)
        return rects

    def _canvas_focus_layer_rows_rect(self) -> pygame.Rect:
        panel = self._canvas_focus_layer_panel_rect()
        buttons = self._canvas_focus_layer_button_rects()
        top = max((rect.bottom for rect in buttons.values()), default=panel.y + 120) + 8
        return pygame.Rect(panel.x + 10, top, panel.width - 20, panel.bottom - top - 10)


