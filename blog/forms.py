from django import forms
from .models import Post

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'slug', 'body']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter a catchy, B2B title...'}),
            'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., why-clean-lead-data-matters'}),
            'body': forms.Textarea(attrs={'class': 'form-textarea', 'placeholder': 'Write your industry or B2B article here...'}),
        }