from langchain_core.vectorstores import VectorStore

from rag_engine.agents.state import AgentState
from rag_engine.rag.retriever import retrieve


def make_retrieval_agent(db: VectorStore, default_top_k: int):
    """Create retrieval agent that attaches a vector store with top_k value by default."""
    
    def retrieval_agent(state: AgentState) -> AgentState:
        """Find relevant documents, assemble context, and collect sources list."""
        top_k = int(state.get("top_k") or default_top_k)
        docs = retrieve(db, state["query"], k=top_k)
        context = "\n\n".join(doc.page_content for doc in docs)
        sources = sorted(
            {
                str(doc.metadata.get("source"))
                for doc in docs
                if doc.metadata.get("source")
            }
        )

        return {
            **state,
            "retrieved_docs": docs,
            "context": context,
            "sources": sources,
        }

    return retrieval_agent
