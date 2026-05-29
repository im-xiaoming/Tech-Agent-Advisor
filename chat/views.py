import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import ChatConversation
from chat.services import stream_chat


def _message_to_history_line(message: dict) -> str:
    role = str(message.get("role") or "").strip().lower()
    speaker = "User" if role == "user" else "Assistant"
    content = str(message.get("content") or "").strip()
    return f"{speaker}: {content}" if content else ""


def _history_lines_from_messages(messages: list[dict]) -> list[str]:
    return [
        line
        for line in (_message_to_history_line(message) for message in messages)
        if line
    ]


def _summary_window_size() -> int:
    try:
        from rag_engine.core.config import settings as rag_settings

        return max(int(rag_settings.num_chats_retained), 0) * 2
    except Exception:
        return 10


def _history_max_length() -> int:
    try:
        from rag_engine.core.config import settings as rag_settings

        return max(int(rag_settings.max_length), 0)
    except Exception:
        return 2048


def _messages_text_length(messages: list[dict]) -> int:
    return len("\n".join(_history_lines_from_messages(messages)))


def _lines_text_length(lines: list[str]) -> int:
    return len("\n".join(lines))


def _summary_cutoff_index(messages: list[dict]) -> int:
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


def _maybe_update_conversation_summary(conversation: ChatConversation, messages: list[dict]) -> list[str]:
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


def _build_history_context(histories, stored_summary: str = "", stored_summary_count: int = 0) -> str:
    """Build prompt history from old summarized turns + recent raw turns."""
    if not histories:
        return f"Tóm tắt hội thoại trước đó:\n{stored_summary}".strip() if stored_summary else ""

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


def home_view(request):
    return JsonResponse(
        {
            "service": "Tech Chatbot RAG Multi-Agent",
            "status": "ok",
            "routes": {
                "chat_page": "/chat/",
                "chat_api": "/chat/message/",
                "admin": "/admin/",
            },
        }
    )


@csrf_exempt
@login_required
@require_POST
def chat_message(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    query = str(payload.get("query", "")).strip()
    session_id = str(payload.get("session_id") or payload.get("chat_id") or "")
    stored_summary, stored_summary_count = _get_conversation_summary(request.user, session_id)
    history = _build_history_context(
        payload.get("history", ""),
        stored_summary=stored_summary,
        stored_summary_count=stored_summary_count,
    )
    
    if not query:
        return JsonResponse({"error": "Field 'query' is required."}, status=400)

    response = StreamingHttpResponse(
        stream_chat(query, history=history, user=request.user, session_id=session_id),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def _normalize_chat_payload(item):
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
    return {
        "id": conversation.client_id,
        "title": conversation.title,
        "messages": conversation.messages or [],
        "summary": conversation.summary,
        "summaryMessageCount": conversation.summary_message_count,
        "summaryUpdatedAt": conversation.summary_updated_at.isoformat() if conversation.summary_updated_at else "",
        "createdAt": conversation.created_at.isoformat(),
        "updatedAt": conversation.updated_at.isoformat(),
    }


@login_required
@require_http_methods(["GET", "POST"])
def chat_history(request):
    if request.method == "GET":
        conversations = ChatConversation.objects.filter(user=request.user)
        return JsonResponse({"chats": [_conversation_to_dict(item) for item in conversations]})

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    items = payload.get("chats", [])
    if not isinstance(items, list):
        return JsonResponse({"error": "Field 'chats' must be a list."}, status=400)

    saved = 0
    for item in items:
        if not isinstance(item, dict):
            continue

        data = _normalize_chat_payload(item)
        if not data["client_id"]:
            continue

        created_at = parse_datetime(data["created_at"]) if data["created_at"] else None
        if created_at and timezone.is_naive(created_at):
            created_at = timezone.make_aware(created_at)

        try:
            conversation = ChatConversation.objects.get(
                user=request.user,
                client_id=data["client_id"],
            )
            changed_fields = []
            if conversation.title != data["title"]:
                conversation.title = data["title"]
                changed_fields.append("title")
            if conversation.messages != data["messages"]:
                conversation.messages = data["messages"]
                changed_fields.append("messages")
                changed_fields.extend(_maybe_update_conversation_summary(conversation, data["messages"]))
            if created_at and conversation.created_at != created_at:
                conversation.created_at = created_at
                changed_fields.append("created_at")
            if changed_fields:
                conversation.save(update_fields=[*changed_fields, "updated_at"])
        except ChatConversation.DoesNotExist:
            conversation = ChatConversation(
                user=request.user,
                client_id=data["client_id"],
                title=data["title"],
                messages=data["messages"],
                created_at=created_at or timezone.now(),
            )
            _maybe_update_conversation_summary(conversation, data["messages"])
            conversation.save()
        saved += 1

    return JsonResponse({"saved": saved})


@login_required
@require_http_methods(["DELETE"])
def chat_history_detail(request, chat_id):
    conversation = get_object_or_404(
        ChatConversation,
        user=request.user,
        client_id=chat_id,
    )
    conversation.delete()
    return JsonResponse({"deleted": True})


@login_required
@require_POST
def chat_history_clear(request):
    deleted, _ = ChatConversation.objects.filter(user=request.user).delete()
    return JsonResponse({"deleted": deleted})


@login_required
def chat_view(request):
    return render(
        request,
        "chat/chat.html",
        {
            "chat_api_url": reverse("chat-message"),
            "chat_history_url": reverse("chat-history"),
            "chat_history_clear_url": reverse("chat-history-clear"),
            "landing_url": reverse("landing"),
            "admin_url": reverse("admin:index"),
            "manager_config_url": reverse("manager-config"),
            "manager_data_url": reverse("manager-product-data"),
            "manager_logs_url": reverse("manager-log-list"),
            "logout_url": reverse("logout"),
        },
    )
