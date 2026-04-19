"""Map / scene editor tool."""

from __future__ import annotations

from .app import SceneEditorApp


def main() -> None:
    app = SceneEditorApp()
    app.run()
