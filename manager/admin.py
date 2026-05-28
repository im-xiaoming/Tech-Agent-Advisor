from django.contrib import admin

from manager.models import ChatLog


@admin.register(ChatLog)
class ChatLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "user",
        "short_query",
        "groundedness_score",
        "hallucination_flag",
        "latency_ms",
    )
    list_filter = ("hallucination_flag", "model_name", "created_at")
    search_fields = ("query", "answer", "user__username")
    readonly_fields = (
        "created_at",
        "user",
        "session_id",
        "query",
        "answer",
        "context_used",
        "retrieved_docs",
        "sources",
        "latency_ms",
        "top_k",
        "model_name",
        "error",
        "groundedness_score",
    )
    fieldsets = (
        ("Meta", {"fields": ("created_at", "user", "session_id", "latency_ms", "top_k", "model_name")}),
        ("Conversation", {"fields": ("query", "answer", "context_used", "sources", "retrieved_docs")}),
        ("Review", {"fields": ("groundedness_score", "hallucination_flag", "reviewer_note", "error")}),
    )

    @admin.display(description="Query")
    def short_query(self, obj):
        return (obj.query or "")[:80]
