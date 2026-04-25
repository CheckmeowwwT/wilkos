from __future__ import annotations

import pygame


class CanvasHistory:
    def __init__(self, max_entries: int = 40) -> None:
        self.max_entries = max_entries
        self.undo_stack: list[pygame.Surface] = []
        self.redo_stack: list[pygame.Surface] = []

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()

    def push(self, surface: pygame.Surface) -> None:
        self.undo_stack.append(surface.copy())
        if len(self.undo_stack) > self.max_entries:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self, current: pygame.Surface) -> pygame.Surface | None:
        if not self.undo_stack:
            return None
        self.redo_stack.append(current.copy())
        return self.undo_stack.pop()

    def redo(self, current: pygame.Surface) -> pygame.Surface | None:
        if not self.redo_stack:
            return None
        self.undo_stack.append(current.copy())
        return self.redo_stack.pop()

    @property
    def undo_count(self) -> int:
        return len(self.undo_stack)
