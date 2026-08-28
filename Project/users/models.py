from django.db import models
from django.contrib.auth.models import User


class UserSettings(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="settings"
    )

    career_notifications = models.BooleanField(default=True)
    resume_notifications = models.BooleanField(default=True)
    job_notifications = models.BooleanField(default=False)

    theme = models.CharField(
        max_length=10,
        choices=[
            ("light", "Light"),
            ("dark", "Dark"),
            ("system", "System Default"),
        ],
        default="light"
    )

    profile_visibility = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} Settings"

class Student(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    full_name = models.CharField(
        max_length=100
    )

    college = models.CharField(
        max_length=100
    )

    course = models.CharField(
        max_length=100,
        blank=True
    )

    cgpa = models.FloatField(
        default=0
    )

    skills = models.TextField(
        blank=True
    )

    def __str__(self):
        return self.full_name



class Resume(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    resume_file = models.FileField(
        upload_to="resumes/"
    )

    # Extracted locally with pypdf and optionally enriched by the configured
    # AI provider. Keeping this data avoids sending the PDF on every request.
    raw_text = models.TextField(blank=True)
    parsed_profile = models.JSONField(default=dict, blank=True)
    parse_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("complete", "Complete"),
            ("failed", "Failed"),
        ],
        default="pending",
    )
    parse_error = models.CharField(max_length=255, blank=True)

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )


    def __str__(self):
        return self.user.username


class InterviewSession(models.Model):
    """One practice interview linked to the resume used as evidence."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="interviews")
    resume = models.ForeignKey(
        Resume,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interviews",
    )
    role = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=20, default="medium")
    interview_type = models.CharField(max_length=30, default="general")
    status = models.CharField(max_length=20, default="in_progress")
    question_count = models.PositiveSmallIntegerField(default=5)
    overall_score = models.FloatField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user.username} - {self.role} ({self.started_at:%Y-%m-%d})"


class InterviewQuestion(models.Model):
    session = models.ForeignKey(
        InterviewSession,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    order = models.PositiveSmallIntegerField()
    question_text = models.TextField()
    category = models.CharField(max_length=50, default="General")
    source = models.CharField(max_length=30, default="fallback")
    source_evidence = models.CharField(max_length=255, blank=True)
    expected_topics = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "order"],
                name="unique_question_order_per_session",
            )
        ]

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:60]}"


class InterviewAnswer(models.Model):
    question = models.OneToOneField(
        InterviewQuestion,
        on_delete=models.CASCADE,
        related_name="answer",
    )
    answer_text = models.TextField(blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    technical_score = models.FloatField(default=0)
    relevance_score = models.FloatField(default=0)
    communication_score = models.FloatField(default=0)
    overall_score = models.FloatField(default=0)
    filler_count = models.PositiveIntegerField(default=0)
    feedback = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Answer for {self.question_id} ({self.overall_score:.1f})"


class InterviewFeedback(models.Model):
    session = models.OneToOneField(
        InterviewSession,
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    strengths = models.JSONField(default=list, blank=True)
    weaknesses = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    # Stored once when an interview is completed so the report page and PDF
    # always show the same professional bilingual answer key.
    professional_answers = models.JSONField(default=list, blank=True)
    generated_by = models.CharField(max_length=20, default="local")
    created_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Feedback for interview {self.session_id}"

