from django.contrib import admin

from manager.models import ChatLog, SemanticCacheEntry


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


@admin.register(SemanticCacheEntry)
class SemanticCacheEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "last_hit_at",
        "short_question",
        "model_name",
        "hit_count",
        "similarity",
        "expires_at",
    )
    list_filter = ("model_name", "created_at", "expires_at")
    search_fields = ("question", "answer", "vector_point_id")
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_hit_at",
        "expires_at",
        "question",
        "answer",
        "sources",
        "filters",
        "model_name",
        "vector_point_id",
        "similarity",
        "hit_count",
    )
    fieldsets = (
        ("Meta", {"fields": ("created_at", "updated_at", "last_hit_at", "expires_at", "model_name")}),
        ("Cache", {"fields": ("question", "answer", "sources", "filters")}),
        ("Vector", {"fields": ("vector_point_id", "similarity", "hit_count")}),
    )

    @admin.display(description="Question")
    def short_question(self, obj):
        return (obj.question or "")[:80]
