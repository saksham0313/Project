from django import forms
from django.contrib.auth.models import User
from .models import Student


class RegisterForm(forms.ModelForm):

    # Password recovery is email-based, so every newly-created account must
    # provide a usable and unambiguous address.
    email = forms.EmailField(required=True)

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

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email



class ProfileForm(forms.ModelForm):

    class Meta:

        model = Student

        fields = [
            "full_name",
            "college",
            "cgpa",
            "skills"
        ]
