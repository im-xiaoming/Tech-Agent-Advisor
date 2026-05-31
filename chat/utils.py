from django.utils import timezone

from accounts.models import ChatConversation


def _message_to_history_line(message: dict) -> str:
    """Chuyển một message dict thành một dòng history có nhãn người nói."""
    role = str(message.get("role") or "").strip().lower()
    speaker = "User" if role == "user" else "Assistant"
    content = str(message.get("content") or "").strip()
    return f"{speaker}: {content}" if content else ""


def _history_lines_from_messages(messages: list[dict]) -> list[str]:
    """Lọc và chuyển danh sách message dict thành các dòng history có nội dung."""
    return [
        line
        for line in (_message_to_history_line(message) for message in messages)
        if line
    ]


def _summary_window_size() -> int:
    """Lấy số message gần nhất cần giữ thô trước khi tóm tắt phần cũ hơn."""
    try:
        from rag_engine.core.config import settings as rag_settings

        return max(int(rag_settings.num_chats_retained), 0) * 2
    except Exception:
        return 10


def _history_max_length() -> int:
    """Lấy giới hạn độ dài history đưa vào prompt, dùng mặc định khi config lỗi."""
    try:
        from rag_engine.core.config import settings as rag_settings

        return max(int(rag_settings.max_length), 0)
    except Exception:
        return 2048


def _messages_text_length(messages: list[dict]) -> int:
    """Tính độ dài text của danh sách message sau khi format thành history."""
    return len("\n".join(_history_lines_from_messages(messages)))


def _lines_text_length(lines: list[str]) -> int:
    """Tính độ dài text của các dòng history đã format sẵn."""
    return len("\n".join(lines))


def _summary_cutoff_index(messages: list[dict]) -> int:
    """Tìm vị trí cắt message: phần trước sẽ được tóm tắt, phần sau giữ thô."""
    recent_window = _summary_window_size()
    cutoff = max(len(messages) - recent_window, 0) if recent_window else len(messages)
    max_length = _history_max_length()

    if max_length <= 0 or len(messages) <= 2:
        return cutoff

    max_cutoff = max(len(messages) - 2, cutoff)
    while cutoff < max_cutoff and _messages_text_length(messages[cutoff:]) > max_length:
        cutoff += 1
    return cutoff


def _summary_cutoff_for_lines(lines: list[str]) -> int:
    """Tìm vị trí cắt cho các dòng history đã format sẵn."""
    recent_window = _summary_window_size()
    cutoff = max(len(lines) - recent_window, 0) if recent_window else len(lines)
    max_length = _history_max_length()

    if max_length <= 0 or len(lines) <= 2:
        return cutoff

    max_cutoff = max(len(lines) - 2, cutoff)
    while cutoff < max_cutoff and _lines_text_length(lines[cutoff:]) > max_length:
        cutoff += 1
    return cutoff


def _build_stored_summary(messages: list[dict]) -> tuple[str, int] | None:
    """Tạo summary lưu DB cho phần message cũ và trả về số message đã tóm tắt."""
    cutoff = _summary_cutoff_index(messages)
    summary_messages = messages[:cutoff]
    if len(summary_messages) < 2:
        return "", 0

    lines = _history_lines_from_messages(summary_messages)
    if not lines:
        return "", 0

    try:
        from rag_engine.core.llm import summarize_history

        summary = summarize_history("\n".join(lines)).strip()
    except Exception:
        return None

    return summary, len(summary_messages)


def _maybe_update_conversation_summary(
    conversation: ChatConversation,
    messages: list[dict],
) -> list[str]:
    """Cập nhật summary trên conversation khi cần và trả về các field đã đổi."""
    summary_count = _summary_cutoff_index(messages)
    if summary_count == conversation.summary_message_count and conversation.summary:
        return []

    result = _build_stored_summary(messages)
    if result is None:
        return []

    summary, summarized_count = result
    conversation.summary = summary
    conversation.summary_message_count = summarized_count
    conversation.summary_updated_at = timezone.now() if summary else None
    return ["summary", "summary_message_count", "summary_updated_at"]


def _get_conversation_summary(user, session_id: str) -> tuple[str, int]:
    """Lấy summary đã lưu của conversation theo user và session client."""
    if not session_id:
        return "", 0
    try:
        conversation = ChatConversation.objects.only(
            "summary",
            "summary_message_count",
        ).get(user=user, client_id=session_id)
    except ChatConversation.DoesNotExist:
        return "", 0
    return conversation.summary, conversation.summary_message_count


def _build_history_context(
    histories,
    stored_summary: str = "",
    stored_summary_count: int = 0,
) -> str:
    """Dựng history prompt từ phần cũ đã tóm tắt và các lượt gần đây."""
    if not histories:
        return (
            f"Tóm tắt hội thoại trước đó:\n{stored_summary}".strip()
            if stored_summary
            else ""
        )

    if not isinstance(histories, list):
        return str(histories).strip()

    messages = [str(item).strip() for item in histories if str(item).strip()]
    if not messages:
        return ""

    cutoff = _summary_cutoff_for_lines(messages)
    old_messages = messages[:cutoff]
    recent_messages = messages[cutoff:]

    parts = []
    if stored_summary:
        stored_count = min(max(int(stored_summary_count or 0), 0), len(messages))
        if cutoff > stored_count:
            extra_old_messages = messages[stored_count:cutoff]
            try:
                from rag_engine.core.llm import summarize_history

                extra_summary = summarize_history("\n".join(extra_old_messages))
            except Exception:
                extra_summary = ""
            if extra_summary:
                stored_summary = f"{stored_summary}\n{extra_summary}".strip()
        recent_messages = messages[max(cutoff, stored_count):]
        parts.append(f"Tóm tắt hội thoại trước đó:\n{stored_summary}")
    elif old_messages:
        old_history = "\n".join(old_messages)
        try:
            from rag_engine.core.llm import summarize_history

            summary = summarize_history(old_history)
        except Exception:
            summary = ""
        if summary:
            parts.append(f"Tóm tắt hội thoại trước đó:\n{summary}")

    if recent_messages:
        parts.append("Các lượt gần đây:\n" + "\n".join(recent_messages))

    return "\n\n".join(parts).strip()


def _normalize_chat_payload(item):
    """Chuẩn hóa payload một chat từ client trước khi lưu vào database."""
    messages = item.get("messages", [])
    if not isinstance(messages, list):
        messages = []

    return {
        "client_id": str(item.get("id") or item.get("client_id") or "").strip(),
        "title": str(item.get("title") or "Untitled chat").strip()[:255],
        "messages": messages,
        "created_at": str(item.get("createdAt") or item.get("created_at") or "").strip(),
    }


def _conversation_to_dict(conversation):
    """Serialize ChatConversation thành dict trả về cho chat history API."""
    return {
        "id": conversation.client_id,
        "title": conversation.title,
        "messages": conversation.messages or [],
        "summary": conversation.summary,
        "summaryMessageCount": conversation.summary_message_count,
        "summaryUpdatedAt": (
            conversation.summary_updated_at.isoformat()
            if conversation.summary_updated_at
            else ""
        ),
        "createdAt": conversation.created_at.isoformat(),
        "updatedAt": conversation.updated_at.isoformat(),
    }
