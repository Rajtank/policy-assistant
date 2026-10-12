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
