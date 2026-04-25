from __future__ import annotations

from pathlib import Path

try:
    from ..models import AssetEntry
except ImportError:
    from models import AssetEntry  # type: ignore[no-redef]


class AssetLibrary:
    def __init__(self, asset_root: Path, media_cache, supported_extensions: set[str]) -> None:
        self.asset_root = asset_root
        self.media_cache = media_cache
        self.supported_extensions = supported_extensions
        self.current_dir = asset_root
        self.page = 0
        self.entries: list[AssetEntry] = []

    def refresh(self, per_page: int) -> None:
        self.entries = self._list_entries()
        self.page = min(self.page, self.max_page(per_page))

    def max_page(self, per_page: int) -> int:
        if per_page <= 0:
            return 0
        return max((len(self.entries) - 1) // per_page, 0)

    def change_dir(self, target: Path, per_page: int) -> str:
        relative = target.resolve().relative_to(self.asset_root.resolve())
        self.current_dir = self.asset_root / relative
        self.page = 0
        self.refresh(per_page)
        return relative.as_posix() if str(relative) != "." else "/"

    def _list_entries(self) -> list[AssetEntry]:
        self.current_dir.mkdir(parents=True, exist_ok=True)
        children = sorted(
            self.current_dir.iterdir(),
            key=lambda path: (not path.is_dir(), path.name.lower()),
        )
        entries: list[AssetEntry] = []
        for child in children:
            if child.is_dir():
                preview = self.media_cache.folder_preview()
            elif child.is_file() and child.suffix.lower() in self.supported_extensions:
                preview = self.media_cache.preview_for_image(child)
            else:
                continue
            entries.append(
                AssetEntry(
                    rel_path=child.relative_to(self.asset_root).as_posix(),
                    name=child.name,
                    path=child,
                    is_dir=child.is_dir(),
                    preview=preview,
                )
            )
        return entries
