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
    arguments = list(sys.argv[1:])
    if "--smoke-test" in arguments:
        arguments.remove("--smoke-test")
        sys.argv = [sys.argv[0], *arguments]
        return _run_smoke_test()

    workspace, remaining = resolve_workspace(arguments)
    runners: dict[str, Callable[[], int]] = {
        "frame": _run_frame,
        "beam": _run_beam,
        "truss": _run_truss,
    }
    sys.argv = [sys.argv[0], *remaining]
    return runners[workspace]()


def _run_frame() -> int:
    from go_struct_desktop.app import main as run

    return run()


def _run_beam() -> int:
    from go_struct_desktop.beam_workspace import main as run

    return run()


def _run_truss() -> int:
    from go_struct_desktop.truss_workspace import main as run

    return run()


def _run_smoke_test() -> int:
    """Import every installed workspace so packaging failures return non-zero."""

    import go_struct_desktop.app  # noqa: F401
    import go_struct_desktop.beam_workspace  # noqa: F401
    import go_struct_desktop.truss_workspace  # noqa: F401

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
