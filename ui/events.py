from __future__ import annotations

import pygame


class UIEventsMixin:
    def _handle_menu_click(self, pos: tuple[int, int]) -> bool:
        buttons = self._menu_buttons()
        for name, rect in buttons.items():
            if rect.collidepoint(pos):
                self.rotation_gizmo_enabled = False
                if name == "canvas":
                    self.workspace_mode = "canvas"
                    self.scene_focus_mode = False
                    self.dropdown_open = None
                    self._update_layout(self.screen_width, self.screen_height)
                    self.status = "Canvas workspace."
                    self._sync_canvas_for_selection()
                elif name == "assets":
                    if self.workspace_mode == "canvas":
                        self.canvas_assets_open = not self.canvas_assets_open
                        self.status = "Asset browser " + ("open." if self.canvas_assets_open else "closed.")
                    else:
                        self.dropdown_open = None
                elif name == "scene":
                    self.workspace_mode = "scene"
                    self.dropdown_open = None if self.dropdown_open == name else name
                    self._update_layout(self.screen_width, self.screen_height)
                    self._fit_active_scene()
                else:
                    self.dropdown_open = None if self.dropdown_open == name else name
                return True

        if self.dropdown_open is not None:
            for label, rect in self._menu_items(self.dropdown_open):
                if rect.collidepoint(pos):
                    if self.dropdown_open == "file":
                        if label == "New":
                            self._new_project()
                        elif label == "Open":
                            self._open_project()
                        elif label == "Save":
                            self._save_project()
                        elif label == "Export PNG":
                            self._export_active_scene_png()
                        elif label == "Export GIF":
                            self._export_active_scene_gif()
                    elif self.dropdown_open == "scene":
                        if label == "New Scene":
                            self._open_new_scene_dialog()
                        elif label == "Save Scene":
                            self._open_save_scene_dialog()
                    elif self.dropdown_open == "canvas_export":
                        if label == "Export PNG":
                            self._export_canvas_png()
                        elif label == "Export as Spritesheet":
                            self._export_canvas_spritesheet()
                        elif label == "Export as GIF":
                            self._export_canvas_gif()
                    self.rotation_gizmo_enabled = False
                    self.dropdown_open = None
                    return True

            panel = self._menu_dropdown_rect(self.dropdown_open)
            if panel.collidepoint(pos):
                return True

        topbar_rect = pygame.Rect(0, 0, self.screen_width, self.topbar_h)
        if topbar_rect.collidepoint(pos):
            self.rotation_gizmo_enabled = False
            self.dropdown_open = None
            return True

        self.dropdown_open = None
        return False

    def _handle_tab_click(self, pos: tuple[int, int]) -> bool:
        tabs_y = self.topbar_h
        tabs_rect = pygame.Rect(0, tabs_y, self.screen_width, self.tabs_h)
        if not tabs_rect.collidepoint(pos):
            return False

        if self.workspace_mode == "canvas":
            export_rect = self._canvas_export_rect()
            if export_rect.collidepoint(pos):
                self.dropdown_open = None if self.dropdown_open == "canvas_export" else "canvas_export"
                return True
            self.dropdown_open = None
            return True

        if self.workspace_mode != "scene":
            return False

        for index, rect, close_rect in self._tab_layouts():
            scene = self.scenes[index]
            if close_rect.collidepoint(pos):
                self._close_scene(index)
                return True
            if rect.collidepoint(pos):
                self.active_scene_idx = index
                self._clear_selection()
                self.resizing_sprite_id = None
                self.rotation_gizmo_enabled = False
                self._fit_active_scene()
                self.status = f"Switched to {scene.name} ({scene.board_width}x{scene.board_height})."
                return True
        return True

    def _handle_canvas_bottom_panel_click(self, pos: tuple[int, int]) -> bool:
        """Handle clicks in the canvas-mode bottom panel (frames + layers)."""
        modifiers = pygame.key.get_mods()
        cmd_held = bool(modifiers & (pygame.KMOD_META | pygame.KMOD_CTRL))
        # Collapse/expand toggle sits above the panel rect
        if self._canvas_bottom_toggle_rect().collidepoint(pos):
            self.canvas_bottom_collapsed = not self.canvas_bottom_collapsed
            self.status = "Animation panel " + ("hidden." if self.canvas_bottom_collapsed else "shown.")
            return True

        if self.canvas_bottom_collapsed:
            # Only the toggle button is interactive when collapsed
            return False
        panel = self._asset_panel_rect()
        if not panel.collidepoint(pos):
            return False
        mid_x = self._canvas_bottom_mid_x(panel)

        # ── Onion / BG toggles ──────────────────────────────────────
        tog_x = panel.x + 6
        tog_y = panel.y + 20
        for tog_key in ("onion", "bgmode"):
            tog_r = pygame.Rect(tog_x, tog_y, 52, 18)
            if tog_r.collidepoint(pos):
                if tog_key == "onion":
                    self.canvas_onion_skin = not self.canvas_onion_skin
                else:
                    self.canvas_bg_light = not self.canvas_bg_light
                return True
            tog_x += 57

        # ── Frame buttons (+, Dup, Del) ──────────────────────────────
        frame_area_y = panel.y + 42
        frame_buttons = self._canvas_bottom_frame_button_rects(panel)
        frame_button_left = min((rect.x for rect in frame_buttons.values()), default=mid_x - 6)
        large_preview_rect = self._canvas_bottom_large_preview_rect(panel)
        frame_right_limit = (large_preview_rect.x - 8) if large_preview_rect is not None else frame_button_left - 6
        frame_area_w = max(40, frame_right_limit - (panel.x + 6))
        n = len(self.canvas_doc.frames)
        if n > 0:
            thumb_w = min(68, max(36, (frame_area_w - 4 * max(n - 1, 0)) // max(n, 1)))
            for key, br in frame_buttons.items():
                if br.collidepoint(pos):
                    if key == "frame_add":
                        self._canvas_add_frame()
                    elif key == "frame_dup":
                        self._canvas_duplicate_frame()
                    elif key == "frame_prev":
                        self._canvas_move_frame(-1)
                    elif key == "frame_next":
                        self._canvas_move_frame(1)
                    elif key == "fps_dn":
                        self._set_canvas_preview_fps(self.canvas_preview_fps - 1)
                        self.status = f"Animation FPS: {self.canvas_preview_fps}."
                    elif key == "fps_up":
                        self._set_canvas_preview_fps(self.canvas_preview_fps + 1)
                        self.status = f"Animation FPS: {self.canvas_preview_fps}."
                    elif key == "fps_val":
                        self.status = f"Animation FPS: {self.canvas_preview_fps}."
                    elif key == "preview_play":
                        self._toggle_canvas_preview()
                    elif key == "frame_del":
                        self._canvas_remove_frame()
                    return True
            # Frame thumbnail clicks
            frame_area_x = panel.x + 6
            thumb_h = panel.height - 48 - 18
            for i in range(n):
                fx = frame_area_x + i * (thumb_w + 4)
                if fx + thumb_w > frame_area_x + frame_area_w:
                    break
                fr = pygame.Rect(fx, frame_area_y, thumb_w, thumb_h)
                if fr.collidepoint(pos):
                    self._canvas_switch_frame(i)
                    return True

        # ── Layer control buttons ────────────────────────────────────
        layer_x = mid_x + 4
        layer_w = panel.right - layer_x - 6
        for key, br in self._canvas_bottom_layer_button_rects(panel).items():
            if br.collidepoint(pos):
                if key == "layer_add":
                    self._canvas_add_layer()
                elif key == "layer_dup":
                    self._canvas_duplicate_layer()
                elif key == "layer_ren":
                    self._open_canvas_rename_dialog("layer")
                elif key == "layer_merge":
                    self._canvas_merge_layers()
                elif key == "layer_up":
                    self._canvas_move_layer(1)
                elif key == "layer_down":
                    self._canvas_move_layer(-1)
                elif key == "layer_vis":
                    fi = self.canvas_doc.frame_idx
                    li = self.canvas_doc.layer_idx
                    if fi < len(self.canvas_doc.layer_visible) and li < len(self.canvas_doc.layer_visible[fi]):
                        self.canvas_doc.layer_visible[fi][li] = not self.canvas_doc.layer_visible[fi][li]
                        self._invalidate_canvas_render_cache(fi)
                        self.status = f"Layer {'shown' if self.canvas_doc.layer_visible[fi][li] else 'hidden'}."
                elif key == "layer_del":
                    self._canvas_remove_layer()
                return True

        # ── Layer row clicks ─────────────────────────────────────────
        if self.canvas_doc.frames:
            fi = self.canvas_doc.frame_idx
            frame_layers = self.canvas_doc.frames[fi] if fi < len(self.canvas_doc.frames) else []
            nl = len(frame_layers)
            row_y, visible_rows, scroll, _ = self._canvas_layer_row_metrics(panel)
            start = max(0, nl - 1 - scroll)
            stop = max(-1, start - visible_rows)
            for li in range(start, stop, -1):
                if row_y + 18 > panel.bottom - 2:
                    break
                row_r = pygame.Rect(layer_x, row_y, layer_w, 18)
                if row_r.collidepoint(pos):
                    # Click on eye dot (left 16px) → toggle visibility; rest → select
                    if pos[0] < row_r.x + 16:
                        if fi < len(self.canvas_doc.layer_visible) and li < len(self.canvas_doc.layer_visible[fi]):
                            self.canvas_doc.layer_visible[fi][li] = not self.canvas_doc.layer_visible[fi][li]
                            self._invalidate_canvas_render_cache(fi)
                            self.status = f"Layer {'shown' if self.canvas_doc.layer_visible[fi][li] else 'hidden'}."
                    else:
                        if cmd_held:
                            self._canvas_toggle_layer_selection(li)
                            self.status = f"Selected {len(self._canvas_selected_layer_indices())} layer(s) for merge."
                        else:
                            self.canvas_doc.layer_idx = li
                            self.canvas_doc.selected_layers = {li}
                            self.canvas_doc.history.clear()
                            self.status = f"Switched to layer {li + 1}."
                    return True
                row_y += 20

        if not cmd_held:
            self._canvas_clear_extra_layer_selection()
        return panel.collidepoint(pos)  # swallow any other click in panel

    def _handle_asset_browser_click(self, pos: tuple[int, int]) -> bool:
        modifiers = pygame.key.get_mods()
        cmd_held = bool(modifiers & (pygame.KMOD_META | pygame.KMOD_CTRL))
        # In canvas mode without asset browser open, dispatch to canvas bottom panel
        if self.workspace_mode == "canvas" and not self.canvas_assets_open:
            return self._handle_canvas_bottom_panel_click(pos)

        # Collapse button lives ABOVE the panel rect — must check before the panel guard
        if self._asset_collapse_button_rect().collidepoint(pos):
            self.asset_panel_collapsed = not self.asset_panel_collapsed
            self._update_layout(self.screen_width, self.screen_height)
            self._fit_active_scene()
            self.status = "Asset panel hidden." if self.asset_panel_collapsed else "Asset panel shown."
            return True

        panel = self._asset_panel_rect()
        if not panel.collidepoint(pos):
            return False

        if self.asset_panel_collapsed:
            return True

        for name, rect in self._toolbar_buttons().items():
            if rect.collidepoint(pos):
                if name == "up":
                    self._go_to_parent_asset_dir()
                elif name == "prev":
                    self.asset_library.page = max(self.asset_library.page - 1, 0)
                elif name == "next":
                    self.asset_library.page = min(self.asset_library.page + 1, self._max_asset_page())
                elif name == "import":
                    self._import_assets_via_dialog()
                elif name == "delete":
                    self._delete_selected_asset()
                elif name == "new_folder":
                    self.dialog_mode = "new_folder"
                    self.folder_name_input = ""
                    self.dropdown_open = None
                    self.status = "Type a folder name and press Enter."
                elif name == "refresh":
                    self._refresh_assets()
                    self.status = "Asset browser refreshed."
                return True

        entry = self._asset_at(pos)
        if entry is None:
            return True
        self.selected_asset_rel = entry.rel_path
        if cmd_held:
            self._queue_native_asset_drag(entry.rel_path, pos)
            return True
        if entry.is_dir:
            self._change_asset_dir(entry.path)
        else:
            if self.workspace_mode == "canvas":
                if not self._canvas_editable(entry.rel_path):
                    self.status = "Canvas mode supports PNG/JPG/BMP assets."
                    return True
                # Set up a drag so the asset only loads if dropped over the
                # canvas view — bare clicks just select the thumbnail.
                self.drag_asset_path = entry.rel_path
                self.status = f"Dragging {entry.name}. Drop on the canvas to open it."
                return True
            self.duplicate_drag_mode = False
            self.duplicate_dragging = False
            self.duplicate_drag_last_cell = None
            self.duplicate_drag_cells.clear()
            self.duplicate_drag_count = 0
            self.drag_asset_path = entry.rel_path
            self.status = f"Dragging {entry.name}. Drop in scene to place it."
        return True

    def _handle_dialog_event(self, event: pygame.event.Event) -> bool:
        if self.dialog_mode == "new_canvas":
            _, presets, w_rect, h_rect, create_rect, cancel_rect = self._new_canvas_dialog_layout()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.dialog_mode = None
                    self.status = "New canvas cancelled."
                elif event.key == pygame.K_RETURN:
                    self._confirm_new_canvas()
                elif event.key == pygame.K_TAB:
                    self.canvas_new_focus = "height" if self.canvas_new_focus == "width" else "width"
                elif event.key == pygame.K_BACKSPACE:
                    if self.canvas_new_focus == "height":
                        self.canvas_new_height_input = self.canvas_new_height_input[:-1]
                    else:
                        self.canvas_new_width_input = self.canvas_new_width_input[:-1]
                elif event.unicode and event.unicode.isdigit():
                    if self.canvas_new_focus == "height":
                        self.canvas_new_height_input += event.unicode
                    else:
                        self.canvas_new_width_input += event.unicode
                return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if create_rect.collidepoint(event.pos):
                    self._confirm_new_canvas()
                elif cancel_rect.collidepoint(event.pos):
                    self.dialog_mode = None
                    self.status = "New canvas cancelled."
                elif w_rect.collidepoint(event.pos):
                    self.canvas_new_focus = "width"
                elif h_rect.collidepoint(event.pos):
                    self.canvas_new_focus = "height"
                else:
                    for sz, rect in presets:
                        if rect.collidepoint(event.pos):
                            self.canvas_new_width_input = str(sz[0])
                            self.canvas_new_height_input = str(sz[1])
                            break
                return True
            return event.type in {pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.MOUSEWHEEL}

        if self.dialog_mode == "new_scene":
            _, options, width_rect, height_rect, create_rect, cancel_rect = self._new_scene_dialog_layout()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.dialog_mode = None
                    self.scene_size_focus = None
                    self.status = "New scene cancelled."
                elif event.key == pygame.K_RETURN:
                    self._confirm_new_scene()
                elif event.key == pygame.K_TAB:
                    self.scene_size_focus = "height" if self.scene_size_focus == "width" else "width"
                elif event.key == pygame.K_BACKSPACE:
                    if self.scene_size_focus == "height":
                        self.custom_scene_height_input = self.custom_scene_height_input[:-1]
                    else:
                        self.scene_size_focus = "width"
                        self.custom_scene_width_input = self.custom_scene_width_input[:-1]
                elif event.unicode and event.unicode.isdigit():
                    if self.scene_size_focus == "height":
                        self.custom_scene_height_input += event.unicode
                    else:
                        self.scene_size_focus = "width"
                        self.custom_scene_width_input += event.unicode
                return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if create_rect.collidepoint(event.pos):
                    self._confirm_new_scene()
                elif cancel_rect.collidepoint(event.pos):
                    self.dialog_mode = None
                    self.scene_size_focus = None
                    self.status = "New scene cancelled."
                elif width_rect.collidepoint(event.pos):
                    self.scene_size_focus = "width"
                elif height_rect.collidepoint(event.pos):
                    self.scene_size_focus = "height"
                else:
                    self.scene_size_focus = None
                    for size, rect in options:
                        if rect.collidepoint(event.pos):
                            self.pending_scene_size = size
                            self.custom_scene_width_input = str(size[0])
                            self.custom_scene_height_input = str(size[1])
                            self.status = f"Selected {size[0]}x{size[1]} for the new scene."
                            break
                return True
            return event.type in {pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.MOUSEWHEEL}

        if self.dialog_mode == "new_folder":
            _, _, create_rect, cancel_rect = self._new_folder_dialog_layout()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.dialog_mode = None
                    self.folder_name_input = ""
                    self.status = "Folder creation cancelled."
                elif event.key == pygame.K_RETURN:
                    self._create_folder()
                elif event.key == pygame.K_BACKSPACE:
                    self.folder_name_input = self.folder_name_input[:-1]
                else:
                    if event.unicode and event.unicode.isprintable() and event.unicode not in {"\r", "\n"}:
                        self.folder_name_input += event.unicode
                return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if create_rect.collidepoint(event.pos):
                    self._create_folder()
                elif cancel_rect.collidepoint(event.pos):
                    self.dialog_mode = None
                    self.folder_name_input = ""
                    self.status = "Folder creation cancelled."
                return True
            return event.type in {pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.MOUSEWHEEL}

        if self.dialog_mode == "save_scene":
            _, _, save_rect, cancel_rect = self._save_scene_dialog_layout()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.dialog_mode = None
                    self.status = "Save scene cancelled."
                elif event.key == pygame.K_RETURN:
                    self._confirm_save_scene()
                elif event.key == pygame.K_BACKSPACE:
                    self.scene_name_input = self.scene_name_input[:-1]
                else:
                    if event.unicode and event.unicode.isprintable() and event.unicode not in {"\r", "\n"}:
                        self.scene_name_input += event.unicode
                return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if save_rect.collidepoint(event.pos):
                    self._confirm_save_scene()
                elif cancel_rect.collidepoint(event.pos):
                    self.dialog_mode = None
                    self.status = "Save scene cancelled."
                return True
            return event.type in {pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.MOUSEWHEEL}

        if self.dialog_mode == "color_picker":
            panel, wheel, value, _, alpha_rect, apply_rect, cancel_rect = self._canvas_color_picker_layout()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._close_canvas_color_picker(apply=False)
                elif event.key == pygame.K_RETURN:
                    self._close_canvas_color_picker(apply=True)
                return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if apply_rect.collidepoint(event.pos):
                    self._close_canvas_color_picker(apply=True)
                elif cancel_rect.collidepoint(event.pos):
                    self._close_canvas_color_picker(apply=False)
                elif wheel.collidepoint(event.pos):
                    self.canvas_color_picker_drag = "wheel"
                    self._update_canvas_color_picker(event.pos)
                elif value.collidepoint(event.pos):
                    self.canvas_color_picker_drag = "value"
                    self._update_canvas_color_picker(event.pos)
                elif alpha_rect.collidepoint(event.pos):
                    self.canvas_color_picker_drag = "alpha"
                    self._update_canvas_color_picker(event.pos)
                elif not panel.collidepoint(event.pos):
                    self._close_canvas_color_picker(apply=False)
                return True
            if event.type == pygame.MOUSEMOTION and self.canvas_color_picker_drag is not None:
                self._update_canvas_color_picker(event.pos)
                return True
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.canvas_color_picker_drag = None
                return True
            return event.type == pygame.MOUSEWHEEL

        if self.dialog_mode == "canvas_rename":
            _, _, save_rect, cancel_rect = self._canvas_rename_dialog_layout()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.dialog_mode = None
                    self.canvas_rename_kind = None
                    self.status = "Rename cancelled."
                elif event.key == pygame.K_RETURN:
                    self._confirm_canvas_rename()
                elif event.key == pygame.K_BACKSPACE:
                    self.canvas_name_input = self.canvas_name_input[:-1]
                elif event.unicode and event.unicode.isprintable() and event.unicode not in {"\r", "\n"}:
                    self.canvas_name_input += event.unicode
                return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if save_rect.collidepoint(event.pos):
                    self._confirm_canvas_rename()
                elif cancel_rect.collidepoint(event.pos):
                    self.dialog_mode = None
                    self.canvas_rename_kind = None
                    self.status = "Rename cancelled."
                return True
            return event.type in {pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.MOUSEWHEEL}

        return False

    def _handle_canvas_focus_layers_click(self, pos: tuple[int, int]) -> bool:
        if not (self.workspace_mode == "canvas" and self.canvas_focus_mode):
            return False
        panel = self._canvas_focus_layer_panel_rect()
        if not panel.collidepoint(pos):
            return False
        modifiers = pygame.key.get_mods()
        cmd_held = bool(modifiers & (pygame.KMOD_META | pygame.KMOD_CTRL))
        for key, br in self._canvas_focus_layer_button_rects().items():
            if br.collidepoint(pos):
                if key == "layer_add":
                    self._canvas_add_layer()
                elif key == "layer_dup":
                    self._canvas_duplicate_layer()
                elif key == "layer_ren":
                    self._open_canvas_rename_dialog("layer")
                elif key == "layer_merge":
                    self._canvas_merge_layers()
                elif key == "layer_up":
                    self._canvas_move_layer(1)
                elif key == "layer_down":
                    self._canvas_move_layer(-1)
                elif key == "layer_vis":
                    fi = self.canvas_doc.frame_idx
                    li = self.canvas_doc.layer_idx
                    if fi < len(self.canvas_doc.layer_visible) and li < len(self.canvas_doc.layer_visible[fi]):
                        self.canvas_doc.layer_visible[fi][li] = not self.canvas_doc.layer_visible[fi][li]
                        self._invalidate_canvas_render_cache(fi)
                        self.status = f"Layer {'shown' if self.canvas_doc.layer_visible[fi][li] else 'hidden'}."
                elif key == "layer_del":
                    self._canvas_remove_layer()
                return True
        rows_rect = self._canvas_focus_layer_rows_rect()
        if rows_rect.collidepoint(pos) and self.canvas_doc.frames:
            fi = self.canvas_doc.frame_idx
            frame_layers = self.canvas_doc.frames[fi] if fi < len(self.canvas_doc.frames) else []
            nl = len(frame_layers)
            row_y = rows_rect.y + 6
            row_h = 20
            visible_rows = max(1, rows_rect.height // row_h)
            start = max(0, nl - 1 - self.canvas_layer_scroll)
            stop = max(-1, start - visible_rows)
            for li in range(start, stop, -1):
                row_r = pygame.Rect(rows_rect.x + 4, row_y, rows_rect.width - 8, 18)
                if row_r.collidepoint(pos):
                    if pos[0] < row_r.x + 16:
                        if fi < len(self.canvas_doc.layer_visible) and li < len(self.canvas_doc.layer_visible[fi]):
                            self.canvas_doc.layer_visible[fi][li] = not self.canvas_doc.layer_visible[fi][li]
                            self._invalidate_canvas_render_cache(fi)
                            self.status = f"Layer {'shown' if self.canvas_doc.layer_visible[fi][li] else 'hidden'}."
                    else:
                        if cmd_held:
                            self._canvas_toggle_layer_selection(li)
                        else:
                            self._canvas_reset_layer_selection(li)
                    return True
                row_y += row_h
        return True
