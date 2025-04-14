# forms.py
from django import forms
from .models import Person

class DriverForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ['surname', 'firstname', 'nickname', 'gender',
                  'birthdate', 'country', 'mugshot', 'email']
        widgets = {
            'mugshot': forms.FileInput(attrs={'class': 'file-input', 'id': 'mugshot-upload'}),
            'birthdate': forms.DateInput(attrs={'type': 'date'}),
        }
