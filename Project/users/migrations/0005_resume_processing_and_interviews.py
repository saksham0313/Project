import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_student_course_alter_student_skills"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="resume",
            name="parse_error",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="resume",
            name="parse_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("complete", "Complete"),
                    ("failed", "Failed"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="resume",
            name="parsed_profile",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="resume",
            name="raw_text",
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name="InterviewSession",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("role", models.CharField(max_length=100)),
                ("difficulty", models.CharField(default="medium", max_length=20)),
                ("interview_type", models.CharField(default="general", max_length=30)),
                ("status", models.CharField(default="in_progress", max_length=20)),
                ("question_count", models.PositiveSmallIntegerField(default=5)),
                ("overall_score", models.FloatField(blank=True, null=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "resume",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="interviews",
                        to="users.resume",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.CreateModel(
            name="InterviewQuestion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order", models.PositiveSmallIntegerField()),
                ("question_text", models.TextField()),
                ("category", models.CharField(default="General", max_length=50)),
                ("source", models.CharField(default="fallback", max_length=30)),
                ("source_evidence", models.CharField(blank=True, max_length=255)),
                ("expected_topics", models.JSONField(blank=True, default=list)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="questions",
                        to="users.interviewsession",
                    ),
                ),
            ],
            options={"ordering": ["order"]},
        ),
        migrations.CreateModel(
            name="InterviewAnswer",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("answer_text", models.TextField(blank=True)),
                ("duration_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("technical_score", models.FloatField(default=0)),
                ("relevance_score", models.FloatField(default=0)),
                ("communication_score", models.FloatField(default=0)),
                ("overall_score", models.FloatField(default=0)),
                ("filler_count", models.PositiveIntegerField(default=0)),
                ("feedback", models.JSONField(blank=True, default=dict)),
                ("submitted_at", models.DateTimeField(auto_now=True)),
                (
                    "question",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="answer",
                        to="users.interviewquestion",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="InterviewFeedback",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("strengths", models.JSONField(blank=True, default=list)),
                ("weaknesses", models.JSONField(blank=True, default=list)),
                ("recommendations", models.JSONField(blank=True, default=list)),
                ("generated_by", models.CharField(default="local", max_length=20)),
                ("created_at", models.DateTimeField(auto_now=True)),
                (
                    "session",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="feedback",
                        to="users.interviewsession",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="interviewquestion",
            constraint=models.UniqueConstraint(
                fields=("session", "order"),
                name="unique_question_order_per_session",
            ),
        ),
    ]
