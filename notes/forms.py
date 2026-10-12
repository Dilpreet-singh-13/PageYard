from django import forms
from django.forms import ModelForm

from .models import Note, Tag


class NoteForm(ModelForm):
    class Meta:
        model = Note
        fields = ['title', 'raw_content'] # tags are handled via separate html endpoints    


class TagForm(ModelForm):
    class Meta:
        model = Tag
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Tag name cannot be empty.")
        return name