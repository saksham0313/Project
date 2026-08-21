from django import forms
from django.contrib.auth.models import User
from .models import Student


class RegisterForm(forms.ModelForm):

    password = forms.CharField(
        widget=forms.PasswordInput
    )

    class Meta:

        model = User

        fields = [
            "username",
            "email",
            "password"
        ]



class ProfileForm(forms.ModelForm):

    class Meta:

        model = Student

        fields = [
            "full_name",
            "college",
            "cgpa",
            "skills"
        ]