import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pdfplumber

logger = logging.getLogger(__name__)

# Rough estimate: 1 token ~ 3.5 chars for English text
CHARS_PER_TOKEN = 3.5


class PdfExtractionError(Exception):
    pass


@dataclass
class PdfPage:
    page_number: int
    text: str


@dataclass
class PdfDocument:
    filename: str
    url: str
    pages: list[PdfPage] = field(default_factory=list)
    total_pages: int = 0


class PdfProcessor:
    """Extract text from regulatory PDFs using pdfplumber."""

    def __init__(self, cache_dir: str = "data/pdfs"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def extract_from_url(self, url: str) -> PdfDocument:
        """Download PDF from URL and extract text from all pages."""
        cached = self._cached_path(url)
        if cached.exists():
            logger.info("Using cached PDF: %s", cached)
            return self.extract_from_path(cached, url=url)

        logger.info("Downloading PDF: %s", url)
        try:
            resp = httpx.get(url, follow_redirects=True, timeout=120)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise PdfExtractionError(f"Failed to download PDF from {url}: {e}") from e

        cached.write_bytes(resp.content)
        return self._extract_bytes(resp.content, filename=cached.name, url=url)

    def extract_from_path(self, path: Path, url: str = "") -> PdfDocument:
        """Extract text from a local PDF file."""
        path = Path(path)
        if not path.exists():
            raise PdfExtractionError(f"PDF not found: {path}")
        return self._extract_bytes(path.read_bytes(), filename=path.name, url=url)

    def chunk_document(self, doc: PdfDocument, max_tokens: int = 80_000) -> list[str]:
        """Split document text into chunks sized for Claude's context window.
        Chunks at page boundaries. Each chunk is prefixed with page range metadata."""
        max_chars = max_tokens * CHARS_PER_TOKEN
        chunks: list[str] = []
        current_pages: list[PdfPage] = []
        current_chars = 0

        for page in doc.pages:
            page_chars = len(page.text)

            # If adding this page would exceed the limit and we have content, flush
            if current_chars + page_chars > max_chars and current_pages:
                chunks.append(self._format_chunk(current_pages))
                current_pages = []
                current_chars = 0

            current_pages.append(page)
            current_chars += page_chars

        if current_pages:
            chunks.append(self._format_chunk(current_pages))

        return chunks

    def _extract_bytes(self, data: bytes, filename: str, url: str) -> PdfDocument:
        pages: list[PdfPage] = []
        try:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    pages.append(PdfPage(page_number=i + 1, text=text))
        except Exception as e:
            raise PdfExtractionError(f"Failed to parse PDF {filename}: {e}") from e

        return PdfDocument(
            filename=filename,
            url=url,
            pages=pages,
            total_pages=len(pages),
        )

    def _format_chunk(self, pages: list[PdfPage]) -> str:
        start = pages[0].page_number
        end = pages[-1].page_number
        header = f"[Pages {start}-{end}]\n\n"
        body = "\n\n".join(
            f"--- Page {p.page_number} ---\n{p.text}" for p in pages
        )
        return header + body

    def _cached_path(self, url: str) -> Path:
        # Derive a safe filename from the URL
        safe = url.split("/")[-1] or "download.pdf"
        safe = re.sub(r'[/\\]', '_', safe)
        if not safe.endswith(".pdf"):
            safe += ".pdf"
        result = (self.cache_dir / safe).resolve()
        if not str(result).startswith(str(self.cache_dir.resolve())):
            result = (self.cache_dir / "download.pdf").resolve()
        return result
