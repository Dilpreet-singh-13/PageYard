import uuid
import markdown
import nh3
from django.conf import settings
from django.db import models


NH3_ALLOWED_TAGS = {
    'a', 'abbr', 'b', 'blockquote', 'code', 'em', 'i', 'li', 'ol',
    'strong', 'ul', 'p', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br', 'hr', 'pre', 'div', 'span',
    'img'
}

NH3_ALLOWED_ATTRIBUTES = {
    'a': {'href', 'title'},
    'img': {'src', 'alt', 'title'},
    'div': {'class'},
    'span': {'class'},
    'code': {'class'},
    'pre': {'class'},
}

NH3_URL_SCHEMES = {'http', 'https', 'mailto'}

MARKDOWN_EXTENSIONS = ['fenced_code', 'tables', 'sane_lists']


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=256, blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        editable=False,
        related_name='note_groups'
    )

    def __str__(self):
        return self.name


class Note(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=256, default='Untitled')
    raw_content = models.TextField(blank=True, default='')
    rendered_content = models.TextField(blank=True, default='')
    is_starred = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='notes')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        editable=False,
        related_name='notes'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Track the initial state of raw_content to detect changes
        self._original_raw_content = self.raw_content

    def render_markdown(self):
        """Rendering and sanitizing of the raw markdown content."""
        html = markdown.markdown(self.raw_content, extensions=MARKDOWN_EXTENSIONS)
        self.rendered_content = nh3.clean(
            html,
            tags=NH3_ALLOWED_TAGS,
            attributes=NH3_ALLOWED_ATTRIBUTES,
            url_schemes=NH3_URL_SCHEMES
        )

    def save(self, *args, **kwargs):
        # Only trigger the expensive Markdown parsing and sanitization if:
        # The object is brand new being created. OR
        # The raw_content has actually been modified.
        if self._state.adding or self.raw_content != self._original_raw_content:
            self.render_markdown()

        super().save(*args, **kwargs)
        
        # Reset the tracker after a successful save
        self._original_raw_content = self.raw_content

    def __str__(self):
        return self.title