from django.db import models


class RagEvaluation(models.Model):
    """One RAGAS evaluation of a single chat answer.

    Rows are created in ``pending`` state and scored by a background daemon
    thread (see :mod:`evaluation.services`) so the chat response is never
    blocked. Metric values are in the 0–1 range; ``None`` means the metric was
    skipped (e.g. ``context_recall`` needs a ``ground_truth`` reference) or it
    failed individually.
    """

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Chờ xử lý"),
        (STATUS_RUNNING, "Đang chạy"),
        (STATUS_DONE, "Hoàn tất"),
        (STATUS_FAILED, "Lỗi"),
    ]

    chat_log = models.ForeignKey(
        "manager.ChatLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # Evaluation inputs (snapshotted so re-runs are reproducible).
    question = models.TextField()
    answer = models.TextField(blank=True, default="")
    contexts = models.JSONField(default=list, blank=True)
    # Optional gold reference; enables the context_recall metric.
    ground_truth = models.TextField(blank=True, default="")

    model_name = models.CharField(max_length=120, blank=True, default="")

    # RAGAS metric scores (0–1).
    faithfulness = models.FloatField(null=True, blank=True)
    answer_relevancy = models.FloatField(null=True, blank=True)
    context_precision = models.FloatField(null=True, blank=True)
    context_recall = models.FloatField(null=True, blank=True)

    latency_ms = models.IntegerField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Eval #{self.pk} ({self.status})"

    @property
    def average_score(self):
        """Mean of the available metric scores, or ``None`` when none ran."""
        values = [
            value
            for value in (
                self.faithfulness,
                self.answer_relevancy,
                self.context_precision,
                self.context_recall,
            )
            if value is not None
        ]
        return sum(values) / len(values) if values else None
