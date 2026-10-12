"""
STEP 1: Read the policy PDF and save it into a search database.

What this file does, in plain words:
  1. Opens the PDF page by page.
  2. Removes the repeated header text at the top of every page.
  3. Cuts the text into small pieces ("chunks"). A new chunk starts every
     time the policy starts a new clause (for example "1.1. Hospitalization
     Expenses" or "a. Pre-Existing Diseases: Code - Excl01").
  4. Saves each chunk with its page number, section and clause name.
     These labels are what we show the user as the "Source".

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

# Patterns that tell us "a new section or clause starts here"
SECTION_RE = re.compile(r"^(SECTION [A-E]\.\s*.+|Annexure [A-C](\s*[-–].*)?)$")
DEFINITION_RE = re.compile(r"^Def\.\s*(\d+)\.\s*(.+?)\s+means")
NUMBERED_RE = re.compile(r"^(\d+(?:\.\d+)*\.)\s+([A-Z][^.]{2,80})$")
EXCLUSION_RE = re.compile(r"^([a-z])\.\s+(.+?):\s*Code\s*[–-]\s*(Excl\d+)")


def clean_page(text, page_no):
    """Drop the company header that repeats on every page.
    The header ends with a line that is just the page number."""
    lines = [l.strip() for l in text.split("\n")]
    for i, line in enumerate(lines[:12]):
        if line == str(page_no):
            return lines[i + 1:]
    return lines


def find_heading(line):
    """If this line starts a new clause, return a short clause name."""
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
    """Return a list of chunks: {"text", "page", "section", "clause"}."""
    reader = PdfReader(pdf_path)
    chunks = []
    section, clause = "Front page", "General"

    for page_no, page in enumerate(reader.pages, start=1):
        buffer = []

        def save():
            text = " ".join(buffer).strip()
            # Very long clauses are split so each piece stays small
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
        save()  # end of page: close the chunk so page numbers stay correct

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
        # We add the section and clause name to the text, so a search for
        # "waiting period" also matches the clause title.
        documents=[f"{c['section']} | {c['clause']}\n{c['text']}" for c in chunks],
        metadatas=[{k: c[k] for k in ("page", "section", "clause")} for c in chunks],
    )
    print(f"Saved {len(chunks)} chunks into ./{DB_FOLDER}")


if __name__ == "__main__":
    build_database()
