from __future__ import annotations

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from canvas.tools import CanvasToolsMixin


class DummyCanvas(CanvasToolsMixin):
    def __init__(self) -> None:
        self.canvas_surface = pygame.Surface((8, 8), pygame.SRCALPHA)
        self.canvas_surface.fill((0, 0, 0, 0))
        self.canvas_selection_pixels: set[tuple[int, int]] = set()
        self.canvas_sel_transform: str | None = None
        self.canvas_sel_lift: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        self.canvas_sel_offset = (0, 0)
        self.canvas_sel_angle = 0.0
        self.canvas_sel_scale = 1.0
        self.canvas_sel_drag_start = None
        self.canvas_sel_drag_mode = ""
        self.canvas_sel_restore_on_cancel = True
        self.canvas_sel_auto_commit = False
        self.canvas_sel_push_undo_on_commit = False
        self.canvas_sel_surface = None
        self.canvas_sel_source_surface = None
        self.canvas_sel_base_bbox = None
        self.canvas_sel_scale_rect = None
        self.canvas_sel_3d_x = 0.0
        self.canvas_sel_3d_y = 0.0
        self.canvas_sel_3d_z = 0.0
        self.canvas_sel_3d_axis = None
        self.canvas_sel_3d_start_angle = 0.0
        self.canvas_sel_3d_last_angle = 0.0
        self.canvas_sel_3d_start_values = (0.0, 0.0, 0.0)
        self._canvas_sel_preview_cache_key = None
        self._canvas_sel_preview_surf = None
        self._canvas_sel_rotate_cache_key = None
        self._canvas_sel_rotate_cache_surf = None
        self._canvas_sel_3d_cache_key = None
        self._canvas_sel_3d_cache_surf = None
        self._canvas_sel_3d_cache_offset = (0.0, 0.0)
        self.canvas_sprite_model = None
        self.status = ""
        self.undo_pushes = 0
        self.change_marks = 0

    def _canvas_push_undo(self) -> None:
        self.undo_pushes += 1

    def _mark_canvas_changed(self, frame_idx: int | None = None) -> None:
        self.change_marks += 1


class CanvasSelectionMoveTests(unittest.TestCase):
    def test_move_commits_opaque_pixels_over_existing_art_only(self) -> None:
        canvas = DummyCanvas()
        canvas.canvas_surface.set_at((1, 1), (220, 40, 40, 255))
        canvas.canvas_surface.set_at((3, 3), (40, 180, 80, 255))
        canvas.canvas_surface.set_at((4, 3), (40, 180, 80, 255))
        canvas.canvas_selection_pixels = {(1, 1), (2, 1), (1, 2), (2, 2)}

        canvas._canvas_enter_sel_transform("move", auto_commit=False)
        canvas.canvas_sel_offset = (2, 2)
        canvas._canvas_commit_sel_transform()

        self.assertEqual(tuple(canvas.canvas_surface.get_at((1, 1))), (0, 0, 0, 0))
        self.assertEqual(tuple(canvas.canvas_surface.get_at((3, 3))), (220, 40, 40, 255))
        self.assertEqual(tuple(canvas.canvas_surface.get_at((4, 3))), (40, 180, 80, 255))

    def test_enter_transform_ignores_transparent_pixels_in_rect_selection(self) -> None:
        canvas = DummyCanvas()
        canvas.canvas_surface.set_at((1, 1), (220, 40, 40, 255))
        canvas.canvas_selection_pixels = {(1, 1), (2, 1), (1, 2), (2, 2)}

        canvas._canvas_enter_sel_transform("move", auto_commit=False)

        self.assertEqual(set(canvas.canvas_sel_lift), {(1, 1)})
        self.assertEqual(canvas.canvas_sel_base_bbox, (1, 1, 1, 1))

    def test_move_commit_rebuilds_from_transform_start_snapshot(self) -> None:
        canvas = DummyCanvas()
        canvas.canvas_surface.set_at((1, 1), (220, 40, 40, 255))
        canvas.canvas_surface.set_at((3, 3), (40, 180, 80, 255))
        canvas.canvas_surface.set_at((4, 3), (40, 180, 80, 255))
        canvas.canvas_selection_pixels = {(1, 1), (2, 1), (1, 2), (2, 2)}

        canvas._canvas_enter_sel_transform("move", auto_commit=False)
        canvas.canvas_surface.set_at((4, 3), (0, 0, 0, 0))
        canvas.canvas_sel_offset = (2, 2)
        canvas._canvas_commit_sel_transform()

        self.assertEqual(tuple(canvas.canvas_surface.get_at((3, 3))), (220, 40, 40, 255))
        self.assertEqual(tuple(canvas.canvas_surface.get_at((4, 3))), (40, 180, 80, 255))

    def test_repeated_nudges_stay_floating_until_final_commit(self) -> None:
        canvas = DummyCanvas()
        canvas.canvas_surface.set_at((1, 1), (220, 40, 40, 255))
        canvas.canvas_surface.set_at((3, 1), (40, 180, 80, 255))
        canvas.canvas_surface.set_at((5, 1), (40, 180, 80, 255))
        canvas.canvas_selection_pixels = {(1, 1)}

        canvas._canvas_move_selection_immediate(2, 0)
        canvas._canvas_move_selection_immediate(2, 0)

        self.assertEqual(canvas.canvas_sel_transform, "move")
        self.assertEqual(canvas.canvas_sel_offset, (4, 0))
        self.assertEqual(tuple(canvas.canvas_surface.get_at((1, 1))), (220, 40, 40, 255))
        self.assertEqual(tuple(canvas.canvas_surface.get_at((3, 1))), (40, 180, 80, 255))

        canvas._canvas_commit_sel_transform()

        self.assertEqual(tuple(canvas.canvas_surface.get_at((1, 1))), (0, 0, 0, 0))
        self.assertEqual(tuple(canvas.canvas_surface.get_at((3, 1))), (40, 180, 80, 255))
        self.assertEqual(tuple(canvas.canvas_surface.get_at((5, 1))), (220, 40, 40, 255))

    def test_paste_transform_does_not_clear_initial_preview_position(self) -> None:
        canvas = DummyCanvas()
        canvas.canvas_surface.set_at((1, 1), (40, 180, 80, 255))
        canvas.canvas_sel_lift = {(1, 1): (220, 40, 40, 255)}
        canvas.canvas_selection_pixels = {(1, 1)}
        canvas.canvas_sel_transform = "move"
        canvas.canvas_sel_offset = (2, 2)
        canvas.canvas_sel_restore_on_cancel = False
        canvas.canvas_sel_auto_commit = False
        canvas.canvas_sel_push_undo_on_commit = True
        canvas._canvas_rebuild_selection_surface()

        canvas._canvas_commit_sel_transform()

        self.assertEqual(tuple(canvas.canvas_surface.get_at((1, 1))), (40, 180, 80, 255))
        self.assertEqual(tuple(canvas.canvas_surface.get_at((3, 3))), (220, 40, 40, 255))


if __name__ == "__main__":
    unittest.main()
