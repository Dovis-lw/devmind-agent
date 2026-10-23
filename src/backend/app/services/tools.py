from __future__ import annotations

import ast
import asyncio
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from app.core.config import settings
from app.schemas.models import DiagnosticFinding, DiagnosticResult


class StaticChecker:
    """轻量静态检查工具，覆盖 Python 与 JavaScript/TypeScript 常见语法问题。"""

    def check(self, code: str, language: str) -> DiagnosticResult:
        findings: list[DiagnosticFinding] = []
        if language == "python":
            try:
                ast.parse(code)
            except SyntaxError as exc:
                findings.append(DiagnosticFinding(level="error", line=exc.lineno, message=exc.msg, rule="python.syntax"))
            if "except:" in code:
                findings.append(DiagnosticFinding(level="warning", message="建议避免裸 except，保留异常类型和处理上下文。", rule="python.bare-except"))
        else:
            lines = code.splitlines()
            for index, line in enumerate(lines, 1):
                if line.count("{") != line.count("}"):
                    findings.append(DiagnosticFinding(level="error", line=index, message="大括号数量不匹配。", rule="js.braces"))
                if "console.log" in line:
                    findings.append(DiagnosticFinding(level="warning", line=index, message="生产代码建议移除调试日志。", rule="js.no-console"))
            if re.search(r"\bany\b", code) and language == "typescript":
                findings.append(DiagnosticFinding(level="warning", message="TypeScript 中发现 any，建议使用明确类型。", rule="ts.no-any"))
        return DiagnosticResult(ok=not any(f.level == "error" for f in findings), language=language, findings=findings, summary="未发现阻断性问题" if not findings else f"发现 {len(findings)} 个问题")


class SafeSandbox:
    """安全沙箱：只写入临时目录，只执行白名单语法检查，不接触宿主项目。"""

    ALLOWED = {"python": "python", "javascript": "node", "typescript": "tsc"}

    @staticmethod
    def _typescript_args(file_path: Path) -> list[str] | None:
        node_path = shutil.which("node")
        local_tsc = Path(__file__).resolve().parents[3] / "frontend" / "node_modules" / "typescript" / "bin" / "tsc"
        if node_path and local_tsc.is_file():
            return [node_path, str(local_tsc), "--noEmit", "--pretty", "false", "--target", "ES2022", str(file_path)]

        tsc_path = shutil.which("tsc")
        if tsc_path and Path(tsc_path).suffix.lower() not in {".cmd", ".bat"}:
            return [tsc_path, "--noEmit", "--pretty", "false", "--target", "ES2022", str(file_path)]
        return None

    async def run(self, code: str, language: str, command: str = "syntax-check") -> dict[str, object]:
        # AI TECH STACK: BACKEND ORCHESTRATION
        if command != "syntax-check":
            return {"ok": False, "status": "blocked", "output": "只允许 syntax-check 白名单命令。"}
        suffix = {"python": ".py", "javascript": ".js", "typescript": ".ts"}[language]
        with tempfile.TemporaryDirectory(prefix="devmind-sandbox-") as directory:
            file_path = Path(directory) / f"snippet{suffix}"
            file_path.write_text(code, encoding="utf-8")
            if language == "python":
                args = [sys.executable, "-m", "py_compile", str(file_path)]
            elif language == "javascript":
                args = ["node", "--check", str(file_path)]
            else:
                args = self._typescript_args(file_path)
                if args is None:
                    return {
                        "ok": False,
                        "status": "unavailable",
                        "output": "TypeScript 沙箱需要后端环境提供 tsc；静态规则检查仍可使用。",
                    }
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    args,
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=settings.sandbox_timeout_seconds,
                    shell=False,
                )
            except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
                return {"ok": False, "status": "timeout-or-unavailable", "output": str(exc)[:1000]}
            output = (result.stdout + result.stderr)[:4000]
            return {"ok": result.returncode == 0, "status": "completed", "output": output or "语法检查通过。"}
