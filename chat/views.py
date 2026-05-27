import json

from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from chat.services import stream_chat
from rag_engine.core.config import settings
from rag_engine.core.llm import summarize_history


def _build_history_context(histories) -> str:
    """Build prompt history from old summarized turns plus recent raw turns."""
    if not histories:
        return ""

    if not isinstance(histories, list):
        return str(histories).strip()

    messages = [str(item).strip() for item in histories if str(item).strip()]
    if not messages:
        return ""

    recent_count = max(int(settings.num_chats_retained), 0)
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

    response = StreamingHttpResponse(
        stream_chat(query, history=history),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def chat_view(request):
    return render(
        request,
        "chat/chat.html",
        {
            "chat_api_url": reverse("chat-message"),
        },
    )
