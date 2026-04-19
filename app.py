from __future__ import annotations

import colorsys
import math
import json
import random
import shutil
import tkinter as tk
from datetime import datetime
from collections import deque
from pathlib import Path
from tkinter import filedialog

import pygame
from PIL import Image, ImageSequence

try:
    from .constants import (
        CANVAS_PALETTE,
        LEGACY_TILE_SIZE,
        SCENE_SIZE_PRESETS,
        SUPPORTED_IMAGE_EXTENSIONS,
    )
    from .models import AssetEntry, SceneDef, SpritePlacement
except ImportError:
    from constants import (  # type: ignore[no-redef]
        CANVAS_PALETTE,
        LEGACY_TILE_SIZE,
        SCENE_SIZE_PRESETS,
        SUPPORTED_IMAGE_EXTENSIONS,
    )
    from models import AssetEntry, SceneDef, SpritePlacement  # type: ignore[no-redef]


class SceneEditorApp:

    # ── canvas_surface property ─────────────────────────────────────────
    # canvas_surface always points to the currently active layer surface.
    # All existing drawing code works unchanged; compositing is done on render.

    @property
    def canvas_surface(self) -> pygame.Surface | None:  # type: ignore[return]
        if not self.canvas_frames:
            return None
        fi = self.canvas_frame_idx
        li = self.canvas_layer_idx
        if fi >= len(self.canvas_frames):
            return None
        frame = self.canvas_frames[fi]
        if not frame or li >= len(frame):
            return None
        return frame[li]

    @canvas_surface.setter
    def canvas_surface(self, val: pygame.Surface | None) -> None:
        if val is None:
            self.canvas_frames = []
            self.canvas_frame_names = []
            self.canvas_layer_names = []
            self.canvas_layer_visible = []
            self.canvas_frame_idx = 0
            self.canvas_layer_idx = 0
            self.canvas_selected_layers = set()
            if hasattr(self, "_canvas_frame_versions"):
                self._canvas_frame_versions = []
            if hasattr(self, "_canvas_composite_cache"):
                self._canvas_composite_cache.clear()
            if hasattr(self, "_canvas_scaled_surface_cache"):
                self._canvas_scaled_surface_cache.clear()
            if hasattr(self, "_canvas_visible_surface_cache"):
                self._canvas_visible_surface_cache.clear()
            if hasattr(self, "_canvas_mipmap_cache"):
                self._canvas_mipmap_cache.clear()
            if hasattr(self, "_clear_canvas_preview_caches"):
                self._clear_canvas_preview_caches()
        else:
            fi = self.canvas_frame_idx
            li = self.canvas_layer_idx
            if (self.canvas_frames
                    and fi < len(self.canvas_frames)
                    and self.canvas_frames[fi]
                    and li < len(self.canvas_frames[fi])):
                self.canvas_frames[fi][li] = val
            else:
                self.canvas_frames = [[val]]
                self.canvas_frame_names = ["Frame 1"]
                self.canvas_layer_names = [["Layer 1"]]
                self.canvas_layer_visible = [[True]]
                self.canvas_frame_idx = 0
                self.canvas_layer_idx = 0
                self.canvas_selected_layers = {0}
            if hasattr(self, "_canvas_frame_versions"):
                self._sync_canvas_render_cache_state()

    def __init__(self) -> None:
        self.root = Path(__file__).resolve().parents[3]
        self.asset_root = self.root / "assets"
        self.legacy_asset_dir = self.asset_root / "images" / "dungeon"
        self.project_path = self.asset_root / "maps" / "scenes_project.json"
        self.scene_dir = self.asset_root / "maps" / "scenes"
        self.asset_root.mkdir(parents=True, exist_ok=True)
        self.scene_dir.mkdir(parents=True, exist_ok=True)

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
        self.drag_pos: tuple[int, int] = (0, 0)
        self.duplicate_drag_mode = False
        self.duplicate_dragging = False
        self.duplicate_drag_template: SpritePlacement | None = None
        self.duplicate_drag_last_cell: tuple[int, int] | None = None
        self.duplicate_drag_cells: set[tuple[int, int]] = set()
        self.duplicate_drag_count = 0
        self.canvas_asset_rel: str | None = None
        # Frames & layers (canvas_surface is a property backed by these)
        self.canvas_frames: list[list[pygame.Surface]] = []
        self.canvas_frame_names: list[str] = []
        self.canvas_layer_names: list[list[str]] = []
        self.canvas_layer_visible: list[list[bool]] = []
        self.canvas_frame_idx: int = 0
        self.canvas_layer_idx: int = 0
        self.canvas_selected_layers: set[int] = {0}
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
        self.canvas_dirty = False
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
        # Undo / redo stacks (store Surface copies)
        self.canvas_undo_stack: list[pygame.Surface] = []
        self.canvas_redo_stack: list[pygame.Surface] = []
        self._canvas_undo_max: int = 40
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
        # Whether undo was pushed for the current stroke
        self._canvas_stroke_undo_pushed: bool = False
        # Asset browser visible in canvas mode (toggle via "Assets" button)
        self.canvas_assets_open: bool = False
        # Canvas bottom panel collapsed
        self.canvas_bottom_collapsed: bool = False
        # Currently hovered canvas tool (for tooltip)
        self.canvas_hovered_tool: str | None = None
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
        self.canvas_sel_base_bbox: tuple[int, int, int, int] | None = None
        self.canvas_sel_scale_rect: tuple[float, float, float, float] | None = None
        # Canvas resize-tool drag state
        self.canvas_resize_dragging: bool = False
        self.canvas_resize_orig: tuple[int, int] = (0, 0)
        self.canvas_resize_anchor: str = ""  # "br" etc.
        # Canvas move-tool drag state (pan via tool)
        self.canvas_move_dragging: bool = False
        self.canvas_move_last: tuple[int, int] = (0, 0)
        # Cached checkerboard surface (keyed by (cw, ch, tile, bg_light))
        self._canvas_checker_cache: tuple | None = None
        self._canvas_checker_surf: pygame.Surface | None = None
        self._canvas_grid_cache: tuple | None = None
        self._canvas_grid_surf: pygame.Surface | None = None
        self._canvas_frame_versions: list[int] = []
        self._canvas_composite_cache: dict[tuple[int, int, int], pygame.Surface] = {}
        self._canvas_scaled_surface_cache: dict[tuple[int, int, int, int, int], pygame.Surface] = {}
        self._canvas_visible_surface_cache: dict[tuple[int, int, int, int, int, int, int, int, int, int], pygame.Surface] = {}
        self._canvas_mipmap_cache: dict[tuple[int, int, int, int], pygame.Surface] = {}
        self._canvas_line_preview_cache_key: tuple | None = None
        self._canvas_line_preview_pixels: set[tuple[int, int]] = set()
        self._canvas_sel_preview_cache_key: tuple | None = None
        self._canvas_sel_preview_surf: pygame.Surface | None = None
        self._canvas_sel_rotate_cache_key: tuple | None = None
        self._canvas_sel_rotate_cache_surf: pygame.Surface | None = None
        self.canvas_tabs: list[dict[str, object]] = []
        self.canvas_tab_idx: int = -1
        self.canvas_next_tab_number: int = 1
        self._init_canvas_tabs()
        self.dragging_sprite_id: int | None = None
        self.sprite_drag_offset = (0.0, 0.0)
        self.selected_sprite_id: int | None = None
        self.selected_sprite_ids: set[int] = set()
        self.panning = False
        self.pan_anchor = (0, 0)
        self.pan_origin = (0.0, 0.0)
        self.resizing_asset_panel = False
        self.resizing_sprite_id: int | None = None
        self.resizing_corner: str | None = None
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
        self.scene_undo_stack: list[dict[str, object]] = []
        self.scene_redo_stack: list[dict[str, object]] = []
        self._scene_undo_max: int = 40

        self.dialog_mode: str | None = None
        self.pending_scene_size = SCENE_SIZE_PRESETS[1]
        self.custom_scene_width_input = str(self.pending_scene_size[0])
        self.custom_scene_height_input = str(self.pending_scene_size[1])
        self.scene_size_focus: str | None = None
        self.folder_name_input = ""

        self.current_asset_dir = self.asset_root
        self.asset_page = 0
        self.assets: list[AssetEntry] = []
        self.preview_cache: dict[str, pygame.Surface] = {}
        self.image_cache: dict[str, pygame.Surface] = {}
        self.animation_cache: dict[str, tuple[list[pygame.Surface], list[int]]] = {}
        self.scaled_cache: dict[tuple[str, int, int, int], pygame.Surface] = {}
        self.image_size_cache: dict[str, tuple[int, int]] = {}
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
        main_top = self.topbar_h + self.tabs_h + self.gutter
        main_bottom = asset_rect.y - self.gutter
        main_height = max(220, main_bottom - main_top)
        mode = getattr(self, "workspace_mode", "scene")
        if mode == "canvas":
            inspector_width = max(220, min(self.canvas_inspector_width, self.screen_width - 420))
            self.canvas_inspector_width = inspector_width
        else:
            inspector_width = max(220, min(300, self.screen_width // 5))
        self.board_rect = pygame.Rect(
            self.gutter,
            main_top,
            self.screen_width - inspector_width - self.gutter * 3,
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

    def _scene_toolbar_rect(self) -> pygame.Rect:
        return pygame.Rect(self.board_rect.x, self.board_rect.y, self.board_rect.width, 30)

    def _scene_viewport_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.board_rect.x,
            self.board_rect.y + 30,
            self.board_rect.width,
            self.board_rect.height - 30,
        )

    def _scene_offset(self, viewport: pygame.Rect) -> tuple[float, float]:
        scene_w = self.active_scene.board_width * self.zoom
        scene_h = self.active_scene.board_height * self.zoom
        return (
            max(0.0, (viewport.width - scene_w) / 2),
            max(0.0, (viewport.height - scene_h) / 2),
        )

    def _fit_active_scene(self) -> None:
        viewport = self._scene_viewport_rect()
        if viewport.width <= 0 or viewport.height <= 0:
            return
        scene = self.active_scene
        scale_x = viewport.width / max(scene.board_width, 1)
        scale_y = viewport.height / max(scene.board_height, 1)
        self.zoom = max(0.1, min(scale_x, scale_y))
        self.camera_x = 0.0
        self.camera_y = 0.0

    def _clamp_camera(self) -> None:
        viewport = self._scene_viewport_rect()
        max_x = max(self.active_scene.board_width - viewport.width / max(self.zoom, 0.001), 0.0)
        max_y = max(self.active_scene.board_height - viewport.height / max(self.zoom, 0.001), 0.0)
        self.camera_x = max(0.0, min(self.camera_x, max_x))
        self.camera_y = max(0.0, min(self.camera_y, max_y))

    def _zoom_at_screen_pos(self, pos: tuple[int, int], wheel_delta: int) -> None:
        if wheel_delta == 0:
            return
        old_zoom = self.zoom
        factor = 1.12 if wheel_delta > 0 else 0.89
        factor = factor ** abs(wheel_delta)
        self.zoom = max(0.08, min(self.zoom * factor, 8.0))
        if abs(self.zoom - old_zoom) < 1e-6:
            return

        viewport = self._scene_viewport_rect()
        local_before = self._board_local_at(pos)
        if local_before is not None:
            offset_x, offset_y = self._scene_offset(viewport)
            self.camera_x = local_before[0] - ((pos[0] - viewport.x - offset_x) / max(self.zoom, 0.001))
            self.camera_y = local_before[1] - ((pos[1] - viewport.y - offset_y) / max(self.zoom, 0.001))
        else:
            world_center_x = self.camera_x + viewport.width / max(old_zoom * 2.0, 1e-6)
            world_center_y = self.camera_y + viewport.height / max(old_zoom * 2.0, 1e-6)
            self.camera_x = world_center_x - viewport.width / max(self.zoom * 2.0, 1e-6)
            self.camera_y = world_center_y - viewport.height / max(self.zoom * 2.0, 1e-6)
        self._clamp_camera()

    def _asset_resize_handle_rect(self) -> pygame.Rect:
        panel = self._asset_panel_rect()
        return pygame.Rect(panel.centerx - 46, panel.y - 7, 92, 14)

    def _resize_asset_panel(self, mouse_y: int) -> None:
        target_height = self.screen_height - self.gutter - int(mouse_y)
        self.asset_h = self._clamp_asset_height(target_height)
        self._update_layout(self.screen_width, self.screen_height, preserve_asset_h=True)
        self._fit_active_scene()

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

    def _load_legacy_asset_paths(self) -> list[str]:
        if not self.legacy_asset_dir.exists():
            return []
        files = sorted(
            path
            for path in self.legacy_asset_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        )
        return [path.relative_to(self.asset_root).as_posix() for path in files]

    @property
    def active_scene(self) -> SceneDef:
        return self.scenes[self.active_scene_idx]

    @staticmethod
    def _clone_sprite(sprite: SpritePlacement) -> SpritePlacement:
        return SpritePlacement(
            sprite_id=sprite.sprite_id,
            asset_path=sprite.asset_path,
            x=sprite.x,
            y=sprite.y,
            width=sprite.width,
            height=sprite.height,
            rotation_x=sprite.rotation_x,
            rotation_y=sprite.rotation_y,
            rotation_z=sprite.rotation_z,
        )

    @classmethod
    def _clone_scene(cls, scene: SceneDef) -> SceneDef:
        return SceneDef(
            name=scene.name,
            board_width=scene.board_width,
            board_height=scene.board_height,
            sprites=[cls._clone_sprite(sprite) for sprite in scene.sprites],
        )

    def _scene_snapshot(self) -> dict[str, object]:
        selected_ids = sorted(self.selected_sprite_ids)
        if not selected_ids and self.selected_sprite_id is not None:
            selected_ids = [self.selected_sprite_id]
        return {
            "scenes": [self._clone_scene(scene) for scene in self.scenes],
            "active_scene_idx": self.active_scene_idx,
            "next_scene_num": self.next_scene_num,
            "next_sprite_id": self.next_sprite_id,
            "selected_sprite_id": self.selected_sprite_id,
            "selected_sprite_ids": selected_ids,
            "camera_x": self.camera_x,
            "camera_y": self.camera_y,
            "zoom": self.zoom,
        }

    def _restore_scene_snapshot(self, snapshot: dict[str, object]) -> None:
        scenes_raw = snapshot.get("scenes")
        if not isinstance(scenes_raw, list) or not scenes_raw:
            return
        self.scenes = [
            self._clone_scene(scene)
            for scene in scenes_raw
            if isinstance(scene, SceneDef)
        ] or [SceneDef(name="Scene 1")]
        self.active_scene_idx = min(
            max(int(snapshot.get("active_scene_idx", 0)), 0),
            len(self.scenes) - 1,
        )
        self.next_scene_num = max(int(snapshot.get("next_scene_num", len(self.scenes) + 1)), 1)
        self.next_sprite_id = max(int(snapshot.get("next_sprite_id", 1)), 1)
        self.camera_x = float(snapshot.get("camera_x", 0.0))
        self.camera_y = float(snapshot.get("camera_y", 0.0))
        self.zoom = max(0.1, min(float(snapshot.get("zoom", self.zoom)), 10.0))
        self.resizing_sprite_id = None
        self.resizing_corner = None
        self.resizing_sprite_ids = []
        self.resize_source_bounds = None
        self.resize_source_sprites = {}
        self.dragging_sprite_id = None
        self.dragging_group_ids.clear()
        self.drag_group_origins = {}
        self.marquee_selecting = False
        self.rotation_gizmo_enabled = False
        self.rotation_gizmo_axis = None
        self.rotation_gizmo_start_values = {}
        self.duplicate_drag_mode = False
        self.duplicate_dragging = False
        self.duplicate_drag_template = None
        self.duplicate_drag_last_cell = None
        self.duplicate_drag_cells.clear()
        self.duplicate_drag_count = 0
        self.drag_asset_path = None
        selection_ids = {
            int(sid) for sid in snapshot.get("selected_sprite_ids", [])
            if isinstance(sid, int)
        }
        primary = snapshot.get("selected_sprite_id")
        primary_id = int(primary) if isinstance(primary, int) else None
        self._set_selection(selection_ids, primary=primary_id)
        self._clamp_camera()

    def _push_scene_undo(self) -> None:
        self.scene_undo_stack.append(self._scene_snapshot())
        if len(self.scene_undo_stack) > self._scene_undo_max:
            self.scene_undo_stack.pop(0)
        self.scene_redo_stack.clear()

    def _scene_undo(self) -> None:
        if not self.scene_undo_stack:
            self.status = "Nothing to undo."
            return
        self.scene_redo_stack.append(self._scene_snapshot())
        snapshot = self.scene_undo_stack.pop()
        self._restore_scene_snapshot(snapshot)
        self.status = f"Undo ({len(self.scene_undo_stack)} left)."

    def _scene_redo(self) -> None:
        if not self.scene_redo_stack:
            self.status = "Nothing to redo."
            return
        self.scene_undo_stack.append(self._scene_snapshot())
        snapshot = self.scene_redo_stack.pop()
        self._restore_scene_snapshot(snapshot)
        self.status = "Redo."

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

    def _safe_scene_filename(self, name: str) -> str:
        slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")
        return slug or "scene"

    def _make_folder_preview(self) -> pygame.Surface:
        preview = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.rect(preview, (242, 196, 93), (10, 22, 60, 42), border_radius=12)
        pygame.draw.rect(preview, (255, 230, 153), (10, 22, 60, 42), 2, border_radius=12)
        pygame.draw.rect(preview, (231, 180, 71), (16, 12, 28, 18), border_radius=8)
        return preview

    def _make_missing_preview(self) -> pygame.Surface:
        preview = pygame.Surface((80, 80), pygame.SRCALPHA)
        preview.fill((98, 46, 54))
        pygame.draw.rect(preview, (232, 139, 151), preview.get_rect(), 2, border_radius=12)
        pygame.draw.line(preview, (255, 221, 227), (20, 20), (60, 60), 4)
        pygame.draw.line(preview, (255, 221, 227), (60, 20), (20, 60), 4)
        return preview

    def _load_image_surface(self, path: Path) -> pygame.Surface:
        cache_key = path.as_posix()
        cached = self.image_cache.get(cache_key)
        if cached is not None:
            return cached

        image = pygame.image.load(cache_key)
        if pygame.display.get_surface() is not None:
            try:
                image = image.convert_alpha()
            except pygame.error:
                image = image.convert()
        self.image_cache[cache_key] = image
        self.image_size_cache[cache_key] = image.get_size()
        return image

    def _load_asset_frames(self, path: Path) -> tuple[list[pygame.Surface], list[int]]:
        cache_key = path.as_posix()
        cached = self.animation_cache.get(cache_key)
        if cached is not None:
            return cached

        if path.suffix.lower() != ".gif":
            image = self._load_image_surface(path)
            frames = [image]
            durations = [100]
            self.animation_cache[cache_key] = (frames, durations)
            return frames, durations

        frames: list[pygame.Surface] = []
        durations: list[int] = []
        try:
            with Image.open(path) as gif:
                for frame in ImageSequence.Iterator(gif):
                    rgba = frame.convert("RGBA")
                    surface = pygame.image.fromstring(rgba.tobytes(), rgba.size, "RGBA")
                    if pygame.display.get_surface() is not None:
                        surface = surface.convert_alpha()
                    frames.append(surface)
                    duration = int(frame.info.get("duration", gif.info.get("duration", 100)) or 100)
                    durations.append(max(40, duration))
        except Exception:
            fallback = self._load_image_surface(path)
            frames = [fallback]
            durations = [100]

        if not frames:
            fallback = self._load_image_surface(path)
            frames = [fallback]
            durations = [100]

        self.image_size_cache[cache_key] = frames[0].get_size()
        self.animation_cache[cache_key] = (frames, durations)
        return frames, durations

    def _frame_index_for_time(self, durations: list[int], ticks_ms: int) -> int:
        if len(durations) <= 1:
            return 0
        total = sum(durations)
        if total <= 0:
            return 0
        moment = ticks_ms % total
        elapsed = 0
        for index, duration in enumerate(durations):
            elapsed += duration
            if moment < elapsed:
                return index
        return len(durations) - 1

    def _image_size_for(self, rel_path: str) -> tuple[int, int] | None:
        asset_path = self.asset_root / rel_path
        cache_key = asset_path.as_posix()
        cached = self.image_size_cache.get(cache_key)
        if cached is not None:
            return cached
        if not asset_path.exists() or asset_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            return None
        try:
            frames, _ = self._load_asset_frames(asset_path)
        except pygame.error:
            return None
        return frames[0].get_size()

    def _get_preview_for_image(self, path: Path) -> pygame.Surface:
        cache_key = f"preview:{path.as_posix()}"
        cached = self.preview_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            frames, _ = self._load_asset_frames(path)
            preview = pygame.transform.smoothscale(frames[0], (80, 80))
        except pygame.error:
            preview = self._make_missing_preview()
        self.preview_cache[cache_key] = preview
        return preview

    def _get_asset_surface(self, rel_path: str, size: tuple[int, int], ticks_ms: int = 0) -> pygame.Surface | None:
        asset_path = self.asset_root / rel_path
        if not asset_path.exists() or asset_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            return None
        try:
            frames, durations = self._load_asset_frames(asset_path)
        except pygame.error:
            return None
        frame_index = self._frame_index_for_time(durations, ticks_ms)
        cache_key = (rel_path, size[0], size[1], frame_index)
        cached = self.scaled_cache.get(cache_key)
        if cached is not None:
            return cached
        scaled = pygame.transform.smoothscale(frames[frame_index], size)
        self.scaled_cache[cache_key] = scaled
        return scaled

    def _apply_xyz_rotation(self, surface: pygame.Surface, sprite: SpritePlacement) -> pygame.Surface:
        # Fake X/Y tilt by compressing against cosine; Z uses true 2D rotation.
        tilt_x = max(0.08, abs(math.cos(math.radians(sprite.rotation_x))))
        tilt_y = max(0.08, abs(math.cos(math.radians(sprite.rotation_y))))
        tilted_w = max(1, int(surface.get_width() * tilt_y))
        tilted_h = max(1, int(surface.get_height() * tilt_x))
        transformed = pygame.transform.smoothscale(surface, (tilted_w, tilted_h))
        if abs(sprite.rotation_z) > 0.001:
            transformed = pygame.transform.rotate(transformed, -sprite.rotation_z)
        return transformed

    def _sprite_render_surface(self, sprite: SpritePlacement, ticks_ms: int) -> pygame.Surface | None:
        base = self._get_asset_surface(sprite.asset_path, (max(1, int(sprite.width)), max(1, int(sprite.height))), ticks_ms)
        if base is None:
            return None
        return self._apply_xyz_rotation(base, sprite)

    def _list_asset_entries(self) -> list[AssetEntry]:
        self.current_asset_dir.mkdir(parents=True, exist_ok=True)
        children = sorted(
            self.current_asset_dir.iterdir(),
            key=lambda path: (not path.is_dir(), path.name.lower()),
        )
        entries: list[AssetEntry] = []
        for child in children:
            if child.is_dir():
                preview = self._make_folder_preview()
            elif child.is_file() and child.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                preview = self._get_preview_for_image(child)
            else:
                continue
            entries.append(
                AssetEntry(
                    rel_path=child.relative_to(self.asset_root).as_posix(),
                    name=child.name,
                    path=child,
                    is_dir=child.is_dir(),
                    preview=preview,
                )
            )
        return entries

    def _refresh_assets(self) -> None:
        self.assets = self._list_asset_entries()
        self.asset_page = min(self.asset_page, self._max_asset_page())

    def _asset_entries_per_page(self) -> int:
        panel = self._asset_panel_rect()
        cols = max(1, (panel.width - 36) // 114)
        return cols * 2

    def _max_asset_page(self) -> int:
        per_page = self._asset_entries_per_page()
        if per_page <= 0:
            return 0
        return max((len(self.assets) - 1) // per_page, 0)

    def _visible_asset_entries(self) -> list[tuple[AssetEntry, pygame.Rect]]:
        per_page = self._asset_entries_per_page()
        start = self.asset_page * per_page
        page_entries = self.assets[start : start + per_page]
        panel = self._asset_panel_rect()
        left = panel.x + 18
        top = panel.y + 84
        slot_w = 114
        slot_h = 132
        cols = max(1, (panel.width - 36) // slot_w)

        visible: list[tuple[AssetEntry, pygame.Rect]] = []
        for idx, entry in enumerate(page_entries):
            row = idx // cols
            col = idx % cols
            rect = pygame.Rect(left + col * slot_w, top + row * slot_h, 96, 96)
            visible.append((entry, rect))
        return visible

    def _asset_panel_rect(self) -> pygame.Rect:
        h = 32 if self.asset_panel_collapsed else self.asset_h
        return pygame.Rect(
            self.gutter,
            self.screen_height - h - self.gutter,
            self.screen_width - self.gutter * 2,
            h,
        )

    def _asset_collapse_button_rect(self) -> pygame.Rect:
        panel = self._asset_panel_rect()
        # Sits as a floating tab ABOVE the panel so it's always reachable
        return pygame.Rect(panel.right - 92, panel.y - 26, 84, 24)

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

    def _toolbar_buttons(self) -> dict[str, pygame.Rect]:
        panel = self._asset_panel_rect()
        x = panel.right - 646
        y = panel.y + 18
        rects: dict[str, pygame.Rect] = {}
        for name, width in [
            ("up", 70),
            ("prev", 70),
            ("next", 70),
            ("import", 96),
            ("delete", 96),
            ("new_folder", 112),
            ("refresh", 112),
        ]:
            rects[name] = pygame.Rect(x, y, width, 32)
            x += width + 8
        return rects

    def _menu_dropdown_rect(self, menu_name: str) -> pygame.Rect:
        if menu_name == "canvas_export":
            base = self._canvas_export_rect()
            item_count = 1 if len(self.canvas_frames) <= 1 else 3
            return pygame.Rect(base.x, base.bottom + 2, 220, item_count * 36 + 10)

        buttons = self._menu_buttons()
        base = buttons[menu_name]
        if menu_name == "file":
            item_count = 4
        elif menu_name == "scene":
            item_count = 2
        else:
            item_count = 0
        return pygame.Rect(base.x, self.topbar_h + 2, 190, item_count * 36 + 10)

    def _menu_items(self, menu_name: str) -> list[tuple[str, pygame.Rect]]:
        if menu_name == "file":
            names = ["New", "Open", "Save", "Export PNG"]
        elif menu_name == "scene":
            names = ["New Scene", "Save Scene"]
        elif menu_name == "canvas_export":
            names = ["Export PNG"]
            if len(self.canvas_frames) > 1:
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
        fi = self.canvas_frame_idx
        nl = len(self.canvas_frames[fi]) if self.canvas_frames and fi < len(self.canvas_frames) else 0
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

    def _asset_at(self, pos: tuple[int, int]) -> AssetEntry | None:
        for entry, rect in self._visible_asset_entries():
            hit_rect = pygame.Rect(rect.x, rect.y, rect.width, rect.height + 28)
            if hit_rect.collidepoint(pos):
                return entry
        return None

    def _change_asset_dir(self, target: Path) -> None:
        try:
            relative = target.resolve().relative_to(self.asset_root.resolve())
        except ValueError:
            self.status = "Folder change blocked: outside assets/."
            return
        self.current_asset_dir = self.asset_root / relative
        self.asset_page = 0
        self._refresh_assets()
        label = relative.as_posix() if str(relative) != "." else "/"
        self.status = f"Browsing assets/{label}"

    def _go_to_parent_asset_dir(self) -> None:
        if self.current_asset_dir == self.asset_root:
            self.status = "Already at assets/ root."
            return
        self._change_asset_dir(self.current_asset_dir.parent)

    def _import_assets_via_dialog(self) -> None:
        root = tk.Tk()
        root.withdraw()
        root.update()
        try:
            selected = filedialog.askopenfilenames(
                title="Import Assets",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All files", "*.*")],
            )
        finally:
            root.destroy()
        if not selected:
            self.status = "Import cancelled."
            return
        imported = 0
        for path in selected:
            source = Path(path)
            if not source.exists():
                continue
            suffix = source.suffix.lower()
            if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
                continue
            target = self.current_asset_dir / source.name
            stem = source.stem
            counter = 2
            while target.exists():
                target = self.current_asset_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            shutil.copy2(source, target)
            self.preview_cache.pop(f"preview:{target.as_posix()}", None)
            self.image_cache.pop(target.as_posix(), None)
            self.animation_cache.pop(target.as_posix(), None)
            self.image_size_cache.pop(target.as_posix(), None)
            imported += 1
        self._refresh_assets()
        self.status = f"Imported {imported} asset(s)." if imported else "No supported assets were selected."

    def _delete_selected_asset(self) -> None:
        if not self.selected_asset_rel:
            self.status = "Select an asset or folder to delete."
            return
        target = (self.asset_root / self.selected_asset_rel).resolve()
        try:
            target.relative_to(self.asset_root.resolve())
        except ValueError:
            self.status = "Delete blocked: outside assets/."
            return
        if not target.exists():
            self.selected_asset_rel = None
            self.status = "That asset no longer exists."
            self._refresh_assets()
            return
        was_current_dir = self.current_asset_dir.resolve() == target if target.is_dir() else False
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        if self.canvas_asset_rel == self.selected_asset_rel:
            self.canvas_asset_rel = None
        self.preview_cache.pop(f"preview:{target.as_posix()}", None)
        self.image_cache.pop(target.as_posix(), None)
        self.animation_cache.pop(target.as_posix(), None)
        self.image_size_cache.pop(target.as_posix(), None)
        deleted_rel = self.selected_asset_rel
        self.selected_asset_rel = None
        if was_current_dir:
            self._change_asset_dir(target.parent if target.parent.is_relative_to(self.asset_root) else self.asset_root)
        else:
            self._refresh_assets()
        self.status = f"Deleted assets/{deleted_rel}."

    def _new_project(self) -> None:
        self._push_scene_undo()
        self.scenes = [SceneDef(name="Scene 1")]
        self.active_scene_idx = 0
        self.next_scene_num = 2
        self.next_sprite_id = 1
        self._clear_selection()
        self.resizing_sprite_id = None
        self.clipboard_sprites = []
        self.rotation_gizmo_enabled = False
        self.camera_x = 0.0
        self.camera_y = 0.0
        self._fit_active_scene()
        self.status = "New project created."

    def _close_scene(self, index: int) -> None:
        if not (0 <= index < len(self.scenes)):
            return
        self._push_scene_undo()
        if len(self.scenes) == 1:
            self.scenes = [SceneDef(name="Scene 1")]
            self.active_scene_idx = 0
            self._clear_selection()
            self.resizing_sprite_id = None
            self.rotation_gizmo_enabled = False
            self.next_scene_num = max(self.next_scene_num, 2)
            self._fit_active_scene()
            self.status = "Closed the last scene and opened a fresh Scene 1."
            return

        closed_name = self.scenes[index].name
        del self.scenes[index]
        if self.active_scene_idx > index:
            self.active_scene_idx -= 1
        elif self.active_scene_idx >= len(self.scenes):
            self.active_scene_idx = len(self.scenes) - 1
        self._clear_selection()
        self.resizing_sprite_id = None
        self.rotation_gizmo_enabled = False
        self._fit_active_scene()
        self.status = f"Closed {closed_name}."

    def _open_new_scene_dialog(self) -> None:
        self.pending_scene_size = SCENE_SIZE_PRESETS[1]
        self.custom_scene_width_input = str(self.pending_scene_size[0])
        self.custom_scene_height_input = str(self.pending_scene_size[1])
        self.scene_size_focus = "width"
        self.dialog_mode = "new_scene"
        self.rotation_gizmo_enabled = False
        self.dropdown_open = None
        self.status = "Pick a resolution for the new scene."

    def _confirm_new_scene(self) -> None:
        parsed = self._parse_custom_scene_size()
        if parsed is None:
            self.status = "Resolution must be whole numbers between 32 and 8192."
            return
        width, height = parsed
        self._push_scene_undo()
        self.pending_scene_size = (width, height)
        name = f"Scene {self.next_scene_num}"
        self.next_scene_num += 1
        self.scenes.append(SceneDef(name=name, board_width=width, board_height=height))
        self.active_scene_idx = len(self.scenes) - 1
        self._clear_selection()
        self.dialog_mode = None
        self.scene_size_focus = None
        self.camera_x = 0.0
        self.camera_y = 0.0
        self._fit_active_scene()
        self.status = f"Created {name} with a {width}x{height} pixel board."

    def _sprite_to_payload(self, sprite: SpritePlacement) -> dict[str, object]:
        return {
            "sprite_id": sprite.sprite_id,
            "asset_path": sprite.asset_path,
            "x": sprite.x,
            "y": sprite.y,
            "width": sprite.width,
            "height": sprite.height,
            "rotation_x": sprite.rotation_x,
            "rotation_y": sprite.rotation_y,
            "rotation_z": sprite.rotation_z,
        }

    def _save_project(self) -> None:
        payload = {
            "active_scene": self.active_scene_idx,
            "next_scene_num": self.next_scene_num,
            "next_sprite_id": self.next_sprite_id,
            "scenes": [
                {
                    "name": scene.name,
                    "board_width": scene.board_width,
                    "board_height": scene.board_height,
                    "sprites": [self._sprite_to_payload(sprite) for sprite in scene.sprites],
                }
                for scene in self.scenes
            ],
        }
        self.project_path.parent.mkdir(parents=True, exist_ok=True)
        self.project_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.status = f"Saved project: {self.project_path.name}"

    def _load_project_if_exists(self) -> None:
        if self.project_path.exists():
            self._open_project()

    def _normalize_loaded_asset_path(self, value: object) -> str | None:
        if isinstance(value, int):
            idx = value - 1
            if 0 <= idx < len(self.legacy_asset_paths):
                return self.legacy_asset_paths[idx]
            return None
        if isinstance(value, str):
            normalized = value.replace("\\", "/").lstrip("/")
            return normalized or None
        return None

    def _clamp_sprite_to_scene(self, sprite: SpritePlacement, scene: SceneDef | None = None) -> None:
        active_scene = scene or self.active_scene
        sprite.width = max(8, min(int(sprite.width), active_scene.board_width))
        sprite.height = max(8, min(int(sprite.height), active_scene.board_height))
        sprite.x = max(0.0, min(float(sprite.x), active_scene.board_width - sprite.width))
        sprite.y = max(0.0, min(float(sprite.y), active_scene.board_height - sprite.height))

    def _sprite_from_payload(self, row: dict[str, object]) -> SpritePlacement | None:
        asset_path = self._normalize_loaded_asset_path(row.get("asset_path"))
        if asset_path is None:
            return None
        try:
            sprite = SpritePlacement(
                sprite_id=int(row.get("sprite_id", 0)),
                asset_path=asset_path,
                x=float(row.get("x", 0.0)),
                y=float(row.get("y", 0.0)),
                width=max(8, int(row.get("width", 32))),
                height=max(8, int(row.get("height", 32))),
                rotation_x=float(row.get("rotation_x", 0.0)),
                rotation_y=float(row.get("rotation_y", 0.0)),
                rotation_z=float(row.get("rotation_z", row.get("rotation", 0.0))),
            )
        except (TypeError, ValueError):
            return None
        return sprite

    def _legacy_sprite_from_placement(self, key: str, value: object) -> SpritePlacement | None:
        asset_path = self._normalize_loaded_asset_path(value)
        if asset_path is None:
            return None
        parts = key.split(",")
        if len(parts) != 2:
            return None
        try:
            cell_x = int(parts[0])
            cell_y = int(parts[1])
        except ValueError:
            return None
        sprite = SpritePlacement(
            sprite_id=self.next_sprite_id,
            asset_path=asset_path,
            x=float(cell_x * LEGACY_TILE_SIZE),
            y=float(cell_y * LEGACY_TILE_SIZE),
            width=LEGACY_TILE_SIZE,
            height=LEGACY_TILE_SIZE,
            rotation_x=0.0,
            rotation_y=0.0,
            rotation_z=0.0,
        )
        self.next_sprite_id += 1
        return sprite

    def _open_project(self) -> None:
        try:
            raw = json.loads(self.project_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.status = "Open failed: invalid project file."
            return

        scenes: list[SceneDef] = []
        loaded_next_sprite_id = int(raw.get("next_sprite_id", 1))
        computed_max_sprite_id = 0

        for row in raw.get("scenes", []):
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "Scene"))
            board_width = max(int(row.get("board_width", 960)), 32)
            board_height = max(int(row.get("board_height", 540)), 32)
            scene = SceneDef(name=name, board_width=board_width, board_height=board_height)

            sprites_raw = row.get("sprites")
            if isinstance(sprites_raw, list):
                for sprite_row in sprites_raw:
                    if not isinstance(sprite_row, dict):
                        continue
                    sprite = self._sprite_from_payload(sprite_row)
                    if sprite is None:
                        continue
                    self._clamp_sprite_to_scene(sprite, scene)
                    scene.sprites.append(sprite)
                    computed_max_sprite_id = max(computed_max_sprite_id, sprite.sprite_id)
            else:
                placements_raw = row.get("placements", {})
                if isinstance(placements_raw, dict):
                    for key, value in placements_raw.items():
                        sprite = self._legacy_sprite_from_placement(str(key), value)
                        if sprite is None:
                            continue
                        self._clamp_sprite_to_scene(sprite, scene)
                        scene.sprites.append(sprite)
                        computed_max_sprite_id = max(computed_max_sprite_id, sprite.sprite_id)

            scenes.append(scene)

        if not scenes:
            scenes = [SceneDef(name="Scene 1")]

        self.scenes = scenes
        self.active_scene_idx = min(max(int(raw.get("active_scene", 0)), 0), len(self.scenes) - 1)
        self.next_scene_num = max(int(raw.get("next_scene_num", len(self.scenes) + 1)), 1)
        self.next_sprite_id = max(loaded_next_sprite_id, computed_max_sprite_id + 1)
        self.scene_undo_stack.clear()
        self.scene_redo_stack.clear()
        self._clear_selection()
        self.rotation_gizmo_enabled = False
        self._fit_active_scene()
        self.status = f"Opened project: {self.project_path.name}"

    def _save_scene(self) -> None:
        scene = self.active_scene
        path = self.scene_dir / f"{self._safe_scene_filename(scene.name)}.json"
        payload = {
            "name": scene.name,
            "board_width": scene.board_width,
            "board_height": scene.board_height,
            "sprites": [self._sprite_to_payload(sprite) for sprite in scene.sprites],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.status = f"Saved scene: {path.name}"

    def _parse_custom_scene_size(self) -> tuple[int, int] | None:
        try:
            width = int(self.custom_scene_width_input.strip() or "0")
            height = int(self.custom_scene_height_input.strip() or "0")
        except ValueError:
            return None
        if not (32 <= width <= 8192 and 32 <= height <= 8192):
            return None
        return width, height

    def _scene_world_origin_on_screen(self) -> tuple[pygame.Rect, float, float]:
        viewport = self._scene_viewport_rect()
        offset_x, offset_y = self._scene_offset(viewport)
        origin_x = viewport.x + offset_x - (self.camera_x * self.zoom)
        origin_y = viewport.y + offset_y - (self.camera_y * self.zoom)
        return viewport, origin_x, origin_y

    def _sprite_by_id(self, sprite_id: int) -> SpritePlacement | None:
        for sprite in self.active_scene.sprites:
            if sprite.sprite_id == sprite_id:
                return sprite
        return None

    def _set_selection(self, sprite_ids: list[int] | set[int], primary: int | None = None) -> None:
        valid = {sprite.sprite_id for sprite in self.active_scene.sprites}
        selected = {sid for sid in sprite_ids if sid in valid}
        self.selected_sprite_ids = selected
        if not selected:
            self.selected_sprite_id = None
            self.rotation_gizmo_axis = None
            return
        if primary is not None and primary in selected:
            self.selected_sprite_id = primary
            return
        if self.selected_sprite_id in selected:
            return
        self.selected_sprite_id = next(iter(selected))

    def _clear_selection(self) -> None:
        self.selected_sprite_ids.clear()
        self.selected_sprite_id = None
        self.rotation_gizmo_axis = None
        self.duplicate_drag_mode = False
        self.duplicate_dragging = False
        self.duplicate_drag_template = None
        self.duplicate_drag_last_cell = None
        self.duplicate_drag_cells.clear()
        self.duplicate_drag_count = 0

    def _selected_sprites(self) -> list[SpritePlacement]:
        if self.selected_sprite_ids:
            return [sprite for sprite in self.active_scene.sprites if sprite.sprite_id in self.selected_sprite_ids]
        sprite = self._selected_sprite()
        return [sprite] if sprite is not None else []

    def _selection_bounds_world(self, sprite_ids: set[int] | None = None) -> tuple[float, float, float, float] | None:
        ids = sprite_ids if sprite_ids is not None else set(self.selected_sprite_ids)
        if not ids and self.selected_sprite_id is not None:
            ids = {self.selected_sprite_id}
        sprites = [sprite for sprite in self.active_scene.sprites if sprite.sprite_id in ids]
        if not sprites:
            return None
        min_x = min(sprite.x for sprite in sprites)
        min_y = min(sprite.y for sprite in sprites)
        max_x = max(sprite.x + sprite.width for sprite in sprites)
        max_y = max(sprite.y + sprite.height for sprite in sprites)
        return (min_x, min_y, max_x, max_y)

    def _sprite_screen_rect(self, sprite: SpritePlacement) -> pygame.Rect:
        _, origin_x, origin_y = self._scene_world_origin_on_screen()
        return pygame.Rect(
            int(origin_x + sprite.x * self.zoom),
            int(origin_y + sprite.y * self.zoom),
            max(1, int(sprite.width * self.zoom)),
            max(1, int(sprite.height * self.zoom)),
        )

    def _selection_screen_rect(self) -> pygame.Rect | None:
        bounds = self._selection_bounds_world()
        if bounds is None:
            return None
        min_x, min_y, max_x, max_y = bounds
        _, origin_x, origin_y = self._scene_world_origin_on_screen()
        return pygame.Rect(
            int(origin_x + min_x * self.zoom),
            int(origin_y + min_y * self.zoom),
            max(1, int((max_x - min_x) * self.zoom)),
            max(1, int((max_y - min_y) * self.zoom)),
        )

    def _selected_resize_handles(self) -> dict[str, pygame.Rect]:
        selection_rect = self._selection_screen_rect()
        if selection_rect is None:
            return {}
        if selection_rect.width < 6 or selection_rect.height < 6:
            return {}
        size = max(8, min(14, int(10 * max(self.zoom, 0.5))))
        half = size // 2
        points = {
            "nw": selection_rect.topleft,
            "ne": selection_rect.topright,
            "sw": selection_rect.bottomleft,
            "se": selection_rect.bottomright,
        }
        return {
            corner: pygame.Rect(point[0] - half, point[1] - half, size, size)
            for corner, point in points.items()
        }

    def _begin_corner_resize(self, corner: str) -> None:
        ids = set(self.selected_sprite_ids)
        if not ids and self.selected_sprite_id is not None:
            ids = {self.selected_sprite_id}
        if not ids:
            return
        bounds = self._selection_bounds_world(ids)
        if bounds is None:
            return
        min_x, min_y, max_x, max_y = bounds
        anchors = {
            "nw": (max_x, max_y),
            "ne": (min_x, max_y),
            "sw": (max_x, min_y),
            "se": (min_x, min_y),
        }
        anchor = anchors.get(corner)
        if anchor is None:
            return
        self.resizing_sprite_id = self.selected_sprite_id
        self.resizing_corner = corner
        self.resizing_sprite_ids = sorted(ids)
        self.resize_source_bounds = bounds
        self.resize_source_sprites = {}
        for sid in self.resizing_sprite_ids:
            sprite = self._sprite_by_id(sid)
            if sprite is None:
                continue
            self.resize_source_sprites[sid] = (sprite.x, sprite.y, sprite.width, sprite.height)
        self.resize_anchor = anchor
        self.dragging_sprite_id = None
        self.dragging_group_ids.clear()
        self.status = "Resizing selected assets."

    def _selected_sprite_for_resize(self) -> SpritePlacement | None:
        if self.resizing_sprite_id is None:
            return None
        return self._sprite_by_id(self.resizing_sprite_id)

    def _apply_corner_resize(self, local_pos: tuple[float, float]) -> None:
        if not self.resizing_sprite_ids or self.resize_source_bounds is None:
            self.resizing_sprite_id = None
            return
        min_x, min_y, max_x, max_y = self.resize_source_bounds
        anchor_x, anchor_y = self.resize_anchor
        pointer_x, pointer_y = local_pos
        min_size = 8.0

        if pointer_x >= anchor_x:
            left = anchor_x
            right = anchor_x + max(pointer_x - anchor_x, min_size)
        else:
            left = anchor_x - max(anchor_x - pointer_x, min_size)
            right = anchor_x

        if pointer_y >= anchor_y:
            top = anchor_y
            bottom = anchor_y + max(pointer_y - anchor_y, min_size)
        else:
            top = anchor_y - max(anchor_y - pointer_y, min_size)
            bottom = anchor_y

        source_w = max(max_x - min_x, 1.0)
        source_h = max(max_y - min_y, 1.0)
        target_w = max(right - left, min_size)
        target_h = max(bottom - top, min_size)
        scale_x = target_w / source_w
        scale_y = target_h / source_h

        for sid in self.resizing_sprite_ids:
            sprite = self._sprite_by_id(sid)
            source_state = self.resize_source_sprites.get(sid)
            if sprite is None or source_state is None:
                continue
            sx, sy, sw, sh = source_state
            sprite.x = left + ((sx - min_x) * scale_x)
            sprite.y = top + ((sy - min_y) * scale_y)
            sprite.width = max(8, int(sw * scale_x))
            sprite.height = max(8, int(sh * scale_y))
            self._clamp_sprite_to_scene(sprite)

    def _marquee_rect(self) -> pygame.Rect:
        x1, y1 = self.marquee_start
        x2, y2 = self.marquee_current
        return pygame.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

    def _canvas_target_asset_rel(self) -> str | None:
        if self.canvas_asset_rel is not None:
            return self.canvas_asset_rel
        selected = self._selected_sprite()
        if selected is None:
            return None
        return selected.asset_path

    def _canvas_editable(self, rel_path: str | None) -> bool:
        if rel_path is None:
            return False
        suffix = (self.asset_root / rel_path).suffix.lower()
        return suffix in {".png", ".jpg", ".jpeg", ".bmp"}

    def _sync_canvas_for_selection(self) -> None:
        rel = self._canvas_target_asset_rel()
        if rel == self.canvas_asset_rel and self.canvas_surface is not None:
            return
        self.canvas_asset_rel = rel
        self.canvas_surface = None
        self.canvas_drawing = False
        self.canvas_last_pixel = None
        self.canvas_dirty = False
        if not self._canvas_editable(rel):
            return
        path = self.asset_root / rel
        try:
            loaded = pygame.image.load(path.as_posix())
            self.canvas_surface = loaded.convert_alpha()
        except pygame.error:
            self.canvas_surface = None
        self._save_active_canvas_tab_state()

    def _canvas_tools_panel_rect(self) -> pygame.Rect:
        if self.workspace_mode == "canvas" and self.canvas_focus_mode:
            width = max(220, self.canvas_inspector_width)
            open_x = self.screen_width - self.gutter - width
            closed_x = self.screen_width + 40
            progress = max(0.0, min(1.0, self.canvas_focus_tools_progress))
            x = int(round(closed_x + (open_x - closed_x) * progress))
            return pygame.Rect(x, self.gutter, width, self.screen_height - self.gutter * 2)
        panel = self._inspector_rect()
        return pygame.Rect(panel.x, panel.y, panel.width, panel.height)

    def _canvas_workspace_panel_rect(self) -> pygame.Rect:
        if self.workspace_mode == "canvas" and self.canvas_focus_mode:
            left_panel = self._canvas_focus_layer_panel_rect()
            width = max(220, self.canvas_inspector_width)
            progress = max(0.0, min(1.0, self.canvas_focus_tools_progress))
            tools_width = max(12, int(round(width * progress)))
            x = left_panel.right + self.gutter
            y = self.gutter
            right = self.screen_width - self.gutter - tools_width
            height = self.screen_height - self.gutter * 2
            return pygame.Rect(x, y, max(220, right - x), max(220, height))
        return self.board_rect

    def _canvas_focus_tools_visible(self) -> bool:
        return bool(
            self.workspace_mode == "canvas"
            and self.canvas_focus_mode
            and self.canvas_focus_tools_progress > 0.01
        )

    def _canvas_focus_layer_panel_rect(self) -> pygame.Rect:
        width = max(220, min(self.canvas_focus_layer_width, self.screen_width // 3))
        return pygame.Rect(
            self.gutter,
            self.gutter,
            width,
            self.screen_height - self.gutter * 2,
        )

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

    @staticmethod
    def _draw_tool_icon(surf: pygame.Surface, name: str, rect: pygame.Rect, col: tuple) -> None:
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

        else:
            # Fallback: render short text
            pass  # caller can fall back to text

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

    def _canvas_layer_control_rects(self, panel: pygame.Rect) -> dict[str, pygame.Rect]:
        actions = self._canvas_selection_action_rects(panel)
        top = max((rect.bottom for rect in actions.values()), default=panel.y + 320) + 22
        gap = 4
        cols = 3
        avail = panel.width - 16
        btn_w = max(34, (avail - gap * (cols - 1)) // cols)
        rects: dict[str, pygame.Rect] = {}
        keys = [
            ("layer_add", "+"),
            ("layer_dup", "Dup"),
            ("layer_ren", "Name"),
            ("layer_up", "Up"),
            ("layer_down", "Dn"),
            ("layer_del", "-"),
        ]
        for i, (key, _) in enumerate(keys):
            row, col = divmod(i, cols)
            rects[key] = pygame.Rect(panel.x + 8 + col * (btn_w + gap), top + row * 28, btn_w, 24)
        return rects

    def _canvas_layer_rects(self, panel: pygame.Rect) -> dict[str, pygame.Rect]:
        """Layer UI rects and visible rows for the active frame."""
        controls = self._canvas_layer_control_rects(panel)
        controls_bottom = max((rect.bottom for rect in controls.values()), default=panel.y + 420)
        y_label = controls_bottom + 10
        header = pygame.Rect(panel.x + 8, y_label, panel.width - 16, 16)
        rects: dict[str, pygame.Rect] = {
            "header": header,
        }
        if not self.canvas_frames:
            return rects
        frame = self.canvas_frames[self.canvas_frame_idx] if self.canvas_frame_idx < len(self.canvas_frames) else []
        # Show layers in reverse (top layer at top of list), up to 3 visible.
        n = len(frame)
        start = max(0, n - 3)
        for display_i, layer_i in enumerate(range(n - 1, start - 1, -1)):
            y_row = y_label + 20 + display_i * 22
            eye = pygame.Rect(panel.x + 8, y_row + 2, 14, 14)
            row = pygame.Rect(panel.x + 26, y_row, panel.width - 34, 18)
            rects[f"layer_{layer_i}"] = row
            rects[f"eye_{layer_i}"] = eye
        return rects

    def _canvas_frame_control_rects(self, panel: pygame.Rect) -> dict[str, pygame.Rect]:
        layer_rects = self._canvas_layer_rects(panel)
        row_bottoms = [rect.bottom for key, rect in layer_rects.items() if key.startswith("layer_")]
        top = (max(row_bottoms, default=layer_rects["header"].bottom) + 24)
        gap = 4
        cols = 3
        avail = panel.width - 16
        btn_w = max(34, (avail - gap * (cols - 1)) // cols)
        rects: dict[str, pygame.Rect] = {}
        keys = [
            ("frame_add", "+"),
            ("frame_dup", "Dup"),
            ("frame_ren", "Name"),
            ("frame_prev", "<"),
            ("frame_next", ">"),
            ("frame_del", "-"),
        ]
        for i, (key, _) in enumerate(keys):
            row, col = divmod(i, cols)
            rects[key] = pygame.Rect(panel.x + 8 + col * (btn_w + gap), top + row * 28, btn_w, 24)
        return rects

    def _canvas_frame_rects(self, panel: pygame.Rect) -> dict[str, pygame.Rect]:
        controls = self._canvas_frame_control_rects(panel)
        controls_bottom = max((rect.bottom for rect in controls.values()), default=panel.y + 520)
        y_label = controls_bottom + 10
        rects: dict[str, pygame.Rect] = {
            "header": pygame.Rect(panel.x + 8, y_label, panel.width - 16, 16),
        }
        n = len(self.canvas_frames)
        if n == 0:
            return rects
        start = max(0, min(self.canvas_frame_idx - 1, n - 3))
        for display_i, frame_i in enumerate(range(start, min(start + 3, n))):
            y_row = y_label + 20 + display_i * 22
            rects[f"frame_{frame_i}"] = pygame.Rect(panel.x + 8, y_row, panel.width - 16, 18)
        return rects

    _CANVAS_TIMELINE_H = 48  # height of frame timeline strip

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

    def _canvas_timeline_rect(self, panel: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(
            panel.x + 4,
            panel.bottom - self._CANVAS_TIMELINE_H - 2,
            panel.width - 8,
            self._CANVAS_TIMELINE_H,
        )

    def _canvas_toolbar_rect(self, panel: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(panel.x + 4, panel.y + 44, panel.width - 8, 34)

    def _canvas_focus_toggle_rect(self, panel: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(panel.right - 34, panel.y + 8, 26, 26)

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

    def _canvas_reset_layer_selection(self, idx: int | None = None) -> None:
        if not self.canvas_frames:
            self.canvas_selected_layers.clear()
            self.canvas_layer_idx = 0
            return
        fi = min(self.canvas_frame_idx, len(self.canvas_frames) - 1)
        layer_count = len(self.canvas_frames[fi])
        if layer_count <= 0:
            self.canvas_selected_layers.clear()
            self.canvas_layer_idx = 0
            return
        target = self.canvas_layer_idx if idx is None else idx
        target = max(0, min(target, layer_count - 1))
        self.canvas_layer_idx = target
        self.canvas_selected_layers = {target}

    def _canvas_selected_layer_indices(self) -> list[int]:
        if not self.canvas_frames:
            return []
        fi = min(self.canvas_frame_idx, len(self.canvas_frames) - 1)
        layer_count = len(self.canvas_frames[fi])
        selected = sorted(li for li in self.canvas_selected_layers if 0 <= li < layer_count)
        if not selected and layer_count > 0:
            selected = [max(0, min(self.canvas_layer_idx, layer_count - 1))]
            self.canvas_selected_layers = set(selected)
        return selected

    def _canvas_toggle_layer_selection(self, idx: int) -> None:
        selected = set(self._canvas_selected_layer_indices())
        if idx in selected and len(selected) > 1:
            selected.remove(idx)
        else:
            selected.add(idx)
        self.canvas_layer_idx = idx
        self.canvas_selected_layers = selected

    def _canvas_clear_extra_layer_selection(self) -> bool:
        selected = self._canvas_selected_layer_indices()
        if len(selected) <= 1:
            return False
        active = max(0, min(self.canvas_layer_idx, len(self.canvas_frames[self.canvas_frame_idx]) - 1))
        self.canvas_selected_layers = {active}
        self.status = f"Layer {active + 1} remains selected."
        return True

    def _sync_canvas_render_cache_state(self) -> None:
        target_len = len(self.canvas_frames)
        current_len = len(self._canvas_frame_versions)
        if current_len < target_len:
            self._canvas_frame_versions.extend([0] * (target_len - current_len))
        elif current_len > target_len:
            self._canvas_frame_versions = self._canvas_frame_versions[:target_len]
        valid_frames = set(range(target_len))
        if len(valid_frames) != target_len:
            return
        self._canvas_composite_cache = {
            key: surf for key, surf in self._canvas_composite_cache.items()
            if key[0] in valid_frames
        }
        self._canvas_scaled_surface_cache = {
            key: surf for key, surf in self._canvas_scaled_surface_cache.items()
            if key[0] in valid_frames
        }
        self._canvas_visible_surface_cache = {
            key: surf for key, surf in self._canvas_visible_surface_cache.items()
            if key[0] in valid_frames
        }
        self._canvas_mipmap_cache = {
            key: surf for key, surf in self._canvas_mipmap_cache.items()
            if key[0] in valid_frames
        }

    def _invalidate_canvas_render_cache(self, frame_idx: int | None = None) -> None:
        self._sync_canvas_render_cache_state()
        targets = range(len(self.canvas_frames)) if frame_idx is None else [frame_idx]
        for idx in targets:
            if not (0 <= idx < len(self._canvas_frame_versions)):
                continue
            self._canvas_frame_versions[idx] += 1
            self._canvas_composite_cache = {
                key: surf for key, surf in self._canvas_composite_cache.items()
                if key[0] != idx
            }
            self._canvas_scaled_surface_cache = {
                key: surf for key, surf in self._canvas_scaled_surface_cache.items()
                if key[0] != idx
            }
            self._canvas_visible_surface_cache = {
                key: surf for key, surf in self._canvas_visible_surface_cache.items()
                if key[0] != idx
            }
            self._canvas_mipmap_cache = {
                key: surf for key, surf in self._canvas_mipmap_cache.items()
                if key[0] != idx
            }

    def _mark_canvas_changed(self, frame_idx: int | None = None) -> None:
        target = self.canvas_frame_idx if frame_idx is None else frame_idx
        self._invalidate_canvas_render_cache(target)
        self.canvas_dirty = True

    _CANVAS_DOC_FIELDS = (
        "canvas_asset_rel",
        "canvas_frames",
        "canvas_frame_names",
        "canvas_layer_names",
        "canvas_layer_visible",
        "canvas_frame_idx",
        "canvas_layer_idx",
        "canvas_selected_layers",
        "canvas_onion_skin",
        "canvas_bg_light",
        "canvas_vp",
        "canvas_smudge_prev",
        "canvas_drawing",
        "canvas_dirty",
        "canvas_last_pixel",
        "canvas_zoom",
        "canvas_offset_x",
        "canvas_offset_y",
        "canvas_panning",
        "canvas_pan_anchor",
        "canvas_pan_origin",
        "canvas_layer_scroll",
        "canvas_preview_fps",
        "canvas_preview_start",
        "canvas_preview_end",
        "canvas_preview_active",
        "canvas_selection_pixels",
        "canvas_lasso_pixels",
        "canvas_lasso_active",
        "canvas_rect_select_active",
        "canvas_rect_select_start",
        "canvas_rect_select_end",
        "canvas_undo_stack",
        "canvas_redo_stack",
        "canvas_paste_active",
        "canvas_paste_pixels",
        "canvas_paste_origin",
        "canvas_preview_playing",
        "canvas_preview_started_ms",
        "canvas_preview_elapsed_ms",
        "canvas_preview_frame_ms",
        "canvas_sel_transform",
        "canvas_sel_lift",
        "canvas_sel_offset",
        "canvas_sel_angle",
        "canvas_sel_scale",
        "canvas_sel_drag_start",
        "canvas_sel_drag_mode",
        "canvas_sel_restore_on_cancel",
        "canvas_sel_auto_commit",
        "canvas_sel_push_undo_on_commit",
        "canvas_sel_surface",
        "canvas_sel_base_bbox",
        "canvas_sel_scale_rect",
        "canvas_resize_dragging",
        "canvas_resize_orig",
        "canvas_resize_anchor",
        "canvas_move_dragging",
        "canvas_move_last",
        "_canvas_checker_cache",
        "_canvas_checker_surf",
        "_canvas_grid_cache",
        "_canvas_grid_surf",
        "_canvas_frame_versions",
        "_canvas_composite_cache",
        "_canvas_scaled_surface_cache",
        "_canvas_visible_surface_cache",
        "_canvas_mipmap_cache",
        "_canvas_line_preview_cache_key",
        "_canvas_line_preview_pixels",
        "_canvas_sel_preview_cache_key",
        "_canvas_sel_preview_surf",
        "_canvas_sel_rotate_cache_key",
        "_canvas_sel_rotate_cache_surf",
        "_canvas_stroke_undo_pushed",
    )

    def _canvas_doc_state(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self._CANVAS_DOC_FIELDS}

    def _canvas_apply_doc_state(self, state: dict[str, object]) -> None:
        for name in self._CANVAS_DOC_FIELDS:
            setattr(self, name, state[name])
        self._sync_canvas_render_cache_state()

    def _next_canvas_tab_name(self) -> str:
        used: set[int] = set()
        for tab in self.canvas_tabs:
            name = str(tab.get("name", "")).strip()
            if name.startswith("Canvas "):
                suffix = name[7:].strip()
                if suffix.isdigit():
                    used.add(int(suffix))
        n = 1
        while n in used:
            n += 1
        self.canvas_next_tab_number = max(self.canvas_next_tab_number, n + 1)
        return f"Canvas {n}"

    def _max_canvas_tabs(self) -> int:
        return 7

    def _init_canvas_tabs(self) -> None:
        initial_name = self._next_canvas_tab_name()
        self.canvas_tabs = [{"name": initial_name, "state": self._canvas_doc_state()}]
        self.canvas_tab_idx = 0

    def _save_active_canvas_tab_state(self) -> None:
        if 0 <= self.canvas_tab_idx < len(self.canvas_tabs):
            self.canvas_tabs[self.canvas_tab_idx]["state"] = self._canvas_doc_state()

    def _switch_canvas_tab(self, idx: int) -> None:
        if not (0 <= idx < len(self.canvas_tabs)) or idx == self.canvas_tab_idx:
            return
        self._save_active_canvas_tab_state()
        self.canvas_tab_idx = idx
        self._canvas_apply_doc_state(self.canvas_tabs[idx]["state"])  # type: ignore[arg-type]
        self.status = f"Switched to {self._canvas_tab_name(idx)}."

    def _delete_current_canvas_tab(self) -> None:
        if len(self.canvas_tabs) <= 1:
            self.status = "Cannot delete the only canvas tab."
            return
        remove_idx = self.canvas_tab_idx
        removed_name = self._canvas_tab_name(remove_idx)
        self.canvas_tabs.pop(remove_idx)
        self.canvas_tab_idx = max(0, min(remove_idx, len(self.canvas_tabs) - 1))
        self._canvas_apply_doc_state(self.canvas_tabs[self.canvas_tab_idx]["state"])  # type: ignore[arg-type]
        self.status = f"Deleted {removed_name}."

    def _canvas_tab_is_placeholder(self, idx: int | None = None) -> bool:
        use_idx = self.canvas_tab_idx if idx is None else idx
        if not (0 <= use_idx < len(self.canvas_tabs)):
            return False
        state = self.canvas_tabs[use_idx].get("state")
        if not isinstance(state, dict):
            return False
        frames = state.get("canvas_frames")
        if isinstance(frames, list) and len(frames) > 0:
            return False
        asset_rel = state.get("canvas_asset_rel")
        return asset_rel in {None, ""}

    def _canvas_tab_name(self, idx: int | None = None) -> str:
        use_idx = self.canvas_tab_idx if idx is None else idx
        if 0 <= use_idx < len(self.canvas_tabs):
            name = str(self.canvas_tabs[use_idx].get("name", "")).strip()
            if name:
                return name
        return f"Canvas {max(1, use_idx + 1)}"

    def _new_canvas_doc_state(self, width: int, height: int) -> dict[str, object]:
        state = self._canvas_doc_state()
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        state.update({
            "canvas_asset_rel": None,
            "canvas_frames": [[surf]],
            "canvas_frame_names": ["Frame 1"],
            "canvas_layer_names": [["Layer 1"]],
            "canvas_layer_visible": [[True]],
            "canvas_frame_idx": 0,
            "canvas_layer_idx": 0,
            "canvas_selected_layers": {0},
            "canvas_onion_skin": False,
            "canvas_bg_light": False,
            "canvas_vp": None,
            "canvas_smudge_prev": None,
            "canvas_drawing": False,
            "canvas_dirty": True,
            "canvas_last_pixel": None,
            "canvas_zoom": 4.0,
            "canvas_offset_x": 0.0,
            "canvas_offset_y": 0.0,
            "canvas_panning": False,
            "canvas_pan_anchor": (0, 0),
            "canvas_pan_origin": (0.0, 0.0),
            "canvas_layer_scroll": 0,
            "canvas_preview_start": None,
            "canvas_preview_end": None,
            "canvas_preview_active": False,
            "canvas_selection_pixels": set(),
            "canvas_lasso_pixels": [],
            "canvas_lasso_active": False,
            "canvas_rect_select_active": False,
            "canvas_rect_select_start": None,
            "canvas_rect_select_end": None,
            "canvas_undo_stack": [],
            "canvas_redo_stack": [],
            "canvas_paste_active": False,
            "canvas_paste_pixels": {},
            "canvas_paste_origin": (0, 0),
            "canvas_preview_playing": True,
            "canvas_preview_started_ms": pygame.time.get_ticks(),
            "canvas_preview_elapsed_ms": 0,
            "canvas_preview_frame_ms": max(1, int(round(1000 / max(1, self.canvas_preview_fps)))),
            "canvas_sel_transform": None,
            "canvas_sel_lift": {},
            "canvas_sel_offset": (0, 0),
            "canvas_sel_angle": 0.0,
            "canvas_sel_scale": 1.0,
            "canvas_sel_drag_start": None,
            "canvas_sel_drag_mode": "",
            "canvas_sel_restore_on_cancel": True,
            "canvas_sel_auto_commit": False,
            "canvas_sel_push_undo_on_commit": False,
            "canvas_sel_surface": None,
            "canvas_sel_base_bbox": None,
            "canvas_sel_scale_rect": None,
            "canvas_resize_dragging": False,
            "canvas_resize_orig": (0, 0),
            "canvas_resize_anchor": "",
            "canvas_move_dragging": False,
            "canvas_move_last": (0, 0),
            "_canvas_checker_cache": None,
            "_canvas_checker_surf": None,
            "_canvas_grid_cache": None,
            "_canvas_grid_surf": None,
            "_canvas_frame_versions": [0],
            "_canvas_composite_cache": {},
            "_canvas_scaled_surface_cache": {},
            "_canvas_visible_surface_cache": {},
            "_canvas_mipmap_cache": {},
            "_canvas_line_preview_cache_key": None,
            "_canvas_line_preview_pixels": set(),
            "_canvas_sel_preview_cache_key": None,
            "_canvas_sel_preview_surf": None,
            "_canvas_sel_rotate_cache_key": None,
            "_canvas_sel_rotate_cache_surf": None,
            "_canvas_stroke_undo_pushed": False,
        })
        return state

    def _canvas_header_tab_rects(self, panel: pygame.Rect) -> list[tuple[int, pygame.Rect]]:
        if self.canvas_focus_mode:
            return []
        header = pygame.Rect(panel.x, panel.y, panel.width, 44)
        x = header.x + 100
        right_limit = header.right - 220
        rects: list[tuple[int, pygame.Rect]] = []
        for idx in range(len(self.canvas_tabs)):
            label = self._canvas_tab_name(idx)
            width = max(84, min(170, 24 + len(label) * 8))
            rect = pygame.Rect(x, header.y + 8, width, 28)
            if rect.right > right_limit:
                break
            rects.append((idx, rect))
            x = rect.right + 6
        return rects

    def _clear_canvas_preview_caches(self) -> None:
        self._canvas_line_preview_cache_key = None
        self._canvas_line_preview_pixels = set()
        self._canvas_sel_preview_cache_key = None
        self._canvas_sel_preview_surf = None
        self._canvas_sel_rotate_cache_key = None
        self._canvas_sel_rotate_cache_surf = None

    def _canvas_patch_render_region(
        self,
        dirty_rect: pygame.Rect,
        frame_idx: int | None = None,
    ) -> None:
        target = self.canvas_frame_idx if frame_idx is None else frame_idx
        self.canvas_dirty = True
        if target < 0 or target >= len(self.canvas_frames) or not self.canvas_frames[target]:
            return
        layers = self.canvas_frames[target]
        sw, sh = layers[0].get_size()
        clipped = dirty_rect.clip(pygame.Rect(0, 0, sw, sh))
        if clipped.width <= 0 or clipped.height <= 0:
            return
        self._sync_canvas_render_cache_state()
        self._canvas_visible_surface_cache.clear()
        self._canvas_mipmap_cache.clear()
        version = self._canvas_frame_versions[target] if target < len(self._canvas_frame_versions) else 0
        cached_comp_keys = [
            key for key in self._canvas_composite_cache
            if key[0] == target and key[1] == version
        ]
        for key in cached_comp_keys:
            comp = self._canvas_composite_cache.get(key)
            if comp is None:
                continue
            alpha = key[2]
            comp.fill((0, 0, 0, 0), clipped)
            for layer_idx, surf in enumerate(layers):
                if not self.canvas_layer_visible[target][layer_idx]:
                    continue
                if alpha < 255:
                    patch = surf.subsurface(clipped).copy()
                    patch.set_alpha(alpha)
                    comp.blit(patch, clipped.topleft)
                else:
                    comp.blit(surf, clipped.topleft, clipped)

        cached_scaled_keys = [
            key for key in self._canvas_scaled_surface_cache
            if key[0] == target and key[1] == version
        ]
        if not cached_scaled_keys:
            return
        src_right = clipped.right
        src_bottom = clipped.bottom
        for key in cached_scaled_keys:
            scaled = self._canvas_scaled_surface_cache.get(key)
            if scaled is None:
                continue
            alpha = key[2]
            dw, dh = key[3], key[4]
            comp = self._canvas_composite_cache.get((target, version, alpha))
            if comp is None:
                continue
            dx0 = int(round(clipped.x * dw / sw))
            dy0 = int(round(clipped.y * dh / sh))
            dx1 = int(round(src_right * dw / sw))
            dy1 = int(round(src_bottom * dh / sh))
            dx0 = max(0, min(dx0, dw - 1))
            dy0 = max(0, min(dy0, dh - 1))
            dx1 = max(dx0 + 1, min(dx1, dw))
            dy1 = max(dy0 + 1, min(dy1, dh))
            patch_w = dx1 - dx0
            patch_h = dy1 - dy0
            if patch_w <= 0 or patch_h <= 0:
                continue
            patch = comp.subsurface(clipped).copy()
            scaled_patch = pygame.transform.scale(patch, (patch_w, patch_h))
            scaled.blit(scaled_patch, (dx0, dy0))

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

    def _canvas_visible_pixel_bounds(
        self,
        draw_rect: pygame.Rect,
        clip_rect: pygame.Rect,
        canvas_size: tuple[int, int],
    ) -> tuple[int, int, int, int] | None:
        if draw_rect.width <= 0 or draw_rect.height <= 0 or self.canvas_zoom <= 0:
            return None
        visible = draw_rect.clip(clip_rect)
        if visible.width <= 0 or visible.height <= 0:
            return None
        sw, sh = canvas_size
        left = max(0, int(math.floor((visible.left - draw_rect.left) / self.canvas_zoom)))
        top = max(0, int(math.floor((visible.top - draw_rect.top) / self.canvas_zoom)))
        right = min(sw - 1, int(math.ceil((visible.right - draw_rect.left) / self.canvas_zoom)) - 1)
        bottom = min(sh - 1, int(math.ceil((visible.bottom - draw_rect.top) / self.canvas_zoom)) - 1)
        if right < left or bottom < top:
            return None
        return (left, top, right, bottom)

    def _canvas_visible_source_dest_rects(
        self,
        draw_rect: pygame.Rect,
        clip_rect: pygame.Rect,
        canvas_size: tuple[int, int],
    ) -> tuple[pygame.Rect, pygame.Rect] | None:
        if draw_rect.width <= 0 or draw_rect.height <= 0 or self.canvas_zoom <= 0:
            return None
        visible = draw_rect.clip(clip_rect)
        if visible.width <= 0 or visible.height <= 0:
            return None
        sw, sh = canvas_size
        src_left = max(0, int(math.floor((visible.left - draw_rect.left) / self.canvas_zoom)))
        src_top = max(0, int(math.floor((visible.top - draw_rect.top) / self.canvas_zoom)))
        src_right = min(sw, int(math.ceil((visible.right - draw_rect.left) / self.canvas_zoom)))
        src_bottom = min(sh, int(math.ceil((visible.bottom - draw_rect.top) / self.canvas_zoom)))
        if src_right <= src_left or src_bottom <= src_top:
            return None
        src_rect = pygame.Rect(src_left, src_top, src_right - src_left, src_bottom - src_top)
        dst_left = draw_rect.left + int(round(src_rect.left * self.canvas_zoom))
        dst_top = draw_rect.top + int(round(src_rect.top * self.canvas_zoom))
        dst_right = draw_rect.left + int(round((src_rect.left + src_rect.width) * self.canvas_zoom))
        dst_bottom = draw_rect.top + int(round((src_rect.top + src_rect.height) * self.canvas_zoom))
        dst_rect = pygame.Rect(
            dst_left,
            dst_top,
            max(1, dst_right - dst_left),
            max(1, dst_bottom - dst_top),
        )
        return src_rect, dst_rect

    def _canvas_scaled_visible_frame_surface(
        self,
        frame_idx: int,
        draw_rect: pygame.Rect,
        clip_rect: pygame.Rect,
        *,
        alpha: int = 255,
    ) -> tuple[pygame.Surface, pygame.Rect, pygame.Rect] | None:
        if frame_idx >= len(self.canvas_frames) or not self.canvas_frames[frame_idx]:
            return None
        comp = self._canvas_composited_frame(frame_idx, alpha=alpha)
        if comp is None:
            return None
        visible_rects = self._canvas_visible_source_dest_rects(draw_rect, clip_rect, comp.get_size())
        if visible_rects is None:
            return None
        src_rect, dst_rect = visible_rects
        mip_level = 0
        source = comp
        source_rect = src_rect.copy()
        ratio = max(
            src_rect.width / max(1, dst_rect.width),
            src_rect.height / max(1, dst_rect.height),
        )
        if ratio >= 2.0:
            mip_level = max(0, int(math.floor(math.log2(ratio))))
            source = self._canvas_mipmap_surface(frame_idx, alpha=alpha, level=mip_level) or comp
            factor = 1 << mip_level
            sx0 = max(0, src_rect.x // factor)
            sy0 = max(0, src_rect.y // factor)
            sx1 = min(source.get_width(), int(math.ceil(src_rect.right / factor)))
            sy1 = min(source.get_height(), int(math.ceil(src_rect.bottom / factor)))
            source_rect = pygame.Rect(sx0, sy0, max(1, sx1 - sx0), max(1, sy1 - sy0))
        self._sync_canvas_render_cache_state()
        version = self._canvas_frame_versions[frame_idx] if frame_idx < len(self._canvas_frame_versions) else 0
        cache_key = (
            frame_idx,
            version,
            alpha,
            mip_level,
            source_rect.x,
            source_rect.y,
            source_rect.width,
            source_rect.height,
            dst_rect.width,
            dst_rect.height,
        )
        cached = self._canvas_visible_surface_cache.get(cache_key)
        if cached is None:
            patch = source.subsurface(source_rect).copy()
            cached = pygame.transform.scale(patch, (dst_rect.width, dst_rect.height))
            if len(self._canvas_visible_surface_cache) > 24:
                self._canvas_visible_surface_cache.clear()
            self._canvas_visible_surface_cache[cache_key] = cached
        return cached, source_rect, dst_rect

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

    def _canvas_mipmap_surface(
        self,
        frame_idx: int,
        *,
        alpha: int = 255,
        level: int = 0,
    ) -> pygame.Surface | None:
        base = self._canvas_composited_frame(frame_idx, alpha=alpha)
        if base is None:
            return None
        if level <= 0:
            return base
        self._sync_canvas_render_cache_state()
        version = self._canvas_frame_versions[frame_idx] if frame_idx < len(self._canvas_frame_versions) else 0
        cache_key = (frame_idx, version, alpha, level)
        cached = self._canvas_mipmap_cache.get(cache_key)
        if cached is not None:
            return cached
        prev = self._canvas_mipmap_surface(frame_idx, alpha=alpha, level=level - 1)
        if prev is None:
            return None
        width = max(1, (prev.get_width() + 1) // 2)
        height = max(1, (prev.get_height() + 1) // 2)
        scaled = pygame.transform.scale(prev, (width, height))
        self._canvas_mipmap_cache[cache_key] = scaled
        return scaled

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

    def _canvas_rename_dialog_layout(self) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
        panel = pygame.Rect(0, 0, 520, 196)
        panel.center = (self.screen_width // 2, self.screen_height // 2)
        input_rect = pygame.Rect(panel.x + 20, panel.y + 82, panel.width - 40, 40)
        save_rect = pygame.Rect(panel.right - 222, panel.bottom - 52, 96, 36)
        cancel_rect = pygame.Rect(panel.right - 114, panel.bottom - 52, 96, 36)
        return panel, input_rect, save_rect, cancel_rect

    def _open_canvas_rename_dialog(self, kind: str) -> None:
        if kind == "layer":
            if not self.canvas_frames:
                return
            self.canvas_rename_kind = "layer"
            self.canvas_rename_index = self.canvas_layer_idx
            fi = self.canvas_frame_idx
            self.canvas_name_input = self.canvas_layer_names[fi][self.canvas_layer_idx]
        elif kind == "frame":
            if not self.canvas_frames:
                return
            self.canvas_rename_kind = "frame"
            self.canvas_rename_index = self.canvas_frame_idx
            self.canvas_name_input = self._canvas_frame_name(self.canvas_frame_idx)
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
            fi = self.canvas_frame_idx
            li = self.canvas_rename_index
            if fi < len(self.canvas_layer_names) and li < len(self.canvas_layer_names[fi]):
                self.canvas_layer_names[fi][li] = name
                self.status = f"Layer renamed to {name}."
        elif self.canvas_rename_kind == "frame":
            idx = self.canvas_rename_index
            if idx < len(self.canvas_frame_names):
                self.canvas_frame_names[idx] = name
                self.status = f"Frame renamed to {name}."
        elif self.canvas_rename_kind == "tab":
            idx = self.canvas_rename_index
            if 0 <= idx < len(self.canvas_tabs):
                self.canvas_tabs[idx]["name"] = name
                self.status = f"Canvas tab renamed to {name}."
        self.dialog_mode = None
        self.canvas_rename_kind = None

    def _canvas_frame_name(self, idx: int) -> str:
        if 0 <= idx < len(self.canvas_frame_names) and self.canvas_frame_names[idx].strip():
            return self.canvas_frame_names[idx]
        return f"Frame {idx + 1}"

    def _copy_canvas_name(self, name: str) -> str:
        base = name.strip() or "Untitled"
        return f"{base} Copy"

    def _unique_export_path(self, target: Path) -> Path:
        if not target.exists():
            return target
        stem = target.stem
        suffix = target.suffix
        counter = 2
        while True:
            candidate = target.with_name(f"{stem}_{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

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

    def _save_canvas_to_assets(self) -> None:
        if self.canvas_surface is None:
            return
        self.status = "Canvas save was removed. Use Export instead."

    def _sync_canvas_preview_to_current_frame(self) -> None:
        if not self.canvas_preview_playing:
            self.canvas_preview_elapsed_ms = max(0, self.canvas_frame_idx) * self.canvas_preview_frame_ms

    def _set_canvas_preview_fps(self, fps: int) -> None:
        self.canvas_preview_fps = max(1, min(int(fps), 60))
        self.canvas_preview_frame_ms = max(1, int(round(1000 / self.canvas_preview_fps)))

    def _canvas_preview_elapsed(self, ticks_ms: int | None = None) -> int:
        if not self.canvas_preview_playing:
            return self.canvas_preview_elapsed_ms
        now = pygame.time.get_ticks() if ticks_ms is None else ticks_ms
        return max(0, now - self.canvas_preview_started_ms)

    def _canvas_preview_frame_idx(self, ticks_ms: int | None = None) -> int:
        n = len(self.canvas_frames)
        if n <= 1:
            return 0
        elapsed = self._canvas_preview_elapsed(ticks_ms)
        durations = [self.canvas_preview_frame_ms] * n
        return self._frame_index_for_time(durations, elapsed)

    def _toggle_canvas_preview(self) -> None:
        if len(self.canvas_frames) <= 1:
            self.canvas_preview_playing = False
            self.canvas_preview_elapsed_ms = 0
            self.status = "Animation preview needs at least two frames."
            return
        if self.canvas_preview_playing:
            self.canvas_preview_elapsed_ms = self._canvas_preview_elapsed()
            self.canvas_preview_playing = False
            self.status = "Animation preview paused."
        else:
            self.canvas_preview_started_ms = pygame.time.get_ticks() - self.canvas_preview_elapsed_ms
            self.canvas_preview_playing = True
            self.status = "Animation preview playing."

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
        preview_comp = self._canvas_composited_frame(preview_idx) if self.canvas_frames else None
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
        caption = f"{label}  {'Playing' if self.canvas_preview_playing and len(self.canvas_frames) > 1 else 'Paused'}  F{preview_idx + 1}/{max(1, len(self.canvas_frames))}"
        screen.blit(small.render(caption, True, (170, 190, 230)), (rect.x + 6, rect.y + 6))

    def _canvas_export_base_name(self) -> str:
        if self.canvas_asset_rel is not None:
            stem = Path(self.canvas_asset_rel).stem.strip()
            if stem:
                return stem
        return "canvas"

    @staticmethod
    def _surface_to_pil_image(surface: pygame.Surface) -> Image.Image:
        return Image.frombytes("RGBA", surface.get_size(), pygame.image.tobytes(surface, "RGBA"))

    def _canvas_export_surfaces(self) -> list[pygame.Surface]:
        frames: list[pygame.Surface] = []
        for idx in range(len(self.canvas_frames)):
            comp = self._canvas_composited_frame(idx)
            if comp is None:
                if self.canvas_surface is None:
                    continue
                comp = pygame.Surface(self.canvas_surface.get_size(), pygame.SRCALPHA)
                comp.fill((0, 0, 0, 0))
            frames.append(comp)
        return frames

    def _export_canvas_gif(self) -> Path | None:
        frames = self._canvas_export_surfaces()
        if not frames:
            self.status = "Nothing to export."
            return None
        self.exported_canvas_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = self._unique_export_path(self.exported_canvas_dir / f"{self._canvas_export_base_name()}_{ts}.gif")
        pil_frames = [self._surface_to_pil_image(frame) for frame in frames]
        first, rest = pil_frames[0], pil_frames[1:]
        first.save(
            target,
            save_all=True,
            append_images=rest,
            duration=self.canvas_preview_frame_ms,
            loop=0,
            disposal=2,
        )
        self.preview_cache.pop(f"preview:{target.as_posix()}", None)
        self.animation_cache.pop(target.as_posix(), None)
        self.image_size_cache.pop(target.as_posix(), None)
        self._refresh_assets()
        self.status = f"Exported GIF to assets/{target.relative_to(self.asset_root).as_posix()}."
        return target

    def _export_canvas_spritesheet(self) -> Path | None:
        frames = self._canvas_export_surfaces()
        if not frames:
            self.status = "Nothing to export."
            return None
        cell_w = max(frame.get_width() for frame in frames)
        cell_h = max(frame.get_height() for frame in frames)
        sheet = pygame.Surface((cell_w * len(frames), cell_h), pygame.SRCALPHA)
        sheet.fill((0, 0, 0, 0))
        for idx, frame in enumerate(frames):
            x = idx * cell_w + (cell_w - frame.get_width()) // 2
            y = (cell_h - frame.get_height()) // 2
            sheet.blit(frame, (x, y))
        self.exported_canvas_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = self._unique_export_path(self.exported_canvas_dir / f"{self._canvas_export_base_name()}_{ts}_sheet.png")
        pygame.image.save(sheet, target.as_posix())
        self.preview_cache.pop(f"preview:{target.as_posix()}", None)
        self.image_cache.pop(target.as_posix(), None)
        self.animation_cache.pop(target.as_posix(), None)
        self.image_size_cache.pop(target.as_posix(), None)
        self._refresh_assets()
        self.status = f"Exported spritesheet to assets/{target.relative_to(self.asset_root).as_posix()}."
        return target

    def _export_canvas_png(self) -> Path | None:
        frames = self._canvas_export_surfaces()
        if not frames:
            self.status = "Nothing to export."
            return None
        frame = frames[min(self.canvas_frame_idx, len(frames) - 1)]
        self.exported_canvas_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_frame{self.canvas_frame_idx + 1}" if len(frames) > 1 else ""
        target = self._unique_export_path(self.exported_canvas_dir / f"{self._canvas_export_base_name()}_{ts}{suffix}.png")
        pygame.image.save(frame, target.as_posix())
        self.preview_cache.pop(f"preview:{target.as_posix()}", None)
        self.image_cache.pop(target.as_posix(), None)
        self.animation_cache.pop(target.as_posix(), None)
        self.image_size_cache.pop(target.as_posix(), None)
        self._refresh_assets()
        self.status = f"Exported PNG to assets/{target.relative_to(self.asset_root).as_posix()}."
        return target

    def _canvas_merge_layers(self) -> None:
        if not self.canvas_frames:
            self.status = "No layers to merge."
            return
        fi = self.canvas_frame_idx
        if fi >= len(self.canvas_frames) or len(self.canvas_frames[fi]) <= 1:
            self.status = "Need at least two layers to merge."
            return
        selected = self._canvas_selected_layer_indices()
        if len(selected) < 2:
            self.status = "Cmd-click two or more layers, then press Merge."
            return
        base_layers = self.canvas_frames[fi]
        merged = pygame.Surface(base_layers[0].get_size(), pygame.SRCALPHA)
        merged.fill((0, 0, 0, 0))
        for li in selected:
            merged.blit(base_layers[li], (0, 0))
        selected_set = set(selected)
        topmost = max(selected)
        merged_name = "Merged " + " + ".join(
            self.canvas_layer_names[fi][li] for li in selected[:3]
        )
        if len(selected) > 3:
            merged_name += "..."
        new_layers: list[pygame.Surface] = []
        new_names: list[str] = []
        new_visible: list[bool] = []
        merged_idx = 0
        for li, surf in enumerate(base_layers):
            if li in selected_set:
                if li == topmost:
                    merged_idx = len(new_layers)
                    new_layers.append(merged)
                    new_names.append(merged_name[:28] or "Merged Layer")
                    new_visible.append(any(self.canvas_layer_visible[fi][sel] for sel in selected))
                continue
            new_layers.append(surf)
            new_names.append(self.canvas_layer_names[fi][li])
            new_visible.append(self.canvas_layer_visible[fi][li])
        self.canvas_frames[fi] = new_layers
        self.canvas_layer_names[fi] = new_names
        self.canvas_layer_visible[fi] = new_visible
        self.canvas_layer_idx = merged_idx
        self.canvas_selected_layers = {merged_idx}
        self.canvas_selection_pixels.clear()
        self.canvas_undo_stack.clear()
        self.canvas_redo_stack.clear()
        self._mark_canvas_changed(fi)
        self.status = f"Merged {len(selected)} layers on frame {fi + 1}."

    # ── Undo / redo ────────────────────────────────────────────────────

    def _canvas_push_undo(self) -> None:
        if self.canvas_surface is None:
            return
        self.canvas_undo_stack.append(self.canvas_surface.copy())
        if len(self.canvas_undo_stack) > self._canvas_undo_max:
            self.canvas_undo_stack.pop(0)
        self.canvas_redo_stack.clear()

    def _canvas_undo(self) -> None:
        if not self.canvas_undo_stack or self.canvas_surface is None:
            self.status = "Nothing to undo."
            return
        self.canvas_redo_stack.append(self.canvas_surface.copy())
        self.canvas_surface = self.canvas_undo_stack.pop()
        self._mark_canvas_changed()
        self.status = f"Undo  ({len(self.canvas_undo_stack)} left)."

    def _canvas_redo(self) -> None:
        if not self.canvas_redo_stack or self.canvas_surface is None:
            self.status = "Nothing to redo."
            return
        self.canvas_undo_stack.append(self.canvas_surface.copy())
        self.canvas_surface = self.canvas_redo_stack.pop()
        self._mark_canvas_changed()
        self.status = "Redo."

    # ── Copy / paste ────────────────────────────────────────────────────

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

    def _canvas_frame_size(self) -> tuple[int, int]:
        """Return (w, h) of the current canvas, or (64,64) if none."""
        surf = self.canvas_surface
        return surf.get_size() if surf is not None else (64, 64)

    def _canvas_add_frame(self) -> None:
        w, h = self._canvas_frame_size()
        new_layer = pygame.Surface((w, h), pygame.SRCALPHA)
        new_layer.fill((0, 0, 0, 0))
        self.canvas_frames.append([new_layer])
        self.canvas_frame_names.append(f"Frame {len(self.canvas_frames)}")
        self.canvas_layer_names.append(["Layer 1"])
        self.canvas_layer_visible.append([True])
        self._sync_canvas_render_cache_state()
        self.canvas_frame_idx = len(self.canvas_frames) - 1
        self.canvas_layer_idx = 0
        self.canvas_undo_stack.clear()
        self.canvas_redo_stack.clear()
        self.canvas_selected_layers = {0}
        self._sync_canvas_preview_to_current_frame()
        self.status = f"Frame {self.canvas_frame_idx + 1} added."

    def _canvas_duplicate_frame(self) -> None:
        if not self.canvas_frames:
            return
        fi = self.canvas_frame_idx
        new_frame = [surf.copy() for surf in self.canvas_frames[fi]]
        new_frame_name = self._copy_canvas_name(self._canvas_frame_name(fi))
        new_names = list(self.canvas_layer_names[fi])
        new_vis = list(self.canvas_layer_visible[fi])
        self.canvas_frames.insert(fi + 1, new_frame)
        self.canvas_frame_names.insert(fi + 1, new_frame_name)
        self.canvas_layer_names.insert(fi + 1, new_names)
        self.canvas_layer_visible.insert(fi + 1, new_vis)
        self._sync_canvas_render_cache_state()
        self.canvas_frame_idx = fi + 1
        self.canvas_selected_layers = {min(self.canvas_layer_idx, len(new_frame) - 1)}
        self._sync_canvas_preview_to_current_frame()
        self.status = f"Duplicated frame → frame {self.canvas_frame_idx + 1}."

    def _canvas_remove_frame(self) -> None:
        if len(self.canvas_frames) <= 1:
            self.status = "Cannot remove the only frame."
            return
        fi = self.canvas_frame_idx
        self.canvas_frames.pop(fi)
        self.canvas_frame_names.pop(fi)
        self.canvas_layer_names.pop(fi)
        self.canvas_layer_visible.pop(fi)
        self._sync_canvas_render_cache_state()
        self.canvas_frame_idx = min(fi, len(self.canvas_frames) - 1)
        self.canvas_layer_idx = min(self.canvas_layer_idx, len(self.canvas_frames[self.canvas_frame_idx]) - 1)
        self._canvas_reset_layer_selection()
        self.canvas_undo_stack.clear()
        self.canvas_redo_stack.clear()
        self._sync_canvas_preview_to_current_frame()
        self.status = f"Frame removed. Now on frame {self.canvas_frame_idx + 1}."

    def _canvas_switch_frame(self, idx: int) -> None:
        if not self.canvas_frames or not (0 <= idx < len(self.canvas_frames)):
            return
        self.canvas_frame_idx = idx
        self.canvas_layer_idx = min(self.canvas_layer_idx, len(self.canvas_frames[idx]) - 1)
        self._canvas_reset_layer_selection()
        self.canvas_undo_stack.clear()
        self.canvas_redo_stack.clear()
        self._sync_canvas_preview_to_current_frame()

    def _canvas_move_frame(self, delta: int) -> None:
        if not self.canvas_frames:
            return
        fi = self.canvas_frame_idx
        target = fi + delta
        if not (0 <= target < len(self.canvas_frames)):
            self.status = "Frame is already at the edge."
            return
        for seq in (self.canvas_frames, self.canvas_frame_names, self.canvas_layer_names, self.canvas_layer_visible):
            seq[fi], seq[target] = seq[target], seq[fi]
        if fi < len(self._canvas_frame_versions) and target < len(self._canvas_frame_versions):
            self._canvas_frame_versions[fi], self._canvas_frame_versions[target] = self._canvas_frame_versions[target], self._canvas_frame_versions[fi]
        self.canvas_frame_idx = target
        self._canvas_reset_layer_selection()
        self._sync_canvas_preview_to_current_frame()
        self.status = f"Frame moved {'forward' if delta > 0 else 'back'}."

    def _canvas_add_layer(self) -> None:
        if not self.canvas_frames:
            return
        w, h = self._canvas_frame_size()
        fi = self.canvas_frame_idx
        new_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        new_surf.fill((0, 0, 0, 0))
        self.canvas_frames[fi].append(new_surf)
        n = len(self.canvas_frames[fi])
        self.canvas_layer_names[fi].append(f"Layer {n}")
        self.canvas_layer_visible[fi].append(True)
        self._invalidate_canvas_render_cache(fi)
        self.canvas_layer_idx = n - 1
        self.canvas_selected_layers = {self.canvas_layer_idx}
        self.canvas_undo_stack.clear()
        self.canvas_redo_stack.clear()
        self.status = f"Layer {n} added."

    def _canvas_duplicate_layer(self) -> None:
        if not self.canvas_frames:
            return
        fi = self.canvas_frame_idx
        li = self.canvas_layer_idx
        self.canvas_frames[fi].insert(li + 1, self.canvas_frames[fi][li].copy())
        self.canvas_layer_names[fi].insert(li + 1, self._copy_canvas_name(self.canvas_layer_names[fi][li]))
        self.canvas_layer_visible[fi].insert(li + 1, self.canvas_layer_visible[fi][li])
        self._invalidate_canvas_render_cache(fi)
        self.canvas_layer_idx = li + 1
        self.canvas_selected_layers = {self.canvas_layer_idx}
        self.canvas_undo_stack.clear()
        self.canvas_redo_stack.clear()
        self.status = "Layer duplicated."

    def _canvas_remove_layer(self) -> None:
        if not self.canvas_frames:
            return
        fi = self.canvas_frame_idx
        if len(self.canvas_frames[fi]) <= 1:
            self.status = "Cannot remove the only layer."
            return
        li = self.canvas_layer_idx
        self.canvas_frames[fi].pop(li)
        self.canvas_layer_names[fi].pop(li)
        self.canvas_layer_visible[fi].pop(li)
        self._invalidate_canvas_render_cache(fi)
        self.canvas_layer_idx = min(li, len(self.canvas_frames[fi]) - 1)
        self._canvas_reset_layer_selection()
        self.canvas_undo_stack.clear()
        self.canvas_redo_stack.clear()
        self.status = "Layer removed."

    def _canvas_move_layer(self, delta: int) -> None:
        if not self.canvas_frames:
            return
        fi = self.canvas_frame_idx
        li = self.canvas_layer_idx
        target = li + delta
        if not (0 <= target < len(self.canvas_frames[fi])):
            self.status = "Layer is already at the edge."
            return
        for seq in (self.canvas_frames[fi], self.canvas_layer_names[fi], self.canvas_layer_visible[fi]):
            seq[li], seq[target] = seq[target], seq[li]
        self._invalidate_canvas_render_cache(fi)
        self.canvas_layer_idx = target
        self.canvas_selected_layers = {target}
        self.canvas_undo_stack.clear()
        self.canvas_redo_stack.clear()
        self.status = f"Layer moved {'up' if delta > 0 else 'down'}."

    def _canvas_composited_frame(self, frame_idx: int, alpha: int = 255) -> pygame.Surface | None:
        """Composite all visible layers of a frame into one surface."""
        if frame_idx >= len(self.canvas_frames) or not self.canvas_frames[frame_idx]:
            return None
        self._sync_canvas_render_cache_state()
        version = self._canvas_frame_versions[frame_idx] if frame_idx < len(self._canvas_frame_versions) else 0
        cache_key = (frame_idx, version, alpha)
        cached = self._canvas_composite_cache.get(cache_key)
        if cached is not None:
            return cached
        layers = self.canvas_frames[frame_idx]
        w, h = layers[0].get_size()
        comp = pygame.Surface((w, h), pygame.SRCALPHA)
        comp.fill((0, 0, 0, 0))
        for i, surf in enumerate(layers):
            if self.canvas_layer_visible[frame_idx][i]:
                if alpha < 255:
                    tmp = surf.copy()
                    tmp.set_alpha(alpha)
                    comp.blit(tmp, (0, 0))
                else:
                    comp.blit(surf, (0, 0))
        self._canvas_composite_cache[cache_key] = comp
        return comp

    def _canvas_scaled_frame_surface(
        self,
        frame_idx: int,
        size: tuple[int, int],
        *,
        alpha: int = 255,
    ) -> pygame.Surface | None:
        if size[0] <= 0 or size[1] <= 0:
            return None
        comp = self._canvas_composited_frame(frame_idx, alpha=alpha)
        if comp is None:
            return None
        source = comp
        ratio = max(
            comp.get_width() / max(1, int(size[0])),
            comp.get_height() / max(1, int(size[1])),
        )
        if ratio >= 2.0:
            mip_level = max(0, int(math.floor(math.log2(ratio))))
            source = self._canvas_mipmap_surface(frame_idx, alpha=alpha, level=mip_level) or comp
        self._sync_canvas_render_cache_state()
        version = self._canvas_frame_versions[frame_idx] if frame_idx < len(self._canvas_frame_versions) else 0
        cache_key = (frame_idx, version, alpha, int(size[0]), int(size[1]))
        cached = self._canvas_scaled_surface_cache.get(cache_key)
        if cached is not None:
            return cached
        scaled = pygame.transform.scale(source, (max(1, int(size[0])), max(1, int(size[1]))))
        self._canvas_scaled_surface_cache[cache_key] = scaled
        return scaled

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

    def _save_canvas_asset(self) -> None:
        self._save_canvas_to_assets()

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
                self._canvas_stroke_undo_pushed = True
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
                        self.canvas_resize_orig = (sw, sh)
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
            orig_w, orig_h = self.canvas_resize_orig
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
        self._canvas_stroke_undo_pushed = False

    def _board_local_at(self, pos: tuple[int, int]) -> tuple[float, float] | None:
        viewport = self._scene_viewport_rect()
        if not viewport.collidepoint(pos):
            return None
        offset_x, offset_y = self._scene_offset(viewport)
        local_x = ((pos[0] - viewport.x - offset_x) / max(self.zoom, 0.001)) + self.camera_x
        local_y = ((pos[1] - viewport.y - offset_y) / max(self.zoom, 0.001)) + self.camera_y
        if not (0.0 <= local_x <= self.active_scene.board_width and 0.0 <= local_y <= self.active_scene.board_height):
            return None
        return float(local_x), float(local_y)

    def _sprite_at(self, local_pos: tuple[float, float]) -> SpritePlacement | None:
        lx, ly = local_pos
        for sprite in reversed(self.active_scene.sprites):
            if sprite.x <= lx <= sprite.x + sprite.width and sprite.y <= ly <= sprite.y + sprite.height:
                return sprite
        return None

    def _selected_sprite(self) -> SpritePlacement | None:
        if self.selected_sprite_id is not None:
            sprite = self._sprite_by_id(self.selected_sprite_id)
            if sprite is not None:
                return sprite
            self.selected_sprite_id = None
        if self.selected_sprite_id is None:
            if self.selected_sprite_ids:
                sid = next(iter(self.selected_sprite_ids))
                self.selected_sprite_id = sid
                return self._sprite_by_id(sid)
        return None

    def _place_new_sprite(
        self,
        asset_path: str,
        local_pos: tuple[float, float],
        *,
        select: bool = True,
        report_status: bool = True,
        push_undo: bool = True,
    ) -> bool:
        native_size = self._image_size_for(asset_path)
        if native_size is None:
            if report_status:
                self.status = "Could not load that asset."
            return False
        if push_undo:
            self._push_scene_undo()
        width, height = native_size
        x = local_pos[0] - width / 2
        y = local_pos[1] - height / 2
        sprite = SpritePlacement(
            sprite_id=self.next_sprite_id,
            asset_path=asset_path,
            x=x,
            y=y,
            width=width,
            height=height,
            rotation_x=0.0,
            rotation_y=0.0,
            rotation_z=0.0,
        )
        self.next_sprite_id += 1
        self._clamp_sprite_to_scene(sprite)
        self.active_scene.sprites.append(sprite)
        if select:
            self._set_selection({sprite.sprite_id}, primary=sprite.sprite_id)
        if report_status:
            self.status = f"Placed {Path(asset_path).name} at its native size ({width}x{height})."
        return True

    def _arm_duplicate_drag_mode(self) -> None:
        sprite = self._selected_sprite()
        if sprite is None:
            self.status = "Select one asset, press D, then drag to duplicate."
            return
        self._copy_selected_sprite()
        self.duplicate_drag_template = SpritePlacement(
            sprite_id=0,
            asset_path=sprite.asset_path,
            x=0.0,
            y=0.0,
            width=sprite.width,
            height=sprite.height,
            rotation_x=sprite.rotation_x,
            rotation_y=sprite.rotation_y,
            rotation_z=sprite.rotation_z,
        )
        self.duplicate_drag_mode = True
        self.duplicate_dragging = False
        self.duplicate_drag_last_cell = None
        self.duplicate_drag_cells.clear()
        self.duplicate_drag_count = 0
        self.status = "Duplicate mode armed. Drag in scene to stamp copies."

    def _stamp_duplicate_cell(self, template: SpritePlacement, cell: tuple[int, int]) -> bool:
        if cell in self.duplicate_drag_cells:
            return False
        cell_w = max(int(template.width), 1)
        cell_h = max(int(template.height), 1)
        center_x = cell[0] * cell_w + (cell_w / 2)
        center_y = cell[1] * cell_h + (cell_h / 2)
        sprite = SpritePlacement(
            sprite_id=self.next_sprite_id,
            asset_path=template.asset_path,
            x=center_x - template.width / 2,
            y=center_y - template.height / 2,
            width=template.width,
            height=template.height,
            rotation_x=template.rotation_x,
            rotation_y=template.rotation_y,
            rotation_z=template.rotation_z,
        )
        self.next_sprite_id += 1
        self._clamp_sprite_to_scene(sprite)
        self.active_scene.sprites.append(sprite)
        self.duplicate_drag_cells.add(cell)
        self.duplicate_drag_count += 1
        return True

    def _stamp_duplicate_drag(self, local_pos: tuple[float, float], *, force: bool = False) -> bool:
        template = self.duplicate_drag_template
        if template is None:
            return False
        cell_w = max(int(template.width), 1)
        cell_h = max(int(template.height), 1)
        current = (
            int(max(local_pos[0], 0.0) // cell_w),
            int(max(local_pos[1], 0.0) // cell_h),
        )
        last = self.duplicate_drag_last_cell
        did_stamp = False
        if last is None:
            did_stamp |= self._stamp_duplicate_cell(template, current)
        else:
            dx = current[0] - last[0]
            dy = current[1] - last[1]
            steps = max(abs(dx), abs(dy))
            if steps == 0 and not force:
                return False
            if steps == 0:
                did_stamp |= self._stamp_duplicate_cell(template, current)
            else:
                for i in range(1, steps + 1):
                    t = i / steps
                    cell = (round(last[0] + dx * t), round(last[1] + dy * t))
                    did_stamp |= self._stamp_duplicate_cell(template, cell)
        self.duplicate_drag_last_cell = current
        return did_stamp

    def _remove_sprite(self, sprite_id: int) -> None:
        for index, sprite in enumerate(self.active_scene.sprites):
            if sprite.sprite_id == sprite_id:
                removed = self.active_scene.sprites.pop(index)
                self.selected_sprite_ids.discard(sprite_id)
                if self.selected_sprite_id == sprite_id:
                    self.selected_sprite_id = None
                if self.resizing_sprite_id == sprite_id:
                    self.resizing_sprite_id = None
                self.status = f"Removed {Path(removed.asset_path).name}."
                return

    def _remove_selected_sprites(self) -> None:
        ids = set(self.selected_sprite_ids)
        if not ids and self.selected_sprite_id is not None:
            ids = {self.selected_sprite_id}
        if not ids:
            return
        self._push_scene_undo()
        self.active_scene.sprites = [sprite for sprite in self.active_scene.sprites if sprite.sprite_id not in ids]
        self._clear_selection()
        self.resizing_sprite_id = None
        self.status = "Removed selected assets."

    def _resize_selected_sprite(self, scale_delta: float) -> None:
        sprites = self._selected_sprites()
        if not sprites:
            return
        self._push_scene_undo()
        for sprite in sprites:
            aspect = sprite.width / max(sprite.height, 1)
            next_width = max(8, int(sprite.width * scale_delta))
            next_height = max(8, int(next_width / max(aspect, 0.0001)))
            center_x = sprite.x + sprite.width / 2
            center_y = sprite.y + sprite.height / 2
            sprite.width = next_width
            sprite.height = next_height
            sprite.x = center_x - sprite.width / 2
            sprite.y = center_y - sprite.height / 2
            self._clamp_sprite_to_scene(sprite)
        self.status = f"Resized {len(sprites)} selected asset(s)."

    def _rotate_selected_sprites(self, axis: str, degrees: float, absolute: bool = False) -> None:
        sprites = self._selected_sprites()
        if not sprites:
            return
        self._push_scene_undo()
        for sprite in sprites:
            current = {"x": sprite.rotation_x, "y": sprite.rotation_y, "z": sprite.rotation_z}.get(axis, 0.0)
            value = degrees if absolute else (current + degrees)
            value %= 360.0
            if axis == "x":
                sprite.rotation_x = value
            elif axis == "y":
                sprite.rotation_y = value
            else:
                sprite.rotation_z = value
        self.status = f"Rotated {len(sprites)} selected asset(s) on {axis.upper()}."

    def _copy_selected_sprite(self) -> None:
        sprites = self._selected_sprites()
        if not sprites:
            self.status = "Select an asset first, then press D to duplicate."
            return
        min_x = min(sprite.x for sprite in sprites)
        min_y = min(sprite.y for sprite in sprites)
        self.clipboard_sprites = [
            SpritePlacement(
                sprite_id=0,
                asset_path=sprite.asset_path,
                x=sprite.x - min_x,
                y=sprite.y - min_y,
                width=sprite.width,
                height=sprite.height,
                rotation_x=sprite.rotation_x,
                rotation_y=sprite.rotation_y,
                rotation_z=sprite.rotation_z,
            )
            for sprite in sprites
        ]
        self.status = f"Copied {len(self.clipboard_sprites)} asset(s). Press V to paste."

    def _paste_sprite(self, local_pos: tuple[float, float] | None) -> None:
        if not self.clipboard_sprites:
            self.status = "Nothing copied yet. Select an asset and press D first."
            return
        self._push_scene_undo()
        source_bounds_w = max(item.x + item.width for item in self.clipboard_sprites)
        source_bounds_h = max(item.y + item.height for item in self.clipboard_sprites)
        if local_pos is None:
            selected = self._selected_sprite()
            if selected is not None:
                local_pos = (selected.x + selected.width / 2 + 24, selected.y + selected.height / 2 + 24)
            else:
                local_pos = (
                    self.active_scene.board_width / 2,
                    self.active_scene.board_height / 2,
                )
        top_left_x = local_pos[0] - source_bounds_w / 2
        top_left_y = local_pos[1] - source_bounds_h / 2
        pasted_ids: set[int] = set()
        for source in self.clipboard_sprites:
            sprite = SpritePlacement(
                sprite_id=self.next_sprite_id,
                asset_path=source.asset_path,
                x=top_left_x + source.x,
                y=top_left_y + source.y,
                width=source.width,
                height=source.height,
                rotation_x=source.rotation_x,
                rotation_y=source.rotation_y,
                rotation_z=source.rotation_z,
            )
            self.next_sprite_id += 1
            self._clamp_sprite_to_scene(sprite)
            self.active_scene.sprites.append(sprite)
            pasted_ids.add(sprite.sprite_id)
        self._set_selection(pasted_ids)
        self.status = f"Pasted {len(pasted_ids)} asset(s)."

    def _nudge_selected_sprite(self, dx: float, dy: float) -> bool:
        sprites = self._selected_sprites()
        if not sprites:
            return False
        self._push_scene_undo()
        for sprite in sprites:
            sprite.x += dx
            sprite.y += dy
            self._clamp_sprite_to_scene(sprite)
        return True

    def _sort_selected_to_front(self) -> None:
        ids = set(self.selected_sprite_ids)
        if not ids:
            if self.selected_sprite_id is None:
                return
            ids = {self.selected_sprite_id}
        if not ids:
            return
        selected = [item for item in self.active_scene.sprites if item.sprite_id in ids]
        self.active_scene.sprites = [item for item in self.active_scene.sprites if item.sprite_id not in ids]
        self.active_scene.sprites.extend(selected)

    def _toggle_rotation_gizmo(self) -> None:
        if self.rotation_gizmo_enabled:
            self.rotation_gizmo_enabled = False
            self.rotation_gizmo_axis = None
            self.status = "Rotation gizmo disabled."
            return
        if not self._selected_sprites():
            self.rotation_gizmo_enabled = False
            self.status = "Select one or more assets first, then press R."
            return
        self.rotation_gizmo_enabled = True
        self.rotation_gizmo_axis = None
        self.status = "Rotation gizmo enabled. Drag X/Y/Z rings to rotate selection."

    def _rotation_gizmo_center_screen(self) -> tuple[float, float] | None:
        rect = self._selection_screen_rect()
        if rect is None:
            return None
        return (float(rect.centerx), float(rect.centery))

    def _rotation_gizmo_metrics(self) -> tuple[float, float, float] | None:
        rect = self._selection_screen_rect()
        if rect is None:
            return None
        base = max(42.0, min(180.0, max(rect.width, rect.height) * 0.65))
        x_ry = max(10.0, base * 0.32)
        y_rx = max(10.0, base * 0.32)
        return (base, x_ry, y_rx)

    def _ring_hit_score(self, value: float, tolerance: float) -> float:
        return abs(value - 1.0) / max(tolerance, 1e-6)

    def _rotation_gizmo_hit_axis(self, pos: tuple[int, int]) -> str | None:
        if not self.rotation_gizmo_enabled or self.dialog_mode is not None or self.dropdown_open is not None:
            return None
        center = self._rotation_gizmo_center_screen()
        metrics = self._rotation_gizmo_metrics()
        if center is None or metrics is None:
            return None
        cx, cy = center
        radius, x_ry, y_rx = metrics
        dx = pos[0] - cx
        dy = pos[1] - cy
        tol = max(0.08, 8.0 / max(radius, 1.0))

        z_val = (dx * dx + dy * dy) / max(radius * radius, 1e-6)
        x_val = (dx * dx) / max(radius * radius, 1e-6) + (dy * dy) / max(x_ry * x_ry, 1e-6)
        y_val = (dx * dx) / max(y_rx * y_rx, 1e-6) + (dy * dy) / max(radius * radius, 1e-6)

        candidates = [
            ("z", self._ring_hit_score(z_val, tol)),
            ("x", self._ring_hit_score(x_val, tol)),
            ("y", self._ring_hit_score(y_val, tol)),
        ]
        axis, score = min(candidates, key=lambda item: item[1])
        if score <= 1.0:
            return axis
        return None

    def _rotation_param_angle(self, axis: str, pos: tuple[int, int], center: tuple[float, float], metrics: tuple[float, float, float]) -> float:
        cx, cy = center
        radius, x_ry, y_rx = metrics
        dx = pos[0] - cx
        dy = pos[1] - cy
        if axis == "z":
            return math.degrees(math.atan2(dy, dx))
        if axis == "x":
            return math.degrees(math.atan2(dy / max(x_ry, 1e-6), dx / max(radius, 1e-6)))
        return math.degrees(math.atan2(dy / max(radius, 1e-6), dx / max(y_rx, 1e-6)))

    def _normalize_angle_delta(self, delta: float) -> float:
        while delta > 180.0:
            delta -= 360.0
        while delta < -180.0:
            delta += 360.0
        return delta

    def _start_rotation_gizmo_drag(self, axis: str, pos: tuple[int, int]) -> bool:
        center = self._rotation_gizmo_center_screen()
        metrics = self._rotation_gizmo_metrics()
        if center is None or metrics is None:
            return False
        ids = {sprite.sprite_id for sprite in self._selected_sprites()}
        if not ids:
            return False
        self.rotation_gizmo_axis = axis
        self.rotation_gizmo_start_angle = self._rotation_param_angle(axis, pos, center, metrics)
        self.rotation_gizmo_start_values = {}
        for sid in ids:
            sprite = self._sprite_by_id(sid)
            if sprite is None:
                continue
            self.rotation_gizmo_start_values[sid] = (sprite.rotation_x, sprite.rotation_y, sprite.rotation_z)
        self.status = f"Rotating selected assets on {axis.upper()} axis."
        return True

    def _update_rotation_gizmo_drag(self, pos: tuple[int, int]) -> None:
        axis = self.rotation_gizmo_axis
        if axis is None:
            return
        center = self._rotation_gizmo_center_screen()
        metrics = self._rotation_gizmo_metrics()
        if center is None or metrics is None:
            return
        current = self._rotation_param_angle(axis, pos, center, metrics)
        delta = self._normalize_angle_delta(current - self.rotation_gizmo_start_angle)
        for sid, (base_x, base_y, base_z) in self.rotation_gizmo_start_values.items():
            sprite = self._sprite_by_id(sid)
            if sprite is None:
                continue
            if axis == "x":
                sprite.rotation_x = (base_x + delta) % 360.0
            elif axis == "y":
                sprite.rotation_y = (base_y + delta) % 360.0
            else:
                sprite.rotation_z = (base_z + delta) % 360.0

    def _render_scene_surface(self, only_ids: set[int] | None = None) -> tuple[pygame.Surface, pygame.Rect]:
        ticks = pygame.time.get_ticks()
        sprites = self.active_scene.sprites if only_ids is None else [s for s in self.active_scene.sprites if s.sprite_id in only_ids]
        if only_ids is None:
            bounds = pygame.Rect(0, 0, self.active_scene.board_width, self.active_scene.board_height)
        else:
            rects: list[pygame.Rect] = []
            for sprite in sprites:
                transformed = self._sprite_render_surface(sprite, ticks)
                if transformed is None:
                    continue
                center = (int(sprite.x + sprite.width / 2), int(sprite.y + sprite.height / 2))
                rects.append(transformed.get_rect(center=center))
            if not rects:
                bounds = pygame.Rect(0, 0, 1, 1)
            else:
                bounds = rects[0].copy()
                for rect in rects[1:]:
                    bounds = bounds.union(rect)

        surface = pygame.Surface((max(1, bounds.width), max(1, bounds.height)), pygame.SRCALPHA)
        for sprite in sprites:
            transformed = self._sprite_render_surface(sprite, ticks)
            if transformed is None:
                continue
            center = (int(sprite.x + sprite.width / 2), int(sprite.y + sprite.height / 2))
            draw_rect = transformed.get_rect(center=center)
            draw_rect.x -= bounds.x
            draw_rect.y -= bounds.y
            surface.blit(transformed, draw_rect)
        return surface, bounds

    def _merge_selected_assets(self) -> None:
        ids = set(self.selected_sprite_ids)
        if not ids and self.selected_sprite_id is not None:
            ids = {self.selected_sprite_id}
        if len(ids) < 2:
            self.status = "Select at least two assets to merge."
            return
        self._push_scene_undo()
        merged_surface, bounds = self._render_scene_surface(only_ids=ids)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"merged_{timestamp}.png"
        target = self.merged_asset_dir / filename
        pygame.image.save(merged_surface, target.as_posix())
        rel_path = target.relative_to(self.asset_root).as_posix()

        self.active_scene.sprites = [sprite for sprite in self.active_scene.sprites if sprite.sprite_id not in ids]
        merged_sprite = SpritePlacement(
            sprite_id=self.next_sprite_id,
            asset_path=rel_path,
            x=float(bounds.x),
            y=float(bounds.y),
            width=max(1, bounds.width),
            height=max(1, bounds.height),
            rotation_x=0.0,
            rotation_y=0.0,
            rotation_z=0.0,
        )
        self._clamp_sprite_to_scene(merged_sprite)
        self.next_sprite_id += 1
        self.active_scene.sprites.append(merged_sprite)
        self.preview_cache.pop(f"preview:{target.as_posix()}", None)
        self.image_cache.pop(target.as_posix(), None)
        self.animation_cache.pop(target.as_posix(), None)
        self.image_size_cache.pop(target.as_posix(), None)
        self._refresh_assets()
        self._set_selection({merged_sprite.sprite_id}, primary=merged_sprite.sprite_id)
        self.status = f"Merged selection to assets/{rel_path}."

    def _export_active_scene_png(self) -> None:
        surface, _ = self._render_scene_surface(only_ids=None)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self._safe_scene_filename(self.active_scene.name)}_{timestamp}.png"
        target = self.exported_asset_dir / filename
        pygame.image.save(surface, target.as_posix())
        self.status = f"Exported scene PNG to assets/{target.relative_to(self.asset_root).as_posix()}."

    def _handle_menu_click(self, pos: tuple[int, int]) -> bool:
        buttons = self._menu_buttons()
        for name, rect in buttons.items():
            if rect.collidepoint(pos):
                self.rotation_gizmo_enabled = False
                if name == "canvas":
                    self.workspace_mode = "canvas"
                    self.dropdown_open = None
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
                    elif self.dropdown_open == "scene":
                        if label == "New Scene":
                            self._open_new_scene_dialog()
                        elif label == "Save Scene":
                            self._save_scene()
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
        n = len(self.canvas_frames)
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
                    fi = self.canvas_frame_idx
                    li = self.canvas_layer_idx
                    if fi < len(self.canvas_layer_visible) and li < len(self.canvas_layer_visible[fi]):
                        self.canvas_layer_visible[fi][li] = not self.canvas_layer_visible[fi][li]
                        self._invalidate_canvas_render_cache(fi)
                        self.status = f"Layer {'shown' if self.canvas_layer_visible[fi][li] else 'hidden'}."
                elif key == "layer_del":
                    self._canvas_remove_layer()
                return True

        # ── Layer row clicks ─────────────────────────────────────────
        if self.canvas_frames:
            fi = self.canvas_frame_idx
            frame_layers = self.canvas_frames[fi] if fi < len(self.canvas_frames) else []
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
                        if fi < len(self.canvas_layer_visible) and li < len(self.canvas_layer_visible[fi]):
                            self.canvas_layer_visible[fi][li] = not self.canvas_layer_visible[fi][li]
                            self._invalidate_canvas_render_cache(fi)
                            self.status = f"Layer {'shown' if self.canvas_layer_visible[fi][li] else 'hidden'}."
                    else:
                        if cmd_held:
                            self._canvas_toggle_layer_selection(li)
                            self.status = f"Selected {len(self._canvas_selected_layer_indices())} layer(s) for merge."
                        else:
                            self.canvas_layer_idx = li
                            self.canvas_selected_layers = {li}
                            self.canvas_undo_stack.clear()
                            self.canvas_redo_stack.clear()
                            self.status = f"Switched to layer {li + 1}."
                    return True
                row_y += 20

        if not cmd_held:
            self._canvas_clear_extra_layer_selection()
        return panel.collidepoint(pos)  # swallow any other click in panel

    def _handle_asset_browser_click(self, pos: tuple[int, int]) -> bool:
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
                    self.asset_page = max(self.asset_page - 1, 0)
                elif name == "next":
                    self.asset_page = min(self.asset_page + 1, self._max_asset_page())
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
        if entry.is_dir:
            self._change_asset_dir(entry.path)
        else:
            if self.workspace_mode == "canvas":
                if self._canvas_editable(entry.rel_path):
                    self.canvas_asset_rel = entry.rel_path
                    self.canvas_surface = None
                    self._sync_canvas_for_selection()
                    self.canvas_offset_x = 0.0
                    self.canvas_offset_y = 0.0
                    self._canvas_fit()
                    self._save_active_canvas_tab_state()
                    self.status = f"Loaded for editing: {entry.name}"
                else:
                    self.status = "Canvas mode supports PNG/JPG/BMP assets."
                return True
            self.duplicate_drag_mode = False
            self.duplicate_dragging = False
            self.duplicate_drag_last_cell = None
            self.duplicate_drag_cells.clear()
            self.duplicate_drag_count = 0
            self.drag_asset_path = entry.rel_path
            self.status = f"Dragging {entry.name}. Drop in scene to place it."
        return True

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

    def _create_folder(self) -> None:
        folder_name = self.folder_name_input.strip().strip("/")
        if not folder_name:
            self.status = "Folder name cannot be empty."
            return
        target = (self.current_asset_dir / folder_name).resolve()
        try:
            target.relative_to(self.asset_root.resolve())
        except ValueError:
            self.status = "Folder path must stay inside assets/."
            return
        if target.exists():
            self.status = "Folder already exists."
            return
        target.mkdir(parents=True, exist_ok=False)
        self.dialog_mode = None
        self.folder_name_input = ""
        self._refresh_assets()
        self.status = f"Created folder {target.relative_to(self.asset_root).as_posix()}"

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

    def _copy_dropped_asset(self, dropped_path: str) -> None:
        source = Path(dropped_path)
        if not source.exists() or not source.is_file():
            self.status = "Only image files can be imported."
            return
        if source.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            self.status = "Unsupported import. Use PNG, JPG, JPEG, BMP, or GIF."
            return

        target = self.current_asset_dir / source.name
        stem = source.stem
        suffix = source.suffix
        counter = 2
        while target.exists():
            target = self.current_asset_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        shutil.copy2(source, target)
        self.preview_cache.pop(f"preview:{target.as_posix()}", None)
        self.image_cache.pop(target.as_posix(), None)
        self.animation_cache.pop(target.as_posix(), None)
        self.image_size_cache.pop(target.as_posix(), None)
        self._refresh_assets()
        parent_rel = target.parent.relative_to(self.asset_root).as_posix()
        self.status = f"Imported {target.name} into {parent_rel if parent_rel != '.' else '/'}"

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

    def _parse_int(self, s: str, fallback: int = 0) -> int:
        try:
            return int(s.strip())
        except ValueError:
            return fallback

    def _input_display_text(self, raw: str, active: bool, fallback: str) -> str:
        text = raw if raw != "" else fallback
        if active and (pygame.time.get_ticks() // 450) % 2 == 0:
            text += "|"
        return text

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
        screen.blit(small.render(zoom_text, True, (180, 180, 186)), (toolbar.right - 90, toolbar.y + 9))

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
            sprite_w = max(1, int(sprite.width * self.zoom))
            sprite_h = max(1, int(sprite.height * self.zoom))
            sprite_rect = self._sprite_screen_rect(sprite)
            tile = self._get_asset_surface(sprite.asset_path, (sprite_w, sprite_h), pygame.time.get_ticks())
            if tile is None:
                pygame.draw.rect(screen, (90, 60, 62), sprite_rect)
                pygame.draw.rect(screen, (180, 130, 136), sprite_rect, 1)
            else:
                transformed = self._apply_xyz_rotation(tile, sprite)
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

        # ── Background: cache a checkerboard that matches the exact draw size ──
        if visible_patch is not None:
            src_rect, dst_rect = visible_patch
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
            if self._canvas_checker_cache != cache_key:
                if self.canvas_bg_light:
                    ca, cb = (255, 255, 255), (210, 210, 215)
                else:
                    ca, cb = (68, 68, 72), (48, 48, 52)
                checker = pygame.Surface((dst_rect.width, dst_rect.height))
                checker.fill(ca)
                row_start = src_rect.y
                row_end = src_rect.bottom
                col_start = src_rect.x
                col_end = src_rect.right
                for row in range(row_start, row_end):
                    y0 = int(round((row - src_rect.y) * dst_rect.height / src_rect.height))
                    y1 = int(round((row + 1 - src_rect.y) * dst_rect.height / src_rect.height))
                    if y1 <= y0:
                        continue
                    for col in range(col_start, col_end):
                        if (row + col) % 2 == 1:
                            x0 = int(round((col - src_rect.x) * dst_rect.width / src_rect.width))
                            x1 = int(round((col + 1 - src_rect.x) * dst_rect.width / src_rect.width))
                            if x1 <= x0:
                                continue
                            checker.fill(cb, (x0, y0, x1 - x0, y1 - y0))
                self._canvas_checker_surf = checker
                self._canvas_checker_cache = cache_key
            if self._canvas_checker_surf is not None:
                screen.blit(self._canvas_checker_surf, dst_rect.topleft)

        # ── Onion skin: previous frame ghost ────────────────────────
        if self.canvas_onion_skin and self.canvas_frame_idx > 0:
            onion = self._canvas_scaled_visible_frame_surface(
                self.canvas_frame_idx - 1,
                draw_rect,
                view,
                alpha=60,
            )
            if onion is not None:
                onion_surf, _, onion_dst = onion
                screen.blit(onion_surf, onion_dst.topleft)
        if self.canvas_onion_skin and self.canvas_frame_idx < len(self.canvas_frames) - 1:
            onion_n = self._canvas_scaled_visible_frame_surface(
                self.canvas_frame_idx + 1,
                draw_rect,
                view,
                alpha=40,
            )
            if onion_n is not None:
                onion_surf_n, _, onion_dst_n = onion_n
                screen.blit(onion_surf_n, onion_dst_n.topleft)

        # ── Composited frame (all visible layers) ────────────────────
        scaled = self._canvas_scaled_visible_frame_surface(
            self.canvas_frame_idx,
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

    def _draw_canvas_timeline(self, screen: pygame.Surface, panel: pygame.Rect,
                               font: pygame.font.Font, small: pygame.font.Font) -> None:
        """Draw the frame timeline strip at the bottom of the canvas workspace."""
        tl = self._canvas_timeline_rect(panel)
        pygame.draw.rect(screen, (20, 20, 24), tl)
        pygame.draw.rect(screen, (48, 48, 56), tl, 1)

        n = len(self.canvas_frames)
        if n == 0:
            msg = small.render("No frames — click New to create a canvas.", True, (80, 80, 90))
            screen.blit(msg, msg.get_rect(centerx=tl.centerx, centery=tl.centery))
        else:
            thumb_w = min(56, max(32, (tl.width - 90) // max(n, 1)))
            for i in range(n):
                fr = pygame.Rect(tl.x + 4 + i * (thumb_w + 4), tl.y + 4, thumb_w, tl.height - 8)
                if fr.right > tl.right - 86:
                    break
                active = (i == self.canvas_frame_idx)
                fill = (50, 80, 140) if active else (32, 32, 38)
                border = (90, 140, 220) if active else (58, 58, 68)
                pygame.draw.rect(screen, fill, fr)
                pygame.draw.rect(screen, border, fr, 1)
                # Mini thumbnail
                th = self._canvas_scaled_frame_surface(i, (fr.width - 4, fr.height - 16))
                if th is not None:
                    screen.blit(th, (fr.x + 2, fr.y + 2))
                lbl = small.render(str(i + 1), True, (200, 220, 255) if active else (130, 130, 145))
                screen.blit(lbl, (fr.x + 2, fr.bottom - 14))
            # Control buttons at far right
            by = tl.y + (tl.height - 22) // 2
            for bx, btxt in [(tl.right - 78, "Dup"), (tl.right - 52, "Del"), (tl.right - 26, "+")]:
                br = pygame.Rect(bx, by, 22, 22)
                pygame.draw.rect(screen, (38, 38, 48), br)
                pygame.draw.rect(screen, (72, 72, 84), br, 1)
                bt = small.render(btxt, True, (190, 190, 200))
                screen.blit(bt, bt.get_rect(center=br.center))
            # Frame/layer counter
            fi_txt = small.render(
                f"F{self.canvas_frame_idx + 1}/{n}  L{self.canvas_layer_idx + 1}/"
                f"{len(self.canvas_frames[self.canvas_frame_idx]) if self.canvas_frames else 1}",
                True, (120, 160, 200))
            screen.blit(fi_txt, (tl.x + 4 + n * (thumb_w + 4) + 4, tl.centery - 7))

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
            disp = self._input_display_text(self.canvas_brush_size_input, self.canvas_brush_size_focus, "1")
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
            bdisp = self._input_display_text(self.canvas_blend_input, self.canvas_blend_focus, "50")
            ls = small.render(bdisp + "%", True, (210, 220, 240))
            screen.blit(ls, ls.get_rect(center=bf.center))

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
            if self.canvas_asset_rel is not None and info_y + 16 <= panel.bottom:
                nt = small.render(Path(self.canvas_asset_rel).name[:22], True, (110, 140, 180))
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

        current_rel = self.current_asset_dir.relative_to(self.asset_root).as_posix()
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
        page_label = f"Page {self.asset_page + 1}/{self._max_asset_page() + 1}"
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

    def _draw_canvas_focus_layers_panel(self, screen: pygame.Surface, font: pygame.font.Font, small: pygame.font.Font) -> None:
        panel = self._canvas_focus_layer_panel_rect()
        self._draw_shadowed_panel(screen, panel, (22, 22, 28), (58, 58, 66), radius=0)
        header = pygame.Rect(panel.x, panel.y, panel.width, 28)
        pygame.draw.rect(screen, (34, 34, 40), header)
        pygame.draw.rect(screen, (62, 62, 72), header, 1)
        screen.blit(font.render("Layers", True, (216, 216, 224)), (header.x + 10, header.y + 4))

        active_layer_visible = bool(
            self.canvas_frames
            and self.canvas_frame_idx < len(self.canvas_layer_visible)
            and self.canvas_layer_idx < len(self.canvas_layer_visible[self.canvas_frame_idx])
            and self.canvas_layer_visible[self.canvas_frame_idx][self.canvas_layer_idx]
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
        if self.canvas_frames:
            fi = self.canvas_frame_idx
            frame_layers = self.canvas_frames[fi] if fi < len(self.canvas_frames) else []
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
                sel = li == self.canvas_layer_idx
                multi_sel = li in selected_layers
                vis = self.canvas_layer_visible[fi][li] if fi < len(self.canvas_layer_visible) else True
                fill = (50, 78, 130) if sel else (40, 62, 96) if multi_sel else (32, 32, 40)
                border = (80, 120, 200) if sel else (96, 144, 198) if multi_sel else (52, 52, 62)
                pygame.draw.rect(screen, fill, row_r)
                pygame.draw.rect(screen, border, row_r, 1)
                pygame.draw.circle(screen, (140, 200, 140) if vis else (70, 70, 80), (row_r.x + 8, row_r.centery), 5)
                nm = (self.canvas_layer_names[fi][li] if fi < len(self.canvas_layer_names) else f"Layer {li + 1}")
                lc = (210, 228, 255) if (sel or multi_sel) else (150, 150, 170)
                screen.blit(small.render(nm[:18], True, lc), (row_r.x + 18, row_r.y + 2))
                row_y += row_h
            if max_scroll > 0:
                track = pygame.Rect(rows_rect.right - 6, rows_rect.y + 2, 4, rows_rect.height - 4)
                pygame.draw.rect(screen, (34, 34, 42), track)
                thumb_h = max(12, int(track.height * (visible_rows / max(nl, 1))))
                thumb_y = track.y + int((track.height - thumb_h) * (self.canvas_layer_scroll / max(max_scroll, 1)))
                pygame.draw.rect(screen, (110, 126, 154), (track.x, thumb_y, track.width, thumb_h))

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
                    fi = self.canvas_frame_idx
                    li = self.canvas_layer_idx
                    if fi < len(self.canvas_layer_visible) and li < len(self.canvas_layer_visible[fi]):
                        self.canvas_layer_visible[fi][li] = not self.canvas_layer_visible[fi][li]
                        self._invalidate_canvas_render_cache(fi)
                        self.status = f"Layer {'shown' if self.canvas_layer_visible[fi][li] else 'hidden'}."
                elif key == "layer_del":
                    self._canvas_remove_layer()
                return True
        rows_rect = self._canvas_focus_layer_rows_rect()
        if rows_rect.collidepoint(pos) and self.canvas_frames:
            fi = self.canvas_frame_idx
            frame_layers = self.canvas_frames[fi] if fi < len(self.canvas_frames) else []
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
                        if fi < len(self.canvas_layer_visible) and li < len(self.canvas_layer_visible[fi]):
                            self.canvas_layer_visible[fi][li] = not self.canvas_layer_visible[fi][li]
                            self._invalidate_canvas_render_cache(fi)
                            self.status = f"Layer {'shown' if self.canvas_layer_visible[fi][li] else 'hidden'}."
                    else:
                        if cmd_held:
                            self._canvas_toggle_layer_selection(li)
                        else:
                            self._canvas_reset_layer_selection(li)
                    return True
                row_y += row_h
        return True

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
        n = len(self.canvas_frames)
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
                active = (i == self.canvas_frame_idx)
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
                "preview_play": "Pause" if self.canvas_preview_playing and len(self.canvas_frames) > 1 else "Play",
                "frame_del": "Del",
            }
            for key, br in frame_buttons.items():
                label = labels[key]
                if key == "frame_add":
                    col = (42, 82, 58)
                elif key == "frame_del":
                    col = (88, 52, 52)
                elif key == "preview_play" and self.canvas_preview_playing and len(self.canvas_frames) > 1:
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
            self.canvas_frames
            and self.canvas_frame_idx < len(self.canvas_layer_visible)
            and self.canvas_layer_idx < len(self.canvas_layer_visible[self.canvas_frame_idx])
            and self.canvas_layer_visible[self.canvas_frame_idx][self.canvas_layer_idx]
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
        if self.canvas_frames:
            fi = self.canvas_frame_idx
            frame_layers = self.canvas_frames[fi] if fi < len(self.canvas_frames) else []
            nl = len(frame_layers)
            row_y, visible_rows, scroll, max_scroll = self._canvas_layer_row_metrics(panel)
            start = max(0, nl - 1 - scroll)
            stop = max(-1, start - visible_rows)
            selected_layers = set(self._canvas_selected_layer_indices())
            for li in range(start, stop, -1):
                if row_y + 18 > panel.bottom - 2:
                    break
                sel = (li == self.canvas_layer_idx)
                multi_sel = li in selected_layers
                vis = self.canvas_layer_visible[fi][li] if fi < len(self.canvas_layer_visible) else True
                row_r = pygame.Rect(layer_x, row_y, layer_w, 18)
                fill = (50, 78, 130) if sel else (40, 62, 96) if multi_sel else (32, 32, 40)
                border = (80, 120, 200) if sel else (96, 144, 198) if multi_sel else (52, 52, 62)
                pygame.draw.rect(screen, fill, row_r)
                pygame.draw.rect(screen, border, row_r, 1)
                # Eye dot
                pygame.draw.circle(screen, (140, 200, 140) if vis else (70, 70, 80), (row_r.x + 8, row_r.centery), 5)
                nm = (self.canvas_layer_names[fi][li] if fi < len(self.canvas_layer_names) else f"Layer {li+1}")
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
            if self.canvas_asset_rel is None:
                chip_text = "Canvas: no asset selected"
            else:
                active_tool_label = dict(self._CANVAS_TOOLS).get(self.canvas_tool, self.canvas_tool.title())
                chip_text = f"Canvas: {Path(self.canvas_asset_rel).name} • {active_tool_label}"
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
            width_value = self._input_display_text(self.custom_scene_width_input, width_active, "0")
            height_value = self._input_display_text(self.custom_scene_height_input, height_active, "0")
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
            cur_w = self._parse_int(self.canvas_new_width_input)
            cur_h = self._parse_int(self.canvas_new_height_input)
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
                screen.blit(font.render(self._input_display_text(val, active, "0"), True, (220, 220, 226)), (rect.x + 10, rect.y + 8))
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
            value = self._input_display_text(self.folder_name_input, True, "")
            color = (244, 248, 255) if self.folder_name_input else (180, 180, 186)
            screen.blit(font.render(value, True, color), (input_rect.x + 12, input_rect.y + 9))
            for rect, label in [(create_rect, "Create"), (cancel_rect, "Cancel")]:
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
            value = self._input_display_text(self.canvas_name_input, True, "")
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
                        self._canvas_switch_frame(max(0, self.canvas_frame_idx - 1))
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_PERIOD and not cmd:
                        self._canvas_switch_frame(min(len(self.canvas_frames) - 1, self.canvas_frame_idx + 1))
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_COMMA and cmd:
                        self._canvas_add_frame()
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_PERIOD and cmd:
                        self._canvas_duplicate_frame()
                    # ── Layer navigation ────────────────────────────────
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_QUOTE and not cmd:
                        new_li = max(0, self.canvas_layer_idx - 1)
                        if new_li != self.canvas_layer_idx:
                            self.canvas_layer_idx = new_li
                            self.canvas_undo_stack.clear()
                            self.canvas_redo_stack.clear()
                    elif self.workspace_mode == "canvas" and event.key == pygame.K_SEMICOLON and not cmd:
                        fi = self.canvas_frame_idx
                        max_li = len(self.canvas_frames[fi]) - 1 if self.canvas_frames else 0
                        new_li = min(max_li, self.canvas_layer_idx + 1)
                        if new_li != self.canvas_layer_idx:
                            self.canvas_layer_idx = new_li
                            self.canvas_undo_stack.clear()
                            self.canvas_redo_stack.clear()
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

                            sprite = self._sprite_at(local)
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
                                self.dragging_sprite_id = sprite.sprite_id
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
                            self.resizing_corner = None
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
                        self.dragging_sprite_id = None
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
                            if rows_rect.collidepoint(self.drag_pos) and self.canvas_frames:
                                nl = len(self.canvas_frames[self.canvas_frame_idx]) if self.canvas_frame_idx < len(self.canvas_frames) else 0
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
