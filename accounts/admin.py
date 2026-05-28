from django.contrib import admin

from accounts.models import ChatConversation


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "created_at", "updated_at")
    search_fields = ("title", "user__username")
    list_filter = ("created_at", "updated_at")
