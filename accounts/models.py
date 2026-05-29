from django.conf import settings
from django.db import models


class ChatConversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_conversations",
    )
    client_id = models.CharField(max_length=80)
    title = models.CharField(max_length=255)
    messages = models.JSONField(default=list, blank=True)
    summary = models.TextField(blank=True, default="")
    summary_message_count = models.PositiveIntegerField(default=0)
    summary_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "client_id"],
                name="unique_user_chat_conversation",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.title}"
