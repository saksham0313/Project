import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import InterviewAnswer, InterviewSession, Resume
from .resume_services import build_local_profile


class ResumeInterviewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="candidate",
            password="StrongPass123!",
        )
        self.client.force_login(self.user)

    def test_anonymous_dashboard_redirects_to_login(self):
        self.client.logout()
        response = self.client.get("/dashboard/")
        self.assertRedirects(response, "/login/?next=/dashboard/")

    def test_upload_rejects_non_pdf(self):
        response = self.client.post(
            "/upload/",
            {"resume": SimpleUploadedFile("resume.docx", b"not a pdf")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only PDF resumes are supported")
        self.assertEqual(Resume.objects.count(), 0)

    @patch("users.views.extract_resume_text")
    def test_upload_builds_local_profile(self, extract):
        extract.return_value = (
            "Education\nDiploma Computer Engineering\n"
            "Skills\nPython, Django, MySQL\n"
            "Projects\nAI Interview Simulator - Django project"
        )
        response = self.client.post(
            "/upload/",
            {
                "resume": SimpleUploadedFile(
                    "resume.pdf",
                    b"%PDF-1.4 fake test payload",
                    content_type="application/pdf",
                )
            },
        )
        self.assertEqual(response.status_code, 200)
        resume = Resume.objects.get(user=self.user)
        self.assertEqual(resume.parse_status, "complete")
        self.assertIn("Django", resume.parsed_profile["skills"])
        self.assertContains(response, "Local resume analysis ready")

    def test_offline_interview_saves_answer_and_report(self):
        raw_text = (
            "Education\nDiploma Computer Engineering\n"
            "Skills\nPython, Django, MySQL\n"
            "Projects\nAI Interview Simulator - Django project"
        )
        resume = Resume.objects.create(
            user=self.user,
            resume_file=SimpleUploadedFile("resume.pdf", b"%PDF-1.4"),
            raw_text=raw_text,
            parsed_profile=build_local_profile(raw_text),
            parse_status="complete",
        )
        response = self.client.post(
            "/api/interview/start/",
            data=json.dumps(
                {
                    "role": "Software Developer",
                    "difficulty": "medium",
                    "interview_type": "general",
                    "count": 5,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["generated_by"], "local")
        self.assertGreaterEqual(len(payload["questions"]), 1)

        question_id = payload["questions"][0]["id"]
        answer_response = self.client.post(
            "/api/interview/answer/",
            data=json.dumps(
                {
                    "question_id": question_id,
                    "answer": "I used Django and Python to build the project and implemented authentication.",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(answer_response.status_code, 200)
        self.assertEqual(InterviewAnswer.objects.count(), 1)

        finish_response = self.client.post(
            "/api/interview/finish/",
            data=json.dumps({"session_id": payload["session_id"]}),
            content_type="application/json",
        )
        self.assertEqual(finish_response.status_code, 200)
        session = InterviewSession.objects.get(pk=payload["session_id"])
        self.assertEqual(session.status, "completed")
        self.assertIsNotNone(session.overall_score)


class PasswordResetTests(TestCase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    @patch("users.views.secrets.randbelow", return_value=123456)
    def test_valid_otp_persists_new_password_and_rejects_old_password(self, _randbelow):
        user = User.objects.create_user(
            username="reset-candidate",
            email="reset-candidate@example.com",
            password="OldStrongPass123!",
        )
        already_logged_in = self.client.__class__()
        already_logged_in.force_login(user)

        response = self.client.post("/forgot-password/", {"email": user.email})
        self.assertRedirects(response, "/forgot-password/verify/")
        response = self.client.post("/forgot-password/verify/", {"otp": "123456"})
        self.assertRedirects(response, "/forgot-password/new/")
        response = self.client.post(
            "/forgot-password/new/",
            {
                "password": "NewStrongPass123!X",
                "confirm_password": "NewStrongPass123!X",
            },
        )
        self.assertRedirects(response, "/login/")

        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPass123!X"))
        self.assertFalse(user.check_password("OldStrongPass123!"))

        old_password_response = self.client.post(
            "/login/",
            {"username": user.username, "password": "OldStrongPass123!"},
        )
        self.assertEqual(old_password_response.status_code, 200)
        self.assertContains(old_password_response, "Invalid username or password.")

        new_password_response = self.client.post(
            "/login/",
            {"username": user.username, "password": "NewStrongPass123!X"},
        )
        self.assertRedirects(new_password_response, "/dashboard/")

        # A session that was open before recovery is also invalidated.
        stale_session_response = already_logged_in.get("/dashboard/")
        self.assertRedirects(stale_session_response, "/login/?next=/dashboard/")

    def test_performance_is_private_and_dashboard_links_to_it(self):
        other_user = User.objects.create_user(
            username="other-candidate",
            password="OtherStrongPass123!",
        )
        InterviewSession.objects.create(
            user=other_user,
            role="Private role",
            status="completed",
            question_count=15,
            overall_score=99,
        )
        self.client.force_login(
            User.objects.create_user(
                username="performance-candidate",
                password="PerformanceStrongPass123!",
            )
        )
        dashboard = self.client.get("/dashboard/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, 'href="/performance/"')
        performance = self.client.get("/performance/")
        self.assertEqual(performance.status_code, 200)
        self.assertContains(performance, "No completed interviews yet")
        self.assertNotContains(performance, "Private role")

    def test_unknown_reset_email_uses_neutral_response(self):
        response = self.client.post(
            "/forgot-password/",
            {"email": "does-not-exist@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "If an active CareerAI account matches this email")
        self.assertNotContains(response, "No active account was found")
        self.assertNotIn("password_reset_otp_hash", self.client.session)

    def test_registration_requires_an_unambiguous_email(self):
        response = self.client.post(
            "/register/",
            {"username": "missing-email", "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")

    def test_malformed_login_post_does_not_raise_server_error(self):
        response = self.client.post("/login/", {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password.")
