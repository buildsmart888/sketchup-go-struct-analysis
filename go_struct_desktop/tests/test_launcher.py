from __future__ import annotations

import pytest

from go_struct_desktop import launcher
from go_struct_desktop.launcher import resolve_workspace


def test_launcher_defaults_to_frame_and_preserves_application_arguments() -> None:
    assert resolve_workspace(["project.goframe.json"]) == ("frame", ["project.goframe.json"])


def test_launcher_extracts_workspace_argument() -> None:
    assert resolve_workspace(["--workspace", "truss", "project.gotruss.json"]) == ("truss", ["project.gotruss.json"])


def test_launcher_runs_packaging_smoke_test_without_starting_a_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launcher.sys, "argv", ["GO-Struct-Desktop.exe", "--smoke-test"])
    monkeypatch.setattr(launcher, "_run_smoke_test", lambda: 73)

    assert launcher.main() == 73


@pytest.mark.parametrize("arguments", [["--workspace"], ["--workspace", "unknown"]])
def test_launcher_rejects_invalid_workspace(arguments: list[str]) -> None:
    with pytest.raises(ValueError):
        resolve_workspace(arguments)
