from __future__ import annotations

import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import pygame

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except Exception:
    QtCore = None  # type: ignore[assignment]
    QtGui = None  # type: ignore[assignment]
    QtWidgets = None  # type: ignore[assignment]

try:
    from ..constants import SUPPORTED_IMAGE_EXTENSIONS
    from ..models import AssetEntry
except ImportError:
    from constants import SUPPORTED_IMAGE_EXTENSIONS  # type: ignore[no-redef]
    from models import AssetEntry  # type: ignore[no-redef]


class AssetBrowserMixin:
    def _asset_resize_handle_rect(self) -> pygame.Rect:
        panel = self._asset_panel_rect()
        return pygame.Rect(panel.centerx - 46, panel.y - 7, 92, 14)

    def _resize_asset_panel(self, mouse_y: int) -> None:
        target_height = self.screen_height - self.gutter - int(mouse_y)
        self.asset_h = self._clamp_asset_height(target_height)
        self._update_layout(self.screen_width, self.screen_height, preserve_asset_h=True)
        self._fit_active_scene()

    def _load_legacy_asset_paths(self) -> list[str]:
        if not self.legacy_asset_dir.exists():
            return []
        files = sorted(
            path
            for path in self.legacy_asset_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        )
        return [path.relative_to(self.asset_root).as_posix() for path in files]

    def _make_folder_preview(self) -> pygame.Surface:
        return self.media_cache.folder_preview()

    def _make_missing_preview(self) -> pygame.Surface:
        return self.media_cache.missing_preview()

    def _load_image_surface(self, path: Path) -> pygame.Surface:
        return self.media_cache.load_image_surface(path)

    def _load_asset_frames(self, path: Path) -> tuple[list[pygame.Surface], list[int]]:
        return self.media_cache.load_asset_frames(path)

    def _ensure_native_drag_source(self):
        if QtWidgets is None or QtCore is None:
            return None
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication([])
        self._qt_drag_app = app
        source = self._qt_drag_source
        if source is None:
            source = QtWidgets.QWidget()
            source.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint, True)
            source.setWindowFlag(QtCore.Qt.WindowType.Tool, True)
            source.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
            source.setWindowOpacity(0.01)
            source.resize(1, 1)
            self._qt_drag_source = source
        return source

    def _queue_native_asset_drag(self, rel_path: str, origin: tuple[int, int]) -> None:
        self.native_drag_asset_rel = rel_path
        self.native_drag_origin = origin
        self.status = f"Drag {Path(rel_path).name} out of the window to copy it."

    def _cancel_native_asset_drag(self) -> None:
        self.native_drag_asset_rel = None
        self.native_drag_origin = None

    def _start_native_asset_drag(self, rel_path: str) -> bool:
        if QtCore is None or QtGui is None or QtWidgets is None:
            self.status = "Native file drag is unavailable on this build."
            return False
        path = (self.asset_root / rel_path).resolve()
        if not path.exists():
            self.status = "That asset no longer exists."
            return False
        source = self._ensure_native_drag_source()
        if source is None:
            self.status = "Native file drag could not be started."
            return False
        if QtGui is not None:
            cursor_pos = QtGui.QCursor.pos()
            source.move(cursor_pos.x(), cursor_pos.y())
        source.show()
        source.raise_()
        mime = QtCore.QMimeData()
        mime.setUrls([QtCore.QUrl.fromLocalFile(str(path))])
        drag = QtGui.QDrag(source)
        drag.setMimeData(mime)
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            preview = self._get_preview_for_image(path)
            rgba = pygame.image.tobytes(preview, "RGBA")
            image = QtGui.QImage(
                rgba,
                preview.get_width(),
                preview.get_height(),
                preview.get_width() * 4,
                QtGui.QImage.Format.Format_RGBA8888,
            ).copy()
            drag.setPixmap(QtGui.QPixmap.fromImage(image))
            drag.setHotSpot(QtCore.QPoint(preview.get_width() // 2, preview.get_height() // 2))
        if self._qt_drag_app is not None:
            self._qt_drag_app.processEvents()
        drag.exec(QtCore.Qt.DropAction.CopyAction)
        source.hide()
        self.status = f"Dragged out {path.name}."
        return True

    def _image_size_for(self, rel_path: str) -> tuple[int, int] | None:
        return self.media_cache.image_size_for(rel_path)

    def _get_preview_for_image(self, path: Path) -> pygame.Surface:
        return self.media_cache.preview_for_image(path)

    def _get_asset_surface(self, rel_path: str, size: tuple[int, int], ticks_ms: int = 0) -> pygame.Surface | None:
        return self.media_cache.asset_surface(rel_path, size, ticks_ms)

    def _refresh_assets(self) -> None:
        self.asset_library.refresh(self._asset_entries_per_page())

    def _asset_entries_per_page(self) -> int:
        panel = self._asset_panel_rect()
        cols = max(1, (panel.width - 36) // 114)
        return cols * 2

    def _max_asset_page(self) -> int:
        return self.asset_library.max_page(self._asset_entries_per_page())

    def _visible_asset_entries(self) -> list[tuple[AssetEntry, pygame.Rect]]:
        per_page = self._asset_entries_per_page()
        start = self.asset_library.page * per_page
        page_entries = self.asset_library.entries[start : start + per_page]
        panel = self._asset_panel_rect()
        left = panel.x + 18
        top = panel.y + 84
        slot_w = 114
        slot_h = 132
        cols = max(1, (panel.width - 36) // slot_w)

        visible: list[tuple[AssetEntry, pygame.Rect]] = []
        for idx, entry in enumerate(page_entries):
            row = idx // cols
            col = idx % cols
            rect = pygame.Rect(left + col * slot_w, top + row * slot_h, 96, 96)
            visible.append((entry, rect))
        return visible

    def _asset_panel_rect(self) -> pygame.Rect:
        h = 32 if self.asset_panel_collapsed else self.asset_h
        return pygame.Rect(
            self.gutter,
            self.screen_height - h - self.gutter,
            self.screen_width - self.gutter * 2,
            h,
        )

    def _asset_collapse_button_rect(self) -> pygame.Rect:
        panel = self._asset_panel_rect()
        # Sits as a floating tab ABOVE the panel so it's always reachable
        return pygame.Rect(panel.right - 92, panel.y - 26, 84, 24)

    def _toolbar_buttons(self) -> dict[str, pygame.Rect]:
        panel = self._asset_panel_rect()
        x = panel.right - 646
        y = panel.y + 18
        rects: dict[str, pygame.Rect] = {}
        for name, width in [
            ("up", 70),
            ("prev", 70),
            ("next", 70),
            ("import", 96),
            ("delete", 96),
            ("new_folder", 112),
            ("refresh", 112),
        ]:
            rects[name] = pygame.Rect(x, y, width, 32)
            x += width + 8
        return rects

    def _asset_at(self, pos: tuple[int, int]) -> AssetEntry | None:
        for entry, rect in self._visible_asset_entries():
            hit_rect = pygame.Rect(rect.x, rect.y, rect.width, rect.height + 28)
            if hit_rect.collidepoint(pos):
                return entry
        return None

    def _change_asset_dir(self, target: Path) -> None:
        try:
            label = self.asset_library.change_dir(target, self._asset_entries_per_page())
        except ValueError:
            self.status = "Folder change blocked: outside assets/."
            return
        self.status = f"Browsing assets/{label}"

    def _go_to_parent_asset_dir(self) -> None:
        if self.asset_library.current_dir == self.asset_root:
            self.status = "Already at assets/ root."
            return
        self._change_asset_dir(self.asset_library.current_dir.parent)

    def _import_assets_via_dialog(self) -> None:
        root = tk.Tk()
        root.withdraw()
        root.update()
        try:
            selected = filedialog.askopenfilenames(
                title="Import Assets",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All files", "*.*")],
            )
        finally:
            root.destroy()
        if not selected:
            self.status = "Import cancelled."
            return
        imported = 0
        for path in selected:
            source = Path(path)
            if not source.exists():
                continue
            suffix = source.suffix.lower()
            if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
                continue
            target = self.asset_library.current_dir / source.name
            stem = source.stem
            counter = 2
            while target.exists():
                target = self.asset_library.current_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            shutil.copy2(source, target)
            self.media_cache.discard_path(target)
            imported += 1
        self._refresh_assets()
        self.status = f"Imported {imported} asset(s)." if imported else "No supported assets were selected."

    def _delete_selected_asset(self) -> None:
        if not self.selected_asset_rel:
            self.status = "Select an asset or folder to delete."
            return
        scene_json_target = self._saved_scene_json_for_asset(self.selected_asset_rel)
        target = (self.asset_root / self.selected_asset_rel).resolve()
        try:
            target.relative_to(self.asset_root.resolve())
        except ValueError:
            self.status = "Delete blocked: outside assets/."
            return
        if not target.exists():
            self.selected_asset_rel = None
            self.status = "That asset no longer exists."
            self._refresh_assets()
            return
        was_current_dir = self.asset_library.current_dir.resolve() == target if target.is_dir() else False
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        if scene_json_target is not None and scene_json_target.exists():
            scene_json_target.unlink()
        if self.canvas_doc.asset_rel == self.selected_asset_rel:
            self.canvas_doc.asset_rel = None
        self.media_cache.discard_path(target)
        deleted_rel = self.selected_asset_rel
        self.selected_asset_rel = None
        if was_current_dir:
            self._change_asset_dir(target.parent if target.parent.is_relative_to(self.asset_root) else self.asset_root)
        else:
            self._refresh_assets()
        self.status = f"Deleted assets/{deleted_rel}."

    def _create_folder(self) -> None:
        folder_name = self.folder_name_input.strip().strip("/")
        if not folder_name:
            self.status = "Folder name cannot be empty."
            return
        target = (self.asset_library.current_dir / folder_name).resolve()
        try:
            target.relative_to(self.asset_root.resolve())
        except ValueError:
            self.status = "Folder path must stay inside assets/."
            return
        if target.exists():
            self.status = "Folder already exists."
            return
        target.mkdir(parents=True, exist_ok=False)
        self.dialog_mode = None
        self.folder_name_input = ""
        self._refresh_assets()
        self.status = f"Created folder {target.relative_to(self.asset_root).as_posix()}"

    def _copy_dropped_asset(self, dropped_path: str) -> None:
        source = Path(dropped_path)
        if not source.exists() or not source.is_file():
            self.status = "Only image files can be imported."
            return
        if source.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            self.status = "Unsupported import. Use PNG, JPG, JPEG, BMP, or GIF."
            return

        target = self.asset_library.current_dir / source.name
        stem = source.stem
        suffix = source.suffix
        counter = 2
        while target.exists():
            target = self.asset_library.current_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        shutil.copy2(source, target)
        self.media_cache.discard_path(target)
        self._refresh_assets()
        parent_rel = target.parent.relative_to(self.asset_root).as_posix()
        self.status = f"Imported {target.name} into {parent_rel if parent_rel != '.' else '/'}"

