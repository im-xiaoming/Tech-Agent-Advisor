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


def _build_history_context(histories) -> str:
    """Build prompt history from old summarized turns plus recent raw turns."""
    if not histories:
        return ""

    if not isinstance(histories, list):
        return str(histories).strip()

    messages = [str(item).strip() for item in histories if str(item).strip()]
    if not messages:
        return ""

    try:
        from rag_engine.core.config import settings as rag_settings
        from rag_engine.core.llm import summarize_history
    except Exception:
        return "\n".join(messages).strip()

    recent_count = max(int(rag_settings.num_chats_retained), 0)
    old_messages = messages[:-recent_count*2] if recent_count else messages
    recent_messages = messages[-recent_count*2:] if recent_count else []

    parts = []
    if old_messages:
        old_history = "\n".join(old_messages)
        summary = summarize_history(old_history)
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
    history = _build_history_context(payload.get("history", ""))
    
    if not query:
        return JsonResponse({"error": "Field 'query' is required."}, status=400)

    session_id = str(payload.get("session_id") or payload.get("chat_id") or "")
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
        "createdAt": conversation.created_at.isoformat(),
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

        defaults = {
            "title": data["title"],
            "messages": data["messages"],
            "created_at": created_at or timezone.now(),
        }

        conversation, _ = ChatConversation.objects.update_or_create(
            user=request.user,
            client_id=data["client_id"],
            defaults=defaults,
        )
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
            "logout_url": reverse("logout"),
        },
    )
