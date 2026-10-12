"""Build the policy search database from the PDF.

Reads the PDF page by page, drops the repeating header, and splits
the text wherever a new clause begins (e.g. "1.1. Hospitalization
Expenses" or "a. Pre-Existing Diseases: Code - Excl01"). Each chunk
remembers its page, section and clause so citations can point
somewhere real.

Run it once:  python ingest.py
"""
import re

from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()

PDF_PATH = "optima-secure-revision-pw.pdf"
DB_FOLDER = "db"
COLLECTION = "policy"
MAX_CHUNK_CHARS = 1500

# Lines that mean "a new section or clause starts here".
SECTION_RE = re.compile(r"^(SECTION [A-E]\.\s*.+|Annexure [A-C](\s*[-–].*)?)$")
DEFINITION_RE = re.compile(r"^Def\.\s*(\d+)\.\s*(.+?)\s+means")
NUMBERED_RE = re.compile(r"^(\d+(?:\.\d+)*\.)\s+([A-Z][^.]{2,80})$")
EXCLUSION_RE = re.compile(r"^([a-z])\.\s+(.+?):\s*Code\s*[–-]\s*(Excl\d+)")


def clean_page(text, page_no):
    """Strip the repeating company header off a page.

    The header always runs until a line that holds only the page
    number, so we cut there.
    """
    lines = [l.strip() for l in text.split("\n")]
    for i, line in enumerate(lines[:12]):
        if line == str(page_no):
            return lines[i + 1:]
    return lines


def find_heading(line):
    """Return a short clause name if this line opens a new clause."""
    m = DEFINITION_RE.match(line)
    if m:
        return f"Def. {m.group(1)} {m.group(2)}"
    m = EXCLUSION_RE.match(line)
    if m:
        return f"{m.group(1)}. {m.group(2)} ({m.group(3)})"
    m = NUMBERED_RE.match(line)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return None


def make_chunks(pdf_path=PDF_PATH):
    """Walk the PDF and return a list of chunks.

    Each chunk looks like {text, page, section, clause}.
    """
    reader = PdfReader(pdf_path)
    chunks = []
    section, clause = "Front page", "General"

    for page_no, page in enumerate(reader.pages, start=1):
        buffer = []

        def save():
            text = " ".join(buffer).strip()
            # Big clauses get sliced so no single chunk is too long to retrieve.
            for start in range(0, len(text), MAX_CHUNK_CHARS):
                piece = text[start:start + MAX_CHUNK_CHARS]
                if len(piece) > 40:
                    chunks.append({"text": piece, "page": page_no,
                                   "section": section, "clause": clause})
            buffer.clear()

        for line in clean_page(page.extract_text() or "", page_no):
            if not line:
                continue
            if SECTION_RE.match(line):
                save()
                section, clause = line, "General"
                continue
            heading = find_heading(line)
            if heading:
                save()
                clause = heading
            buffer.append(line)
        save()  # flush at the end of a page so page numbers stay accurate

    return chunks


def build_database():
    import chromadb
    from chromadb.utils import embedding_functions

    chunks = make_chunks()
    client = chromadb.PersistentClient(path=DB_FOLDER)
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass

    embedder = embedding_functions.DefaultEmbeddingFunction()
    db = client.create_collection(COLLECTION, embedding_function=embedder)

    db.add(
        ids=[str(i) for i in range(len(chunks))],
        # Prepend the section and clause name so a search for "waiting
        # period" also catches chunks whose clause title says it.
        documents=[f"{c['section']} | {c['clause']}\n{c['text']}" for c in chunks],
        metadatas=[{k: c[k] for k in ("page", "section", "clause")} for c in chunks],
    )
    print(f"Saved {len(chunks)} chunks into ./{DB_FOLDER}")


if __name__ == "__main__":
    build_database()
