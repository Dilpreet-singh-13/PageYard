import uuid

import markdown
import nh3
from django.conf import settings
from django.db import models


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=256, blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

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
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, editable=False,
                                   related_name='notes')

    def save(self, *args, **kwargs):
        html = markdown.markdown(self.raw_content, extensions=['extra', ])
        self.rendered_content = nh3.clean(
            html,
            tags={
                'a', 'abbr', 'b', 'blockquote', 'code', 'em', 'i', 'li', 'ol',
                'strong', 'ul', 'p', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
                'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br', 'hr', 'pre', 'div', 'span',
                'img'
            },
            attributes={
                'a': {'href', 'title'},
                'img': {'src', 'alt', 'title'},
                'div': {'class'},
                'span': {'class'},
                'code': {'class'},
                'pre': {'class'},
            },
            url_schemes={'http', 'https', 'mailto'}
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title