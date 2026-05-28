from langgraph.graph import END, StateGraph

from rag_engine.agents.advisor.agent import advisor_agent, smalltalk_agent
from rag_engine.agents.guardrails.agent import no_context_guardrail_agent
from rag_engine.agents.retrieval.agent import make_retrieval_agent
from rag_engine.agents.state import AgentState
from rag_engine.agents.supervisor.agent import supervisor_agent
from rag_engine.core.config import settings


def _route_after_supervisor(state: AgentState) -> str:
    """Choose next step after supervisor based on route in state."""
    route = state.get("route")
    if route == "product_advice":
        return "retrieval"
    if route == "smalltalk":
        return "smalltalk"
    return "end"


def _route_after_retrieval(state: AgentState) -> str:
    """Choose next step after retrieval based on retrieved documents."""
    return "advisor" if state.get("retrieved_docs") else "no_context_guardrails"


def build_chat_graph(db, top_k: int | None = None):
    """Build the chat graph including supervisor, retrieval, advisor and guardrails.

    Args:
        db: VectorStore instance for retrieval agent.
        top_k: Optional default top_k for retrieval agent, overrides config if provided.

    Returns:
        Compiled StateGraph instance representing the multi-agent workflow.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_agent)
    workflow.add_node("retrieval", make_retrieval_agent(db, top_k or settings.rag_top_k))
    workflow.add_node("advisor", advisor_agent)
    workflow.add_node("smalltalk", smalltalk_agent)
    workflow.add_node("no_context_guardrails", no_context_guardrail_agent)

    workflow.set_entry_point("supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {"retrieval": "retrieval", "smalltalk": "smalltalk", "end": END},
    )
    workflow.add_conditional_edges(
        "retrieval",
        _route_after_retrieval,
        {"advisor": "advisor", "no_context_guardrails": "no_context_guardrails"},
    )
    workflow.add_edge("advisor", END)
    workflow.add_edge("smalltalk", END)
    workflow.add_edge("no_context_guardrails", END)

    return workflow.compile()
