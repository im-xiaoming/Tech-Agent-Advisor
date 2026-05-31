from django.conf import settings
from django.db import models


class ChatLog(models.Model):
    FLAG_UNCHECKED = "unchecked"
    FLAG_OK = "ok"
    FLAG_SUSPICIOUS = "suspicious"
    FLAG_CONFIRMED = "confirmed"
    FLAG_CHOICES = [
        (FLAG_UNCHECKED, "Chưa kiểm tra"),
        (FLAG_OK, "OK"),
        (FLAG_SUSPICIOUS, "Nghi ngờ"),
        (FLAG_CONFIRMED, "Hallucination"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=80, blank=True, default="")

    query = models.TextField()
    answer = models.TextField(blank=True, default="")
    context_used = models.TextField(blank=True, default="")
    retrieved_docs = models.JSONField(default=list, blank=True)
    sources = models.JSONField(default=list, blank=True)

    latency_ms = models.IntegerField(null=True, blank=True)
    top_k = models.IntegerField(null=True, blank=True)
    model_name = models.CharField(max_length=120, blank=True, default="")
    error = models.TextField(blank=True, default="")

    groundedness_score = models.FloatField(null=True, blank=True)
    hallucination_flag = models.CharField(
        max_length=20,
        choices=FLAG_CHOICES,
        default=FLAG_UNCHECKED,
    )
    reviewer_note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["hallucination_flag"]),
        ]

    def __str__(self):
        return f"#{self.pk} {self.query[:60]}"


class SemanticCacheEntry(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_hit_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    question = models.TextField()
    answer = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    model_name = models.CharField(max_length=120, blank=True, default="")

    vector_point_id = models.CharField(max_length=80, blank=True, default="")
    similarity = models.FloatField(null=True, blank=True)
    hit_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"], name="manager_sem_created_1ef41d_idx"),
            models.Index(fields=["expires_at"], name="manager_sem_expires_6fbb51_idx"),
            models.Index(fields=["model_name"], name="manager_sem_model_n_27a822_idx"),
        ]

    def __str__(self):
        return f"#{self.pk} {self.question[:60]}"
