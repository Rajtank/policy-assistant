"""
STEP 2: Answer a policy question (normal RAG).

How it works, in plain words:
  1. SEARCH:   find the 8 policy chunks that best match the question.
  2. ANSWER:   give those chunks to the LLM, numbered [1] to [8], and tell it:
               "use only these, and put [number] after every fact".
  3. SOURCES:  our code (not the LLM) reads which numbers were used and
               prints the real page, section and clause for each one.
               So the LLM can never invent a page number.

Try it:  python rag.py "What is the waiting period for pre-existing diseases?"
"""
import os
import re
import sys

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def get_api_key():
    return os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")


def get_api_base_url():
    if os.getenv("OPENAI_BASE_URL"):
        return os.getenv("OPENAI_BASE_URL")
    if os.getenv("GROQ_API_KEY"):
        return "https://api.groq.com/openai/v1"
    return None


llm = OpenAI(api_key=get_api_key(), base_url=get_api_base_url())

# Users say "kidney stone", the policy says "calculus diseases of Urogenital
# system". Adding policy words to the search helps find the right clause.
EXTRA_WORDS = {
    "kidney stone": "calculus diseases of Urogenital system specified disease waiting period",
    "gallbladder": "diseases of gall bladder cholecystectomy specified disease waiting period",
    "gall bladder": "cholecystectomy specified disease waiting period",
    "already had": "pre-existing disease Excl01 waiting period",
    "room rent": "Room Rent At Actuals proportionate deduction plan chart",
    "documents": "list of documents required for a claim",
    "exclusion": "waiting period exclusions Code Excl",
}

SYSTEM_PROMPT = """You are a health insurance policy assistant for the
HDFC ERGO my:Optima Secure policy. Rules:
1. If the user's question is unrelated to health insurance or this policy,
   do not answer it using retrieved extracts. Say: "This assistant answers
   questions about the HDFC ERGO my:Optima Secure health-insurance policy.
   The policy document does not contain information about this question."
2. Use ONLY the numbered policy extracts given to you. No outside knowledge.
3. Put the extract number in square brackets after every fact, like [2].
4. Write in simple language a customer can understand.
5. Always mention conditions, limits and exceptions.
6. Do not assume anything. If the answer depends on missing details (for
   example plan name, sum insured, date of purchase, whether the illness
   existed before buying), say exactly what is missing.
7. If the extracts do not answer the question, say "The policy document
   does not clearly answer this."

Reply in this format:
Answer: <2 to 5 simple sentences>
Conditions and exceptions:
- <point> [n]
Information needed (only if something is missing):
- <point>"""

_db = None


def get_db():
    global _db
    if _db is None:
        client = chromadb.PersistentClient(path="db")
        embedder = embedding_functions.DefaultEmbeddingFunction()
        try:
            _db = client.get_collection("policy", embedding_function=embedder)
        except Exception:
            from ingest import build_database
            build_database()
            _db = client.get_collection("policy", embedding_function=embedder)
    return _db


def search_policy(question, k=8):
    """Return the k best matching chunks with their page/section/clause."""
    query = question
    for user_word, policy_words in EXTRA_WORDS.items():
        if user_word in question.lower():
            query += " " + policy_words
    result = get_db().query(query_texts=[query], n_results=k)
    return [
        {"text": doc, **meta}
        for doc, meta in zip(result["documents"][0], result["metadatas"][0])
    ]


def format_sources(chunks, answer):
    """Turn the [n] numbers used in the answer into real page references."""
    used = sorted({
        int(n) for n in re.findall(r"(?:\[|【)(\d+)(?:\]|】)", answer)
    })
    lines, seen = [], set()
    for n in used:
        if 1 <= n <= len(chunks):
            c = chunks[n - 1]
            key = (c["page"], c["clause"])
            if key not in seen:
                seen.add(key)
                lines.append(f"[{n}] Page: {c['page']} | Section: {c['section']} "
                             f"| Clause: {c['clause']}")
    return "Source:\n" + ("\n".join(lines) if lines else "No source found")


def ask(question):
    """Full RAG answer: search, then answer, then add sources."""
    chunks = search_policy(question)
    extracts = "\n\n".join(
        f"[{i}] (Page {c['page']}, {c['clause']})\n{c['text']}"
        for i, c in enumerate(chunks, start=1)
    )
    reply = llm.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Policy extracts:\n{extracts}\n\nQuestion: {question}"},
        ],
    )
    answer = reply.choices[0].message.content
    return answer + "\n\n" + format_sources(chunks, answer)


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What is the waiting period for pre-existing diseases?"
    print(ask(q))
