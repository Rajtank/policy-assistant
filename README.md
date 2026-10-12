# Optima Secure Policy Assistant

An AI assistant that answers questions about the HDFC ERGO my:Optima
Secure health policy, with real page / clause citations. A small
agent handles the cost and market questions by also searching the
web.

## The files

| File | What it does |
|---|---|
| `ingest.py` | Reads the PDF and builds the search database. |
| `rag.py` | Answers a policy question with Page / Section / Clause. |
| `agent.py` | Answers questions that need the policy and the web (e.g. treatment prices). |
| `app.py` | Streamlit UI. Optional. |

## Running it

```bash
pip install -r requirements.txt

# Fill in `.env` with your provider settings.
# Groq example:
#   GROQ_API_KEY=...
#   OPENAI_BASE_URL=https://api.groq.com/openai/v1
#   OPENAI_MODEL=llama-3.3-70b-versatile
# Embeddings run locally via Chroma, so no separate embedding API is needed.

python ingest.py                         # creates ./db (run once)
python rag.py                            # Is day care treatment covered under this policy?
python agent.py                          # the Ahmedabad kidney stone question
python evaluate.py                       # run the QA checks
streamlit run app.py                     # optional UI
```


## How it works

### `rag.py` (plain RAG)

1. Pull the 8 chunks most similar to the question.
2. Pass them to the LLM, numbered `[1]` to `[8]`, with instructions
   to tag every fact with the matching number.
3. Our own code turns those tags into real Page / Section / Clause
   lines. The model never writes a page number itself, so it cannot
   invent one.

### `agent.py` (agentic flow)

1. Parse the question for a treatment and a city.
2. Ask `rag.py` whether it is covered and what waiting periods apply.
3. Search the web for treatment options, then search again for the
   cost of each option in that city.
4. Write one answer that keeps policy facts (page cited) separate
   from web prices (links, flagged as estimates).

Questions that are not about health insurance (sports, for example)
are caught up front and refused before any policy or web lookup
happens.

## Why chunks follow the policy's own clauses

Each chunk starts where the policy itself starts a new clause (e.g.
"a. Pre-Existing Diseases: Code - Excl01"), so it already carries
its page, section and clause label. That is why answers can cite
"Page 28, Section C, Clause Excl01" instead of just a page number.

## Checking answer quality

Run `python evaluate.py` to run a small fixed set of policy
questions. It reports top-8 retrieval recall, expected-fact checks,
source-clause traces, abstention when personal details are missing,
and refusal of unrelated questions. These are regex-based
heuristics, not a replacement for reading the PDF yourself before
you trust the numbers.

### Latest run

| Metric | Score |
|---|---|
| Retrieval Recall@8 | 7 / 7 (100%) |
| Key-fact checks | 5 / 8 (62%) |
| Gold-source citation trace | 7 / 7 (100%) |
| Missing-personal-detail abstention | 0 / 1 (0%) |
| Out-of-scope rejection | 2 / 2 (100%) |

Per-case breakdown:

| # | Facts | Retrieval | Citation | Question |
|---|---|---|---|---|
| 1 | PASS | PASS | PASS | What is the waiting period for a pre-existing disease? |
| 2 | PASS | PASS | PASS | How long is the waiting period for specified procedures? |
| 3 | PASS | PASS | PASS | Does the policy have an initial waiting period for illnesses? |
| 4 | FAIL | PASS | PASS | What qualifies as day care treatment under the policy? (missing fact group 1) |
| 5 | PASS | PASS | PASS | What happens if I choose a room above my policy room-rent limit? |
| 6 | FAIL | PASS | PASS | How long is the free-look period, and when does it apply? (missing fact group 1) |
| 7 | PASS | PASS | PASS | Name three documents the policy lists for a reimbursement claim. |
| 8 | FAIL | N/A | PASS | What exact premium will I pay at my next renewal? (missing fact group 2) |

Out-of-scope question ("When will we host the Cricket World Cup?"):
policy mode PASS, agent mode PASS.

What this says in plain terms: retrieval and citation accuracy are
strong, but three answers skipped an expected fact (day-care defining
window, free-look 30-day keyword, and the "schedule" reference the
abstention case was supposed to mention). Those are the first things
worth tightening in the prompt or the chunk coverage.
