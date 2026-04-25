from __future__ import annotations

from pathlib import Path

import pygame
from PIL import Image, ImageSequence

try:
    from .core.utils import frame_index_for_time
except ImportError:
    from core.utils import frame_index_for_time  # type: ignore[no-redef]


class MediaCache:
    """Loads and caches editor image assets, previews, animation frames, and scaled surfaces."""

    def __init__(self, asset_root: Path, supported_extensions: set[str]) -> None:
        self.asset_root = asset_root
        self.supported_extensions = supported_extensions
        self.preview_cache: dict[str, pygame.Surface] = {}
        self.image_cache: dict[str, pygame.Surface] = {}
        self.animation_cache: dict[str, tuple[list[pygame.Surface], list[int]]] = {}
        self.scaled_cache: dict[tuple[str, int, int, int], pygame.Surface] = {}
        self.image_size_cache: dict[str, tuple[int, int]] = {}

    def folder_preview(self) -> pygame.Surface:
        preview = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.rect(preview, (242, 196, 93), (10, 22, 60, 42), border_radius=12)
        pygame.draw.rect(preview, (255, 230, 153), (10, 22, 60, 42), 2, border_radius=12)
        pygame.draw.rect(preview, (231, 180, 71), (16, 12, 28, 18), border_radius=8)
        return preview

    def missing_preview(self) -> pygame.Surface:
        preview = pygame.Surface((80, 80), pygame.SRCALPHA)
        preview.fill((98, 46, 54))
        pygame.draw.rect(preview, (232, 139, 151), preview.get_rect(), 2, border_radius=12)
        pygame.draw.line(preview, (255, 221, 227), (20, 20), (60, 60), 4)
        pygame.draw.line(preview, (255, 221, 227), (60, 20), (20, 60), 4)
        return preview

    def load_image_surface(self, path: Path) -> pygame.Surface:
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

    def load_asset_frames(self, path: Path) -> tuple[list[pygame.Surface], list[int]]:
        cache_key = path.as_posix()
        cached = self.animation_cache.get(cache_key)
        if cached is not None:
            return cached

        if path.suffix.lower() != ".gif":
            image = self.load_image_surface(path)
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
            fallback = self.load_image_surface(path)
            frames = [fallback]
            durations = [100]

        if not frames:
            fallback = self.load_image_surface(path)
            frames = [fallback]
            durations = [100]

        self.image_size_cache[cache_key] = frames[0].get_size()
        self.animation_cache[cache_key] = (frames, durations)
        return frames, durations

    def image_size_for(self, rel_path: str) -> tuple[int, int] | None:
        asset_path = self.asset_root / rel_path
        cache_key = asset_path.as_posix()
        cached = self.image_size_cache.get(cache_key)
        if cached is not None:
            return cached
        if not asset_path.exists() or asset_path.suffix.lower() not in self.supported_extensions:
            return None
        try:
            frames, _ = self.load_asset_frames(asset_path)
        except pygame.error:
            return None
        return frames[0].get_size()

    def preview_for_image(self, path: Path) -> pygame.Surface:
        cache_key = f"preview:{path.as_posix()}"
        cached = self.preview_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            frames, _ = self.load_asset_frames(path)
            preview = pygame.transform.smoothscale(frames[0], (80, 80))
        except pygame.error:
            preview = self.missing_preview()
        self.preview_cache[cache_key] = preview
        return preview

    def asset_surface(
        self,
        rel_path: str,
        size: tuple[int, int],
        ticks_ms: int = 0,
    ) -> pygame.Surface | None:
        asset_path = self.asset_root / rel_path
        if not asset_path.exists() or asset_path.suffix.lower() not in self.supported_extensions:
            return None
        try:
            frames, durations = self.load_asset_frames(asset_path)
        except pygame.error:
            return None
        frame_index = frame_index_for_time(durations, ticks_ms)
        cache_key = (rel_path, size[0], size[1], frame_index)
        cached = self.scaled_cache.get(cache_key)
        if cached is not None:
            return cached
        scaled = pygame.transform.smoothscale(frames[frame_index], size)
        self.scaled_cache[cache_key] = scaled
        return scaled

    def discard_path(self, path: Path) -> None:
        key = path.as_posix()
        self.preview_cache.pop(f"preview:{key}", None)
        self.image_cache.pop(key, None)
        self.animation_cache.pop(key, None)
        self.image_size_cache.pop(key, None)
        try:
            rel_path = path.relative_to(self.asset_root).as_posix()
        except ValueError:
            return
        self.scaled_cache = {
            cache_key: surface
            for cache_key, surface in self.scaled_cache.items()
            if cache_key[0] != rel_path
        }
