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

if "question" not in st.session_state:
    st.session_state.question = ""

with st.sidebar:
    st.markdown("### Try a sample")
    for i, sample in enumerate(SAMPLES):
        if st.button(sample, key=f"sample_{i}", use_container_width=True):
            st.session_state.question = sample

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

question = st.text_input("Ask about the policy", value=st.session_state.question)

if st.button("Ask", type="primary"):
    if not question.strip():
        st.warning("Please enter a question or pick a sample from the sidebar.")
    else:
        if mode == "Policy RAG":
            chosen = "rag"
        elif mode == "Agent":
            chosen = "agent"
        else:
            chosen = route(question)

        if chosen == "agent":
            with st.spinner("Agent is working (policy, then web search)..."):
                st.markdown(run_agent(question))
        else:
            with st.spinner("Searching the policy..."):
                st.text(ask(question))
