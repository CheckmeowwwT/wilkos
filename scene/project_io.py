from __future__ import annotations

import json
from pathlib import Path

import pygame

try:
    from ..constants import LEGACY_TILE_SIZE, SCENE_SIZE_PRESETS
    from ..core.utils import safe_scene_filename
    from ..models import SceneDef, SpritePlacement
except ImportError:
    from constants import LEGACY_TILE_SIZE, SCENE_SIZE_PRESETS  # type: ignore[no-redef]
    from core.utils import safe_scene_filename  # type: ignore[no-redef]
    from models import SceneDef, SpritePlacement  # type: ignore[no-redef]


class SceneProjectIOMixin:
    @property
    def active_scene(self) -> SceneDef:
        return self.scenes[self.active_scene_idx]

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
        self.scene_history.clear()
        self._clear_selection()
        self.rotation_gizmo_enabled = False
        self._fit_active_scene()
        self.status = f"Opened project: {self.project_path.name}"

    def _resolve_scene_save_basename(self, scene_name: str) -> str:
        """Return a basename that won't overwrite an unrelated saved scene.

        Same scene re-saved → reuse its existing basename.
        Name collides with a different scene → suffix _2, _3, ... until free.
        """
        base = safe_scene_filename(scene_name)
        self.scene_json_dir.mkdir(parents=True, exist_ok=True)
        candidate = base
        suffix = 2
        while True:
            json_path = self.scene_json_dir / f"{candidate}.json"
            if not json_path.exists():
                return candidate
            try:
                existing = json.loads(json_path.read_text(encoding="utf-8"))
                existing_name = str(existing.get("name", "")) if isinstance(existing, dict) else ""
            except (OSError, ValueError, json.JSONDecodeError):
                existing_name = ""
            if existing_name == scene_name:
                return candidate
            candidate = f"{base}_{suffix}"
            suffix += 1

    def _save_scene(self) -> None:
        scene = self.active_scene
        safe_name = self._resolve_scene_save_basename(scene.name)
        path = self.scene_json_dir / f"{safe_name}.json"
        payload = {
            "name": scene.name,
            "board_width": scene.board_width,
            "board_height": scene.board_height,
            "sprites": [self._sprite_to_payload(sprite) for sprite in scene.sprites],
        }
        self.scene_json_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        preview_path = self.scene_asset_dir / f"{safe_name}.png"
        surface, _ = self._render_scene_surface(only_ids=None)
        pygame.image.save(surface, preview_path.as_posix())
        self.media_cache.discard_path(preview_path)
        self._refresh_assets()
        self.status = f"Saved scene: {path.name} and {preview_path.name}"

    def _open_save_scene_dialog(self) -> None:
        self.scene_name_input = self.active_scene.name.strip() or f"Scene {self.active_scene_idx + 1}"
        self.dialog_mode = "save_scene"
        self.status = "Name the scene, then save it."

    def _confirm_save_scene(self) -> None:
        name = self.scene_name_input.strip()
        if not name:
            self.status = "Scene name cannot be empty."
            return
        self.active_scene.name = name
        self.dialog_mode = None
        self._save_scene()

    def _load_scene_file(self, path: Path) -> SceneDef | None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        name = str(raw.get("name", path.stem))
        board_width = max(int(raw.get("board_width", 960)), 32)
        board_height = max(int(raw.get("board_height", 540)), 32)
        scene = SceneDef(name=name, board_width=board_width, board_height=board_height)
        sprites_raw = raw.get("sprites")
        if isinstance(sprites_raw, list):
            for sprite_row in sprites_raw:
                if not isinstance(sprite_row, dict):
                    continue
                sprite = self._sprite_from_payload(sprite_row)
                if sprite is None:
                    continue
                self._clamp_sprite_to_scene(sprite, scene)
                scene.sprites.append(sprite)
        return scene

    def _saved_scene_json_for_asset(self, rel_path: str) -> Path | None:
        normalized = rel_path.replace("\\", "/").lstrip("/")
        rel = Path(normalized)
        if not rel.parts or rel.parts[0] != "scenes":
            return None
        target = self.scene_json_dir / f"{rel.stem}.json"
        return target if target.exists() else None

    def _place_saved_scene_asset(self, rel_path: str, local_pos: tuple[float, float]) -> bool:
        json_path = self._saved_scene_json_for_asset(rel_path)
        if json_path is None:
            return False
        loaded_scene = self._load_scene_file(json_path)
        if loaded_scene is None or not loaded_scene.sprites:
            self.status = f"Could not load scene data for {Path(rel_path).name}."
            return True

        self._push_scene_undo()

        src_min_x = min(s.x for s in loaded_scene.sprites)
        src_min_y = min(s.y for s in loaded_scene.sprites)
        src_max_x = max(s.x + s.width for s in loaded_scene.sprites)
        src_max_y = max(s.y + s.height for s in loaded_scene.sprites)
        src_w = max(1.0, src_max_x - src_min_x)
        src_h = max(1.0, src_max_y - src_min_y)

        active = self.active_scene
        scale = min(1.0, active.board_width / src_w, active.board_height / src_h)
        target_w = src_w * scale
        target_h = src_h * scale

        desired_left = local_pos[0] - target_w / 2.0
        desired_top = local_pos[1] - target_h / 2.0
        final_left = max(0.0, min(desired_left, active.board_width - target_w))
        final_top = max(0.0, min(desired_top, active.board_height - target_h))

        new_ids: set[int] = set()
        for source in loaded_scene.sprites:
            rel_x = (source.x - src_min_x) * scale
            rel_y = (source.y - src_min_y) * scale
            new_w = max(8, int(round(source.width * scale)))
            new_h = max(8, int(round(source.height * scale)))
            sprite = SpritePlacement(
                sprite_id=self.next_sprite_id,
                asset_path=source.asset_path,
                x=final_left + rel_x,
                y=final_top + rel_y,
                width=new_w,
                height=new_h,
                rotation_x=source.rotation_x,
                rotation_y=source.rotation_y,
                rotation_z=source.rotation_z,
            )
            self.next_sprite_id += 1
            self.active_scene.sprites.append(sprite)
            new_ids.add(sprite.sprite_id)
        self._set_selection(new_ids)
        self.status = f"Loaded scene {loaded_scene.name} into the board."
        return True

    def _parse_custom_scene_size(self) -> tuple[int, int] | None:
        try:
            width = int(self.custom_scene_width_input.strip() or "0")
            height = int(self.custom_scene_height_input.strip() or "0")
        except ValueError:
            return None
        if not (32 <= width <= 8192 and 32 <= height <= 8192):
            return None
        return width, height

