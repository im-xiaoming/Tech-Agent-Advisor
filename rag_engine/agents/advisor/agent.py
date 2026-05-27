from rag_engine.agents.state import AgentState
from rag_engine.core.llm import generate_response
from rag_engine.core.prompt_loader import load_advisor_prompt, load_smalltalk_prompt


def advisor_agent(state: AgentState) -> AgentState:
    """Generate final answer for the user from prompt, context, and query."""
    
    system_prompt, user_prompt = load_advisor_prompt()
    user_prompt = user_prompt.format(
        context=state.get("context", ""),
        query=state["query"],
        history=state.get("history", ""),
    )

    answer = generate_response(system_prompt, user_prompt, temperature=float(state.get("temperature", 0.1)))
    return {**state, "answer": answer}


def smalltalk_agent(state: AgentState) -> AgentState:
    """Generate final answer for the user from prompt, context, and query."""
    
    system_prompt, user_prompt = load_smalltalk_prompt()
    user_prompt = user_prompt.format(
        query=state["query"],
        history=state.get("history", ""),
    )
    answer = generate_response(system_prompt, user_prompt, temperature=float(state.get("temperature", 0.5)))
    return {**state, "answer": answer, "sources": []}
