from __future__ import annotations

import pytest

from go_struct_desktop.launcher import resolve_workspace


def test_launcher_defaults_to_frame_and_preserves_application_arguments() -> None:
    assert resolve_workspace(["project.goframe.json"]) == ("frame", ["project.goframe.json"])


def test_launcher_extracts_workspace_argument() -> None:
    assert resolve_workspace(["--workspace", "truss", "project.gotruss.json"]) == ("truss", ["project.gotruss.json"])


@pytest.mark.parametrize("arguments", [["--workspace"], ["--workspace", "unknown"]])
def test_launcher_rejects_invalid_workspace(arguments: list[str]) -> None:
    with pytest.raises(ValueError):
        resolve_workspace(arguments)
