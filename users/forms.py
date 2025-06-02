from django import forms
from users.models import CustomUser, IntegrationApplication

class CustomUserForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password']
        widgets = {
            'password': forms.PasswordInput()
        }

class IntegrationApplicationForm(forms.ModelForm):
    class Meta: 
        model = IntegrationApplication
        fields = ['name', 'redirect_uri', 'description']