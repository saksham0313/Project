from django.shortcuts import render, redirect

from django.contrib.auth.models import User

from django.contrib.auth import authenticate, login, logout

from .forms import RegisterForm

from django.contrib.auth.decorators import login_required

from django.shortcuts import render, redirect

from django.conf import settings

from .models import Resume, UserSettings, Student



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

        # Save resume in the Resume database model
        Resume.objects.create(
            user=request.user,
            resume_file=resume
        )

        return render(
            request,
            "users/upload_resume.html",
            {
                "user_settings": user_settings,
                "message": "Resume uploaded successfully!"
            }
        )

    return render(
        request,
        "users/upload_resume.html",
        {
            "user_settings": user_settings
        }
    )



def register(request):

    if request.method == "POST":

        form = RegisterForm(request.POST)

        if form.is_valid():

            user = form.save(
                commit=False
            )

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


    return render(
        request,
        "users/login.html"
    )



def user_logout(request):

    logout(request)

    return redirect(
        "login"
    )



def dashboard(request):

    user_settings, created = UserSettings.objects.get_or_create(
        user=request.user
    )

    return render(
        request,
        "users/dashboard.html",
        {
            "user_settings": user_settings
        }
    )

def dashboard(request):

    resumes = Resume.objects.filter(
        user=request.user
    )

    user_settings, created = UserSettings.objects.get_or_create(
        user=request.user
    )

    return render(
        request,
        "users/dashboard.html",
        {
            "resumes": resumes,
            "user_settings": user_settings,
            "resume_uploaded": resumes.exists(),
        }
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