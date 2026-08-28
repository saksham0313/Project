import json
import os
import secrets
import time

from django.shortcuts import render, redirect

from django.contrib.auth.models import User

from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password

from .forms import RegisterForm

from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from django.shortcuts import render, redirect

from django.conf import settings

from .models import (
    InterviewAnswer,
    InterviewFeedback,
    InterviewQuestion,
    InterviewSession,
    Resume,
    Student,
    UserSettings,
)
from .pdf_reports import build_interview_report_pdf
from .resume_services import (
    ResumeProcessingError,
    build_local_profile,
    evaluate_answer,
    feedback_from_answers,
    generate_career_guidance,
    generate_interview_feedback,
    generate_professional_answers,
    generate_questions,
    extract_resume_text,
)


def landing_page(request):
    """Public first page explaining CareerAI before authentication."""

    return render(request, "users/index.html")



@login_required
def settings_page(request):

    # Get or create settings for this user
    user_settings, created = UserSettings.objects.get_or_create(
        user=request.user
    )

    # Get or create student profile
    student, created = Student.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.get_full_name() or request.user.username,
            "college": "",
            "course": "",
            "cgpa": 0,
            "skills": "",
        }
    )

    # =========================
    # SAVE SETTINGS
    # =========================

    if request.method == "POST":

        # -------------------------
        # Profile
        # -------------------------

        full_name = request.POST.get(
            "full_name",
            ""
        ).strip()

        college = request.POST.get(
            "college",
            ""
        ).strip()

        course = request.POST.get(
            "course",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip()


        # Save profile information
        student.full_name = full_name
        student.college = college
        student.course = course
        student.save()


        # Save email
        request.user.email = email
        request.user.save()


        # -------------------------
        # Notifications
        # -------------------------

        user_settings.career_notifications = (
            "career_notifications" in request.POST
        )

        user_settings.resume_notifications = (
            "resume_notifications" in request.POST
        )

        user_settings.job_notifications = (
            "job_notifications" in request.POST
        )


        # -------------------------
        # Theme
        # -------------------------

        user_settings.theme = request.POST.get(
            "theme",
            "light"
        )


        # -------------------------
        # Privacy
        # -------------------------

        user_settings.profile_visibility = (
            "profile_visibility" in request.POST
        )


        # Save UserSettings
        user_settings.save()


        # Return to settings page
        return redirect("settings")


    # =========================
    # DISPLAY SETTINGS PAGE
    # =========================

    return render(
        request,
        "users/settings.html",
        {
            "user_settings": user_settings,
            "student": student,
        }
    )


@login_required
def upload_resume(request):

    user_settings, created = UserSettings.objects.get_or_create(
        user=request.user
    )

    if request.method == "POST":

        resume = request.FILES.get("resume")

        if not resume:
            return render(
                request,
                "users/upload_resume.html",
                {
                    "user_settings": user_settings,
                    "error": "Please select a resume file first."
                }
            )

        extension = os.path.splitext(resume.name or "")[1].lower()
        if extension != ".pdf":
            return render(
                request,
                "users/upload_resume.html",
                {"user_settings": user_settings, "error": "Only PDF resumes are supported."},
            )

        max_size = getattr(settings, "RESUME_MAX_SIZE", 10 * 1024 * 1024)
        if resume.size > max_size:
            return render(
                request,
                "users/upload_resume.html",
                {
                    "user_settings": user_settings,
                    "error": f"Resume must be smaller than {max_size // (1024 * 1024)} MB.",
                },
            )

        # Extension checks alone are trivial to bypass, so also verify the PDF
        # signature before saving user-controlled content.
        header = resume.read(5)
        resume.seek(0)
        if header != b"%PDF-":
            return render(
                request,
                "users/upload_resume.html",
                {"user_settings": user_settings, "error": "The uploaded file is not a valid PDF."},
            )

        saved_resume = Resume.objects.create(
            user=request.user,
            resume_file=resume,
            parse_status="pending",
        )
        try:
            raw_text = extract_resume_text(saved_resume.resume_file)
            student = Student.objects.filter(user=request.user).first()
            saved_resume.raw_text = raw_text
            saved_resume.parsed_profile = build_local_profile(raw_text, student)
            saved_resume.parse_status = "complete"
            saved_resume.parse_error = ""
            saved_resume.save(update_fields=["raw_text", "parsed_profile", "parse_status", "parse_error"])
            message = "Resume uploaded and locally analysed. You can now start a resume-based interview."
        except ResumeProcessingError as exc:
            saved_resume.parse_status = "failed"
            saved_resume.parse_error = str(exc)[:255]
            saved_resume.save(update_fields=["parse_status", "parse_error"])
            message = f"Resume uploaded, but text extraction failed: {exc}"

        return render(
            request,
            "users/upload_resume.html",
            {
                "user_settings": user_settings,
                "message": message,
                "resume": saved_resume,
            },
        )

    return render(
        request,
        "users/upload_resume.html",
        {
            "user_settings": user_settings
        }
    )


PASSWORD_RESET_SESSION_KEYS = (
    "password_reset_email",
    "password_reset_otp_hash",
    "password_reset_sent_at",
    "password_reset_attempts",
    "password_reset_verified",
    "password_reset_verified_at",
)


def _clear_password_reset_session(request):
    for key in PASSWORD_RESET_SESSION_KEYS:
        request.session.pop(key, None)
    request.session.modified = True


def _password_reset_user(request):
    email = str(request.session.get("password_reset_email", "")).strip().lower()
    if not email:
        return None
    return User.objects.filter(email__iexact=email, is_active=True).order_by("id").first()


def _password_reset_expired(request, timestamp_key="password_reset_sent_at"):
    try:
        started_at = float(request.session.get(timestamp_key, 0))
    except (TypeError, ValueError):
        return True
    expiry = max(60, int(getattr(settings, "PASSWORD_RESET_OTP_EXPIRY_SECONDS", 600)))
    return not started_at or (time.time() - started_at) > expiry


def _mask_email(email):
    local, separator, domain = email.partition("@")
    if not separator:
        return email
    if len(local) <= 2:
        masked_local = local[:1] + "*"
    else:
        masked_local = f"{local[0]}{'*' * max(1, len(local) - 2)}{local[-1]}"
    return f"{masked_local}@{domain}"


def _send_password_reset_otp(request, user):
    """Create a short-lived hashed OTP and send it through configured email."""

    otp = f"{secrets.randbelow(1_000_000):06d}"
    email = user.email.strip().lower()
    request.session["password_reset_email"] = email
    request.session["password_reset_otp_hash"] = make_password(otp)
    request.session["password_reset_sent_at"] = int(time.time())
    request.session["password_reset_attempts"] = 0
    request.session["password_reset_verified"] = False
    request.session.pop("password_reset_verified_at", None)
    request.session.modified = True

    expiry_minutes = max(1, int(getattr(settings, "PASSWORD_RESET_OTP_EXPIRY_SECONDS", 600) / 60))
    subject = "CareerAI password reset OTP"
    body = (
        f"Hello {user.get_short_name() or user.username},\n\n"
        f"Your CareerAI password reset OTP is: {otp}\n\n"
        f"This OTP expires in {expiry_minutes} minutes. Do not share it with anyone.\n\n"
        "If you did not request a password reset, you can ignore this email.\n"
        "CareerAI"
    )
    try:
        html_body = render_to_string(
            "users/emails/password_reset_otp.html",
            {
                "otp": otp,
                "display_name": user.get_short_name() or user.username,
                "email": email,
                "expiry_minutes": expiry_minutes,
            },
        )
        message = EmailMultiAlternatives(
            subject,
            body,
            getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@careerai.local"),
            [email],
        )
        message.attach_alternative(html_body, "text/html")
        sent_count = message.send(fail_silently=False)
    except Exception:
        _clear_password_reset_session(request)
        return False
    if sent_count < 1:
        _clear_password_reset_session(request)
        return False
    return True


def forgot_password(request):
    if request.method == "POST":
        email = str(request.POST.get("email", "")).strip().lower()
        if not email:
            return render(request, "users/forgot_password.html", {"error": "Enter your registered email address."})

        user = User.objects.filter(email__iexact=email, is_active=True).order_by("id").first()
        if user is None or not user.email:
            return render(
                request,
                "users/forgot_password.html",
                {"error": "No active account was found with this email address.", "email": email},
            )

        if not _send_password_reset_otp(request, user):
            return render(
                request,
                "users/forgot_password.html",
                {
                    "error": "OTP email could not be sent. Check your email settings and try again.",
                    "email": email,
                },
            )
        return redirect("verify_password_otp")

    return render(request, "users/forgot_password.html")


def verify_password_otp(request):
    email = str(request.session.get("password_reset_email", "")).strip().lower()
    if not email:
        return redirect("forgot_password")
    if _password_reset_expired(request):
        _clear_password_reset_session(request)
        messages.error(request, "That OTP expired. Request a new one.")
        return redirect("forgot_password")

    error = ""
    if request.method == "POST":
        entered_otp = str(request.POST.get("otp", "")).strip()
        try:
            attempts = int(request.session.get("password_reset_attempts", 0))
        except (TypeError, ValueError):
            attempts = 0
        max_attempts = max(3, int(getattr(settings, "PASSWORD_RESET_MAX_ATTEMPTS", 5)))
        if attempts >= max_attempts:
            _clear_password_reset_session(request)
            messages.error(request, "Too many incorrect attempts. Request a new OTP.")
            return redirect("forgot_password")

        request.session["password_reset_attempts"] = attempts + 1
        stored_hash = request.session.get("password_reset_otp_hash", "")
        if len(entered_otp) != 6 or not entered_otp.isdigit() or not stored_hash or not check_password(entered_otp, stored_hash):
            error = f"Incorrect OTP. You have {max(0, max_attempts - attempts - 1)} attempts left."
        else:
            request.session["password_reset_verified"] = True
            request.session["password_reset_verified_at"] = int(time.time())
            request.session.pop("password_reset_otp_hash", None)
            request.session.modified = True
            return redirect("password_reset_new")

    return render(
        request,
        "users/verify_otp.html",
        {"masked_email": _mask_email(email), "error": error},
    )


def resend_password_otp(request):
    if request.method != "POST":
        return redirect("verify_password_otp")
    user = _password_reset_user(request)
    if user is None:
        _clear_password_reset_session(request)
        messages.error(request, "Start the password reset again.")
        return redirect("forgot_password")

    try:
        sent_at = float(request.session.get("password_reset_sent_at", 0))
    except (TypeError, ValueError):
        sent_at = 0
    cooldown = max(10, int(getattr(settings, "PASSWORD_RESET_RESEND_COOLDOWN_SECONDS", 30)))
    if sent_at and (time.time() - sent_at) < cooldown:
        messages.error(request, f"Wait {cooldown} seconds before requesting another OTP.")
        return redirect("verify_password_otp")

    if _send_password_reset_otp(request, user):
        messages.success(request, "A new OTP was sent to your registered email.")
    else:
        messages.error(request, "OTP email could not be sent. Check your email settings.")
    return redirect("verify_password_otp")


def password_reset_new(request):
    if not request.session.get("password_reset_verified") or _password_reset_expired(request, "password_reset_verified_at"):
        _clear_password_reset_session(request)
        messages.error(request, "Verify a valid OTP before setting a new password.")
        return redirect("forgot_password")

    user = _password_reset_user(request)
    if user is None:
        _clear_password_reset_session(request)
        messages.error(request, "That account is no longer available.")
        return redirect("forgot_password")

    errors = []
    if request.method == "POST":
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if not password:
            errors.append("Enter a new password.")
        if not errors:
            try:
                validate_password(password, user=user)
            except ValidationError as exc:
                errors.extend(exc.messages)
        if not errors:
            user.set_password(password)
            user.save(update_fields=["password"])
            _clear_password_reset_session(request)
            messages.success(request, "Password changed successfully. Sign in with your new password.")
            return redirect("login")

    return render(
        request,
        "users/reset_password.html",
        {"errors": errors, "masked_email": _mask_email(user.email)},
    )



def register(request):

    if request.method == "POST":

        form = RegisterForm(request.POST)

        if form.is_valid():

            user = form.save(
                commit=False
            )

            try:
                validate_password(
                    form.cleaned_data["password"],
                    user=user,
                )
            except ValidationError as exc:
                form.add_error("password", exc)
                return render(request, "users/register.html", {"form": form})

            user.set_password(
                form.cleaned_data["password"]
            )

            user.save()

            return redirect(
                "login"
            )


    else:

        form = RegisterForm()


    return render(
        request,
        "users/register.html",
        {
            "form": form
        }
    )



def user_login(request):

    if request.method == "POST":

        username = request.POST["username"]

        password = request.POST["password"]


        user = authenticate(
            request,
            username=username,
            password=password
        )


        if user:

            login(
                request,
                user
            )

            return redirect(
                "dashboard"
            )

        messages.error(request, "Invalid username or password.")


    return render(
        request,
        "users/login.html"
    )



def user_logout(request):

    logout(request)

    return redirect(
        "login"
    )



@login_required
def dashboard(request):

    resumes = Resume.objects.filter(
        user=request.user
    )

    user_settings, created = UserSettings.objects.get_or_create(
        user=request.user
    )

    sessions = InterviewSession.objects.filter(user=request.user)
    completed_sessions = sessions.filter(status="completed")
    scores = [session.overall_score for session in completed_sessions if session.overall_score is not None]
    average_score = round(sum(scores) / len(scores), 1) if scores else None
    progress_label = "Ready for interview" if resumes.exists() else "Upload a resume"

    return render(
        request,
        "users/dashboard.html",
        {
            "resumes": resumes,
            "user_settings": user_settings,
            "resume_uploaded": resumes.exists(),
            "interview_count": sessions.count(),
            "average_score": average_score,
            "progress_label": progress_label,
        }
    )


@login_required
def career_guidance_page(request):
    """Show resume-grounded next steps, using Gemini when configured."""

    latest_resume = (
        Resume.objects.filter(user=request.user)
        .order_by("-uploaded_at")
        .first()
    )
    guidance = None
    generated_by = ""
    error = ""

    if request.method == "POST":
        if latest_resume is None:
            error = "Upload a resume before requesting career suggestions."
        else:
            try:
                if not latest_resume.raw_text:
                    latest_resume.raw_text = extract_resume_text(latest_resume.resume_file)
                    latest_resume.parsed_profile = build_local_profile(latest_resume.raw_text)
                    latest_resume.parse_status = "complete"
                    latest_resume.parse_error = ""
                    latest_resume.save(update_fields=["raw_text", "parsed_profile", "parse_status", "parse_error"])
                profile = latest_resume.parsed_profile or build_local_profile(latest_resume.raw_text)
                last_session = (
                    InterviewSession.objects.filter(user=request.user, status="completed")
                    .select_related("feedback")
                    .first()
                )
                interview_feedback = None
                if last_session and hasattr(last_session, "feedback"):
                    interview_feedback = {
                        "strengths": last_session.feedback.strengths,
                        "weaknesses": last_session.feedback.weaknesses,
                        "recommendations": last_session.feedback.recommendations,
                    }
                guidance, generated_by = generate_career_guidance(
                    profile=profile,
                    raw_text=latest_resume.raw_text,
                    interview_feedback=interview_feedback,
                )
            except ResumeProcessingError as exc:
                error = str(exc)

    return render(
        request,
        "users/career_guidance.html",
        {
            "latest_resume": latest_resume,
            "guidance": guidance,
            "generated_by": generated_by,
            "error": error,
        },
    )

@login_required
def ai_interview(request):

    interview_questions = {

        "Software Developer": {

            "easy": [
                {
                    "question": "What programming languages are you comfortable working with?",
                    "type": "Programming"
                },
                {
                    "question": "What is the difference between a variable and a constant?",
                    "type": "Programming Basics"
                },
                {
                    "question": "Tell me about a software project you have worked on.",
                    "type": "Project"
                },
                {
                    "question": "What is a function and why is it useful?",
                    "type": "Programming Basics"
                },
                {
                    "question": "How do you usually debug a simple programming error?",
                    "type": "Problem Solving"
                },
            ],

            "medium": [
                {
                    "question": "Explain the difference between a list, tuple, and dictionary in Python.",
                    "type": "Python"
                },
                {
                    "question": "How would you debug a Django application that is returning a 500 error?",
                    "type": "Django"
                },
                {
                    "question": "What is the difference between GET and POST requests?",
                    "type": "Web Development"
                },
                {
                    "question": "How would you optimize a database query that is taking too long?",
                    "type": "Database"
                },
                {
                    "question": "Describe a software project you worked on and explain an important technical decision you made.",
                    "type": "Project"
                },
            ],

            "hard": [
                {
                    "question": "How would you design a scalable web application that needs to support millions of users?",
                    "type": "System Design"
                },
                {
                    "question": "A production application suddenly becomes slow. Walk me through how you would investigate the problem.",
                    "type": "Performance"
                },
                {
                    "question": "How would you design a database for an application with millions of records and frequent queries?",
                    "type": "Database Design"
                },
                {
                    "question": "How would you design an authentication system for a large web application?",
                    "type": "Architecture"
                },
                {
                    "question": "How would you improve the reliability of an application that frequently experiences unexpected failures?",
                    "type": "Software Architecture"
                },
            ],
        },


        "Web Developer": {

            "easy": [
                {
                    "question": "What are HTML, CSS, and JavaScript used for?",
                    "type": "Web Basics"
                },
                {
                    "question": "What is the purpose of HTML tags?",
                    "type": "HTML"
                },
                {
                    "question": "What is CSS used for on a website?",
                    "type": "CSS"
                },
                {
                    "question": "What is the difference between a website and a web application?",
                    "type": "Web Development"
                },
                {
                    "question": "Tell me about a website you have created or worked on.",
                    "type": "Project"
                },
            ],

            "medium": [
                {
                    "question": "Explain the difference between frontend and backend development.",
                    "type": "Web Development"
                },
                {
                    "question": "How does a browser communicate with a web server?",
                    "type": "HTTP"
                },
                {
                    "question": "What is responsive web design and why is it important?",
                    "type": "Frontend"
                },
                {
                    "question": "How would you improve the loading speed of a website?",
                    "type": "Performance"
                },
                {
                    "question": "Explain how APIs are used in modern web applications.",
                    "type": "API"
                },
            ],

            "hard": [
                {
                    "question": "How would you architect a web application expected to handle a very large number of simultaneous users?",
                    "type": "Architecture"
                },
                {
                    "question": "How would you investigate a sudden increase in API response time?",
                    "type": "Performance"
                },
                {
                    "question": "How would you design a secure authentication and authorization system?",
                    "type": "Security"
                },
                {
                    "question": "How would you reduce frontend performance problems in a large web application?",
                    "type": "Frontend Performance"
                },
                {
                    "question": "How would you design an API that needs to remain reliable when one of its dependent services fails?",
                    "type": "API Architecture"
                },
            ],
        },


        "Data Analyst": {

            "easy": [
                {
                    "question": "What is data analysis?",
                    "type": "Data Basics"
                },
                {
                    "question": "What is the difference between a row and a column in a dataset?",
                    "type": "Data Basics"
                },
                {
                    "question": "What is Excel commonly used for in data analysis?",
                    "type": "Excel"
                },
                {
                    "question": "What is a database?",
                    "type": "Database"
                },
                {
                    "question": "Why are charts useful when analyzing data?",
                    "type": "Visualization"
                },
            ],

            "medium": [
                {
                    "question": "Explain the difference between INNER JOIN and LEFT JOIN in SQL.",
                    "type": "SQL"
                },
                {
                    "question": "How would you handle missing values in a dataset?",
                    "type": "Data Cleaning"
                },
                {
                    "question": "What is the difference between mean, median, and mode?",
                    "type": "Statistics"
                },
                {
                    "question": "How would you identify an outlier in a dataset?",
                    "type": "Data Analysis"
                },
                {
                    "question": "How would you choose an appropriate chart to present a business trend?",
                    "type": "Data Visualization"
                },
            ],

            "hard": [
                {
                    "question": "How would you optimize a SQL query that is taking several minutes to execute?",
                    "type": "Advanced SQL"
                },
                {
                    "question": "How would you determine whether a correlation between two variables is statistically meaningful?",
                    "type": "Statistics"
                },
                {
                    "question": "How would you investigate a major change in a company's key performance indicator?",
                    "type": "Business Analysis"
                },
                {
                    "question": "How would you design a data pipeline for a dashboard that needs regularly updated data?",
                    "type": "Data Engineering"
                },
                {
                    "question": "How would you explain a complex analytical finding to a non-technical business manager?",
                    "type": "Communication"
                },
            ],
        },


        "AI / ML Engineer": {

            "easy": [
                {
                    "question": "What is artificial intelligence?",
                    "type": "AI Basics"
                },
                {
                    "question": "What is machine learning?",
                    "type": "Machine Learning"
                },
                {
                    "question": "What programming language is commonly used for machine learning?",
                    "type": "Programming"
                },
                {
                    "question": "What is a dataset?",
                    "type": "Data"
                },
                {
                    "question": "What is the purpose of training a machine learning model?",
                    "type": "Machine Learning"
                },
            ],

            "medium": [
                {
                    "question": "What is the difference between supervised and unsupervised learning?",
                    "type": "Machine Learning"
                },
                {
                    "question": "Why is data preprocessing important before training a model?",
                    "type": "Data Preprocessing"
                },
                {
                    "question": "What is overfitting and how can you reduce it?",
                    "type": "Model Training"
                },
                {
                    "question": "How would you evaluate a classification model?",
                    "type": "Model Evaluation"
                },
                {
                    "question": "What is the difference between precision and recall?",
                    "type": "Model Evaluation"
                },
            ],

            "hard": [
                {
                    "question": "How would you design a machine learning system that needs to process millions of predictions per day?",
                    "type": "ML System Design"
                },
                {
                    "question": "How would you investigate a machine learning model whose performance has degraded after deployment?",
                    "type": "Model Monitoring"
                },
                {
                    "question": "How would you handle severe class imbalance in a classification problem?",
                    "type": "Machine Learning"
                },
                {
                    "question": "How would you choose between a traditional machine learning model and a deep learning model for a new problem?",
                    "type": "Model Selection"
                },
                {
                    "question": "How would you deploy and monitor a machine learning model in a production environment?",
                    "type": "ML Deployment"
                },
            ],
        },
    }


    user_settings, created = UserSettings.objects.get_or_create(
        user=request.user
    )


    return render(
        request,
        "users/ai_interview.html",
        {
            "interview_questions": interview_questions,
            "user_settings": user_settings,
        }
    )


# ---------------------------------------------------------------------------
# Resume-grounded interview workflow
# ---------------------------------------------------------------------------

@login_required
def ai_interview_page(request):
    user_settings, _ = UserSettings.objects.get_or_create(user=request.user)
    latest_resume = (
        Resume.objects.filter(user=request.user)
        .order_by("-uploaded_at")
        .first()
    )
    return render(
        request,
        "users/ai_interview.html",
        {
            "user_settings": user_settings,
            "latest_resume": latest_resume,
        },
    )


def _json_body(request):
    try:
        value = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


@login_required
@require_POST
def interview_start_api(request):
    payload = _json_body(request)
    if payload is None:
        return JsonResponse({"error": "Send a JSON request body."}, status=400)

    role = str(payload.get("role", "Software Developer")).strip()[:100]
    difficulty = str(payload.get("difficulty", "medium")).lower()
    interview_type = str(payload.get("interview_type", "general")).lower()
    language = str(payload.get("language", "en")).strip().lower()
    # Normal interviews are intentionally substantial (15–30 questions).
    # Hard interviews always run the full 40-question format, regardless of
    # the value sent by an older client.
    try:
        requested_count = int(payload.get("count", 15))
    except (TypeError, ValueError):
        requested_count = 15
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"
    if interview_type not in {"general", "technical", "behavioral"}:
        interview_type = "general"
    if language not in {"en", "hi", "bilingual"}:
        language = "en"
    count = 40 if difficulty == "hard" else max(15, min(requested_count, 30))

    resume = (
        Resume.objects.filter(user=request.user)
        .order_by("-uploaded_at")
        .first()
    )
    if resume is None:
        return JsonResponse(
            {"error": "Upload a PDF resume before starting an interview."},
            status=400,
        )

    if not resume.raw_text:
        try:
            resume.raw_text = extract_resume_text(resume.resume_file)
            resume.parsed_profile = build_local_profile(resume.raw_text)
            resume.parse_status = "complete"
            resume.parse_error = ""
            resume.save(update_fields=["raw_text", "parsed_profile", "parse_status", "parse_error"])
        except ResumeProcessingError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

    profile = resume.parsed_profile or build_local_profile(resume.raw_text)
    questions, generated_by = generate_questions(
        profile=profile,
        raw_text=resume.raw_text,
        role=role,
        difficulty=difficulty,
        interview_type=interview_type,
        count=count,
        language=language,
    )
    if not questions:
        return JsonResponse({"error": "Could not generate interview questions."}, status=503)

    session = InterviewSession.objects.create(
        user=request.user,
        resume=resume,
        role=role or "Software Developer",
        difficulty=difficulty,
        interview_type=interview_type,
        question_count=len(questions),
    )
    question_rows = []
    for index, item in enumerate(questions, start=1):
        question_rows.append(
            InterviewQuestion(
                session=session,
                order=index,
                question_text=item["question"],
                category=item.get("category", item.get("type", "General")),
                source=item.get("source", generated_by),
                source_evidence=item.get("source_evidence", ""),
                expected_topics=item.get("expected_topics", []),
            )
        )
    InterviewQuestion.objects.bulk_create(question_rows)

    return JsonResponse(
        {
            "session_id": session.id,
            "generated_by": generated_by,
            "language": language,
            "resume_profile": {
                "skills": profile.get("skills", [])[:12],
                "projects": [
                    item.get("name", "")
                    for item in profile.get("projects", [])
                    if isinstance(item, dict)
                ][:5],
            },
            "questions": [
                {
                    "id": question.id,
                    "order": question.order,
                    "question": question.question_text,
                    "category": question.category,
                    "source": question.source,
                    "source_evidence": question.source_evidence,
                }
                for question in session.questions.all()
            ],
        }
    )


@login_required
@require_POST
def interview_answer_api(request):
    payload = _json_body(request)
    if payload is None:
        return JsonResponse({"error": "Send a JSON request body."}, status=400)
    try:
        question_id = int(payload.get("question_id"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "A valid question_id is required."}, status=400)

    question = (
        InterviewQuestion.objects.select_related("session")
        .filter(id=question_id, session__user=request.user)
        .first()
    )
    if question is None:
        return JsonResponse({"error": "Question not found."}, status=404)
    answer_text = str(payload.get("answer", ""))[:12_000]
    duration = payload.get("duration_seconds")
    try:
        duration = max(0, min(int(duration), 86_400)) if duration is not None else None
    except (TypeError, ValueError):
        duration = None

    question_data = {
        "question": question.question_text,
        "expected_topics": question.expected_topics or [],
    }
    scores, generated_by = evaluate_answer(question_data, answer_text)
    answer, _ = InterviewAnswer.objects.update_or_create(
        question=question,
        defaults={
            "answer_text": answer_text,
            "duration_seconds": duration,
            "technical_score": scores["technical_score"],
            "relevance_score": scores["relevance_score"],
            "communication_score": scores["communication_score"],
            "overall_score": scores["overall_score"],
            "filler_count": scores["filler_count"],
            "feedback": {"items": scores.get("feedback", []), "generated_by": generated_by},
        },
    )
    return JsonResponse(
        {
            "answer_id": answer.id,
            "generated_by": generated_by,
            "scores": scores,
        }
    )


@login_required
@require_POST
def interview_finish_api(request):
    payload = _json_body(request)
    if payload is None:
        return JsonResponse({"error": "Send a JSON request body."}, status=400)
    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "A valid session_id is required."}, status=400)
    session = InterviewSession.objects.select_related("resume").filter(id=session_id, user=request.user).first()
    if session is None:
        return JsonResponse({"error": "Interview session not found."}, status=404)

    # Finishing is idempotent: refreshing the report must not regenerate a
    # different answer key for the same interview.
    if session.status == "completed" and hasattr(session, "feedback"):
        feedback = _professional_answer_key_for_session(session, session.feedback)
        return JsonResponse(
            {
                "session_id": session.id,
                "overall_score": session.overall_score or 0.0,
                "generated_by": feedback.generated_by,
                "answers_generated_by": "stored",
                "report_url": reverse("interview_report", args=[session.id]),
                "pdf_url": reverse("interview_report_pdf", args=[session.id]),
                "strengths": feedback.strengths,
                "weaknesses": feedback.weaknesses,
                "recommendations": feedback.recommendations,
                "professional_answers": feedback.professional_answers,
            }
        )

    answer_rows = list(
        InterviewAnswer.objects.filter(question__session=session)
        .select_related("question")
        .values(
            "overall_score",
            "filler_count",
            "feedback",
            "answer_text",
            "question__question_text",
            "question__order",
        )
    )
    overall_score = round(
        sum(float(item["overall_score"]) for item in answer_rows) / len(answer_rows),
        2,
    ) if answer_rows else 0.0
    summary, feedback_generated_by = generate_interview_feedback(answer_rows)
    session_questions = list(session.questions.all())
    question_payload = [
        {
            "order": question.order,
            "question": question.question_text,
            "category": question.category,
            "source_evidence": question.source_evidence,
            "expected_topics": question.expected_topics or [],
        }
        for question in session_questions
    ]
    resume_profile = session.resume.parsed_profile if session.resume else {}
    resume_text = session.resume.raw_text if session.resume else ""
    professional_answers, answers_generated_by = generate_professional_answers(
        questions=question_payload,
        profile=resume_profile or {},
        raw_text=resume_text or "",
        role=session.role,
        difficulty=session.difficulty,
    )
    session.status = "completed"
    session.overall_score = overall_score
    session.completed_at = timezone.now()
    session.save(update_fields=["status", "overall_score", "completed_at"])
    InterviewFeedback.objects.update_or_create(
        session=session,
        defaults={
            **summary,
            "professional_answers": professional_answers,
            "generated_by": feedback_generated_by,
        },
    )
    return JsonResponse(
        {
            "session_id": session.id,
            "overall_score": overall_score,
            "generated_by": feedback_generated_by,
            "answers_generated_by": answers_generated_by,
            "report_url": reverse("interview_report", args=[session.id]),
            "pdf_url": reverse("interview_report_pdf", args=[session.id]),
            "professional_answers": professional_answers,
            **summary,
        }
    )


