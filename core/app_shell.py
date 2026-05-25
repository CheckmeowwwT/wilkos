from __future__ import annotations

from pathlib import Path

import pygame

try:
    from ..browser.library import AssetLibrary
    from ..canvas.model import CanvasDocument
    from ..canvas.session import CanvasSession
    from ..constants import CANVAS_PALETTE, SCENE_SIZE_PRESETS, SUPPORTED_IMAGE_EXTENSIONS
    from ..media_cache import MediaCache
    from ..models import SceneDef, SpritePlacement
except ImportError:
    from browser.library import AssetLibrary  # type: ignore[no-redef]
    from canvas.model import CanvasDocument  # type: ignore[no-redef]
    from canvas.session import CanvasSession  # type: ignore[no-redef]
    from constants import CANVAS_PALETTE, SCENE_SIZE_PRESETS, SUPPORTED_IMAGE_EXTENSIONS  # type: ignore[no-redef]
    from media_cache import MediaCache  # type: ignore[no-redef]
    from models import SceneDef, SpritePlacement  # type: ignore[no-redef]


class CoreAppMixin:
    def __init__(self) -> None:
        self.root = Path(__file__).resolve().parents[3]
        self.asset_root = self.root / "assets"
        self.legacy_asset_dir = self.asset_root / "images" / "dungeon"
        self.project_path = self.asset_root / "maps" / "scenes_project.json"
        self.scene_dir = self.asset_root / "maps" / "scenes"
        self.scene_asset_dir = self.asset_root / "scenes"
        self.scene_json_dir = self.root / "json_scenes"
        self.asset_json_dir = self.asset_root / "json"
        self.asset_root.mkdir(parents=True, exist_ok=True)
        self.scene_dir.mkdir(parents=True, exist_ok=True)
        self.scene_asset_dir.mkdir(parents=True, exist_ok=True)
        self.scene_json_dir.mkdir(parents=True, exist_ok=True)
        self.asset_json_dir.mkdir(parents=True, exist_ok=True)

        self.min_window_size = (1100, 760)
        self.screen_width = 1440
        self.screen_height = 920
        self.windowed_size = (self.screen_width, self.screen_height)
        self.window_flags = pygame.RESIZABLE
        self.is_fullscreen = False
        self.topbar_h = 52
        self.tabs_h = 34
        self.asset_h = 220
        self.asset_panel_collapsed: bool = False
        self.gutter = 14
        self.canvas_bottom_split: float = 0.66
        self.canvas_bottom_split_dragging: bool = False
        self.canvas_preview_fps: int = 8
        self.canvas_layer_scroll: int = 0
        self.canvas_inspector_width: int = 280
        self.canvas_inspector_top_offset: int = 0
        self.canvas_inspector_resize_left: bool = False
        self.canvas_inspector_resize_top: bool = False
        self.canvas_focus_mode: bool = False
        self.scene_focus_mode: bool = False
        self.canvas_light_mode: str = "bulb"
        self.canvas_last_r_press_ms: int = -10000
        self.canvas_colorkey_input: str = "255,255,255"
        self.canvas_colorkey_focus: bool = False
        self.canvas_focus_layer_width: int = 260
        self.canvas_focus_tools_open: bool = False
        self.canvas_focus_tools_progress: float = 0.0
        self.selected_asset_rel: str | None = None
        self.board_rect = pygame.Rect(0, 0, 0, 0)
        self._update_layout(self.screen_width, self.screen_height)

        self.camera_x = 0.0
        self.camera_y = 0.0
        self.zoom = 1.0
        self.workspace_mode = "scene"
        self.dropdown_open: str | None = None
        self.drag_asset_path: str | None = None
        self.native_drag_asset_rel: str | None = None
        self.native_drag_origin: tuple[int, int] | None = None
        self.drag_pos: tuple[int, int] = (0, 0)
        self.duplicate_drag_mode = False
        self.duplicate_dragging = False
        self.duplicate_drag_template: SpritePlacement | None = None
        self.duplicate_drag_last_cell: tuple[int, int] | None = None
        self.duplicate_drag_cells: set[tuple[int, int]] = set()
        self.duplicate_drag_count = 0
        self.canvas_session = CanvasSession(CanvasDocument())
        self.canvas_doc = self.canvas_session.doc
        # Onion skin & background mode
        self.canvas_onion_skin: bool = False
        self.canvas_bg_light: bool = False
        # Vanishing point (canvas pixel coords)
        self.canvas_vp: tuple[int, int] | None = None
        # Smudge scratch buffer (stores sampled colours during a stroke)
        self.canvas_smudge_prev: tuple[int, int] | None = None
        # canvas_surface property setter initialises canvas_frames when assigned
        self.canvas_surface: pygame.Surface | None = None  # type: ignore[assignment]
        self.canvas_tool = "pencil"
        self.canvas_brush_size: int = 1
        self.canvas_color: tuple[int, int, int, int] = CANVAS_PALETTE[0]
        self.canvas_color_usage: dict[tuple[int, int, int, int], int] = {
            tuple(color): max(1, 5 - i) for i, color in enumerate(CANVAS_PALETTE[:5])
        }
        self.canvas_color_hue: float = 0.0
        self.canvas_color_sat: float = 0.0
        self.canvas_color_val: float = 0.0
        self.canvas_color_picker_drag: str | None = None
        self.canvas_color_before_picker: tuple[int, int, int, int] = self.canvas_color
        self.canvas_color_wheel_cache: dict[tuple[int, int], pygame.Surface] = {}
        self.canvas_name_input: str = ""
        self.canvas_rename_kind: str | None = None
        self.canvas_rename_index: int = 0
        self._sync_canvas_hsv_from_color(self.canvas_color)
        self.canvas_drawing = False
        self.canvas_last_pixel: tuple[int, int] | None = None
        # Canvas zoom / pan (independent of scene zoom)
        self.canvas_zoom: float = 4.0
        self.canvas_offset_x: float = 0.0
        self.canvas_offset_y: float = 0.0
        self.canvas_panning: bool = False
        self.canvas_pan_anchor: tuple[int, int] = (0, 0)
        self.canvas_pan_origin: tuple[float, float] = (0.0, 0.0)
        # New-canvas dialog
        self.canvas_new_width_input: str = "64"
        self.canvas_new_height_input: str = "64"
        self.canvas_new_focus: str = "width"
        # Custom brush size input
        self.canvas_brush_size_input: str = "1"
        self.canvas_brush_size_focus: bool = False
        # Shape/line tool preview (pixel coords)
        self.canvas_preview_start: tuple[int, int] | None = None
        self.canvas_preview_end: tuple[int, int] | None = None
        self.canvas_preview_active: bool = False
        # Freeform lasso selection
        self.canvas_selection_pixels: set[tuple[int, int]] = set()
        self.canvas_lasso_pixels: list[tuple[int, int]] = []
        self.canvas_lasso_active: bool = False
        self.canvas_rect_select_active: bool = False
        self.canvas_rect_select_start: tuple[int, int] | None = None
        self.canvas_rect_select_end: tuple[int, int] | None = None
        # Fill toggle for circle/square tools
        self.canvas_fill_shapes: bool = False
        # Canvas clipboard (pixel coord → RGBA color)
        self.canvas_clipboard: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        # Paste state
        self.canvas_paste_active: bool = False
        self.canvas_paste_pixels: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        self.canvas_paste_origin: tuple[int, int] = (0, 0)
        # Blend tool strength (0–1)
        self.canvas_blend_strength: float = 0.5
        self.canvas_blend_input: str = "50"
        self.canvas_blend_focus: bool = False
        # Mirror symmetry while drawing
        self.canvas_mirror_h: bool = False
        self.canvas_mirror_v: bool = False
        # Custom mirror center (pixel coords). When None, mirror about canvas center.
        self.canvas_mirror_center: tuple[int, int] | None = None
        # Asset browser visible in canvas mode (toggle via "Assets" button)
        self.canvas_assets_open: bool = False
        # Canvas bottom panel collapsed
        self.canvas_bottom_collapsed: bool = False
        self.canvas_preview_playing: bool = True
        self.canvas_preview_started_ms: int = 0
        self.canvas_preview_elapsed_ms: int = 0
        self.canvas_preview_frame_ms: int = max(1, int(round(1000 / self.canvas_preview_fps)))
        # Canvas selection transform gizmo mode: "move", "scale", "rotate" or None
        self.canvas_sel_transform: str | None = None
        # Lifted pixels during transform (snapshot copied off canvas, keyed by original pixel pos)
        self.canvas_sel_lift: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        # Current transform offset/angle/scale for live preview
        self.canvas_sel_offset: tuple[int, int] = (0, 0)
        self.canvas_sel_angle: float = 0.0
        self.canvas_sel_scale: float = 1.0
        # Screen pos where transform drag began (for relative calculations)
        self.canvas_sel_drag_start: tuple[int, int] | None = None
        self.canvas_sel_drag_mode: str = ""  # "corner_tl"/"corner_br"/etc. for scale, "rot_handle" for rotate
        self.canvas_sel_restore_on_cancel: bool = True
        self.canvas_sel_auto_commit: bool = False
        self.canvas_sel_push_undo_on_commit: bool = False
        self.canvas_sel_surface: pygame.Surface | None = None
        self.canvas_sel_source_surface: pygame.Surface | None = None
        self.canvas_sel_base_bbox: tuple[int, int, int, int] | None = None
        self.canvas_sel_scale_rect: tuple[float, float, float, float] | None = None
        self.canvas_sel_3d_x: float = 0.0
        self.canvas_sel_3d_y: float = 0.0
        self.canvas_sel_3d_z: float = 0.0
        self.canvas_sel_3d_axis: str | None = None
        self.canvas_sel_3d_start_angle: float = 0.0
        self.canvas_sel_3d_last_angle: float = 0.0
        self.canvas_sel_3d_start_values: tuple[float, float, float] = (0.0, 0.0, 0.0)
        # Canvas resize-tool drag state
        self.canvas_resize_dragging: bool = False
        self.canvas_resize_anchor: str = ""  # "br" etc.
        # Canvas move-tool drag state (pan via tool)
        self.canvas_move_dragging: bool = False
        self.canvas_move_last: tuple[int, int] = (0, 0)
        # Cached checkerboard surface (keyed by (cw, ch, tile, bg_light))
        self._canvas_checker_cache: tuple | None = None
        self._canvas_checker_surf: pygame.Surface | None = None
        self._canvas_checker_base_key: tuple | None = None
        self._canvas_checker_base: pygame.Surface | None = None
        self._canvas_grid_cache: tuple | None = None
        self._canvas_grid_surf: pygame.Surface | None = None
        self._canvas_line_preview_cache_key: tuple | None = None
        self._canvas_line_preview_pixels: set[tuple[int, int]] = set()
        self._canvas_sel_preview_cache_key: tuple | None = None
        self._canvas_sel_preview_surf: pygame.Surface | None = None
        self._canvas_sel_rotate_cache_key: tuple | None = None
        self._canvas_sel_rotate_cache_surf: pygame.Surface | None = None
        self._canvas_sel_3d_cache_key: tuple | None = None
        self._canvas_sel_3d_cache_surf: pygame.Surface | None = None
        self._canvas_sel_3d_cache_offset: tuple[float, float] = (0.0, 0.0)
        self.canvas_sprite_model: dict | None = None
        self._init_canvas_tabs()
        self.selected_sprite_id: int | None = None
        self.selected_sprite_ids: set[int] = set()
        self.panning = False
        self.pan_anchor = (0, 0)
        self.pan_origin = (0.0, 0.0)
        self.resizing_asset_panel = False
        self.resizing_sprite_id: int | None = None
        self.resizing_sprite_ids: list[int] = []
        self.resize_source_bounds: tuple[float, float, float, float] | None = None
        self.resize_source_sprites: dict[int, tuple[float, float, int, int]] = {}
        self.resize_anchor = (0.0, 0.0)
        self.clipboard_sprites: list[SpritePlacement] = []
        self.dragging_group_ids: set[int] = set()
        self.drag_group_start_local = (0.0, 0.0)
        self.drag_group_origins: dict[int, tuple[float, float]] = {}
        self.marquee_selecting = False
        self.marquee_start = (0, 0)
        self.marquee_current = (0, 0)
        self.marquee_additive = False
        self.rotation_gizmo_enabled = False
        self.rotation_gizmo_axis: str | None = None
        self.rotation_gizmo_start_angle = 0.0
        self.rotation_gizmo_start_values: dict[int, tuple[float, float, float]] = {}
        self._init_scene_history()

        self.dialog_mode: str | None = None
        self.pending_scene_size = SCENE_SIZE_PRESETS[1]
        self.custom_scene_width_input = str(self.pending_scene_size[0])
        self.custom_scene_height_input = str(self.pending_scene_size[1])
        self.scene_size_focus: str | None = None
        self.scene_name_input = ""
        self.folder_name_input = ""

        self.media_cache = MediaCache(self.asset_root, SUPPORTED_IMAGE_EXTENSIONS)
        self.asset_library = AssetLibrary(self.asset_root, self.media_cache, SUPPORTED_IMAGE_EXTENSIONS)
        self._qt_drag_app: object | None = None
        self._qt_drag_source: object | None = None
        self.legacy_asset_paths = self._load_legacy_asset_paths()
        self.merged_asset_dir = self.asset_root / "merged assets"
        self.exported_asset_dir = self.asset_root / "exported complete assets"
        self.exported_canvas_dir = self.asset_root / "exported canvasses"
        self.merged_asset_dir.mkdir(parents=True, exist_ok=True)
        self.exported_asset_dir.mkdir(parents=True, exist_ok=True)
        self.exported_canvas_dir.mkdir(parents=True, exist_ok=True)
        (self.asset_root / "sprites").mkdir(parents=True, exist_ok=True)

        self.scenes: list[SceneDef] = [SceneDef(name="Scene 1")]
        self.active_scene_idx = 0
        self.next_scene_num = 2
        self.next_sprite_id = 1
        self.status = "Ready. Create scenes, browse assets, and drag images or GIFs into the board."
        self.background_surface: pygame.Surface | None = None
        self._load_project_if_exists()

    def _asset_height_limits(self) -> tuple[int, int]:
        min_asset_h = 170
        max_asset_h = max(
            min_asset_h,
            self.screen_height - self.topbar_h - self.tabs_h - self.gutter * 5 - 220,
        )
        return min_asset_h, max_asset_h

    def _clamp_asset_height(self, asset_h: int) -> int:
        min_asset_h, max_asset_h = self._asset_height_limits()
        return max(min_asset_h, min(int(asset_h), max_asset_h))

    def _update_layout(self, width: int, height: int, preserve_asset_h: bool = True) -> None:
        self.screen_width = max(int(width), self.min_window_size[0])
        self.screen_height = max(int(height), self.min_window_size[1])
        default_asset_h = max(220, min(340, self.screen_height // 3))
        self.asset_h = self._clamp_asset_height(self.asset_h if preserve_asset_h else default_asset_h)
        asset_rect = self._asset_panel_rect()
        mode = getattr(self, "workspace_mode", "scene")
        scene_focus = mode == "scene" and getattr(self, "scene_focus_mode", False)
        if scene_focus:
            main_top = self.gutter
        else:
            main_top = self.topbar_h + self.tabs_h + self.gutter
        main_bottom = asset_rect.y - self.gutter
        main_height = max(220, main_bottom - main_top)
        if mode == "canvas":
            inspector_width = max(220, min(self.canvas_inspector_width, self.screen_width - 420))
            self.canvas_inspector_width = inspector_width
        elif scene_focus:
            inspector_width = 0
        else:
            inspector_width = max(220, min(300, self.screen_width // 5))
        if scene_focus:
            board_width = self.screen_width - self.gutter * 2
        else:
            board_width = self.screen_width - inspector_width - self.gutter * 3
        self.board_rect = pygame.Rect(
            self.gutter,
            main_top,
            board_width,
            main_height,
        )

    def _inspector_rect(self) -> pygame.Rect:
        mode = getattr(self, "workspace_mode", "scene")
        base_y = self.board_rect.y
        base_h = self.board_rect.height
        if mode == "canvas":
            max_offset = max(0, base_h - 220)
            self.canvas_inspector_top_offset = max(0, min(self.canvas_inspector_top_offset, max_offset))
            base_y += self.canvas_inspector_top_offset
            base_h -= self.canvas_inspector_top_offset
        return pygame.Rect(
            self.board_rect.right + self.gutter,
            base_y,
            self.screen_width - self.board_rect.right - self.gutter * 2,
            base_h,
        )

    def _resize_window(self, screen: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
        if self.is_fullscreen:
            return screen
        width = max(int(size[0]), self.min_window_size[0])
        height = max(int(size[1]), self.min_window_size[1])
        screen = pygame.display.set_mode((width, height), self.window_flags)
        self.windowed_size = (width, height)
        self._update_layout(width, height)
        self._fit_active_scene()
        self.background_surface = self._build_background()
        self.status = f"Window resized to {width}x{height}. Press F11 for fullscreen."
        return screen

    def _toggle_fullscreen(self, screen: pygame.Surface) -> pygame.Surface:
        if self.is_fullscreen:
            screen = pygame.display.set_mode(self.windowed_size, self.window_flags)
            self.is_fullscreen = False
            width, height = screen.get_size()
            self._update_layout(width, height)
            self._fit_active_scene()
            self.background_surface = self._build_background()
            self.status = f"Exited fullscreen. Window restored to {width}x{height}."
            return screen

        self.windowed_size = (self.screen_width, self.screen_height)
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.is_fullscreen = True
        width, height = screen.get_size()
        self._update_layout(width, height)
        self._fit_active_scene()
        self.background_surface = self._build_background()
        self.status = "Entered fullscreen. Press F11 to exit."
        return screen

    def _make_font(self, size: int, bold: bool = False) -> pygame.font.Font:
        for family in ["Arial Narrow", "ArialNarrow", "Helvetica Neue", "HelveticaNeue",
                       "SF Pro Display", "SFProDisplay", "Avenir Next", "AvenirNext",
                       "Segoe UI", "DejaVu Sans"]:
            match = pygame.font.match_font(family, bold=bold)
            if match:
                return pygame.font.Font(match, size)
        return pygame.font.Font(None, size)

    def _build_background(self) -> pygame.Surface:
        background = pygame.Surface((self.screen_width, self.screen_height))
        background.fill((34, 34, 38))
        for y in range(0, self.screen_height, 72):
            pygame.draw.line(background, (40, 40, 44), (0, y), (self.screen_width, y), 1)
        return background
