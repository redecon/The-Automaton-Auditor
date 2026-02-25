# src/tools/doc_tools.py

from PyPDF2 import PdfReader

def ingest_pdf(pdf_path: str, chunk_size: int = 500) -> list[str]:
    """Read PDF and return text chunks for queryable interface."""
    try:
        reader = PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() or ""

        # Chunk into smaller pieces
        chunks = [
            full_text[i:i+chunk_size]
            for i in range(0, len(full_text), chunk_size)
        ]
        return chunks
    except Exception as e:
        raise RuntimeError(f"Error reading PDF: {e}")

def keyword_search(chunks: list[str], keywords: list[str]) -> dict:
    """Search for keywords across chunks."""
    results = {kw: False for kw in keywords}
    for chunk in chunks:
        for kw in keywords:
            if kw.lower() in chunk.lower():
                results[kw] = True
    return results


def keyword_search(text: str, keywords: list) -> dict:
    """Search for keywords and return context snippets."""
    results = {}
    for kw in keywords:
        if kw.lower() in text.lower():
            # Grab a snippet around the keyword
            idx = text.lower().find(kw.lower())
            snippet = text[max(0, idx-50): idx+100]
            results[kw] = snippet
        else:
            results[kw] = None
    return results
