"""Run a small repeatable evaluation of policy retrieval and answers."""
import contextlib
import io
import re

import agent
import rag


POLICY_CASES = [
    {
        "question": "What is the waiting period for a pre-existing disease?",
        "page": 28,
        "clause": "Pre-Existing Diseases (Excl01)",
        "facts": [
            [r"\b36\s*months?\b"],
            [r"\bcontinuous coverage\b"],
            [r"\bdeclared\b", r"\baccepted\b"],
        ],
    },
    {
        "question": "How long is the waiting period for specified procedures?",
        "page": 28,
        "clause": "Specified Disease/Procedure waiting period (Excl02)",
        "facts": [
            [r"\b24\s*months?\b"],
            [r"\bcontinuous coverage\b"],
            [r"\baccident\b"],
        ],
    },
    {
        "question": "Does the policy have an initial waiting period for illnesses?",
        "page": 30,
        "clause": "30-day waiting period (Excl03)",
        "facts": [
            [r"\b30\s*days?\b"],
            [r"\b12\s*months?\b"],
            [r"\baccident\b"],
        ],
    },
    {
        "question": "What qualifies as day care treatment under the policy?",
        "page": 4,
        "clause": "Def. 11 Day Care Treatment",
        "facts": [
            [r"\bless than 24 hours\b", r"\bunder 24 hours\b"],
            [r"\ban[ae]e?sthesia\b"],
            [r"\bout[- ]?patient\b"],
        ],
    },
    {
        "question": "What happens if I choose a room above my policy room-rent limit?",
        "page": 12,
        "clause": "1.1.1. Other Expenses",
        "facts": [
            [r"\bproportionate\b"],
            [r"\bpolicy schedule\b"],
        ],
    },
    {
        "question": "How long is the free-look period, and when does it apply?",
        "page": 35,
        "clause": "1.8. Free look Period",
        "facts": [
            [r"\b30 days\b"],
            [r"\bnew individual\b"],
            [r"\breceipt\b", r"\breceiv(?:e|ed|ing)\b"],
        ],
    },
    {
        "question": "Name three documents the policy lists for a reimbursement claim.",
        "page": 43,
        "clause": "1.7. List of documents required for a Claim",
        "facts": [
            [r"\bclaim form\b"],
            [r"\bdischarge\b"],
            [r"\bhospital bill\b", r"\bfinal bill\b"],
        ],
    },
    {
        "question": "What exact premium will I pay at my next renewal?",
        "page": None,
        "clause": None,
        "facts": [
            [r"\bnot (?:provided|specified|available|clearly answer)\b",
             r"\bdoes not (?:state|provide|specify)\b"],
            [r"\bschedule\b"],
        ],
        "abstention": True,
    },
]

OUT_OF_SCOPE_QUESTION = "When will we host the Cricket World Cup?"


def has_fact(answer, alternatives):
    return any(re.search(pattern, answer, re.IGNORECASE) for pattern in alternatives)


def run():
    retrieval_passes = 0
    retrieval_cases = 0
    answer_passes = 0
    citation_passes = 0
    abstention_passes = 0
    citation_cases = 0

    print("Policy answer tests")
    for index, case in enumerate(POLICY_CASES, start=1):
        chunks = rag.search_policy(case["question"], k=8)
        if case["clause"] is not None:
            retrieval_cases += 1
            retrieved_gold = any(
                chunk["page"] == case["page"] and case["clause"] in chunk["clause"]
                for chunk in chunks
            )
            retrieval_passes += int(retrieved_gold)
        else:
            retrieved_gold = None

        answer = rag.ask(case["question"])
        facts_ok = all(has_fact(answer, group) for group in case["facts"])
        answer_passes += int(facts_ok)

        if case.get("abstention", False):
            abstention_passes += int(facts_ok)
            citation_ok = True
        else:
            citation_cases += 1
            citation_ok = (
                f"Page: {case['page']}" in answer
                and case["clause"].casefold() in answer.casefold()
            )
            citation_passes += int(citation_ok)

        print(
            f"{index}. {'PASS' if facts_ok else 'FAIL'} | "
            f"retrieval "
            f"{'N/A' if retrieved_gold is None else ('PASS' if retrieved_gold else 'FAIL')} | "
            f"citation {'PASS' if citation_ok else 'FAIL'} | "
            f"{case['question']}"
        )
        if not facts_ok:
            missing = [
                str(group_index)
                for group_index, group in enumerate(case["facts"], start=1)
                if not has_fact(answer, group)
            ]
            print("   Missing expected fact group(s): " + ", ".join(missing))

    out_of_scope_policy = rag.ask(OUT_OF_SCOPE_QUESTION)
    policy_rejected = (
        "policy document does not contain" in out_of_scope_policy.casefold()
        and "no source found" in out_of_scope_policy.casefold()
    )

    with contextlib.redirect_stdout(io.StringIO()):
        out_of_scope_agent = agent.run_agent(OUT_OF_SCOPE_QUESTION)
    agent_rejected = (
        "policy document does not contain" in out_of_scope_agent.casefold()
        and "treatment options and typical cost" not in out_of_scope_agent.casefold()
    )
    out_of_scope_passes = int(policy_rejected) + int(agent_rejected)
    print(
        f"Out-of-scope question: policy {'PASS' if policy_rejected else 'FAIL'}; "
        f"agent {'PASS' if agent_rejected else 'FAIL'}"
    )

    print("\nSummary")
    print(f"Retrieval Recall@8: {retrieval_passes}/{retrieval_cases} "
          f"({retrieval_passes / retrieval_cases:.0%})")
    print(f"Key-fact checks: {answer_passes}/{len(POLICY_CASES)} "
          f"({answer_passes / len(POLICY_CASES):.0%})")
    print(f"Gold-source citation trace: {citation_passes}/{citation_cases} "
          f"({citation_passes / citation_cases:.0%})")
    print(f"Missing-personal-detail abstention: {abstention_passes}/1 "
          f"({abstention_passes:.0%})")
    print(f"Out-of-scope rejection: {out_of_scope_passes}/2 "
          f"({out_of_scope_passes / 2:.0%})")
    print("\nThese are automated checks, not a substitute for human review of "
          "whether each citation fully supports its answer.")


if __name__ == "__main__":
    run()
