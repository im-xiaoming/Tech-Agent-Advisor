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
from chat.utils import (
    _build_history_context,
    _conversation_to_dict,
    _get_conversation_summary,
    _maybe_update_conversation_summary,
    _normalize_chat_payload,
)


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
    stored_summary, stored_summary_count = _get_conversation_summary(
        request.user,
        session_id,
    )
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
                changed_fields.extend(
                    _maybe_update_conversation_summary(conversation, data["messages"])
                )
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
