from django.contrib import admin

# Register your models here.

from django.contrib import admin
from .models import (
    InterviewAnswer,
    InterviewFeedback,
    InterviewQuestion,
    InterviewSession,
    Resume,
    Student,
    UserSettings,
)


admin.site.register(Student)

admin.site.register(Resume)
admin.site.register(UserSettings)
admin.site.register(InterviewSession)
admin.site.register(InterviewQuestion)
admin.site.register(InterviewAnswer)
admin.site.register(InterviewFeedback)
