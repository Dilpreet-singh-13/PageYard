from django.contrib.postgres.search import SearchVector
from django.db import connection
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Note, NoteAttachment


@receiver(post_save, sender=Note)
def update_note_search_vector(sender, instance, update_fields, **kwargs):
    """
    Rebuild search_vector after any save that changes content (PostgreSQL only).

    Uses .update() rather than instance.save() deliberately:
    - update() is a direct SQL UPDATE — no model overhead, no signals fired, no risk of recursion.
    - Checking update_fields means trash(), restore(), and toggle_star() calls
      (which pass explicit update_fields with no content fields) skip this entirely — no wasted DB round-trip on metadata-only saves.
    """
    if connection.vendor != "postgresql":
        return

    content_fields = {"title", "raw_content"}  # fields taken from Note model

    # only update if any content changes (not metadata changes)
    if update_fields is not None and not content_fields.intersection(update_fields):
        return

    Note.objects.filter(pk=instance.pk).update(
        search_vector=SearchVector("title", weight="A") + SearchVector("raw_content", weight="B")
    )


@receiver(post_delete, sender=NoteAttachment)
def delete_attachment_file(sender, instance, **kwargs):
    """
    Delete the actual file from Cloudflare R2 when an attachment row is deleted.

    This fires in two scenarios:
        1. User permanently deletes a note -> Postgres CASCADE deletes NoteAttachment rows -> this signal fires for each one.
        2. User deletes a single attachment directly.

    on_delete=CASCADE handles the DB row. This signal handles the R2 file.
    Without it, deleted notes leave orphaned files in R2 indefinitely.

    save=False is to not attempt to update the model row (as it's already deleted)
    django-storages translates this into a Cloudflare R2 / S3 DeleteObject call
    """

    if instance.file:
        instance.file.delete(save=False)
