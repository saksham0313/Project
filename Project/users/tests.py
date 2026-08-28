import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

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
