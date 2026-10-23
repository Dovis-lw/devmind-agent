from __future__ import annotations

import io
import zipfile

import pytest

from app.services.documents import (
    MAX_ARCHIVE_FILE_BYTES,
    MAX_ARCHIVE_FILES,
    MAX_ARCHIVE_TOTAL_BYTES,
    infer_document_type,
    is_supported_document,
    parse_document,
    safe_filename,
)
from app.services.storage import InMemoryStore
from app.services.tasks import TaskService


def make_zip(entries: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


def test_safe_filename_removes_client_path() -> None:
    assert safe_filename("../../secret.md") == "secret.md"
    assert safe_filename(r"C:\\temp\\report.txt") == "report.txt"


def test_supported_suffixes_and_types() -> None:
    assert is_supported_document("guide.MD")
    assert infer_document_type("main.ts") == "typescript"
    assert not is_supported_document("payload.exe")


def test_zip_parser_skips_secrets_and_path_traversal() -> None:
    content = make_zip(
        [
            ("src/main.py", b"print('ok')"),
            (".env", b"SECRET=do-not-index"),
            ("../escape.py", b"print('unsafe')"),
        ]
    )
    kind, text = parse_document("project.zip", content)
    assert kind == "code-archive"
    assert "src/main.py" in text
    assert "do-not-index" not in text
    assert "unsafe" not in text


def test_zip_parser_enforces_file_count_limit() -> None:
    content = make_zip([(f"file-{index}.txt", b"x") for index in range(MAX_ARCHIVE_FILES + 1)])
    with pytest.raises(ValueError, match="文件数量"):
        parse_document("project.zip", content)


def test_zip_parser_enforces_single_file_limit() -> None:
    content = make_zip([("large.txt", b"x" * (MAX_ARCHIVE_FILE_BYTES + 1))])
    with pytest.raises(ValueError, match="过大"):
        parse_document("project.zip", content)


def test_zip_parser_enforces_total_size_limit() -> None:
    each = MAX_ARCHIVE_FILE_BYTES
    count = MAX_ARCHIVE_TOTAL_BYTES // each + 1
    content = make_zip([(f"file-{index}.txt", b"x" * each) for index in range(count)])
    with pytest.raises(ValueError, match="过大"):
        parse_document("project.zip", content)


@pytest.mark.asyncio
async def test_failed_document_parse_marks_task_failed() -> None:
    store = InMemoryStore()
    document = store.add_document("kb-demo", "broken.pdf", "pdf", "upload", "")
    task = await TaskService(store).index_document(document.id, b"not-a-pdf")
    assert task.status == "failed"
    assert document.status == "failed"
    assert "索引失败" in task.message
