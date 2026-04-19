from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pygame


@dataclass
class AssetEntry:
    rel_path: str
    name: str
    path: Path
    is_dir: bool
    preview: pygame.Surface


@dataclass
class SpritePlacement:
    sprite_id: int
    asset_path: str
    x: float
    y: float
    width: int
    height: int
    rotation_x: float = 0.0
    rotation_y: float = 0.0
    rotation_z: float = 0.0

    @property
    def rotation(self) -> float:
        return self.rotation_z

    @rotation.setter
    def rotation(self, value: float) -> None:
        self.rotation_z = float(value)


@dataclass
class SceneDef:
    name: str
    board_width: int = 960
    board_height: int = 540
    sprites: list[SpritePlacement] = field(default_factory=list)
