from __future__ import annotations

try:
    from ..core.utils import clone_scene
    from ..history.canvas_history import CanvasHistory
    from ..history.scene_history import SceneHistory
    from ..models import SceneDef
except ImportError:
    from core.utils import clone_scene  # type: ignore[no-redef]
    from history.canvas_history import CanvasHistory  # type: ignore[no-redef]
    from history.scene_history import SceneHistory  # type: ignore[no-redef]
    from models import SceneDef  # type: ignore[no-redef]


class HistoryMixin:
    def _init_scene_history(self) -> None:
        self.scene_history = SceneHistory()

    def _init_canvas_history(self) -> None:
        self.canvas_doc.history = CanvasHistory()

    def _scene_snapshot(self) -> dict[str, object]:
        selected_ids = sorted(self.selected_sprite_ids)
        if not selected_ids and self.selected_sprite_id is not None:
            selected_ids = [self.selected_sprite_id]
        return {
            "scenes": [clone_scene(scene) for scene in self.scenes],
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
            clone_scene(scene)
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
        self.resizing_sprite_ids = []
        self.resize_source_bounds = None
        self.resize_source_sprites = {}
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
        self.scene_history.push(self._scene_snapshot())

    def _scene_undo(self) -> None:
        snapshot = self.scene_history.undo(self._scene_snapshot())
        if snapshot is None:
            self.status = "Nothing to undo."
            return
        self._restore_scene_snapshot(snapshot)
        self.status = f"Undo ({self.scene_history.undo_count} left)."

    def _scene_redo(self) -> None:
        snapshot = self.scene_history.redo(self._scene_snapshot())
        if snapshot is None:
            self.status = "Nothing to redo."
            return
        self._restore_scene_snapshot(snapshot)
        self.status = "Redo."


    def _canvas_push_undo(self) -> None:
        """Record the current canvas surface before a canvas edit."""
        self.canvas_session.push_undo(self.canvas_surface)

    def _canvas_undo(self) -> None:
        """Restore the previous canvas surface and refresh the view state."""
        surface, message = self.canvas_session.undo(self.canvas_surface)
        if surface is None:
            self.status = message
            return
        self.canvas_surface = surface
        self._mark_canvas_changed()
        self.status = message

    def _canvas_redo(self) -> None:
        """Restore the next canvas surface and refresh the view state."""
        surface, message = self.canvas_session.redo(self.canvas_surface)
        if surface is None:
            self.status = message
            return
        self.canvas_surface = surface
        self._mark_canvas_changed()
        self.status = message

   
