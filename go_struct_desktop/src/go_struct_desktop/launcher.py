"""Single executable entry point for the installed GO Struct workspaces."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Callable


def resolve_workspace(arguments: Sequence[str]) -> tuple[str, list[str]]:
    """Extract the installer shortcut workspace without passing it to Qt."""

    remaining = list(arguments)
    workspace = "frame"
    if "--workspace" in remaining:
        index = remaining.index("--workspace")
        if index == len(remaining) - 1:
            raise ValueError("--workspace requires frame, beam, or truss")
        workspace = remaining[index + 1].lower()
        del remaining[index : index + 2]
    if workspace not in {"frame", "beam", "truss"}:
        raise ValueError(f"Unknown workspace: {workspace}")
    return workspace, remaining


def main() -> int:
    workspace, remaining = resolve_workspace(sys.argv[1:])
    runners: dict[str, Callable[[], int]] = {
        "frame": _run_frame,
        "beam": _run_beam,
        "truss": _run_truss,
    }
    sys.argv = [sys.argv[0], *remaining]
    return runners[workspace]()


def _run_frame() -> int:
    from .app import main as run

    return run()


def _run_beam() -> int:
    from .beam_workspace import main as run

    return run()


def _run_truss() -> int:
    from .truss_workspace import main as run

    return run()
if __name__ == "__main__":
    raise SystemExit(main())
