from django.urls import path

from chat.views import (
    chat_history,
    chat_history_detail,
    chat_history_clear,
    chat_message,
    chat_view,
)


urlpatterns = [
    path("", chat_view, name="home"),
    path("chat/", chat_view, name="chat-view"),
    path("message/", chat_message, name="chat-message"),
    path("history/", chat_history, name="chat-history"),
    path("history/clear/", chat_history_clear, name="chat-history-clear"),
    path("history/<str:chat_id>/", chat_history_detail, name="chat-history-detail"),
]
