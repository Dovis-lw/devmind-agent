from __future__ import annotations

import io
import zipfile
from pathlib import Path, PurePosixPath

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".zip"}
MAX_ARCHIVE_FILES = 500
MAX_ARCHIVE_FILE_BYTES = 1_000_000
MAX_ARCHIVE_TOTAL_BYTES = 12_000_000


def safe_filename(name: str) -> str:
    """Drop client-provided paths and control characters from upload names."""
    cleaned = Path(name.replace("\\", "/")).name.strip().replace("\x00", "")
    return cleaned[:160] or "untitled.txt"


def is_supported_document(name: str) -> bool:
    return Path(name).suffix.lower() in SUPPORTED_SUFFIXES


def infer_document_type(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return {
        ".pdf": "pdf",
        ".docx": "word",
        ".md": "markdown",
        ".txt": "text",
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".zip": "archive",
    }.get(suffix, "text")


def _safe_archive_member(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return not path.is_absolute() and ".." not in path.parts


def parse_document(name: str, content: bytes) -> tuple[str, str]:
    kind = infer_document_type(name)
    if kind == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return kind, "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if kind == "word":
        from docx import Document as WordDocument

        document = WordDocument(io.BytesIO(content))
        return kind, "\n\n".join(paragraph.text for paragraph in document.paragraphs)
    if kind == "archive":
        parts: list[str] = []
        total_bytes = 0
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_FILES:
                raise ValueError(f"压缩包文件数量不能超过 {MAX_ARCHIVE_FILES}")
            for info in members:
                if info.is_dir() or not _safe_archive_member(info.filename):
                    continue
                if info.flag_bits & 0x1:
                    continue
                if info.file_size > MAX_ARCHIVE_FILE_BYTES:
                    raise ValueError(f"压缩包内单个文件过大，不能超过 {MAX_ARCHIVE_FILE_BYTES} 字节")
                total_bytes += info.file_size
                if total_bytes > MAX_ARCHIVE_TOTAL_BYTES:
                    raise ValueError("压缩包解压后的可索引内容过大")
                lowered = info.filename.lower()
                if Path(info.filename).name.startswith(".") or ".env" in lowered:
                    continue
                if infer_document_type(info.filename) in {"python", "javascript", "typescript", "markdown", "text"}:
                    data = archive.read(info)
                    parts.append(f"## FILE: {info.filename}\n{data.decode('utf-8', errors='ignore')}")
        return "code-archive", "\n\n".join(parts)
    return kind, content.decode("utf-8", errors="ignore")


