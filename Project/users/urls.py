from django.urls import path

from . import views



urlpatterns = [

    path("", views.user_login, name="home"),

    path("settings/", views.settings_page, name="settings"),
    
   path(
    "register/",
    views.register,
    name="register"
),


    path(
        "login/",
        views.user_login,
        name="login"
    ),


    path(
        "logout/",
        views.user_logout,
        name="logout"
    ),


    path(
        "dashboard/",
        views.dashboard,
        name="dashboard"
    ),

    path(
        "upload/",
        views.upload_resume,
        name="upload_resume"
    ),

    path(
    "ai-interview/",
    views.ai_interview,
    name="ai_interview"
),

]