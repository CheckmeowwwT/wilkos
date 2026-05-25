from __future__ import annotations

import pygame

try:
    from ..history.canvas_history import CanvasHistory
    from .model import CanvasDocument
except ImportError:
    from history.canvas_history import CanvasHistory  # type: ignore[no-redef]
    from canvas.model import CanvasDocument  # type: ignore[no-redef]


class CanvasSession:
    DOC_FIELDS = (
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
        "canvas_history",
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
        "canvas_sel_source_surface",
        "canvas_sel_base_bbox",
        "canvas_sel_scale_rect",
        "canvas_sel_3d_x",
        "canvas_sel_3d_y",
        "canvas_sel_3d_z",
        "canvas_sel_3d_axis",
        "canvas_sel_3d_start_angle",
        "canvas_sel_3d_last_angle",
        "canvas_sel_3d_start_values",
        "canvas_resize_dragging",
        "canvas_resize_anchor",
        "canvas_move_dragging",
        "canvas_move_last",
        "_canvas_checker_cache",
        "_canvas_checker_surf",
        "_canvas_checker_base_key",
        "_canvas_checker_base",
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
        "_canvas_sel_3d_cache_key",
        "_canvas_sel_3d_cache_surf",
        "_canvas_sel_3d_cache_offset",
        "canvas_sprite_model",
    )

    def __init__(self, doc: CanvasDocument) -> None:
        """Keep the active canvas document and its tab bookkeeping together."""
        self.doc = doc
        self.tabs: list[dict[str, object]] = []
        self.tab_idx: int = -1
        self.next_tab_number: int = 1

    def doc_state(self, owner: object) -> dict[str, object]:
        """Capture all app state that belongs to the active canvas tab."""
        return {name: getattr(owner, name) for name in self.DOC_FIELDS}

    def apply_doc_state(self, owner: object, state: dict[str, object]) -> None:
        """Restore a canvas tab snapshot onto the app and refresh caches."""
        for name in self.DOC_FIELDS:
            setattr(owner, name, state[name])
        owner._sync_canvas_render_cache_state()

    def next_tab_name(self) -> str:
        """Pick the first unused Canvas N tab name."""
        used: set[int] = set()
        for tab in self.tabs:
            name = str(tab.get("name", "")).strip()
            if name.startswith("Canvas "):
                suffix = name[7:].strip()
                if suffix.isdigit():
                    used.add(int(suffix))
        n = 1
        while n in used:
            n += 1
        self.next_tab_number = max(self.next_tab_number, n + 1)
        return f"Canvas {n}"

    def max_tabs(self) -> int:
        """Return the current canvas tab limit."""
        return 7

    def init_tabs(self, owner: object) -> None:
        """Create the first canvas tab from the current document state."""
        initial_name = self.next_tab_name()
        self.tabs = [{"name": initial_name, "state": self.doc_state(owner)}]
        self.tab_idx = 0

    def save_active_tab_state(self, owner: object) -> None:
        """Store the current document state in the active tab."""
        if 0 <= self.tab_idx < len(self.tabs):
            self.tabs[self.tab_idx]["state"] = self.doc_state(owner)

    def switch_tab(self, owner: object, idx: int) -> str | None:
        """Switch tabs and return the status message for the UI."""
        if not (0 <= idx < len(self.tabs)) or idx == self.tab_idx:
            return None
        self.save_active_tab_state(owner)
        self.tab_idx = idx
        self.apply_doc_state(owner, self.tabs[idx]["state"])  # type: ignore[arg-type]
        return f"Switched to {self.tab_name(idx)}."

    def delete_current_tab(self, owner: object) -> str:
        """Delete the active canvas tab and return the status message."""
        if len(self.tabs) <= 1:
            removed_name = self.tab_name(self.tab_idx if self.tabs else 0)
            # Wipe back to the startup blank-canvas placeholder state so the
            # workspace looks like it did before any canvas existed.
            self._reset_owner_to_placeholder(owner)
            tab_name = removed_name if removed_name else self.next_tab_name()
            self.tabs = [{"name": tab_name, "state": self.doc_state(owner)}]
            self.tab_idx = 0
            return f"Cleared {removed_name}. No canvases left."
        remove_idx = self.tab_idx
        removed_name = self.tab_name(remove_idx)
        self.tabs.pop(remove_idx)
        self.tab_idx = max(0, min(remove_idx, len(self.tabs) - 1))
        self.apply_doc_state(owner, self.tabs[self.tab_idx]["state"])  # type: ignore[arg-type]
        return f"Deleted {removed_name}."

    def _reset_owner_to_placeholder(self, owner: object) -> None:
        """Drop the owner back to the empty, pre-canvas state used at startup."""
        owner.canvas_surface = None  # setter wipes frames/layers/caches
        owner.canvas_asset_rel = None
        owner.canvas_selection_pixels = set()
        owner.canvas_lasso_pixels = []
        owner.canvas_lasso_active = False
        owner.canvas_rect_select_active = False
        owner.canvas_rect_select_start = None
        owner.canvas_rect_select_end = None
        owner.canvas_paste_active = False
        owner.canvas_paste_pixels = {}
        owner.canvas_paste_origin = (0, 0)
        owner.canvas_sel_transform = None
        owner.canvas_sel_lift = {}
        owner.canvas_sel_surface = None
        owner.canvas_sel_source_surface = None
        owner.canvas_sel_base_bbox = None
        owner.canvas_sel_scale_rect = None
        owner.canvas_vp = None
        owner.canvas_preview_active = False
        owner.canvas_focus_mode = False
        owner.canvas_focus_tools_open = False
        owner.canvas_focus_tools_progress = 0.0

    def tab_is_placeholder(self, idx: int | None = None) -> bool:
        """Report whether a tab still holds the initial empty canvas state."""
        use_idx = self.tab_idx if idx is None else idx
        if not (0 <= use_idx < len(self.tabs)):
            return False
        state = self.tabs[use_idx].get("state")
        if not isinstance(state, dict):
            return False
        frames = state.get("canvas_frames")
        if isinstance(frames, list) and len(frames) > 0:
            return False
        asset_rel = state.get("canvas_asset_rel")
        return asset_rel in {None, ""}

    def tab_name(self, idx: int | None = None) -> str:
        """Return a display name for the requested canvas tab."""
        use_idx = self.tab_idx if idx is None else idx
        if 0 <= use_idx < len(self.tabs):
            name = str(self.tabs[use_idx].get("name", "")).strip()
            if name:
                return name
        return f"Canvas {max(1, use_idx + 1)}"

    def new_doc_state(self, owner: object, width: int, height: int) -> dict[str, object]:
        """Build the clean document state used for a new canvas tab."""
        state = self.doc_state(owner)
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
            "canvas_history": CanvasHistory(),
            "canvas_paste_active": False,
            "canvas_paste_pixels": {},
            "canvas_paste_origin": (0, 0),
            "canvas_preview_playing": True,
            "canvas_preview_started_ms": pygame.time.get_ticks(),
            "canvas_preview_elapsed_ms": 0,
            "canvas_preview_frame_ms": max(1, int(round(1000 / max(1, owner.canvas_preview_fps)))),
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
            "canvas_sel_source_surface": None,
            "canvas_sel_base_bbox": None,
            "canvas_sel_scale_rect": None,
            "canvas_sel_3d_x": 0.0,
            "canvas_sel_3d_y": 0.0,
            "canvas_sel_3d_z": 0.0,
            "canvas_sel_3d_axis": None,
            "canvas_sel_3d_start_angle": 0.0,
            "canvas_sel_3d_last_angle": 0.0,
            "canvas_sel_3d_start_values": (0.0, 0.0, 0.0),
            "canvas_resize_dragging": False,
            "canvas_resize_anchor": "",
            "canvas_move_dragging": False,
            "canvas_move_last": (0, 0),
            "_canvas_checker_cache": None,
            "_canvas_checker_surf": None,
            "_canvas_checker_base_key": None,
            "_canvas_checker_base": None,
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
            "_canvas_sel_3d_cache_key": None,
            "_canvas_sel_3d_cache_surf": None,
            "_canvas_sel_3d_cache_offset": (0.0, 0.0),
            "canvas_sprite_model": None,
        })
        return state

    def push_undo(self, surface: pygame.Surface | None) -> None:
        """Save the current editable surface in canvas undo history."""
        if surface is not None:
            self.doc.history.push(surface)

    def undo(self, surface: pygame.Surface | None) -> tuple[pygame.Surface | None, str]:
        """Return the previous canvas surface and a UI status message."""
        if surface is None:
            return None, "Nothing to undo."
        restored = self.doc.history.undo(surface)
        if restored is None:
            return None, "Nothing to undo."
        return restored, f"Undo  ({self.doc.history.undo_count} left)."

    def redo(self, surface: pygame.Surface | None) -> tuple[pygame.Surface | None, str]:
        """Return the next canvas surface and a UI status message."""
        if surface is None:
            return None, "Nothing to redo."
        restored = self.doc.history.redo(surface)
        if restored is None:
            return None, "Nothing to redo."
        return restored, "Redo."
