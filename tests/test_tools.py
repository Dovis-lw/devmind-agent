import subprocess

import pytest

from app.core.config import settings
from app.services.tools import SafeSandbox, StaticChecker


def test_python_checker_reports_syntax_error():
    result = StaticChecker().check("def broken(:\n    pass", "python")
    assert not result.ok
    assert result.findings[0].rule == "python.syntax"


def test_typescript_checker_reports_any():
    result = StaticChecker().check("const value: any = 1;", "typescript")
    assert result.ok
    assert any(item.rule == "ts.no-any" for item in result.findings)


@pytest.mark.asyncio
async def test_sandbox_blocks_non_whitelisted_command():
    result = await SafeSandbox().run("print('ok')", "python", "rm -rf /")
    assert result["status"] == "blocked"


@pytest.mark.asyncio
async def test_sandbox_uses_configured_timeout(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(settings, "sandbox_timeout_seconds", 3)
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = await SafeSandbox().run("print('ok')", "python")

    assert result["ok"] is True
    assert captured["timeout"] == 3
    assert captured["shell"] is False


@pytest.mark.asyncio
async def test_typescript_sandbox_reports_unavailable_without_tsc(monkeypatch):
    monkeypatch.setattr(SafeSandbox, "_typescript_args", staticmethod(lambda _path: None))
    result = await SafeSandbox().run("const value: number = 1", "typescript")
    assert result["status"] == "unavailable"