def _professional_answer_key_for_session(session, feedback):
    """Backfill the answer key for sessions completed before this feature."""

    if feedback.professional_answers:
        return feedback
    session_questions = list(session.questions.all())
    question_payload = [
        {
            "order": question.order,
            "question": question.question_text,
            "category": question.category,
            "source_evidence": question.source_evidence,
            "expected_topics": question.expected_topics or [],
        }
        for question in session_questions
    ]
    resume = session.resume
    answers, _ = generate_professional_answers(
        questions=question_payload,
        profile=(resume.parsed_profile if resume else {}) or {},
        raw_text=(resume.raw_text if resume else "") or "",
        role=session.role,
        difficulty=session.difficulty,
    )
    feedback.professional_answers = answers
    feedback.save(update_fields=["professional_answers"])
    return feedback


@login_required
def interview_report(request, session_id):
    session = (
        InterviewSession.objects.select_related("resume")
        .filter(id=session_id, user=request.user)
        .prefetch_related("questions__answer")
        .first()
    )
    if session is None:
        return HttpResponse("Interview report not found.", status=404)
    feedback = InterviewFeedback.objects.filter(session=session).first()
    if session.status != "completed" or feedback is None:
        messages.info(request, "Complete the interview to view its report.")
        return redirect("ai_interview")
    feedback = _professional_answer_key_for_session(session, feedback)
    answer_by_order = {
        int(item.get("order")): item
        for item in (feedback.professional_answers or [])
        if isinstance(item, dict) and str(item.get("order", "")).isdigit()
    }
    report_questions = []
    for question in session.questions.all():
        candidate = getattr(question, "answer", None)
        model_answer = answer_by_order.get(question.order, {})
        report_questions.append(
            {
                "order": question.order,
                "question": question.question_text,
                "category": question.category,
                "evidence": question.source_evidence,
                "answer_en": model_answer.get("answer_en", "Professional answer unavailable."),
                "answer_hi": model_answer.get("answer_hi", "इस प्रश्न के लिए professional answer उपलब्ध नहीं है।"),
                "candidate_answer": candidate.answer_text if candidate else "",
                "candidate_score": candidate.overall_score if candidate else None,
            }
        )
    return render(
        request,
        "users/interview_report.html",
        {
            "session": session,
            "feedback": feedback,
            "report_questions": report_questions,
            "pdf_url": reverse("interview_report_pdf", args=[session.id]),
        },
    )


@login_required
def interview_report_pdf(request, session_id):
    session = (
        InterviewSession.objects.select_related("resume")
        .filter(id=session_id, user=request.user)
        .prefetch_related("questions__answer")
        .first()
    )
    if session is None:
        return HttpResponse("Interview report not found.", status=404)
    feedback = InterviewFeedback.objects.filter(session=session).first()
    if session.status != "completed" or feedback is None:
        return HttpResponse("Complete the interview before downloading its report.", status=400)
    _professional_answer_key_for_session(session, feedback)
    try:
        pdf_bytes = build_interview_report_pdf(session)
    except RuntimeError as exc:
        return HttpResponse(str(exc), status=503)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="careerai_interview_report_{session.id}.pdf"'
    return response


@login_required
@require_GET
def interview_history_api(request):
    sessions = InterviewSession.objects.filter(user=request.user)[:20]
    return JsonResponse(
        {
            "sessions": [
                {
                    "id": session.id,
                    "role": session.role,
                    "difficulty": session.difficulty,
                    "status": session.status,
                    "score": session.overall_score,
                    "started_at": session.started_at.isoformat(),
                }
                for session in sessions
            ]
        }
    )
