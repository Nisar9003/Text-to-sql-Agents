"""
PDF Processor module.

Extracts tables and text from an uploaded PDF using pdfplumber,
and classifies the PDF as "structured" (contains tables) or
"unstructured" (plain text / narrative document).
"""
import re
import pdfplumber


def sanitize_identifier(name: str) -> str:
    """
    Converts an arbitrary string into a safe SQL identifier
    (table name or column name): lowercase, underscores only,
    no leading digit, no SQL-unsafe characters.
    """
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        name = "column"
    if name[0].isdigit():
        name = f"col_{name}"
    return name


def extract_pdf_content(file_path: str) -> dict:
    """
    Extracts all tables and all text from a PDF file.

    Returns:
        {
            "tables": [ { "columns": [...], "rows": [[...], ...] }, ... ],
            "text": "full extracted text, page by page",
            "page_count": int
        }
    """
    tables = []
    text_parts = []

    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            # --- Table extraction ---
            page_tables = page.extract_tables()
            for raw_table in page_tables:
                if not raw_table or len(raw_table) < 2:
                    continue  # need at least a header row + 1 data row
                header = [
                    sanitize_identifier(str(cell) if cell else f"col_{i}")
                    for i, cell in enumerate(raw_table[0])
                ]
                # de-duplicate column names if sanitization caused collisions
                seen = {}
                unique_header = []
                for col in header:
                    if col in seen:
                        seen[col] += 1
                        unique_header.append(f"{col}_{seen[col]}")
                    else:
                        seen[col] = 0
                        unique_header.append(col)

                data_rows = [row for row in raw_table[1:] if any(cell not in (None, "") for cell in row)]
                if data_rows:
                    tables.append({"columns": unique_header, "rows": data_rows})

            # --- Text extraction ---
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    return {
        "tables": tables,
        "text": "\n\n".join(text_parts),
        "page_count": page_count,
    }


def classify_pdf(extracted: dict) -> str:
    """
    Returns 'structured' if the PDF contains at least one usable table,
    otherwise 'unstructured'.
    """
    return "structured" if extracted["tables"] else "unstructured"


def chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    """
    Splits long text into chunks (by paragraph, roughly max_chars each)
    so it can be stored as separate rows for later retrieval.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks if chunks else ([text] if text.strip() else [])
