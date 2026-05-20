from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import pygame

try:
    from ..core.utils import frame_index_for_time, surface_to_pil_image
except ImportError:
    from core.utils import frame_index_for_time, surface_to_pil_image  # type: ignore[no-redef]


class CanvasDocumentMixin:
    def _canvas_target_asset_rel(self) -> str | None:
        if self.canvas_doc.asset_rel is not None:
            return self.canvas_doc.asset_rel
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
        if rel == self.canvas_doc.asset_rel and self.canvas_surface is not None:
            return
        self.canvas_doc.asset_rel = rel
        self.canvas_surface = None
        self.canvas_drawing = False
        self.canvas_last_pixel = None
        if not self._canvas_editable(rel):
            return
        path = self.asset_root / rel
        try:
            loaded = pygame.image.load(path.as_posix())
            self.canvas_surface = loaded.convert_alpha()
        except pygame.error:
            self.canvas_surface = None
        self._save_active_canvas_tab_state()

    def _canvas_stamp_asset_on_current_layer(self, rel_path: str) -> bool:
        """Drop an asset onto the active layer of the active frame.

        Scales to fit canvas dimensions (preserving aspect), centers, and blits
        on top so other frames and other layers stay intact. Used by the
        canvas-mode asset drop so building animation frames doesn't wipe the
        existing frames.
        """
        if self.canvas_surface is None or not self._canvas_editable(rel_path):
            return False
        path = self.asset_root / rel_path
        try:
            asset = pygame.image.load(path.as_posix()).convert_alpha()
        except pygame.error:
            self.status = "Could not load that asset."
            return False
        self._canvas_push_undo()
        cw, ch = self.canvas_surface.get_size()
        aw, ah = asset.get_size()
        scale = min(1.0, cw / max(1, aw), ch / max(1, ah))
        if scale < 1.0:
            new_w = max(1, int(round(aw * scale)))
            new_h = max(1, int(round(ah * scale)))
            asset = pygame.transform.scale(asset, (new_w, new_h))
            aw, ah = new_w, new_h
        offset = ((cw - aw) // 2, (ch - ah) // 2)
        self.canvas_surface.blit(asset, offset)
        self._mark_canvas_changed()
        self._save_active_canvas_tab_state()
        return True

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

    def _canvas_reset_layer_selection(self, idx: int | None = None) -> None:
        if not self.canvas_doc.frames:
            self.canvas_doc.selected_layers.clear()
            self.canvas_doc.layer_idx = 0
            return
        fi = min(self.canvas_doc.frame_idx, len(self.canvas_doc.frames) - 1)
        layer_count = len(self.canvas_doc.frames[fi])
        if layer_count <= 0:
            self.canvas_doc.selected_layers.clear()
            self.canvas_doc.layer_idx = 0
            return
        target = self.canvas_doc.layer_idx if idx is None else idx
        target = max(0, min(target, layer_count - 1))
        self.canvas_doc.layer_idx = target
        self.canvas_doc.selected_layers = {target}

    def _canvas_selected_layer_indices(self) -> list[int]:
        if not self.canvas_doc.frames:
            return []
        fi = min(self.canvas_doc.frame_idx, len(self.canvas_doc.frames) - 1)
        layer_count = len(self.canvas_doc.frames[fi])
        selected = sorted(li for li in self.canvas_doc.selected_layers if 0 <= li < layer_count)
        if not selected and layer_count > 0:
            selected = [max(0, min(self.canvas_doc.layer_idx, layer_count - 1))]
            self.canvas_doc.selected_layers = set(selected)
        return selected

    def _canvas_toggle_layer_selection(self, idx: int) -> None:
        selected = set(self._canvas_selected_layer_indices())
        if idx in selected and len(selected) > 1:
            selected.remove(idx)
        else:
            selected.add(idx)
        self.canvas_doc.layer_idx = idx
        self.canvas_doc.selected_layers = selected

    def _canvas_clear_extra_layer_selection(self) -> bool:
        selected = self._canvas_selected_layer_indices()
        if len(selected) <= 1:
            return False
        active = max(0, min(self.canvas_doc.layer_idx, len(self.canvas_doc.frames[self.canvas_doc.frame_idx]) - 1))
        self.canvas_doc.selected_layers = {active}
        self.status = f"Layer {active + 1} remains selected."
        return True

    def _sync_canvas_render_cache_state(self) -> None:
        target_len = len(self.canvas_doc.frames)
        current_len = len(self.canvas_doc.frame_versions)
        if current_len < target_len:
            self.canvas_doc.frame_versions.extend([0] * (target_len - current_len))
        elif current_len > target_len:
            self.canvas_doc.frame_versions = self.canvas_doc.frame_versions[:target_len]
        valid_frames = set(range(target_len))
        if len(valid_frames) != target_len:
            return
        self.canvas_doc.composite_cache = {
            key: surf for key, surf in self.canvas_doc.composite_cache.items()
            if key[0] in valid_frames
        }
        self.canvas_doc.scaled_surface_cache = {
            key: surf for key, surf in self.canvas_doc.scaled_surface_cache.items()
            if key[0] in valid_frames
        }
        self.canvas_doc.visible_surface_cache = {
            key: surf for key, surf in self.canvas_doc.visible_surface_cache.items()
            if key[0] in valid_frames
        }
        self.canvas_doc.mipmap_cache = {
            key: surf for key, surf in self.canvas_doc.mipmap_cache.items()
            if key[0] in valid_frames
        }

    def _invalidate_canvas_render_cache(self, frame_idx: int | None = None) -> None:
        self._sync_canvas_render_cache_state()
        targets = range(len(self.canvas_doc.frames)) if frame_idx is None else [frame_idx]
        for idx in targets:
            if not (0 <= idx < len(self.canvas_doc.frame_versions)):
                continue
            self.canvas_doc.frame_versions[idx] += 1
            self.canvas_doc.composite_cache = {
                key: surf for key, surf in self.canvas_doc.composite_cache.items()
                if key[0] != idx
            }
            self.canvas_doc.scaled_surface_cache = {
                key: surf for key, surf in self.canvas_doc.scaled_surface_cache.items()
                if key[0] != idx
            }
            self.canvas_doc.visible_surface_cache = {
                key: surf for key, surf in self.canvas_doc.visible_surface_cache.items()
                if key[0] != idx
            }
            self.canvas_doc.mipmap_cache = {
                key: surf for key, surf in self.canvas_doc.mipmap_cache.items()
                if key[0] != idx
            }

    def _mark_canvas_changed(self, frame_idx: int | None = None) -> None:
        target = self.canvas_doc.frame_idx if frame_idx is None else frame_idx
        self._invalidate_canvas_render_cache(target)

    def _canvas_doc_state(self) -> dict[str, object]:
        """Capture all state that belongs to the active canvas tab."""
        return self.canvas_session.doc_state(self)

    def _canvas_apply_doc_state(self, state: dict[str, object]) -> None:
        """Restore the active canvas tab state from a snapshot."""
        self.canvas_session.apply_doc_state(self, state)

    def _next_canvas_tab_name(self) -> str:
        """Return the next available canvas tab display name."""
        return self.canvas_session.next_tab_name()

    def _max_canvas_tabs(self) -> int:
        """Return the current canvas tab limit."""
        return self.canvas_session.max_tabs()

    def _init_canvas_tabs(self) -> None:
        """Create the initial canvas tab for the app."""
        self.canvas_session.init_tabs(self)

    def _save_active_canvas_tab_state(self) -> None:
        """Save current canvas state into the active tab."""
        self.canvas_session.save_active_tab_state(self)

    def _switch_canvas_tab(self, idx: int) -> None:
        """Switch the active canvas tab and show the result."""
        message = self.canvas_session.switch_tab(self, idx)
        if message is not None:
            self.status = message

    def _delete_current_canvas_tab(self) -> None:
        """Delete the current canvas tab and show the result."""
        self.status = self.canvas_session.delete_current_tab(self)

    def _canvas_tab_is_placeholder(self, idx: int | None = None) -> bool:
        """Report whether a canvas tab is still the empty starter tab."""
        return self.canvas_session.tab_is_placeholder(idx)

    def _canvas_tab_name(self, idx: int | None = None) -> str:
        """Return a display name for a canvas tab."""
        return self.canvas_session.tab_name(idx)

    def _new_canvas_doc_state(self, width: int, height: int) -> dict[str, object]:
        """Build the default state for a new blank canvas document."""
        return self.canvas_session.new_doc_state(self, width, height)

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
        self._canvas_sel_3d_cache_key = None
        self._canvas_sel_3d_cache_surf = None
        self._canvas_sel_3d_cache_offset = (0.0, 0.0)

    def _canvas_patch_render_region(
        self,
        dirty_rect: pygame.Rect,
        frame_idx: int | None = None,
    ) -> None:
        target = self.canvas_doc.frame_idx if frame_idx is None else frame_idx
        if target < 0 or target >= len(self.canvas_doc.frames) or not self.canvas_doc.frames[target]:
            return
        layers = self.canvas_doc.frames[target]
        sw, sh = layers[0].get_size()
        clipped = dirty_rect.clip(pygame.Rect(0, 0, sw, sh))
        if clipped.width <= 0 or clipped.height <= 0:
            return
        self._sync_canvas_render_cache_state()
        self.canvas_doc.visible_surface_cache.clear()
        self.canvas_doc.mipmap_cache.clear()
        version = self.canvas_doc.frame_versions[target] if target < len(self.canvas_doc.frame_versions) else 0
        cached_comp_keys = [
            key for key in self.canvas_doc.composite_cache
            if key[0] == target and key[1] == version
        ]
        for key in cached_comp_keys:
            comp = self.canvas_doc.composite_cache.get(key)
            if comp is None:
                continue
            alpha = key[2]
            comp.fill((0, 0, 0, 0), clipped)
            for layer_idx, surf in enumerate(layers):
                if not self.canvas_doc.layer_visible[target][layer_idx]:
                    continue
                if alpha < 255:
                    patch = surf.subsurface(clipped).copy()
                    patch.set_alpha(alpha)
                    comp.blit(patch, clipped.topleft)
                else:
                    comp.blit(surf, clipped.topleft, clipped)

        cached_scaled_keys = [
            key for key in self.canvas_doc.scaled_surface_cache
            if key[0] == target and key[1] == version
        ]
        if not cached_scaled_keys:
            return
        src_right = clipped.right
        src_bottom = clipped.bottom
        for key in cached_scaled_keys:
            scaled = self.canvas_doc.scaled_surface_cache.get(key)
            if scaled is None:
                continue
            alpha = key[2]
            dw, dh = key[3], key[4]
            comp = self.canvas_doc.composite_cache.get((target, version, alpha))
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
        if frame_idx >= len(self.canvas_doc.frames) or not self.canvas_doc.frames[frame_idx]:
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
        version = self.canvas_doc.frame_versions[frame_idx] if frame_idx < len(self.canvas_doc.frame_versions) else 0
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
        cached = self.canvas_doc.visible_surface_cache.get(cache_key)
        if cached is None:
            patch = source.subsurface(source_rect).copy()
            cached = pygame.transform.scale(patch, (dst_rect.width, dst_rect.height))
            if len(self.canvas_doc.visible_surface_cache) > 24:
                self.canvas_doc.visible_surface_cache.clear()
            self.canvas_doc.visible_surface_cache[cache_key] = cached
        return cached, source_rect, dst_rect

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
        version = self.canvas_doc.frame_versions[frame_idx] if frame_idx < len(self.canvas_doc.frame_versions) else 0
        cache_key = (frame_idx, version, alpha, level)
        cached = self.canvas_doc.mipmap_cache.get(cache_key)
        if cached is not None:
            return cached
        prev = self._canvas_mipmap_surface(frame_idx, alpha=alpha, level=level - 1)
        if prev is None:
            return None
        width = max(1, (prev.get_width() + 1) // 2)
        height = max(1, (prev.get_height() + 1) // 2)
        scaled = pygame.transform.scale(prev, (width, height))
        self.canvas_doc.mipmap_cache[cache_key] = scaled
        return scaled

    def _canvas_frame_name(self, idx: int) -> str:
        if 0 <= idx < len(self.canvas_doc.frame_names) and self.canvas_doc.frame_names[idx].strip():
            return self.canvas_doc.frame_names[idx]
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

    def _save_canvas_to_assets(self) -> None:
        if self.canvas_surface is None:
            return
        self.status = "Canvas save was removed. Use Export instead."

    def _sync_canvas_preview_to_current_frame(self) -> None:
        if not self.canvas_preview_playing:
            self.canvas_preview_elapsed_ms = max(0, self.canvas_doc.frame_idx) * self.canvas_preview_frame_ms

    def _set_canvas_preview_fps(self, fps: int) -> None:
        self.canvas_preview_fps = max(1, min(int(fps), 60))
        self.canvas_preview_frame_ms = max(1, int(round(1000 / self.canvas_preview_fps)))

    def _canvas_preview_elapsed(self, ticks_ms: int | None = None) -> int:
        if not self.canvas_preview_playing:
            return self.canvas_preview_elapsed_ms
        now = pygame.time.get_ticks() if ticks_ms is None else ticks_ms
        return max(0, now - self.canvas_preview_started_ms)

    def _canvas_preview_frame_idx(self, ticks_ms: int | None = None) -> int:
        n = len(self.canvas_doc.frames)
        if n <= 1:
            return 0
        elapsed = self._canvas_preview_elapsed(ticks_ms)
        durations = [self.canvas_preview_frame_ms] * n
        return frame_index_for_time(durations, elapsed)

    def _toggle_canvas_preview(self) -> None:
        if len(self.canvas_doc.frames) <= 1:
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

    def _canvas_export_base_name(self) -> str:
        if self.canvas_doc.asset_rel is not None:
            stem = Path(self.canvas_doc.asset_rel).stem.strip()
            if stem:
                return stem
        return "canvas"

    def _canvas_export_surfaces(self) -> list[pygame.Surface]:
        frames: list[pygame.Surface] = []
        for idx in range(len(self.canvas_doc.frames)):
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
        pil_frames = [surface_to_pil_image(frame) for frame in frames]
        first, rest = pil_frames[0], pil_frames[1:]
        first.save(
            target,
            save_all=True,
            append_images=rest,
            duration=self.canvas_preview_frame_ms,
            loop=0,
            disposal=2,
        )
        self.media_cache.discard_path(target)
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
        self.media_cache.discard_path(target)
        self._refresh_assets()
        self.status = f"Exported spritesheet to assets/{target.relative_to(self.asset_root).as_posix()}."
        return target

    def _export_canvas_png(self) -> Path | None:
        frames = self._canvas_export_surfaces()
        if not frames:
            self.status = "Nothing to export."
            return None
        frame = frames[min(self.canvas_doc.frame_idx, len(frames) - 1)]
        self.exported_canvas_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_frame{self.canvas_doc.frame_idx + 1}" if len(frames) > 1 else ""
        target = self._unique_export_path(self.exported_canvas_dir / f"{self._canvas_export_base_name()}_{ts}{suffix}.png")
        pygame.image.save(frame, target.as_posix())
        self.media_cache.discard_path(target)
        self._refresh_assets()
        self.status = f"Exported PNG to assets/{target.relative_to(self.asset_root).as_posix()}."
        return target

    def _canvas_merge_layers(self) -> None:
        if not self.canvas_doc.frames:
            self.status = "No layers to merge."
            return
        fi = self.canvas_doc.frame_idx
        if fi >= len(self.canvas_doc.frames) or len(self.canvas_doc.frames[fi]) <= 1:
            self.status = "Need at least two layers to merge."
            return
        selected = self._canvas_selected_layer_indices()
        if len(selected) < 2:
            self.status = "Cmd-click two or more layers, then press Merge."
            return
        base_layers = self.canvas_doc.frames[fi]
        merged = pygame.Surface(base_layers[0].get_size(), pygame.SRCALPHA)
        merged.fill((0, 0, 0, 0))
        for li in selected:
            merged.blit(base_layers[li], (0, 0))
        selected_set = set(selected)
        topmost = max(selected)
        merged_name = "Merged " + " + ".join(
            self.canvas_doc.layer_names[fi][li] for li in selected[:3]
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
                    new_visible.append(any(self.canvas_doc.layer_visible[fi][sel] for sel in selected))
                continue
            new_layers.append(surf)
            new_names.append(self.canvas_doc.layer_names[fi][li])
            new_visible.append(self.canvas_doc.layer_visible[fi][li])
        self.canvas_doc.frames[fi] = new_layers
        self.canvas_doc.layer_names[fi] = new_names
        self.canvas_doc.layer_visible[fi] = new_visible
        self.canvas_doc.layer_idx = merged_idx
        self.canvas_doc.selected_layers = {merged_idx}
        self.canvas_selection_pixels.clear()
        self.canvas_doc.history.clear()
        self._mark_canvas_changed(fi)
        self.status = f"Merged {len(selected)} layers on frame {fi + 1}."

    # ── Undo / redo ────────────────────────────────────────────────────

    def _canvas_frame_size(self) -> tuple[int, int]:
        """Return (w, h) of the current canvas, or (64,64) if none."""
        surf = self.canvas_surface
        return surf.get_size() if surf is not None else (64, 64)

    def _canvas_add_frame(self) -> None:
        w, h = self._canvas_frame_size()
        new_layer = pygame.Surface((w, h), pygame.SRCALPHA)
        new_layer.fill((0, 0, 0, 0))
        self.canvas_doc.frames.append([new_layer])
        self.canvas_doc.frame_names.append(f"Frame {len(self.canvas_doc.frames)}")
        self.canvas_doc.layer_names.append(["Layer 1"])
        self.canvas_doc.layer_visible.append([True])
        self._sync_canvas_render_cache_state()
        self.canvas_doc.frame_idx = len(self.canvas_doc.frames) - 1
        self.canvas_doc.layer_idx = 0
        self.canvas_doc.history.clear()
        self.canvas_doc.selected_layers = {0}
        self._sync_canvas_preview_to_current_frame()
        self.status = f"Frame {self.canvas_doc.frame_idx + 1} added."

    def _canvas_duplicate_frame(self) -> None:
        if not self.canvas_doc.frames:
            return
        fi = self.canvas_doc.frame_idx
        new_frame = [surf.copy() for surf in self.canvas_doc.frames[fi]]
        new_frame_name = self._copy_canvas_name(self._canvas_frame_name(fi))
        new_names = list(self.canvas_doc.layer_names[fi])
        new_vis = list(self.canvas_doc.layer_visible[fi])
        self.canvas_doc.frames.insert(fi + 1, new_frame)
        self.canvas_doc.frame_names.insert(fi + 1, new_frame_name)
        self.canvas_doc.layer_names.insert(fi + 1, new_names)
        self.canvas_doc.layer_visible.insert(fi + 1, new_vis)
        self._sync_canvas_render_cache_state()
        self.canvas_doc.frame_idx = fi + 1
        self.canvas_doc.selected_layers = {min(self.canvas_doc.layer_idx, len(new_frame) - 1)}
        self._sync_canvas_preview_to_current_frame()
        self.status = f"Duplicated frame → frame {self.canvas_doc.frame_idx + 1}."

    def _canvas_remove_frame(self) -> None:
        if len(self.canvas_doc.frames) <= 1:
            self.status = "Cannot remove the only frame."
            return
        fi = self.canvas_doc.frame_idx
        self.canvas_doc.frames.pop(fi)
        self.canvas_doc.frame_names.pop(fi)
        self.canvas_doc.layer_names.pop(fi)
        self.canvas_doc.layer_visible.pop(fi)
        self._sync_canvas_render_cache_state()
        self.canvas_doc.frame_idx = min(fi, len(self.canvas_doc.frames) - 1)
        self.canvas_doc.layer_idx = min(self.canvas_doc.layer_idx, len(self.canvas_doc.frames[self.canvas_doc.frame_idx]) - 1)
        self._canvas_reset_layer_selection()
        self.canvas_doc.history.clear()
        self._sync_canvas_preview_to_current_frame()
        self.status = f"Frame removed. Now on frame {self.canvas_doc.frame_idx + 1}."

    def _canvas_switch_frame(self, idx: int) -> None:
        if not self.canvas_doc.frames or not (0 <= idx < len(self.canvas_doc.frames)):
            return
        self.canvas_doc.frame_idx = idx
        self.canvas_doc.layer_idx = min(self.canvas_doc.layer_idx, len(self.canvas_doc.frames[idx]) - 1)
        self._canvas_reset_layer_selection()
        self.canvas_doc.history.clear()
        self._sync_canvas_preview_to_current_frame()

    def _canvas_move_frame(self, delta: int) -> None:
        if not self.canvas_doc.frames:
            return
        fi = self.canvas_doc.frame_idx
        target = fi + delta
        if not (0 <= target < len(self.canvas_doc.frames)):
            self.status = "Frame is already at the edge."
            return
        for seq in (self.canvas_doc.frames, self.canvas_doc.frame_names, self.canvas_doc.layer_names, self.canvas_doc.layer_visible):
            seq[fi], seq[target] = seq[target], seq[fi]
        if fi < len(self.canvas_doc.frame_versions) and target < len(self.canvas_doc.frame_versions):
            self.canvas_doc.frame_versions[fi], self.canvas_doc.frame_versions[target] = self.canvas_doc.frame_versions[target], self.canvas_doc.frame_versions[fi]
        self.canvas_doc.frame_idx = target
        self._canvas_reset_layer_selection()
        self._sync_canvas_preview_to_current_frame()
        self.status = f"Frame moved {'forward' if delta > 0 else 'back'}."

    def _canvas_add_layer(self) -> None:
        if not self.canvas_doc.frames:
            return
        w, h = self._canvas_frame_size()
        fi = self.canvas_doc.frame_idx
        new_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        new_surf.fill((0, 0, 0, 0))
        self.canvas_doc.frames[fi].append(new_surf)
        n = len(self.canvas_doc.frames[fi])
        self.canvas_doc.layer_names[fi].append(f"Layer {n}")
        self.canvas_doc.layer_visible[fi].append(True)
        self._invalidate_canvas_render_cache(fi)
        self.canvas_doc.layer_idx = n - 1
        self.canvas_doc.selected_layers = {self.canvas_doc.layer_idx}
        self.canvas_doc.history.clear()
        self.status = f"Layer {n} added."

    def _canvas_duplicate_layer(self) -> None:
        if not self.canvas_doc.frames:
            return
        fi = self.canvas_doc.frame_idx
        li = self.canvas_doc.layer_idx
        self.canvas_doc.frames[fi].insert(li + 1, self.canvas_doc.frames[fi][li].copy())
        self.canvas_doc.layer_names[fi].insert(li + 1, self._copy_canvas_name(self.canvas_doc.layer_names[fi][li]))
        self.canvas_doc.layer_visible[fi].insert(li + 1, self.canvas_doc.layer_visible[fi][li])
        self._invalidate_canvas_render_cache(fi)
        self.canvas_doc.layer_idx = li + 1
        self.canvas_doc.selected_layers = {self.canvas_doc.layer_idx}
        self.canvas_doc.history.clear()
        self.status = "Layer duplicated."

    def _canvas_remove_layer(self) -> None:
        if not self.canvas_doc.frames:
            return
        fi = self.canvas_doc.frame_idx
        if len(self.canvas_doc.frames[fi]) <= 1:
            self.status = "Cannot remove the only layer."
            return
        li = self.canvas_doc.layer_idx
        self.canvas_doc.frames[fi].pop(li)
        self.canvas_doc.layer_names[fi].pop(li)
        self.canvas_doc.layer_visible[fi].pop(li)
        self._invalidate_canvas_render_cache(fi)
        self.canvas_doc.layer_idx = min(li, len(self.canvas_doc.frames[fi]) - 1)
        self._canvas_reset_layer_selection()
        self.canvas_doc.history.clear()
        self.status = "Layer removed."

    def _canvas_move_layer(self, delta: int) -> None:
        if not self.canvas_doc.frames:
            return
        fi = self.canvas_doc.frame_idx
        li = self.canvas_doc.layer_idx
        target = li + delta
        if not (0 <= target < len(self.canvas_doc.frames[fi])):
            self.status = "Layer is already at the edge."
            return
        for seq in (self.canvas_doc.frames[fi], self.canvas_doc.layer_names[fi], self.canvas_doc.layer_visible[fi]):
            seq[li], seq[target] = seq[target], seq[li]
        self._invalidate_canvas_render_cache(fi)
        self.canvas_doc.layer_idx = target
        self.canvas_doc.selected_layers = {target}
        self.canvas_doc.history.clear()
        self.status = f"Layer moved {'up' if delta > 0 else 'down'}."

    def _canvas_composited_frame(self, frame_idx: int, alpha: int = 255) -> pygame.Surface | None:
        """Composite all visible layers of a frame into one surface."""
        if frame_idx >= len(self.canvas_doc.frames) or not self.canvas_doc.frames[frame_idx]:
            return None
        self._sync_canvas_render_cache_state()
        version = self.canvas_doc.frame_versions[frame_idx] if frame_idx < len(self.canvas_doc.frame_versions) else 0
        cache_key = (frame_idx, version, alpha)
        cached = self.canvas_doc.composite_cache.get(cache_key)
        if cached is not None:
            return cached
        layers = self.canvas_doc.frames[frame_idx]
        w, h = layers[0].get_size()
        comp = pygame.Surface((w, h), pygame.SRCALPHA)
        comp.fill((0, 0, 0, 0))
        for i, surf in enumerate(layers):
            if self.canvas_doc.layer_visible[frame_idx][i]:
                if alpha < 255:
                    tmp = surf.copy()
                    tmp.set_alpha(alpha)
                    comp.blit(tmp, (0, 0))
                else:
                    comp.blit(surf, (0, 0))
        self.canvas_doc.composite_cache[cache_key] = comp
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
        version = self.canvas_doc.frame_versions[frame_idx] if frame_idx < len(self.canvas_doc.frame_versions) else 0
        cache_key = (frame_idx, version, alpha, int(size[0]), int(size[1]))
        cached = self.canvas_doc.scaled_surface_cache.get(cache_key)
        if cached is not None:
            return cached
        scaled = pygame.transform.scale(source, (max(1, int(size[0])), max(1, int(size[1]))))
        self.canvas_doc.scaled_surface_cache[cache_key] = scaled
        return scaled
