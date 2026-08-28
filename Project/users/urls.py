from django.urls import path
from django.views.generic import RedirectView

from . import views


urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url="/static/users/favicon.svg", permanent=False), name="favicon"),
    path("", views.landing_page, name="home"),
    path("settings/", views.settings_page, name="settings"),
    path("register/", views.register, name="register"),
    path("login/", views.user_login, name="login"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("forgot-password/verify/", views.verify_password_otp, name="verify_password_otp"),
    path("forgot-password/resend/", views.resend_password_otp, name="resend_password_otp"),
    path("forgot-password/new/", views.password_reset_new, name="password_reset_new"),
    path("logout/", views.user_logout, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("career-guidance/", views.career_guidance_page, name="career_guidance"),
    path("upload/", views.upload_resume, name="upload_resume"),
    path("ai-interview/", views.ai_interview_page, name="ai_interview"),
    path("interview/<int:session_id>/report/", views.interview_report, name="interview_report"),
    path("interview/<int:session_id>/report.pdf", views.interview_report_pdf, name="interview_report_pdf"),
    path("api/interview/start/", views.interview_start_api, name="interview_start_api"),
    path("api/interview/answer/", views.interview_answer_api, name="interview_answer_api"),
    path("api/interview/finish/", views.interview_finish_api, name="interview_finish_api"),
    path("api/interview/history/", views.interview_history_api, name="interview_history_api"),
]
