from django.forms import ModelForm

from .models import Note, Group


class NoteForm(ModelForm):
    class Meta:
        model = Note
        fields = ['title', 'group', 'raw_content']


class GroupForm(ModelForm):
    class Meta:
        model = Group
        fields = ['name']