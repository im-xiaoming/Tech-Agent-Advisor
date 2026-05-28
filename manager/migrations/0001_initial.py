from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("session_id", models.CharField(blank=True, default="", max_length=80)),
                ("query", models.TextField()),
                ("answer", models.TextField(blank=True, default="")),
                ("context_used", models.TextField(blank=True, default="")),
                ("retrieved_docs", models.JSONField(blank=True, default=list)),
                ("sources", models.JSONField(blank=True, default=list)),
                ("latency_ms", models.IntegerField(blank=True, null=True)),
                ("top_k", models.IntegerField(blank=True, null=True)),
                ("model_name", models.CharField(blank=True, default="", max_length=120)),
                ("error", models.TextField(blank=True, default="")),
                ("groundedness_score", models.FloatField(blank=True, null=True)),
                (
                    "hallucination_flag",
                    models.CharField(
                        choices=[
                            ("unchecked", "Chưa kiểm tra"),
                            ("ok", "OK"),
                            ("suspicious", "Nghi ngờ"),
                            ("confirmed", "Hallucination"),
                        ],
                        default="unchecked",
                        max_length=20,
                    ),
                ),
                ("reviewer_note", models.TextField(blank=True, default="")),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="chat_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["-created_at"], name="manager_cha_created_idx"),
                    models.Index(fields=["hallucination_flag"], name="manager_cha_hallu_idx"),
                ],
            },
        ),
    ]
