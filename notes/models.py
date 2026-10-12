import re
import uuid
from django.conf import settings
from django.db import models
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.utils import timezone
from .constants import TRASH_RETENTION_DAYS
from .render import render_markdown

PLAIN_PREVIEW_MAX_LENGTH = 250

# Regex pipeline to strip common Markdown syntax for plain-text previews.
# Order matters: images/links first (so their alt/label text is kept),
# then inline markers, then block-level prefixes.
_STRIP_MD_PATTERNS: list[tuple[str, str]] = [
    (r"!\[([^\]]*)\]\([^)]*\)", r"\1"),  # images  → alt text
    (r"\[([^\]]*)\]\([^)]*\)", r"\1"),   # links   → label text
    (r"`{1,3}[^`]*`{1,3}", ""),           # inline code / fenced spans
    (r"^#{1,6}\s+", ""),                  # headings
    (r"^>\s?", ""),                        # blockquotes
    (r"^[-*+]\s+", ""),                   # unordered list markers
    (r"^\d+\.\s+", ""),                   # ordered list markers
    (r"[*_]{1,3}", ""),                   # bold / italic markers
    (r"~{2}", ""),                         # strikethrough markers
    (r"^---+$", ""),                       # horizontal rules
]
_STRIP_MD_COMPILED = [(re.compile(p, re.MULTILINE), r) for p, r in _STRIP_MD_PATTERNS]


def _make_plain_preview(raw_content: str) -> str:
    """Return a plain-text preview of *raw_content*, capped at PLAIN_PREVIEW_MAX_LENGTH chars."""
    text = raw_content
    for pattern, replacement in _STRIP_MD_COMPILED:
        text = pattern.sub(replacement, text)
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > PLAIN_PREVIEW_MAX_LENGTH:
        return text[:PLAIN_PREVIEW_MAX_LENGTH] + "\u2026"
    return text

# Kept in sync with build_attachment_key() inside utils
# scans for public/images/<user_id>/<note_id>/<attachment_uuid>.<ext>
ATTACHMENT_ID_RE = re.compile(r"/public/images/[^/]+/[^/]+/([0-9a-f-]{36})\.")


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tags",
        editable=False,
    )

    class Meta:
        unique_together = ["name", "created_by"]
        ordering = ["name"]
        indexes = [
            models.Index(fields=["created_by", "name"]),
        ]

    def __str__(self):
        return self.name


# No .get method overlaod so Note.objects.get() works as is, removing any chances of unexpected behavious
class NoteQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=Note.Status.ACTIVE)

    def trashed(self):
        return self.filter(status=Note.Status.TRASH)

    def by_user(self, user):
        return self.filter(created_by=user)


class Note(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TRASH = "trash", "Trash"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=256, default="Untitled")
    raw_content = models.TextField(blank=True, default="")
    rendered_content = models.TextField(blank=True, default="")
    plain_preview = models.CharField(max_length=PLAIN_PREVIEW_MAX_LENGTH + 1, blank=True, default="")
    is_starred = models.BooleanField(default=False, db_index=True)
    status = models.CharField(
        max_length=8, choices=Status, default=Status.ACTIVE, db_index=True
    )
    tags = models.ManyToManyField("Tag", blank=True, related_name="notes")

    # postgresql based search vector, updated via signals (post_save)
    search_vector = SearchVectorField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    # populated only when status=TRASH
    # celery auto purges any note with: trashed_at__lt=now()-TRASH_RETENTION_DAYS
    trashed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        editable=False,
        related_name="notes",
    )

    objects = NoteQuerySet.as_manager()

    class Meta:
        indexes = [GinIndex(fields=["search_vector"])]
        ordering = ["-updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Track the initial/original state to skip re-rendering when
        # only metadata changes (eg starred, trashed). So we avoid unnecessary markdown
        # parsing, cleaning on every save
        self._original_raw_content = self.raw_content

    def update_render_markdown(self):
        """Rendering and sanitizing of the raw markdown content."""
        self.rendered_content = render_markdown(self.raw_content)
        self.plain_preview = _make_plain_preview(self.raw_content)

    def save(self, *args, **kwargs):
        # only re-render if content actually changes OR
        # the object is brand new being created.
        if self._state.adding or self.raw_content != self._original_raw_content:
            self.update_render_markdown()

        super().save(*args, **kwargs)

        # reset the tracker after a successful save, so next save() can detect changes
        self._original_raw_content = self.raw_content

    # State tensition helpers: trash note, recover note
    def trash(self) -> None:
        f"Soft delete. Put the note in trash. A note stays in trash for {TRASH_RETENTION_DAYS} days unless restored, after {TRASH_RETENTION_DAYS} days its auto-purged by background celery job."
        self.status = self.Status.TRASH
        self.trashed_at = timezone.now()
        self.updated_at = timezone.now()
        self.save(update_fields=["status", "trashed_at", "updated_at"])

    def restore(self) -> None:
        "Restore note from trash back to active"
        self.status = self.Status.ACTIVE
        self.trashed_at = None
        self.updated_at = timezone.now()
        self.save(update_fields=["status", "trashed_at", "updated_at"])

    def sync_attachments(self) -> None:
        """
        Reconciles NoteAttachments against raw_content.
        Marks attachments missing from the text as orphaned, and un-orphans any that have been re-added.
        """
        # this function is overall quite well optimized as we avoid pulling attachments into memory 
        # and useing python to iterate in a for loop
        # instead Django convets these directly into SQL statements executed on the DB

        # get all currently present attachment IDs in the latest raw content
        present_attachment_ids = set(ATTACHMENT_ID_RE.findall(self.raw_content))
        # get all the IDs that were linked to the Note & marked Completed, we'll filter out from these
        all_completed_attachments = self.attachments.filter(
            status=NoteAttachment.UploadStatus.COMPLETE
        )

        # remove the attachments that still exist > now only the ones not currently present remain
        # then filter out the ones that haven't been orphaned yet (ie orphaned_at=null)
        # finally set to orphaned
        all_completed_attachments.exclude(id__in=present_attachment_ids).filter(
            orphaned_at__isnull=True
        ).update(orphaned_at=timezone.now())

        # Un-orphan if the user pasted the exact URL back into the note
        all_completed_attachments.filter(
            id__in=present_attachment_ids, orphaned_at__isnull=False
        ).update(orphaned_at=None)

    @property
    def is_trashed(self) -> bool:
        return self.status == self.Status.TRASH

    def __str__(self) -> str:
        return self.title


class NoteAttachment(models.Model):
    class UploadStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETE = "complete", "Complete"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="attachments")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        editable=False,
        related_name="attachments",
    )
    # upload_to is NOT actually used!
    # Its only kept bcz FileField expects it & keep django internals predictable
    # actual file uploads take place on client side to R2 (or other object storage)
    file = models.FileField(upload_to="attachments/")
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes.")
    mime_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    # tracks when an image was removed from the markdown text (used by the image removal & image sync pipeline)
    orphaned_at = models.DateTimeField(null=True, blank=True, db_index=True)
    # Tracks the R2 upload lifecycle. New attachments are created as
    # PENDING before a presigned upload URL is issued, and marked COMPLETE once
    # the client successfully uploads the object.
    status = models.CharField(
        max_length=20,
        choices=UploadStatus.choices,
        default=UploadStatus.PENDING,
        db_index=True,
    )

    def __str__(self):
        return f"{self.original_filename} -> note: {self.note_id}"
