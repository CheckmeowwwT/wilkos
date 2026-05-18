from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import pygame

try:
    from ..core.utils import safe_scene_filename, surface_to_pil_image
    from ..models import SceneDef, SpritePlacement
except ImportError:
    from core.utils import safe_scene_filename, surface_to_pil_image  # type: ignore[no-redef]
    from models import SceneDef, SpritePlacement  # type: ignore[no-redef]


class SceneEditingMixin:
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

    def _sprite_screen_surface(self, sprite: SpritePlacement, ticks_ms: int) -> pygame.Surface | None:
        draw_w = max(1, int(sprite.width * self.zoom))
        draw_h = max(1, int(sprite.height * self.zoom))
        base = self._get_asset_surface(sprite.asset_path, (draw_w, draw_h), ticks_ms)
        if base is None:
            return None
        return self._apply_xyz_rotation(base, sprite)

    def _clamp_sprite_to_scene(self, sprite: SpritePlacement, scene: SceneDef | None = None) -> None:
        active_scene = scene or self.active_scene
        sprite.width = max(8, min(int(sprite.width), active_scene.board_width))
        sprite.height = max(8, min(int(sprite.height), active_scene.board_height))
        sprite.x = max(0.0, min(float(sprite.x), active_scene.board_width - sprite.width))
        sprite.y = max(0.0, min(float(sprite.y), active_scene.board_height - sprite.height))

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
        self.resizing_sprite_ids = sorted(ids)
        self.resize_source_bounds = bounds
        self.resize_source_sprites = {}
        for sid in self.resizing_sprite_ids:
            sprite = self._sprite_by_id(sid)
            if sprite is None:
                continue
            self.resize_source_sprites[sid] = (sprite.x, sprite.y, sprite.width, sprite.height)
        self.resize_anchor = anchor
        self.dragging_group_ids.clear()
        self.status = "Resizing selected assets."

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

    def _sprite_at_screen(self, screen_pos: tuple[int, int]) -> SpritePlacement | None:
        ticks_ms = pygame.time.get_ticks()
        for sprite in reversed(self.active_scene.sprites):
            sprite_rect = self._sprite_screen_rect(sprite)
            if not sprite_rect.collidepoint(screen_pos):
                continue

            asset_path = self.asset_root / sprite.asset_path
            if asset_path.suffix.lower() != ".gif":
                return sprite

            rendered = self._sprite_screen_surface(sprite, ticks_ms)
            if rendered is None:
                return sprite

            rendered_rect = rendered.get_rect(center=sprite_rect.center)
            if not rendered_rect.collidepoint(screen_pos):
                continue

            sample_x = int(screen_pos[0] - rendered_rect.x)
            sample_y = int(screen_pos[1] - rendered_rect.y)
            if not (0 <= sample_x < rendered.get_width() and 0 <= sample_y < rendered.get_height()):
                continue
            if rendered.get_at((sample_x, sample_y)).a <= 8:
                continue
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
        # Fit-scale preserving aspect ratio when the asset is bigger than the scene,
        # so dropping a 1024x768 asset onto a 256x256 scene yields a centered
        # 256x192 sprite instead of a stretched 256x256 fill.
        active = self.active_scene
        scale = min(
            1.0,
            active.board_width / max(1, width),
            active.board_height / max(1, height),
        )
        if scale < 1.0:
            width = max(8, int(round(width * scale)))
            height = max(8, int(round(height * scale)))
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
            self.status = f"Placed {Path(asset_path).name} ({width}x{height})."
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

    def _render_scene_surface(self, only_ids: set[int] | None = None, ticks_ms: int | None = None) -> tuple[pygame.Surface, pygame.Rect]:
        ticks = pygame.time.get_ticks() if ticks_ms is None else ticks_ms
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
        self.media_cache.discard_path(target)
        self._refresh_assets()
        self._set_selection({merged_sprite.sprite_id}, primary=merged_sprite.sprite_id)
        self.status = f"Merged selection to assets/{rel_path}."

    def _export_active_scene_png(self) -> None:
        surface, _ = self._render_scene_surface(only_ids=None)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_scene_filename(self.active_scene.name)}_{timestamp}.png"
        target = self._unique_export_path(self.exported_asset_dir / filename)
        pygame.image.save(surface, target.as_posix())
        self.status = f"Exported scene PNG to assets/{target.relative_to(self.asset_root).as_posix()}."

    def _scene_export_timeline(self) -> tuple[list[int], list[int]]:
        unique_paths: list[str] = []
        seen: set[str] = set()
        for sprite in self.active_scene.sprites:
            rel_path = sprite.asset_path
            if rel_path in seen:
                continue
            seen.add(rel_path)
            unique_paths.append(rel_path)

        animated: list[list[int]] = []
        cycle_ms = 0
        for rel_path in unique_paths:
            asset_path = self.asset_root / rel_path
            if asset_path.suffix.lower() != ".gif":
                continue
            try:
                frames, durations = self._load_asset_frames(asset_path)
            except pygame.error:
                continue
            if len(frames) <= 1 or not durations:
                continue
            cleaned = [max(40, int(duration)) for duration in durations]
            animated.append(cleaned)
            cycle_ms = max(cycle_ms, sum(cleaned))

        if not animated or cycle_ms <= 0:
            return [0], [100]

        boundaries: set[int] = {0}
        for durations in animated:
            elapsed = 0
            idx = 0
            while elapsed < cycle_ms:
                boundaries.add(elapsed)
                elapsed += durations[idx % len(durations)]
                idx += 1

        times = sorted(t for t in boundaries if 0 <= t < cycle_ms)
        if not times or times[0] != 0:
            times.insert(0, 0)

        max_frames = 180
        if len(times) > max_frames:
            step = cycle_ms / max_frames
            times = sorted({min(cycle_ms - 1, int(round(i * step))) for i in range(max_frames)})
            if not times or times[0] != 0:
                times.insert(0, 0)

        durations_ms: list[int] = []
        for idx, start in enumerate(times):
            end = times[idx + 1] if idx + 1 < len(times) else cycle_ms
            durations_ms.append(max(40, end - start))
        return times, durations_ms

    def _export_active_scene_gif(self) -> None:
        frame_times, frame_durations = self._scene_export_timeline()
        surfaces = [self._render_scene_surface(only_ids=None, ticks_ms=ticks)[0] for ticks in frame_times]
        if not surfaces:
            self.status = "Nothing to export."
            return

        self.exported_asset_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_scene_filename(self.active_scene.name)}_{timestamp}.gif"
        target = self._unique_export_path(self.exported_asset_dir / filename)
        pil_frames = [surface_to_pil_image(frame) for frame in surfaces]
        first, rest = pil_frames[0], pil_frames[1:]
        duration: int | list[int] = frame_durations[0] if len(frame_durations) == 1 else frame_durations
        first.save(
            target,
            save_all=True,
            append_images=rest,
            duration=duration,
            loop=0,
            disposal=2,
        )
        self.media_cache.discard_path(target)
        self._refresh_assets()
        self.status = f"Exported scene GIF to assets/{target.relative_to(self.asset_root).as_posix()}."


