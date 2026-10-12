"""Agent for questions the policy alone cannot answer.

Example:
    "If I need kidney stone surgery, how much will it cost, what
     treatment options are available, and what does each cost in
     Ahmedabad?"

The policy has no hospital prices, so the agent does a four-stage mix:

  1. Pull the treatment and city out of the question.
  2. Ask the policy (via rag.py) whether it is covered and what
     waiting periods apply. The answer comes with page numbers.
  3. Search the web for treatment options, then for each option
     search its typical cost in that city. The follow-up searches
     are decided on the fly. That is the "agentic" part.
  4. Write one answer that keeps policy facts (with pages) separate
     from web prices (with links, flagged as estimates).

    python agent.py
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
    """Free DuckDuckGo search. Returns [{title, url, text}, ...]."""
    try:
        return [{"title": r["title"], "url": r["href"], "text": r["body"]}
                for r in DDGS().text(query, max_results=n)]
    except Exception as error:
        print("  web search failed:", error)
        return []


# ---------- 1. understand the question ----------
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


# ---------- 2. check the policy ----------
def check_policy(info):
    return ask_policy(info["policy_question"])


# ---------- 3. search the web ----------
def research_market(info):
    treatment, city = info["treatment"], info["city"]

    # First, what are the main treatment options?
    results = web_search(f"{treatment} treatment options types of surgery")
    options = chat(
        "From these search results, list the main treatment options for "
        f"{treatment}. Return JSON: {{\"options\": [\"name\", ...]}} "
        "with at most 5 short names.\n\n" + json.dumps(results),
        as_json=True,
    )["options"]

    # Then price each one in the given city.
    findings = []
    for option in options:
        hits = web_search(f"{option} cost in {city} hospital price rupees", n=4)
        findings.append({"option": option, "results": hits})
    return findings


# ---------- 4. combine everything ----------
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
    print("1. understanding the question...")
    info = understand(question)
    print("  ", info)
    if not info.get("is_health_insurance_question", False):
        return (
            "This assistant answers questions about the HDFC ERGO my:Optima "
            "Secure health-insurance policy and related medical treatment "
            "options. The policy document does not contain information about "
            "this question, so I can't answer it from the policy."
        )

    print("2. checking the policy document...")
    policy_answer = check_policy(info)
    print("3. searching the web for options and prices...")
    market = research_market(info)
    print("4. writing the final answer...\n")
    return combine(question, info, policy_answer, market)


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or (
        "If I need kidney stone surgery, how much will it cost, what treatment "
        "options are available in the market, and how much does each option "
        "typically cost? Tell me for Ahmedabad?")
    print(run_agent(q))
