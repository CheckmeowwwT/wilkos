from __future__ import annotations


class SceneHistory:
    def __init__(self, max_entries: int = 40) -> None:
        self.max_entries = max_entries
        self.undo_stack: list[dict[str, object]] = []
        self.redo_stack: list[dict[str, object]] = []

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()

    def push(self, snapshot: dict[str, object]) -> None:
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > self.max_entries:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self, current_snapshot: dict[str, object]) -> dict[str, object] | None:
        if not self.undo_stack:
            return None
        self.redo_stack.append(current_snapshot)
        return self.undo_stack.pop()

    def redo(self, current_snapshot: dict[str, object]) -> dict[str, object] | None:
        if not self.redo_stack:
            return None
        self.undo_stack.append(current_snapshot)
        return self.redo_stack.pop()

    @property
    def undo_count(self) -> int:
        return len(self.undo_stack)
