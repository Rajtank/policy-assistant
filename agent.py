"""
STEP 3: The agent (Agentic RAG) for questions the policy alone cannot answer.

Example question:
  "If I need kidney stone surgery, how much will it cost, what treatment
   options are available in the market, and how much does each option
   typically cost? Tell me for Ahmedabad?"

The policy does not have hospital prices. So the agent works in 4 steps:

  Step 1  UNDERSTAND   The LLM reads the question and pulls out:
                       treatment = "kidney stone surgery", city = "Ahmedabad".
  Step 2  POLICY       Ask our RAG system (rag.py): is this covered?
                       Any waiting period? (answer comes with page numbers)
  Step 3  WEB          Search the internet:
                       3a. "What are the treatment options?"
                       3b. For EACH option the LLM found, search its cost.
                       (The agent decides the follow-up searches itself.
                        This is what makes it "agentic".)
  Step 4  COMBINE      Write one answer with clearly separate parts:
                       policy facts (with page numbers) and market prices
                       (with web links, marked as estimates).

Try it:  python agent.py
"""
import json
import os
import sys

from ddgs import DDGS
from dotenv import load_dotenv
from openai import OpenAI

from rag import ask as ask_policy, get_api_base_url, get_api_key

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
llm = OpenAI(api_key=get_api_key(), base_url=get_api_base_url())


def chat(prompt, as_json=False):
    extra = {"response_format": {"type": "json_object"}} if as_json else {}
    reply = llm.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
        **extra,
    )
    text = reply.choices[0].message.content
    return json.loads(text) if as_json else text


def web_search(query, n=5):
    """Free web search (DuckDuckGo). Returns title, link and short text."""
    try:
        return [{"title": r["title"], "url": r["href"], "text": r["body"]}
                for r in DDGS().text(query, max_results=n)]
    except Exception as error:
        print("  web search failed:", error)
        return []


# ---------------- Step 1: understand the question ----------------
def understand(question):
    return chat(
        "Classify the user's request before extracting details. Return JSON "
        'with "is_health_insurance_question" (boolean): true only if the '
        "request is about health insurance, this policy, medical coverage, "
        "or treatment options/costs; false for unrelated topics such as "
        "sports, events, or general knowledge. Do not invent a treatment "
        "for unrelated or unclear questions. Also return "
        '"treatment" (the medical procedure or illness), "city" (or "India" '
        "if none) and \"policy_question\" (a short question to ask the policy "
        "document about coverage and waiting periods for this treatment).\n\n"
        f"Question: {question}",
        as_json=True,
    )


# ---------------- Step 2: check the policy ----------------
def check_policy(info):
    return ask_policy(info["policy_question"])


# ---------------- Step 3: search the web ----------------
def research_market(info):
    treatment, city = info["treatment"], info["city"]

    # 3a. Find treatment options
    results = web_search(f"{treatment} treatment options types of surgery")
    options = chat(
        "From these search results, list the main treatment options for "
        f"{treatment}. Return JSON: {{\"options\": [\"name\", ...]}} "
        "with at most 5 short names.\n\n" + json.dumps(results),
        as_json=True,
    )["options"]

    # 3b. For each option, search the cost in the city
    findings = []
    for option in options:
        hits = web_search(f"{option} cost in {city} hospital price rupees", n=4)
        findings.append({"option": option, "results": hits})
    return findings


# ---------------- Step 4: combine everything ----------------
def combine(question, info, policy_answer, market):
    return chat(f"""You are a helpful health insurance assistant.
User question: {question}

PART A - what the insurance policy says (trust this, keep page numbers):
{policy_answer}

PART B - web search results about treatment options and prices in {info['city']}:
{json.dumps(market)}

Write a simple answer with these headings:
1. What your policy says   (only from PART A, keep the Source lines)
2. Treatment options and typical cost in {info['city']}
   (a small table: option | what it is | typical cost range in rupees | source link).
   Use only numbers found in PART B. If no price was found, write "not found".
3. What this means for you   (combine both: e.g. if a waiting period applies,
   the user may have to pay the full cost)
4. Important note   (web prices are estimates, they change by hospital,
   room type and city; confirm with the hospital and the insurer)
Use simple words.""")


def run_agent(question):
    print("Step 1: understanding the question...")
    info = understand(question)
    print("  ", info)
    if not info.get("is_health_insurance_question", False):
        return (
            "This assistant answers questions about the HDFC ERGO my:Optima "
            "Secure health-insurance policy and related medical treatment "
            "options. The policy document does not contain information about "
            "this question, so I can't answer it from the policy."
        )

    print("Step 2: checking the policy document...")
    policy_answer = check_policy(info)
    print("Step 3: searching the web for options and prices...")
    market = research_market(info)
    print("Step 4: writing the final answer...\n")
    return combine(question, info, policy_answer, market)


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or (
        "If I need kidney stone surgery, how much will it cost, what treatment "
        "options are available in the market, and how much does each option "
        "typically cost? Tell me for Ahmedabad?")
    print(run_agent(q))
