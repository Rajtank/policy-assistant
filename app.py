"""
STEP 4 (optional): Streamlit demo page for the policy assistant.

Run:  streamlit run app.py
"""
import streamlit as st

from agent import run_agent
from rag import ask

SAMPLES = [
    "What is the waiting period for pre-existing diseases?",
    "Is day care treatment covered under this policy?",
    "If I am hospitalized and my daily room rent is around ₹15,000, will it be covered?",
    "I purchased the policy 5 months ago. Will my kidney stone surgery be covered?",
    "I already had gallbladder stones when I purchased the policy 130 days ago. "
    "Now I need surgery. Will this treatment be covered?",
    "What are the exclusions related to my condition?",
    "What documents are required for a claim?",
    "If I need kidney stone surgery, how much will it cost, what treatment "
    "options are available in the market, and how much does each option "
    "typically cost? Tell me for Ahmedabad?",
]

AGENT_HINTS = ("cost", "price", "how much", "market", "options", "hospital",
               "rupees", "₹", "cheap", "expensive")


def route(question: str) -> str:
    q = question.lower()
    return "agent" if any(word in q for word in AGENT_HINTS) else "rag"


st.set_page_config(page_title="Optima Secure Policy AI Assistant", layout="wide")

if "question_input" not in st.session_state:
    st.session_state.question_input = ""
if "last_answer" not in st.session_state:
    st.session_state.last_answer = None
if "history" not in st.session_state:
    st.session_state.history = []


def clear_all():
    st.session_state.question_input = ""
    st.session_state.last_answer = None


def clear_history():
    st.session_state.history = []


def set_sample(sample):
    st.session_state.question_input = sample
    st.session_state.last_answer = None


def load_from_history(index):
    entry = st.session_state.history[index]
    st.session_state.question_input = entry["question"]
    st.session_state.last_answer = (entry["kind"], entry["content"])


with st.sidebar:
    st.markdown("### History")
    if not st.session_state.history:
        st.caption("Your past questions will appear here.")
    else:
        for i, entry in enumerate(reversed(st.session_state.history)):
            real_index = len(st.session_state.history) - 1 - i
            label = entry["question"]
            if len(label) > 60:
                label = label[:57] + "..."
            st.button(
                label,
                key=f"hist_{real_index}",
                use_container_width=True,
                on_click=load_from_history,
                args=(real_index,),
            )
        st.button(
            "Clear history",
            key="clear_history_btn",
            use_container_width=True,
            on_click=clear_history,
        )

    st.markdown("### Mode")
    mode = st.radio(
        "Mode",
        ["Auto (router)", "Policy RAG", "Agent"],
        label_visibility="collapsed",
    )

st.title("Optima Secure Policy AI Assistant")
st.caption(
    "Answers come only from the HDFC ERGO my:Optima Secure policy wording, "
    "with page and clause references. Cost / market questions go to an agent "
    "that also searches the web."
)

main_col, samples_col = st.columns([3, 1])

with samples_col:
    st.markdown("### Try a sample")
    for i, sample in enumerate(SAMPLES):
        st.button(
            sample,
            key=f"sample_{i}",
            use_container_width=True,
            on_click=set_sample,
            args=(sample,),
        )

with main_col:
    with st.form("ask_form", clear_on_submit=False):
        question = st.text_input("Ask about the policy", key="question_input")
        col_ask, col_clear = st.columns([1, 1])
        submitted = col_ask.form_submit_button("Ask", type="primary", use_container_width=True)
        col_clear.form_submit_button("Clear", use_container_width=True, on_click=clear_all)

    if submitted:
        if not question.strip():
            st.warning("Please enter a question or pick a sample on the right.")
        else:
            if mode == "Policy RAG":
                chosen = "rag"
            elif mode == "Agent":
                chosen = "agent"
            else:
                chosen = route(question)

            if chosen == "agent":
                with st.spinner("Agent is working (policy, then web search)..."):
                    answer = run_agent(question)
                    st.session_state.last_answer = ("markdown", answer)
            else:
                with st.spinner("Searching the policy..."):
                    answer = ask(question)
                    st.session_state.last_answer = ("text", answer)

            kind, content = st.session_state.last_answer
            st.session_state.history.append(
                {"question": question, "kind": kind, "content": content}
            )

    if st.session_state.last_answer:
        kind, content = st.session_state.last_answer
        if kind == "markdown":
            st.markdown(content)
        else:
            st.text(content)
