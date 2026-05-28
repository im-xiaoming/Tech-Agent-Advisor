from rag_engine.agents.state import AgentState
from rag_engine.core.llm import generate_response, generate_response_stream
from rag_engine.core.prompt_loader import load_advisor_prompt, load_smalltalk_prompt


def _build_advisor_prompts(state: AgentState, extra_instructions: str = "") -> tuple[str, str]:
    system_prompt, user_prompt = load_advisor_prompt()
    user_prompt = user_prompt.format(
        context=state.get("context", ""),
        query=state["query"],
        history=state.get("history", ""),
        extra_instructions=extra_instructions,
    )
    return system_prompt, user_prompt


def advisor_agent(state: AgentState) -> AgentState:
    """Generate final answer for the user from prompt, context, and query."""
    system_prompt, user_prompt = _build_advisor_prompts(state)
    answer = generate_response(
        system_prompt,
        user_prompt,
        temperature=float(state.get("temperature", 0.1)),
    )
    return {**state, "answer": answer}


def stream_advisor_tokens(state: AgentState, extra_instructions: str = ""):
    """Yield answer tokens from the advisor LLM in real time.

    ``extra_instructions`` is appended into the user prompt — used by the
    regenerate-on-fail flow to add stricter guidance on a second attempt.
    """
    system_prompt, user_prompt = _build_advisor_prompts(state, extra_instructions)
    yield from generate_response_stream(
        system_prompt,
        user_prompt,
        temperature=float(state.get("temperature", 0.1)),
    )


def _build_smalltalk_prompts(state: AgentState) -> tuple[str, str]:
    system_prompt, user_prompt = load_smalltalk_prompt()
    user_prompt = user_prompt.format(
        query=state["query"],
        history=state.get("history", ""),
    )
    return system_prompt, user_prompt


def smalltalk_agent(state: AgentState) -> AgentState:
    """Generate final answer for the user from prompt, context, and query."""
    system_prompt, user_prompt = _build_smalltalk_prompts(state)
    answer = generate_response(
        system_prompt,
        user_prompt,
        temperature=float(state.get("temperature", 0.7)),
    )
    return {**state, "answer": answer, "sources": []}


def stream_smalltalk_tokens(state: AgentState):
    """Yield smalltalk tokens from the LLM in real time."""
    system_prompt, user_prompt = _build_smalltalk_prompts(state)
    yield from generate_response_stream(
        system_prompt,
        user_prompt,
        temperature=float(state.get("temperature", 0.7)),
    )
