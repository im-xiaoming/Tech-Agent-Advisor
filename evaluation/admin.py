from django.contrib import admin
from django.utils.html import format_html

from evaluation.models import RagEvaluation
from evaluation.services import run_evaluation_async


def _fmt(value):
    return f"{value:.3f}" if value is not None else "—"


@admin.register(RagEvaluation)
class RagEvaluationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "status",
        "short_question",
        "faithfulness_display",
        "answer_relevancy_display",
        "context_precision_display",
        "context_recall_display",
        "average_display",
        "model_name",
    )
    list_filter = ("status", "model_name", "created_at")
    search_fields = ("question", "answer", "ground_truth")
    date_hierarchy = "created_at"
    list_select_related = ("chat_log",)
    actions = ["rerun_evaluation"]

    # ground_truth stays editable so reviewers can add a gold reference and
    # re-run to unlock the context_recall metric.
    readonly_fields = (
        "created_at",
        "updated_at",
        "chat_log",
        "status",
        "question",
        "answer",
        "contexts",
        "model_name",
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "average_display",
        "latency_ms",
        "error",
    )
    fieldsets = (
        ("Meta", {"fields": ("created_at", "updated_at", "chat_log", "status", "model_name", "latency_ms")}),
        ("Sample", {"fields": ("question", "answer", "contexts", "ground_truth")}),
        (
            "Scores",
            {
                "fields": (
                    "faithfulness",
                    "answer_relevancy",
                    "context_precision",
                    "context_recall",
                    "average_display",
                    "error",
                )
            },
        ),
    )

    @admin.display(description="Question")
    def short_question(self, obj):
        return (obj.question or "")[:70]

    @admin.display(description="Faithfulness", ordering="faithfulness")
    def faithfulness_display(self, obj):
        return _fmt(obj.faithfulness)

    @admin.display(description="Answer rel.", ordering="answer_relevancy")
    def answer_relevancy_display(self, obj):
        return _fmt(obj.answer_relevancy)

    @admin.display(description="Ctx prec.", ordering="context_precision")
    def context_precision_display(self, obj):
        return _fmt(obj.context_precision)

    @admin.display(description="Ctx recall", ordering="context_recall")
    def context_recall_display(self, obj):
        return _fmt(obj.context_recall)

    @admin.display(description="Avg")
    def average_display(self, obj):
        avg = obj.average_score
        if avg is None:
            return "—"
        color = "#16a34a" if avg >= 0.7 else "#d97706" if avg >= 0.4 else "#dc2626"
        return format_html('<b style="color:{}">{}</b>', color, f"{avg:.3f}")

    @admin.action(description="Chạy lại đánh giá (luồng nền)")
    def rerun_evaluation(self, request, queryset):
        count = 0
        for evaluation in queryset:
            run_evaluation_async(evaluation.pk)
            count += 1
        self.message_user(request, f"Đã khởi chạy lại {count} đánh giá ở luồng nền.")
