import hashlib, io, re, uuid
from dataclasses import dataclass
import fitz

@dataclass
class PageText:
    page_number: int
    text: str
    extraction_method: str


def validate_pdf(data: bytes, max_bytes: int) -> None:
    if not data or len(data) > max_bytes:
        raise ValueError(f'File must be non-empty and no larger than {max_bytes // (1024*1024)} MB')
    if not data.startswith(b'%PDF-'):
        raise ValueError('File signature is not a valid PDF')
    # Opening with PyMuPDF validates the PDF structure more meaningfully than extension checks.
    with fitz.open(stream=data, filetype='pdf') as doc:
        if doc.page_count == 0 or doc.page_count > 1000:
            raise ValueError('PDF page count is outside the accepted range (1-1000)')


def extract_pages(data: bytes) -> tuple[list[PageText], list[str]]:
    pages, warnings = [], []
    with fitz.open(stream=data, filetype='pdf') as doc:
        for index, page in enumerate(doc, start=1):
            text = page.get_text('text', sort=True).strip()
            method = 'pymupdf-text'
            if len(text) < 30:
                # OCR is deliberately an adapter boundary. Install/configure Tesseract or
                # an approved Document AI service; do not silently send bank docs to SaaS.
                try:
                    import pytesseract
                    from PIL import Image
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image = Image.open(io.BytesIO(pix.tobytes('png')))
                    text = pytesseract.image_to_string(image).strip()
                    method = 'tesseract-ocr'
                except ImportError:
                    warnings.append(f'Page {index}: little/no text found; OCR adapter not installed')
                except Exception as exc:
                    warnings.append(f'Page {index}: OCR failed ({type(exc).__name__})')
            if text:
                pages.append(PageText(index, text, method))
    return pages, warnings


def normalize(text: str) -> str:
    text = text.replace('\x00', ' ')
    return re.sub(r'[ \t]+', ' ', text).strip()


def chunk_page(text: str, size: int, overlap: int) -> list[str]:
    text = normalize(text)
    if not text: return []
    if overlap >= size: raise ValueError('chunk overlap must be smaller than chunk size')
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = max(text.rfind('. ', start, end), text.rfind('\n', start, end))
            if boundary > start + int(size * .6): end = boundary + 1
        part = text[start:end].strip()
        if part: chunks.append(part)
        if end >= len(text): break
        start = max(start + 1, end - overlap)
    return chunks


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_chunks(pages, metadata: dict, filename: str, content_hash: str, size: int, overlap: int):
    rows = []
    for page in pages:
        for ordinal, chunk in enumerate(chunk_page(page.text, size, overlap)):
            rows.append({
                **metadata, 'text': chunk, 'filename': filename,
                'page': page.page_number, 'chunk_id': str(uuid.uuid4()),
                'chunk_ordinal': ordinal, 'content_sha256': content_hash,
                'extraction_method': page.extraction_method,
            })
    return rows
