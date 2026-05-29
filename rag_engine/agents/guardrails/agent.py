from rag_engine.agents.state import AgentState


NO_CONTEXT_ANSWER = (
    "Mình chưa tìm thấy dữ liệu nội bộ đủ liên quan để trả lời chính xác. "
    "Bạn có thể hỏi rõ hơn về tên sản phẩm, nhu cầu, ngân sách hoặc thông số cần so sánh."
)


def no_context_guardrail_agent(state: AgentState) -> AgentState:
    """Answer with a default message when no relevant context is found."""
    return {**state, "answer": NO_CONTEXT_ANSWER, "error": "No retrieved context."}
