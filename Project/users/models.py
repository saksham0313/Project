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

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )


    def __str__(self):
        return self.user.username

    