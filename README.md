# Optima Secure Policy Assistant (simple version)

An AI assistant that answers questions about the HDFC ERGO my:Optima Secure
policy, with page numbers, plus one agent that also searches the web.

## The 4 files you need to know

| File | What it does | In one line |
|---|---|---|
| `ingest.py` | Reads the PDF and saves it into a search database | "Cut the book into labelled pages" |
| `rag.py` | Answers a policy question with Page / Section / Clause | "Find the right page, then answer from it" |
| `agent.py` | Answers questions that need the policy AND the internet | "Check the policy, then Google the prices, then combine" |
| `app.py` | Small web page to demo both | Optional |

## How to run (5 minutes)

```bash
pip install -r requirements.txt

# Add your API key and provider settings to `.env`.
# Groq uses GROQ_API_KEY, OPENAI_BASE_URL=https://api.groq.com/openai/v1,
# and an available chat model in OPENAI_MODEL. Chroma creates embeddings locally.

python ingest.py                         # run once, creates the ./db folder
python rag.py "Is day care treatment covered under this policy?"
python agent.py                          # runs the Ahmedabad kidney stone question
python evaluate.py                       # run the policy QA evaluation set
streamlit run app.py                     # optional demo page
```

Keep `.env` private; do not commit API keys. Groq provides the chat model here,
while Chroma's default embedding function runs locally and does not require a
separate embedding API.

## How it works

**Normal RAG (rag.py)**

1. Search: find the 8 most relevant pieces of the policy.
2. Answer: the LLM reads only those pieces and puts [1], [2] after each fact.
3. Sources: our code turns [1], [2] into the real Page, Section and Clause.
   The LLM never types the page number itself, so it cannot make one up.

**Agent (agent.py)**

1. Understand: pull out the treatment and the city from the question.
2. Policy: ask rag.py if it is covered and what waiting periods apply.
3. Web: search treatment options, then search the price of each option in the city.
4. Combine: one answer with policy facts (page numbers) kept apart from web prices (links).
5. Out-of-scope questions (for example, sports questions) are identified before
   policy or web research, and the app explains that the policy does not cover them.

## Why the chunks follow the policy's own clauses

Every chunk starts where the policy starts a new clause (for example
"a. Pre-Existing Diseases: Code - Excl01"). So each chunk already knows
its page, section and clause name. That is how every answer can say
"Page 28, Section C, Clause Excl01".

## Evaluate answer quality

Run `python evaluate.py` to check a small fixed set of policy questions.
It reports top-8 retrieval recall, expected-fact checks, source-clause traces,
missing personal-detail abstention, and unrelated-question rejection. The fact
checks are automated heuristics; manually confirm answers and citations against
the PDF before relying on the results.
