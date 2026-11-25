"""Read RFP text from uploads (TXT, PDF, DOCX) and the bundled samples."""
import io
import re

from .config import RFP_DIR


def list_samples() -> dict[str, str]:
    return {p.stem.split("_", 1)[1].replace("_", " ").title(): p.read_text(encoding="utf-8")
            for p in sorted(RFP_DIR.glob("*.txt"))}


def read_upload(name: str, data: bytes) -> str:
    ext = name.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        from pypdf import PdfReader
        text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    elif ext == "docx":
        from docx import Document
        text = "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    else:
        text = data.decode("utf-8", errors="ignore")
    return re.sub(r"\n{3,}", "\n\n", text).strip()
