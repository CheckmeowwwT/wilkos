from __future__ import annotations

import pygame

try:
    from .core.app_shell import CoreAppMixin
    from .browser.asset_browser import AssetBrowserMixin
    from .history.undo_redo import HistoryMixin
    from .scene.project_io import SceneProjectIOMixin
    from .scene.editing import SceneEditingMixin
    from .canvas.document import CanvasDocumentMixin
    from .canvas.tools import CanvasToolsMixin
    from .ui.layout import UILayoutMixin
    from .ui.events import UIEventsMixin
    from .ui.render import UIRenderMixin
except ImportError:
    from core.app_shell import CoreAppMixin  # type: ignore[no-redef]
    from browser.asset_browser import AssetBrowserMixin  # type: ignore[no-redef]
    from history.undo_redo import HistoryMixin  # type: ignore[no-redef]
    from scene.project_io import SceneProjectIOMixin  # type: ignore[no-redef]
    from scene.editing import SceneEditingMixin  # type: ignore[no-redef]
    from canvas.document import CanvasDocumentMixin  # type: ignore[no-redef]
    from canvas.tools import CanvasToolsMixin  # type: ignore[no-redef]
    from ui.layout import UILayoutMixin  # type: ignore[no-redef]
    from ui.events import UIEventsMixin  # type: ignore[no-redef]
    from ui.render import UIRenderMixin  # type: ignore[no-redef]


