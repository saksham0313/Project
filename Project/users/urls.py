from django.urls import path

from . import views


urlpatterns = [
    path("", views.user_login, name="home"),
    path("settings/", views.settings_page, name="settings"),
    path("register/", views.register, name="register"),
    path("login/", views.user_login, name="login"),
    path("logout/", views.user_logout, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("career-guidance/", views.career_guidance_page, name="career_guidance"),
    path("upload/", views.upload_resume, name="upload_resume"),
    path("ai-interview/", views.ai_interview_page, name="ai_interview"),
    path("api/interview/start/", views.interview_start_api, name="interview_start_api"),
    path("api/interview/answer/", views.interview_answer_api, name="interview_answer_api"),
    path("api/interview/finish/", views.interview_finish_api, name="interview_finish_api"),
    path("api/interview/history/", views.interview_history_api, name="interview_history_api"),
]
