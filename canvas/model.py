from __future__ import annotations

import math

import pygame

try:
    from ..history.canvas_history import CanvasHistory
except ImportError:
    from history.canvas_history import CanvasHistory  # type: ignore[no-redef]


class CanvasDocument:
    def __init__(self) -> None:
        self.asset_rel: str | None = None
        self.frames: list[list[pygame.Surface]] = []
        self.frame_names: list[str] = []
        self.layer_names: list[list[str]] = []
        self.layer_visible: list[list[bool]] = []
        self.frame_idx = 0
        self.layer_idx = 0
        self.selected_layers: set[int] = {0}
        self.history = CanvasHistory()
        self.frame_versions: list[int] = []
        self.composite_cache: dict[tuple[int, int, int], pygame.Surface] = {}
        self.scaled_surface_cache: dict[tuple[int, int, int, int, int], pygame.Surface] = {}
        self.visible_surface_cache: dict[tuple[int, int, int, int, int, int, int, int, int, int], pygame.Surface] = {}
        self.mipmap_cache: dict[tuple[int, int, int, int], pygame.Surface] = {}

    @property
    def surface(self) -> pygame.Surface | None:
        if not self.frames:
            return None
        if self.frame_idx >= len(self.frames):
            return None
        frame = self.frames[self.frame_idx]
        if not frame or self.layer_idx >= len(frame):
            return None
        return frame[self.layer_idx]

    @surface.setter
    def surface(self, surface: pygame.Surface | None) -> None:
        if surface is None:
            self.clear()
            return
        if (
            self.frames
            and self.frame_idx < len(self.frames)
            and self.frames[self.frame_idx]
            and self.layer_idx < len(self.frames[self.frame_idx])
        ):
            self.frames[self.frame_idx][self.layer_idx] = surface
        else:
            self.frames = [[surface]]
            self.frame_names = ["Frame 1"]
            self.layer_names = [["Layer 1"]]
            self.layer_visible = [[True]]
            self.frame_idx = 0
            self.layer_idx = 0
            self.selected_layers = {0}
        self.sync_cache_state()

    def clear(self) -> None:
        self.frames = []
        self.frame_names = []
        self.layer_names = []
        self.layer_visible = []
        self.frame_idx = 0
        self.layer_idx = 0
        self.selected_layers = set()
        self.history.clear()
        self.frame_versions = []
        self.clear_render_cache()

    def clear_render_cache(self) -> None:
        self.composite_cache.clear()
        self.scaled_surface_cache.clear()
        self.visible_surface_cache.clear()
        self.mipmap_cache.clear()

    def sync_cache_state(self) -> None:
        target_len = len(self.frames)
        current_len = len(self.frame_versions)
        if current_len < target_len:
            self.frame_versions.extend([0] * (target_len - current_len))
        elif current_len > target_len:
            self.frame_versions = self.frame_versions[:target_len]
        valid_frames = set(range(target_len))
        self.composite_cache = {
            key: surf for key, surf in self.composite_cache.items()
            if key[0] in valid_frames
        }
        self.scaled_surface_cache = {
            key: surf for key, surf in self.scaled_surface_cache.items()
            if key[0] in valid_frames
        }
        self.visible_surface_cache = {
            key: surf for key, surf in self.visible_surface_cache.items()
            if key[0] in valid_frames
        }
        self.mipmap_cache = {
            key: surf for key, surf in self.mipmap_cache.items()
            if key[0] in valid_frames
        }

    def invalidate_cache(self, frame_idx: int | None = None) -> None:
        self.sync_cache_state()
        targets = range(len(self.frames)) if frame_idx is None else [frame_idx]
        for idx in targets:
            if not (0 <= idx < len(self.frame_versions)):
                continue
            self.frame_versions[idx] += 1
            self.composite_cache = {key: surf for key, surf in self.composite_cache.items() if key[0] != idx}
            self.scaled_surface_cache = {key: surf for key, surf in self.scaled_surface_cache.items() if key[0] != idx}
            self.visible_surface_cache = {key: surf for key, surf in self.visible_surface_cache.items() if key[0] != idx}
            self.mipmap_cache = {key: surf for key, surf in self.mipmap_cache.items() if key[0] != idx}

    def frame_size(self) -> tuple[int, int]:
        surface = self.surface
        return surface.get_size() if surface is not None else (64, 64)

    def frame_name(self, idx: int) -> str:
        if 0 <= idx < len(self.frame_names) and self.frame_names[idx].strip():
            return self.frame_names[idx]
        return f"Frame {idx + 1}"

    def reset_layer_selection(self, idx: int | None = None) -> None:
        if not self.frames:
            self.selected_layers.clear()
            self.layer_idx = 0
            return
        fi = min(self.frame_idx, len(self.frames) - 1)
        layer_count = len(self.frames[fi])
        if layer_count <= 0:
            self.selected_layers.clear()
            self.layer_idx = 0
            return
        target = self.layer_idx if idx is None else idx
        target = max(0, min(target, layer_count - 1))
        self.layer_idx = target
        self.selected_layers = {target}

    def selected_layer_indices(self) -> list[int]:
        if not self.frames:
            return []
        fi = min(self.frame_idx, len(self.frames) - 1)
        layer_count = len(self.frames[fi])
        selected = sorted(li for li in self.selected_layers if 0 <= li < layer_count)
        if not selected and layer_count > 0:
            selected = [max(0, min(self.layer_idx, layer_count - 1))]
            self.selected_layers = set(selected)
        return selected

    def toggle_layer_selection(self, idx: int) -> None:
        selected = set(self.selected_layer_indices())
        if idx in selected and len(selected) > 1:
            selected.remove(idx)
        else:
            selected.add(idx)
        self.layer_idx = idx
        self.selected_layers = selected

    def clear_extra_layer_selection(self) -> int | None:
        selected = self.selected_layer_indices()
        if len(selected) <= 1:
            return None
        active = max(0, min(self.layer_idx, len(self.frames[self.frame_idx]) - 1))
        self.selected_layers = {active}
        return active

    def add_frame(self) -> int:
        w, h = self.frame_size()
        new_layer = pygame.Surface((w, h), pygame.SRCALPHA)
        new_layer.fill((0, 0, 0, 0))
        self.frames.append([new_layer])
        self.frame_names.append(f"Frame {len(self.frames)}")
        self.layer_names.append(["Layer 1"])
        self.layer_visible.append([True])
        self.sync_cache_state()
        self.frame_idx = len(self.frames) - 1
        self.layer_idx = 0
        self.history.clear()
        self.selected_layers = {0}
        return self.frame_idx

    def duplicate_frame(self, copy_name) -> int | None:
        if not self.frames:
            return None
        fi = self.frame_idx
        new_frame = [surf.copy() for surf in self.frames[fi]]
        self.frames.insert(fi + 1, new_frame)
        self.frame_names.insert(fi + 1, copy_name(self.frame_name(fi)))
        self.layer_names.insert(fi + 1, list(self.layer_names[fi]))
        self.layer_visible.insert(fi + 1, list(self.layer_visible[fi]))
        self.sync_cache_state()
        self.frame_idx = fi + 1
        self.selected_layers = {min(self.layer_idx, len(new_frame) - 1)}
        return self.frame_idx

    def remove_frame(self) -> bool:
        if len(self.frames) <= 1:
            return False
        fi = self.frame_idx
        self.frames.pop(fi)
        self.frame_names.pop(fi)
        self.layer_names.pop(fi)
        self.layer_visible.pop(fi)
        self.sync_cache_state()
        self.frame_idx = min(fi, len(self.frames) - 1)
        self.layer_idx = min(self.layer_idx, len(self.frames[self.frame_idx]) - 1)
        self.reset_layer_selection()
        self.history.clear()
        return True

    def switch_frame(self, idx: int) -> bool:
        if not self.frames or not (0 <= idx < len(self.frames)):
            return False
        self.frame_idx = idx
        self.layer_idx = min(self.layer_idx, len(self.frames[idx]) - 1)
        self.reset_layer_selection()
        self.history.clear()
        return True

    def move_frame(self, delta: int) -> bool:
        if not self.frames:
            return False
        fi = self.frame_idx
        target = fi + delta
        if not (0 <= target < len(self.frames)):
            return False
        for seq in (self.frames, self.frame_names, self.layer_names, self.layer_visible):
            seq[fi], seq[target] = seq[target], seq[fi]
        if fi < len(self.frame_versions) and target < len(self.frame_versions):
            self.frame_versions[fi], self.frame_versions[target] = self.frame_versions[target], self.frame_versions[fi]
        self.frame_idx = target
        self.reset_layer_selection()
        return True

    def add_layer(self) -> int | None:
        if not self.frames:
            return None
        w, h = self.frame_size()
        fi = self.frame_idx
        new_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        new_surf.fill((0, 0, 0, 0))
        self.frames[fi].append(new_surf)
        n = len(self.frames[fi])
        self.layer_names[fi].append(f"Layer {n}")
        self.layer_visible[fi].append(True)
        self.invalidate_cache(fi)
        self.layer_idx = n - 1
        self.selected_layers = {self.layer_idx}
        self.history.clear()
        return n

    def duplicate_layer(self, copy_name) -> bool:
        if not self.frames:
            return False
        fi = self.frame_idx
        li = self.layer_idx
        self.frames[fi].insert(li + 1, self.frames[fi][li].copy())
        self.layer_names[fi].insert(li + 1, copy_name(self.layer_names[fi][li]))
        self.layer_visible[fi].insert(li + 1, self.layer_visible[fi][li])
        self.invalidate_cache(fi)
        self.layer_idx = li + 1
        self.selected_layers = {self.layer_idx}
        self.history.clear()
        return True

    def remove_layer(self) -> bool:
        if not self.frames:
            return False
        fi = self.frame_idx
        if len(self.frames[fi]) <= 1:
            return False
        li = self.layer_idx
        self.frames[fi].pop(li)
        self.layer_names[fi].pop(li)
        self.layer_visible[fi].pop(li)
        self.invalidate_cache(fi)
        self.layer_idx = min(li, len(self.frames[fi]) - 1)
        self.reset_layer_selection()
        self.history.clear()
        return True

    def move_layer(self, delta: int) -> bool:
        if not self.frames:
            return False
        fi = self.frame_idx
        li = self.layer_idx
        target = li + delta
        if not (0 <= target < len(self.frames[fi])):
            return False
        for seq in (self.frames[fi], self.layer_names[fi], self.layer_visible[fi]):
            seq[li], seq[target] = seq[target], seq[li]
        self.invalidate_cache(fi)
        self.layer_idx = target
        self.selected_layers = {target}
        self.history.clear()
        return True

    def merge_selected_layers(self) -> int | None:
        if not self.frames:
            return None
        fi = self.frame_idx
        if fi >= len(self.frames) or len(self.frames[fi]) <= 1:
            return None
        selected = self.selected_layer_indices()
        if len(selected) < 2:
            return None
        base_layers = self.frames[fi]
        merged = pygame.Surface(base_layers[0].get_size(), pygame.SRCALPHA)
        merged.fill((0, 0, 0, 0))
        for li in selected:
            merged.blit(base_layers[li], (0, 0))
        selected_set = set(selected)
        topmost = max(selected)
        merged_name = "Merged " + " + ".join(self.layer_names[fi][li] for li in selected[:3])
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
                    new_visible.append(any(self.layer_visible[fi][sel] for sel in selected))
                continue
            new_layers.append(surf)
            new_names.append(self.layer_names[fi][li])
            new_visible.append(self.layer_visible[fi][li])
        self.frames[fi] = new_layers
        self.layer_names[fi] = new_names
        self.layer_visible[fi] = new_visible
        self.layer_idx = merged_idx
        self.selected_layers = {merged_idx}
        self.history.clear()
        self.invalidate_cache(fi)
        return len(selected)

    def composited_frame(self, frame_idx: int, alpha: int = 255) -> pygame.Surface | None:
        if frame_idx >= len(self.frames) or not self.frames[frame_idx]:
            return None
        self.sync_cache_state()
        version = self.frame_versions[frame_idx] if frame_idx < len(self.frame_versions) else 0
        cache_key = (frame_idx, version, alpha)
        cached = self.composite_cache.get(cache_key)
        if cached is not None:
            return cached
        layers = self.frames[frame_idx]
        w, h = layers[0].get_size()
        comp = pygame.Surface((w, h), pygame.SRCALPHA)
        comp.fill((0, 0, 0, 0))
        for i, surf in enumerate(layers):
            if self.layer_visible[frame_idx][i]:
                if alpha < 255:
                    tmp = surf.copy()
                    tmp.set_alpha(alpha)
                    comp.blit(tmp, (0, 0))
                else:
                    comp.blit(surf, (0, 0))
        self.composite_cache[cache_key] = comp
        return comp

    def mipmap_surface(self, frame_idx: int, *, alpha: int = 255, level: int = 0) -> pygame.Surface | None:
        base = self.composited_frame(frame_idx, alpha=alpha)
        if base is None:
            return None
        if level <= 0:
            return base
        self.sync_cache_state()
        version = self.frame_versions[frame_idx] if frame_idx < len(self.frame_versions) else 0
        cache_key = (frame_idx, version, alpha, level)
        cached = self.mipmap_cache.get(cache_key)
        if cached is not None:
            return cached
        prev = self.mipmap_surface(frame_idx, alpha=alpha, level=level - 1)
        if prev is None:
            return None
        width = max(1, (prev.get_width() + 1) // 2)
        height = max(1, (prev.get_height() + 1) // 2)
        scaled = pygame.transform.scale(prev, (width, height))
        self.mipmap_cache[cache_key] = scaled
        return scaled

    def scaled_frame_surface(self, frame_idx: int, size: tuple[int, int], *, alpha: int = 255) -> pygame.Surface | None:
        if size[0] <= 0 or size[1] <= 0:
            return None
        comp = self.composited_frame(frame_idx, alpha=alpha)
        if comp is None:
            return None
        source = comp
        ratio = max(comp.get_width() / max(1, int(size[0])), comp.get_height() / max(1, int(size[1])))
        if ratio >= 2.0:
            mip_level = max(0, int(math.floor(math.log2(ratio))))
            source = self.mipmap_surface(frame_idx, alpha=alpha, level=mip_level) or comp
        self.sync_cache_state()
        version = self.frame_versions[frame_idx] if frame_idx < len(self.frame_versions) else 0
        cache_key = (frame_idx, version, alpha, int(size[0]), int(size[1]))
        cached = self.scaled_surface_cache.get(cache_key)
        if cached is not None:
            return cached
        scaled = pygame.transform.scale(source, (max(1, int(size[0])), max(1, int(size[1]))))
        self.scaled_surface_cache[cache_key] = scaled
        return scaled