class SceneEditorApp(
    CoreAppMixin,
    AssetBrowserMixin,
    HistoryMixin,
    SceneProjectIOMixin,
    SceneEditingMixin,
    CanvasDocumentMixin,
    CanvasToolsMixin,
    UILayoutMixin,
    UIEventsMixin,
    UIRenderMixin,
):
    @property
    def canvas_tabs(self) -> list[dict[str, object]]:
        return self.canvas_session.tabs

    @canvas_tabs.setter
    def canvas_tabs(self, val: list[dict[str, object]]) -> None:
        self.canvas_session.tabs = val

    @property
    def canvas_tab_idx(self) -> int:
        return self.canvas_session.tab_idx

    @canvas_tab_idx.setter
    def canvas_tab_idx(self, val: int) -> None:
        self.canvas_session.tab_idx = val

    @property
    def canvas_next_tab_number(self) -> int:
        return self.canvas_session.next_tab_number

    @canvas_next_tab_number.setter
    def canvas_next_tab_number(self, val: int) -> None:
        self.canvas_session.next_tab_number = val

    @property
    def canvas_asset_rel(self) -> str | None:
        return self.canvas_doc.asset_rel

    @canvas_asset_rel.setter
    def canvas_asset_rel(self, val: str | None) -> None:
        self.canvas_doc.asset_rel = val

    @property
    def canvas_frames(self) -> list[list[pygame.Surface]]:
        return self.canvas_doc.frames

    @canvas_frames.setter
    def canvas_frames(self, val: list[list[pygame.Surface]]) -> None:
        self.canvas_doc.frames = val

    @property
    def canvas_frame_names(self) -> list[str]:
        return self.canvas_doc.frame_names

    @canvas_frame_names.setter
    def canvas_frame_names(self, val: list[str]) -> None:
        self.canvas_doc.frame_names = val

    @property
    def canvas_layer_names(self) -> list[list[str]]:
        return self.canvas_doc.layer_names

    @canvas_layer_names.setter
    def canvas_layer_names(self, val: list[list[str]]) -> None:
        self.canvas_doc.layer_names = val

    @property
    def canvas_layer_visible(self) -> list[list[bool]]:
        return self.canvas_doc.layer_visible

    @canvas_layer_visible.setter
    def canvas_layer_visible(self, val: list[list[bool]]) -> None:
        self.canvas_doc.layer_visible = val

    @property
    def canvas_frame_idx(self) -> int:
        return self.canvas_doc.frame_idx

    @canvas_frame_idx.setter
    def canvas_frame_idx(self, val: int) -> None:
        self.canvas_doc.frame_idx = val

    @property
    def canvas_layer_idx(self) -> int:
        return self.canvas_doc.layer_idx

    @canvas_layer_idx.setter
    def canvas_layer_idx(self, val: int) -> None:
        self.canvas_doc.layer_idx = val

    @property
    def canvas_selected_layers(self) -> set[int]:
        return self.canvas_doc.selected_layers

    @canvas_selected_layers.setter
    def canvas_selected_layers(self, val: set[int]) -> None:
        self.canvas_doc.selected_layers = val

    @property
    def canvas_history(self):
        return self.canvas_doc.history

    @canvas_history.setter
    def canvas_history(self, val) -> None:
        self.canvas_doc.history = val

    @property
    def _canvas_frame_versions(self) -> list[int]:
        return self.canvas_doc.frame_versions

    @_canvas_frame_versions.setter
    def _canvas_frame_versions(self, val: list[int]) -> None:
        self.canvas_doc.frame_versions = val

    @property
    def _canvas_composite_cache(self) -> dict[tuple[int, int, int], pygame.Surface]:
        return self.canvas_doc.composite_cache

    @_canvas_composite_cache.setter
    def _canvas_composite_cache(self, val: dict[tuple[int, int, int], pygame.Surface]) -> None:
        self.canvas_doc.composite_cache = val

    @property
    def _canvas_scaled_surface_cache(self) -> dict[tuple[int, int, int, int, int], pygame.Surface]:
        return self.canvas_doc.scaled_surface_cache

    @_canvas_scaled_surface_cache.setter
    def _canvas_scaled_surface_cache(self, val: dict[tuple[int, int, int, int, int], pygame.Surface]) -> None:
        self.canvas_doc.scaled_surface_cache = val

    @property
    def _canvas_visible_surface_cache(self) -> dict[tuple[int, int, int, int, int, int, int, int, int, int], pygame.Surface]:
        return self.canvas_doc.visible_surface_cache

    @_canvas_visible_surface_cache.setter
    def _canvas_visible_surface_cache(
        self,
        val: dict[tuple[int, int, int, int, int, int, int, int, int, int], pygame.Surface],
    ) -> None:
        self.canvas_doc.visible_surface_cache = val

    @property
    def _canvas_mipmap_cache(self) -> dict[tuple[int, int, int, int], pygame.Surface]:
        return self.canvas_doc.mipmap_cache

    @_canvas_mipmap_cache.setter
    def _canvas_mipmap_cache(self, val: dict[tuple[int, int, int, int], pygame.Surface]) -> None:
        self.canvas_doc.mipmap_cache = val

    @property
    def canvas_surface(self) -> pygame.Surface | None:  # type: ignore[return]
        if not self.canvas_doc.frames:
            return None
        fi = self.canvas_doc.frame_idx
        li = self.canvas_doc.layer_idx
        if fi >= len(self.canvas_doc.frames):
            return None
        frame = self.canvas_doc.frames[fi]
        if not frame or li >= len(frame):
            return None
        return frame[li]

    @canvas_surface.setter
    def canvas_surface(self, val: pygame.Surface | None) -> None:
        if val is None:
            self.canvas_doc.frames = []
            self.canvas_doc.frame_names = []
            self.canvas_doc.layer_names = []
            self.canvas_doc.layer_visible = []
            self.canvas_doc.frame_idx = 0
            self.canvas_doc.layer_idx = 0
            self.canvas_doc.selected_layers = set()
            if hasattr(self, "_canvas_frame_versions"):
                self.canvas_doc.frame_versions = []
            if hasattr(self, "_canvas_composite_cache"):
                self.canvas_doc.composite_cache.clear()
            if hasattr(self, "_canvas_scaled_surface_cache"):
                self.canvas_doc.scaled_surface_cache.clear()
            if hasattr(self, "_canvas_visible_surface_cache"):
                self.canvas_doc.visible_surface_cache.clear()
            if hasattr(self, "_canvas_mipmap_cache"):
                self.canvas_doc.mipmap_cache.clear()
            if hasattr(self, "_clear_canvas_preview_caches"):
                self._clear_canvas_preview_caches()
        else:
            fi = self.canvas_doc.frame_idx
            li = self.canvas_doc.layer_idx
            if (self.canvas_doc.frames
                    and fi < len(self.canvas_doc.frames)
                    and self.canvas_doc.frames[fi]
                    and li < len(self.canvas_doc.frames[fi])):
                self.canvas_doc.frames[fi][li] = val
            else:
                self.canvas_doc.frames = [[val]]
                self.canvas_doc.frame_names = ["Frame 1"]
                self.canvas_doc.layer_names = [["Layer 1"]]
                self.canvas_doc.layer_visible = [[True]]
                self.canvas_doc.frame_idx = 0
                self.canvas_doc.layer_idx = 0
                self.canvas_doc.selected_layers = {0}
            if hasattr(self, "_canvas_frame_versions"):
                self._sync_canvas_render_cache_state()

    def run(self) -> None:
        pygame.init()
        pygame.display.set_caption("Scene Editor")
        screen = pygame.display.set_mode((self.screen_width, self.screen_height), self.window_flags)
        pygame.event.set_allowed(None)
        pygame.event.set_allowed([
            pygame.QUIT,
            pygame.KEYDOWN,
            pygame.MOUSEBUTTONDOWN,
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
            pygame.MOUSEWHEEL,
            pygame.DROPFILE,
            pygame.VIDEORESIZE,
            pygame.WINDOWSIZECHANGED,
            pygame.MULTIGESTURE,
            pygame.FINGERMOTION,
        ])
        title_font = self._make_font(20, bold=True)
        font = self._make_font(18)
        small = self._make_font(14)
        clock = pygame.time.Clock()
        self.background_surface = self._build_background()
        self._refresh_assets()
        self._fit_active_scene()

        running = True
        while running:
            self.drag_pos = pygame.mouse.get_pos()
            self._update_canvas_focus_tools_hover()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    continue

                if self.dialog_mode is not None and self._handle_dialog_event(event):
                    continue

                if event.type == pygame.KEYDOWN:
                    modifiers = pygame.key.get_mods()
                    cmd = bool(modifiers & (pygame.KMOD_META | pygame.KMOD_CTRL))
                    shift = bool(modifiers & pygame.KMOD_SHIFT)
                    if event.key == pygame.K_ESCAPE:
                        if self.workspace_mode == "canvas" and self.canvas_sel_transform:
                            self._canvas_cancel_sel_transform()
                        elif self.workspace_mode == "canvas" and self.canvas_paste_active:
                            self.canvas_paste_active = False
                            self.status = "Paste cancelled."
                        elif self.workspace_mode == "canvas" and self.canvas_selection_pixels:
                            self.canvas_selection_pixels.clear()
                            self.status = "Selection cleared."
                        else:
                            running = False
                    elif event.key == pygame.K_DELETE and self.workspace_mode == "canvas" and self.canvas_selection_pixels:
                        if self.canvas_surface is not None:
                            self._canvas_push_undo()
                            for px, py in self.canvas_selection_pixels:
                                self.canvas_surface.set_at((px, py), (0, 0, 0, 0))
                            self._mark_canvas_changed()
                            self.canvas_selection_pixels.clear()
                            self.status = "Deleted selected pixels."
                    elif event.key == pygame.K_BACKSPACE and self.workspace_mode == "canvas" and self.canvas_selection_pixels:
                        if self.canvas_surface is not None:
                            self._canvas_push_undo()
                            for px, py in self.canvas_selection_pixels:
                                self.canvas_surface.set_at((px, py), (0, 0, 0, 0))
                            self._mark_canvas_changed()
                            self.canvas_selection_pixels.clear()
                            self.status = "Deleted selected pixels."
                    elif event.key == pygame.K_F11:
                        screen = self._toggle_fullscreen(screen)
                    elif event.key == pygame.K_RETURN and (modifiers & pygame.KMOD_ALT):
                        screen = self._toggle_fullscreen(screen)
                    elif event.key == pygame.K_RETURN and self.workspace_mode == "canvas" and self.canvas_paste_active:
                        self._canvas_paste_commit()
                    # ── Canvas text input fields ────────────────────────
                    elif self.workspace_mode == "canvas" and self.canvas_blend_focus and not cmd:
                        if event.key in {pygame.K_RETURN, pygame.K_ESCAPE}:
                            try:
                                pct = max(0, min(100, int(self.canvas_blend_input or "50")))
                            except ValueError:
                                pct = 50
                            self.canvas_blend_strength = pct / 100.0
                            self.canvas_blend_input = str(pct)
                            self.canvas_blend_focus = False
                        elif event.key == pygame.K_BACKSPACE:
                            self.canvas_blend_input = self.canvas_blend_input[:-1]
                        elif event.unicode and event.unicode.isdigit():
                            self.canvas_blend_input += event.unicode
                    elif self.workspace_mode == "canvas" and self.canvas_brush_size_focus and not cmd:
                        if event.key == pygame.K_RETURN or event.key == pygame.K_ESCAPE:
                            try:
                                self.canvas_brush_size = max(1, min(128, int(self.canvas_brush_size_input or "1")))
                            except ValueError:
                                self.canvas_brush_size = 1
                            self.canvas_brush_size_input = str(self.canvas_brush_size)
                            self.canvas_brush_size_focus = False
                        elif event.key == pygame.K_BACKSPACE:
                            self.canvas_brush_size_input = self.canvas_brush_size_input[:-1]
                        elif event.unicode and event.unicode.isdigit():
                            self.canvas_brush_size_input += event.unicode
                    elif self.workspace_mode == "canvas" and not cmd and event.key in {
                        pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
                    }:
                        slot_idx = event.key - pygame.K_1
                        self._canvas_apply_quick_palette_slot(slot_idx)
                    # ── Canvas paste nudge ──────────────────────────────
                    elif self.workspace_mode == "canvas" and self.canvas_paste_active and not cmd:
                        ox, oy = self.canvas_paste_origin
                        nudge = 10 if shift else 1
                        if event.key == pygame.K_LEFT:
                            self.canvas_paste_origin = (ox - nudge, oy)
                        elif event.key == pygame.K_RIGHT:
                            self.canvas_paste_origin = (ox + nudge, oy)
                        elif event.key == pygame.K_UP:
                            self.canvas_paste_origin = (ox, oy - nudge)
                        elif event.key == pygame.K_DOWN:
                            self.canvas_paste_origin = (ox, oy + nudge)
                    # ── Canvas Cmd shortcuts ────────────────────────────
                    elif self.workspace_mode == "canvas" and cmd and event.key == pygame.K_z:
                        if shift:
                            self._canvas_redo()
                        else:
                            self._canvas_undo()
                    elif self.workspace_mode == "scene" and cmd and event.key == pygame.K_z:
                        if shift:
                            self._scene_redo()
                        else:
                            self._scene_undo()
                    elif self.workspace_mode == "canvas" and cmd and event.key == pygame.K_c:
                        self._canvas_copy_selection()
                    elif self.workspace_mode == "canvas" and cmd and event.key == pygame.K_v:
                        self._canvas_paste_start()
                    # ── Canvas selection transforms (no Cmd) ───────────
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_LEFTBRACKET and not cmd:
                        self._canvas_rotate_selection(cw=False)
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_RIGHTBRACKET and not cmd:
                        self._canvas_rotate_selection(cw=True)
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_h and not cmd:
                        self._canvas_flip_selection(horizontal=True)
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_j and not cmd:
                        self._canvas_flip_selection(horizontal=False)
                    # ── Frame navigation ────────────────────────────────
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_COMMA and shift and not cmd:
                        self._canvas_move_frame(-1)
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_PERIOD and shift and not cmd:
                        self._canvas_move_frame(1)
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_COMMA and not cmd:
                        self._canvas_switch_frame(max(0, self.canvas_doc.frame_idx - 1))
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_PERIOD and not cmd:
                        self._canvas_switch_frame(min(len(self.canvas_doc.frames) - 1, self.canvas_doc.frame_idx + 1))
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_COMMA and cmd:
                        self._canvas_add_frame()
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_PERIOD and cmd:
                        self._canvas_duplicate_frame()
                    # ── Layer navigation ────────────────────────────────
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_QUOTE and not cmd:
                        new_li = max(0, self.canvas_doc.layer_idx - 1)
                        if new_li != self.canvas_doc.layer_idx:
                            self.canvas_doc.layer_idx = new_li
                            self.canvas_doc.history.clear()
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_SEMICOLON and not cmd:
                        fi = self.canvas_doc.frame_idx
                        max_li = len(self.canvas_doc.frames[fi]) - 1 if self.canvas_doc.frames else 0
                        new_li = min(max_li, self.canvas_doc.layer_idx + 1)
                        if new_li != self.canvas_doc.layer_idx:
                            self.canvas_doc.layer_idx = new_li
                            self.canvas_doc.history.clear()
                    # ── VP tool reset ────────────────────────────────────
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_v and not cmd:
                        if self.canvas_tool == "vpoint":
                            self.canvas_vp = None
                            self.status = "Vanishing point cleared."
                    # ── Canvas selection transform gizmos ────────────────
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_m and not cmd:
                        if self.canvas_selection_pixels:
                            self._canvas_enter_sel_transform("move")
                        else:
                            self.canvas_tool = "move"
                            self.status = "Move tool: drag to pan canvas."
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_r and not cmd:
                        if self.canvas_selection_pixels:
                            self._canvas_enter_sel_transform("rotate")
                        elif self.canvas_surface is not None:
                            # No selection: rotate whole canvas 90° CW
                            self._canvas_push_undo()
                            self.canvas_surface = pygame.transform.rotate(self.canvas_surface, -90)
                            self._mark_canvas_changed()
                            self.status = "Canvas rotated 90° CW."
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_s and not cmd:
                        if self.canvas_selection_pixels:
                            self._canvas_enter_sel_transform("scale")
                        # (no-sel case: S without Cmd does nothing in canvas mode)
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_RETURN and self.canvas_sel_transform:
                        self._canvas_commit_sel_transform()
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_ESCAPE and self.canvas_sel_transform:
                        self._canvas_cancel_sel_transform()
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_SPACE and not cmd:
                        self._toggle_canvas_preview()
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_g and cmd and shift:
                        self._export_canvas_gif()
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_e and cmd and shift:
                        self._export_canvas_spritesheet()
                    elif event.key == pygame.K_s and cmd:
                        self._save_project()
                    elif event.key == pygame.K_o and (modifiers & (pygame.KMOD_META | pygame.KMOD_CTRL)):
                        self._open_project()
                    elif event.key == pygame.K_n and (modifiers & (pygame.KMOD_META | pygame.KMOD_CTRL)):
                        self._open_new_scene_dialog()
                    elif event.key == pygame.K_e and (modifiers & (pygame.KMOD_META | pygame.KMOD_CTRL)):
                        self._export_active_scene_png()
                    elif self.workspace_mode == "scene" and event.key in {pygame.K_DELETE, pygame.K_BACKSPACE} and (
                        self.selected_sprite_id is not None or self.selected_sprite_ids
                    ):
                        self._remove_selected_sprites()
                    elif self.workspace_mode == "scene" and event.key in {pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS}:
                        self._resize_selected_sprite(1.08)
                    elif self.workspace_mode == "scene" and event.key in {pygame.K_MINUS, pygame.K_KP_MINUS}:
                        self._resize_selected_sprite(0.92)
                    elif self.workspace_mode == "scene" and event.key == pygame.K_r:
                        self._toggle_rotation_gizmo()
                    elif self.workspace_mode == "scene" and event.key == pygame.K_d and not (modifiers & (pygame.KMOD_META | pygame.KMOD_CTRL)):
                        self._arm_duplicate_drag_mode()
                    elif self.workspace_mode == "scene" and event.key == pygame.K_c and (modifiers & (pygame.KMOD_META | pygame.KMOD_CTRL)):
                        self._copy_selected_sprite()
                    elif self.workspace_mode == "scene" and event.key == pygame.K_v and not (modifiers & (pygame.KMOD_META | pygame.KMOD_CTRL)):
                        self._paste_sprite(self._board_local_at(self.drag_pos))
                    elif self.workspace_mode == "scene" and event.key == pygame.K_m and not (modifiers & (pygame.KMOD_META | pygame.KMOD_CTRL)):
                        self._merge_selected_assets()
                    elif self.workspace_mode == "scene" and event.key == pygame.K_LEFT:
                        if not self._nudge_selected_sprite(-4, 0):
                            self.camera_x -= 24 / max(self.zoom, 0.001)
                            self._clamp_camera()
                    elif self.workspace_mode == "scene" and event.key == pygame.K_RIGHT:
                        if not self._nudge_selected_sprite(4, 0):
                            self.camera_x += 24 / max(self.zoom, 0.001)
                            self._clamp_camera()
                    elif self.workspace_mode == "scene" and event.key == pygame.K_UP:
                        if not self._nudge_selected_sprite(0, -4):
                            self.camera_y -= 24 / max(self.zoom, 0.001)
                            self._clamp_camera()
                    elif self.workspace_mode == "scene" and event.key == pygame.K_DOWN:
                        if not self._nudge_selected_sprite(0, 4):
                            self.camera_y += 24 / max(self.zoom, 0.001)
                            self._clamp_camera()
                elif event.type == pygame.VIDEORESIZE:
                    screen = self._resize_window(screen, event.size)
                elif event.type == pygame.WINDOWSIZECHANGED and not self.is_fullscreen:
                    window_size = (max(int(event.x), self.min_window_size[0]), max(int(event.y), self.min_window_size[1]))
                    if window_size != (self.screen_width, self.screen_height):
                        screen = self._resize_window(screen, window_size)
                elif event.type == pygame.DROPFILE:
                    self._copy_dropped_asset(event.file)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        modifiers = pygame.key.get_mods()
                        cmd_held = bool(modifiers & (pygame.KMOD_META | pygame.KMOD_CTRL))
                        focus_canvas = self.workspace_mode == "canvas" and self.canvas_focus_mode
                        if (
                            self.workspace_mode == "canvas"
                            and not cmd_held
                            and len(self._canvas_selected_layer_indices()) > 1
                        ):
                            panel_rect = self._canvas_focus_layer_panel_rect() if focus_canvas else self._asset_panel_rect()
                            if self.canvas_assets_open or self.canvas_bottom_collapsed or not panel_rect.collidepoint(event.pos):
                                self._canvas_clear_extra_layer_selection()
                        if not focus_canvas and self._asset_resize_handle_rect().collidepoint(event.pos):
                            self.resizing_asset_panel = True
                            self.dropdown_open = None
                            self.status = "Resizing asset browser."
                            continue
                        if self.workspace_mode == "canvas" and not self.canvas_assets_open and not focus_canvas:
                            bottom_panel = self._asset_panel_rect()
                            if self._canvas_bottom_split_handle_rect(bottom_panel).collidepoint(event.pos):
                                self.canvas_bottom_split_dragging = True
                                self.dropdown_open = None
                                self.status = "Resizing frame/layer split."
                                continue
                        if self.workspace_mode == "canvas":
                            if focus_canvas and self._handle_canvas_focus_layers_click(event.pos):
                                continue
                            if self._canvas_inspector_left_handle_rect().collidepoint(event.pos):
                                self.canvas_inspector_resize_left = True
                                self.dropdown_open = None
                                self.status = "Resizing canvas tools width."
                                continue
                            if self._canvas_inspector_top_handle_rect().collidepoint(event.pos):
                                self.canvas_inspector_resize_top = True
                                self.dropdown_open = None
                                self.status = "Moving canvas tools down."
                                continue
                        if not focus_canvas:
                            if self._handle_menu_click(event.pos):
                                continue
                            if self._handle_tab_click(event.pos):
                                continue
                            if self._handle_asset_browser_click(event.pos):
                                continue
                        if self._handle_canvas_click(event.pos):
                            continue
                        local = self._board_local_at(event.pos)
                        if local is not None:
                            if self.duplicate_drag_mode:
                                self._push_scene_undo()
                                self.duplicate_dragging = True
                                self.duplicate_drag_last_cell = None
                                self.duplicate_drag_cells.clear()
                                self.duplicate_drag_count = 0
                                self._stamp_duplicate_drag(local, force=True)
                                self.status = "Duplicating..."
                                continue
                            modifiers = pygame.key.get_mods()
                            additive_select = bool(modifiers & pygame.KMOD_SHIFT)
                            axis = self._rotation_gizmo_hit_axis(event.pos)
                            if axis is not None:
                                self._push_scene_undo()
                            if axis is not None and self._start_rotation_gizmo_drag(axis, event.pos):
                                continue
                            resized = False
                            for corner, handle_rect in self._selected_resize_handles().items():
                                if handle_rect.collidepoint(event.pos):
                                    self._push_scene_undo()
                                    self._begin_corner_resize(corner)
                                    resized = True
                                    break
                            if resized:
                                continue

                            selection_rect = self._selection_screen_rect()
                            sprite = None
                            if selection_rect is not None and selection_rect.collidepoint(event.pos):
                                sprite = self._selected_sprite()
                            if sprite is None:
                                sprite = self._sprite_at_screen(event.pos)
                            if sprite is not None:
                                if additive_select:
                                    ids = set(self.selected_sprite_ids)
                                    ids.add(sprite.sprite_id)
                                    self._set_selection(ids, primary=sprite.sprite_id)
                                elif sprite.sprite_id not in self.selected_sprite_ids:
                                    self._set_selection({sprite.sprite_id}, primary=sprite.sprite_id)
                                elif not self.selected_sprite_ids:
                                    self._set_selection({sprite.sprite_id}, primary=sprite.sprite_id)
                                self.resizing_sprite_id = None
                                self._push_scene_undo()
                                self._sort_selected_to_front()
                                self.dragging_group_ids = set(self.selected_sprite_ids)
                                if not self.dragging_group_ids and self.selected_sprite_id is not None:
                                    self.dragging_group_ids = {self.selected_sprite_id}
                                self.drag_group_start_local = local
                                self.drag_group_origins = {}
                                for sid in self.dragging_group_ids:
                                    found = self._sprite_by_id(sid)
                                    if found is not None:
                                        self.drag_group_origins[sid] = (found.x, found.y)
                                self.status = f"Moving {len(self.dragging_group_ids)} selected asset(s)."
                            else:
                                self.resizing_sprite_id = None
                                self.resizing_sprite_ids = []
                                self.resize_source_bounds = None
                                self.resize_source_sprites = {}
                                self.dragging_group_ids.clear()
                                self.marquee_selecting = True
                                self.marquee_start = event.pos
                                self.marquee_current = event.pos
                                self.marquee_additive = additive_select
                                if not additive_select:
                                    self._clear_selection()
                                self.dropdown_open = None
                        else:
                            self.resizing_sprite_id = None
                            self.resizing_sprite_ids = []
                            self.resize_source_bounds = None
                            self.resize_source_sprites = {}
                            self.dragging_group_ids.clear()
                            self.dropdown_open = None
                    elif self.workspace_mode == "canvas" and event.button in {2, 3}:
                        view = self._canvas_view_rect(self._canvas_workspace_panel_rect())
                        if view.collidepoint(event.pos):
                            if self.canvas_selection_pixels:
                                if self.canvas_sel_transform != "move" or not self.canvas_sel_lift:
                                    self._canvas_enter_sel_transform("move", auto_commit=True)
                                self.canvas_sel_drag_start = event.pos
                                self.canvas_drawing = True
                            else:
                                self.canvas_panning = True
                                self.canvas_pan_anchor = event.pos
                                self.canvas_pan_origin = (self.canvas_offset_x, self.canvas_offset_y)
                    elif self.workspace_mode == "scene" and event.button in {2, 3} and self._scene_viewport_rect().collidepoint(event.pos):
                        self.panning = True
                        self.pan_anchor = event.pos
                        self.pan_origin = (self.camera_x, self.camera_y)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self._cancel_native_asset_drag()
                        self._handle_canvas_mouse_up()
                        if self.resizing_asset_panel:
                            self.resizing_asset_panel = False
                            self.status = f"Asset browser height set to {self.asset_h}px."
                        if self.canvas_bottom_split_dragging:
                            self.canvas_bottom_split_dragging = False
                            self.status = "Frame/layer split updated."
                        if self.canvas_inspector_resize_left:
                            self.canvas_inspector_resize_left = False
                            self.status = f"Canvas tools width set to {self.canvas_inspector_width}px."
                        if self.canvas_inspector_resize_top:
                            self.canvas_inspector_resize_top = False
                            self.status = "Canvas tools position updated."
                        if self.resizing_sprite_id is not None:
                            self.resizing_sprite_id = None
                            self.resizing_sprite_ids = []
                            self.resize_source_bounds = None
                            self.resize_source_sprites = {}
                        if self.rotation_gizmo_axis is not None:
                            self.rotation_gizmo_axis = None
                            self.rotation_gizmo_start_values = {}
                        if self.marquee_selecting:
                            selection_rect = self._marquee_rect()
                            hit_ids = {
                                sprite.sprite_id
                                for sprite in self.active_scene.sprites
                                if self._sprite_screen_rect(sprite).colliderect(selection_rect)
                            }
                            if self.marquee_additive:
                                hit_ids |= self.selected_sprite_ids
                            self._set_selection(hit_ids)
                            self.marquee_selecting = False
                        local = self._board_local_at(event.pos)
                        if self.drag_asset_path is not None:
                            if local is not None:
                                if not self._place_saved_scene_asset(self.drag_asset_path, local):
                                    self._place_new_sprite(self.drag_asset_path, local)
                        if self.duplicate_dragging:
                            self.duplicate_dragging = False
                            self.duplicate_drag_mode = False
                            if self.duplicate_drag_count > 0:
                                self.status = f"Duplicated {self.duplicate_drag_count} asset(s)."
                            self.duplicate_drag_last_cell = None
                            self.duplicate_drag_cells.clear()
                            self.duplicate_drag_count = 0
                        self.drag_asset_path = None
                        self.dragging_group_ids.clear()
                        self.drag_group_origins = {}
                    elif self.workspace_mode == "scene" and event.button in {2, 3}:
                        self.panning = False
                    elif self.workspace_mode == "canvas" and event.button in {2, 3}:
                        if self.canvas_sel_transform and self.canvas_sel_auto_commit and self.canvas_sel_drag_start is not None:
                            self._canvas_commit_sel_transform()
                        self.canvas_drawing = False
                        self.canvas_panning = False
                elif event.type == pygame.MOUSEMOTION:
                    if self._handle_canvas_motion(event.pos):
                        continue
                    if self.native_drag_asset_rel is not None and self.native_drag_origin is not None:
                        dx = event.pos[0] - self.native_drag_origin[0]
                        dy = event.pos[1] - self.native_drag_origin[1]
                        if (dx * dx + dy * dy) >= 64:
                            rel_path = self.native_drag_asset_rel
                            self._cancel_native_asset_drag()
                            if self._start_native_asset_drag(rel_path):
                                continue
                    if self.resizing_asset_panel:
                        self._resize_asset_panel(event.pos[1])
                    elif self.canvas_bottom_split_dragging and self.workspace_mode == "canvas" and not self.canvas_assets_open:
                        panel = self._asset_panel_rect()
                        ratio = (event.pos[0] - panel.x) / max(panel.width, 1)
                        self.canvas_bottom_split = max(0.45, min(0.82, ratio))
                    elif self.canvas_inspector_resize_left and self.workspace_mode == "canvas":
                        desired_left = max(self.gutter + 360, min(event.pos[0], self.screen_width - self.gutter - 220))
                        self.canvas_inspector_width = max(220, self.screen_width - desired_left - self.gutter)
                        self._update_layout(self.screen_width, self.screen_height)
                    elif self.canvas_inspector_resize_top and self.workspace_mode == "canvas":
                        offset = event.pos[1] - self.board_rect.y
                        self.canvas_inspector_top_offset = max(0, min(offset, max(0, self.board_rect.height - 220)))
                    elif self.panning:
                        mx, my = event.pos
                        self.camera_x = self.pan_origin[0] - ((mx - self.pan_anchor[0]) / max(self.zoom, 0.001))
                        self.camera_y = self.pan_origin[1] - ((my - self.pan_anchor[1]) / max(self.zoom, 0.001))
                        self._clamp_camera()
                    elif self.resizing_sprite_id is not None:
                        local = self._board_local_at(event.pos)
                        if local is not None:
                            self._apply_corner_resize(local)
                    elif self.rotation_gizmo_axis is not None:
                        self._update_rotation_gizmo_drag(event.pos)
                    elif self.duplicate_dragging:
                        local = self._board_local_at(event.pos)
                        if local is not None:
                            self._stamp_duplicate_drag(local)
                    elif self.dragging_group_ids:
                        local = self._board_local_at(event.pos)
                        if local is not None:
                            dx = local[0] - self.drag_group_start_local[0]
                            dy = local[1] - self.drag_group_start_local[1]
                            for sid in self.dragging_group_ids:
                                sprite = self._sprite_by_id(sid)
                                origin = self.drag_group_origins.get(sid)
                                if sprite is None or origin is None:
                                    continue
                                sprite.x = origin[0] + dx
                                sprite.y = origin[1] + dy
                                self._clamp_sprite_to_scene(sprite)
                    elif self.marquee_selecting:
                        self.marquee_current = event.pos
                elif event.type == pygame.MOUSEWHEEL:
                    mods = pygame.key.get_mods()
                    cmd_held = bool(mods & (pygame.KMOD_META | pygame.KMOD_CTRL))
                    # pygame exposes high-resolution wheel deltas as snake_case.
                    # Keep camelCase as a fallback for compatibility with older assumptions.
                    precise_x = getattr(event, "precise_x", getattr(event, "preciseX", float(event.x)))
                    precise_y = getattr(event, "precise_y", getattr(event, "preciseY", float(event.y)))
                    # flipped=True on macOS natural scroll; compensate
                    flipped = getattr(event, "flipped", False)
                    if flipped:
                        precise_x, precise_y = -precise_x, -precise_y
                    if self.workspace_mode == "canvas":
                        if self.canvas_focus_mode:
                            rows_rect = self._canvas_focus_layer_rows_rect()
                            if rows_rect.collidepoint(self.drag_pos) and self.canvas_doc.frames:
                                nl = len(self.canvas_doc.frames[self.canvas_doc.frame_idx]) if self.canvas_doc.frame_idx < len(self.canvas_doc.frames) else 0
                                visible_rows = max(1, rows_rect.height // 20)
                                max_scroll = max(0, nl - visible_rows)
                                if max_scroll > 0:
                                    delta = -1 if precise_y > 0 else 1
                                    self.canvas_layer_scroll = max(0, min(self.canvas_layer_scroll + delta, max_scroll))
                                    continue
                        elif not self.canvas_assets_open:
                            layer_panel = self._asset_panel_rect()
                            if self._canvas_layer_rows_rect(layer_panel).collidepoint(self.drag_pos):
                                _, _, _, max_scroll = self._canvas_layer_row_metrics(layer_panel)
                                if max_scroll > 0:
                                    delta = -1 if precise_y > 0 else 1
                                    self.canvas_layer_scroll = max(0, min(self.canvas_layer_scroll + delta, max_scroll))
                                    continue
                    if self.workspace_mode == "canvas":
                        view = self._canvas_view_rect(self._canvas_workspace_panel_rect())
                        if view.collidepoint(self.drag_pos):
                            if cmd_held:
                                # Cmd + scroll → zoom
                                zoom_delta = precise_y if abs(precise_y) > abs(precise_x) else precise_x
                                self._canvas_zoom_at(self.drag_pos, 1 if zoom_delta > 0 else -1)
                            else:
                                if self.canvas_selection_pixels:
                                    step_x = int(round(-precise_x * 8 / max(self.canvas_zoom, 0.001)))
                                    step_y = int(round(precise_y * 8 / max(self.canvas_zoom, 0.001)))
                                    if step_x == 0 and abs(precise_x) > 0.01:
                                        step_x = -1 if precise_x > 0 else 1
                                    if step_y == 0 and abs(precise_y) > 0.01:
                                        step_y = 1 if precise_y > 0 else -1
                                    self._canvas_move_selection_immediate(step_x, step_y)
                                else:
                                    # Two-finger swipe → pan
                                    self.canvas_offset_x -= precise_x * 8
                                    self.canvas_offset_y += precise_y * 8
                    elif self.workspace_mode == "scene":
                        if cmd_held:
                            zoom_delta = precise_y if abs(precise_y) > abs(precise_x) else precise_x
                            self._zoom_at_screen_pos(self.drag_pos, 1 if zoom_delta > 0 else -1)
                        else:
                            self.camera_x -= precise_x * 20 / max(self.zoom, 0.001)
                            self.camera_y -= precise_y * 20 / max(self.zoom, 0.001)
                            self._clamp_camera()
                elif event.type == pygame.MULTIGESTURE:
                    # Trackpad pinch → continuous zoom anchored to gesture centre (SDL2)
                    dDist = getattr(event, "dDist", 0.0)
                    if abs(dDist) > 0.0003:
                        factor = max(0.1, 1.0 + dDist * 10.0)
                        if self.workspace_mode == "canvas" and self.canvas_surface is not None:
                            # event.x/y are normalised [0,1] screen coords
                            gx = int(event.x * self.screen_width)
                            gy = int(event.y * self.screen_height)
                            panel = self._canvas_workspace_panel_rect()
                            view = self._canvas_view_rect(panel)
                            old_zoom = self.canvas_zoom
                            self.canvas_zoom = max(0.5, min(self.canvas_zoom * factor, 20.0))
                            if abs(self.canvas_zoom - old_zoom) > 1e-6:
                                scale = self.canvas_zoom / max(old_zoom, 1e-6)
                                mx = gx - view.centerx - self.canvas_offset_x
                                my = gy - view.centery - self.canvas_offset_y
                                self.canvas_offset_x += mx - mx * scale
                                self.canvas_offset_y += my - my * scale
                        elif self.workspace_mode == "scene":
                            self.zoom = max(0.1, min(self.zoom * factor, 10.0))

            if self.background_surface is not None:
                screen.blit(self.background_surface, (0, 0))
            else:
                screen.fill((11, 16, 28))

            focus_canvas = self.workspace_mode == "canvas" and self.canvas_focus_mode
            if not focus_canvas:
                self._draw_topbar(screen, title_font, small)
                self._draw_tabs(screen, small)
            if self.workspace_mode == "canvas":
                self._draw_canvas_workspace(screen, font, small)
            else:
                self._draw_scene_board(screen, font, small)
            if focus_canvas:
                self._draw_canvas_focus_layers_panel(screen, font, small)
                if self._canvas_focus_tools_visible():
                    self._draw_inspector(screen, font, small)
                else:
                    hover_strip = pygame.Rect(self.screen_width - 8, self.screen_height // 2 - 48, 4, 96)
                    pygame.draw.rect(screen, (92, 112, 150), hover_strip)
            else:
                self._draw_inspector(screen, font, small)
                self._draw_asset_browser(screen, font, small)
                self._draw_dropdowns(screen, small)

            self._draw_status(screen, small)

            if self.drag_asset_path is not None:
                size = self._image_size_for(self.drag_asset_path)
                if size is not None:
                    preview_w = min(size[0], 160)
                    preview_h = min(size[1], 160)
                    if size[0] > 160 or size[1] > 160:
                        scale = min(160 / max(size[0], 1), 160 / max(size[1], 1))
                        preview_w = max(1, int(size[0] * scale))
                        preview_h = max(1, int(size[1] * scale))
                    ghost = self._get_asset_surface(self.drag_asset_path, (preview_w, preview_h), pygame.time.get_ticks())
                    if ghost is not None:
                        drag_preview = ghost.copy()
                        drag_preview.set_alpha(210)
                        screen.blit(drag_preview, (self.drag_pos[0] - preview_w // 2, self.drag_pos[1] - preview_h // 2))

            if self.dialog_mode is not None:
                self._draw_dialog(screen, font, small)

            pygame.display.flip()
            clock.tick(120)

        pygame.quit()
