from __future__ import annotations

import pygame
from PIL import Image

try:
    from ..models import SceneDef, SpritePlacement
except ImportError:
    from models import SceneDef, SpritePlacement  # type: ignore[no-redef]


def clone_sprite(sprite: SpritePlacement) -> SpritePlacement:
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


def clone_scene(scene: SceneDef) -> SceneDef:
    return SceneDef(
        name=scene.name,
        board_width=scene.board_width,
        board_height=scene.board_height,
        sprites=[clone_sprite(sprite) for sprite in scene.sprites],
    )


def frame_index_for_time(durations: list[int], ticks_ms: int) -> int:
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


def input_display_text(raw: str, active: bool, fallback: str) -> str:
    text = raw if raw != "" else fallback
    if active and (pygame.time.get_ticks() // 450) % 2 == 0:
        text += "|"
    return text


def parse_int(value: str, fallback: int = 0) -> int:
    try:
        return int(value.strip())
    except ValueError:
        return fallback


def safe_scene_filename(name: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")
    return slug or "scene"


def surface_to_pil_image(surface: pygame.Surface) -> Image.Image:
    raw = pygame.image.tobytes(surface, "RGBA")
    return Image.frombytes("RGBA", surface.get_size(), raw)
