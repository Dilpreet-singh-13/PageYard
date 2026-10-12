import logging
from datetime import timedelta
from botocore.exceptions import ClientError
from celery import shared_task
from django.utils import timezone

from .constants import TRASH_RETENTION_DAYS, STALE_PENDING_ATTACHMENT_HOURS
from .utils import _r2_object_exists

from notes.models import NoteAttachment, Note

logger = logging.getLogger(__name__)



def _safe_delete(instance) -> bool:
    """
    Deletes a model instance, catching and logging failures so one bad row
    doesn't abort the rest of a sweep batch (e.g. the post_delete R2 cleanup
    signal raising on a transient network/auth error). Failed rows are just
    picked up again on the next scheduled run.
    """
    try:
        instance.delete()
        return True
    except Exception:
        # Broad Exception cathcing is intentional, meant to be a last resort log here.
        logger.exception(
            "Failed to delete %s (pk=%s), leaving for next sweep",
            instance.__class__.__name__,
            instance.pk,
        )
        return False


@shared_task(ignore_result=True)
def sweep_stale_pending_attachments(stale_after_hours: int = STALE_PENDING_ATTACHMENT_HOURS) -> dict:
    """
    Handles NoteAttachment rows stuck at PENDING because the upload actually
    succeeded in R2 but the confirm request (note_attachment_complete) never
    arrived — e.g. tab closed, network drop, or a JS error right after the
    presigned PUT.

    For each stale row, checks R2 directly via head_object:
        - Present in R2: the upload really did succeed, so promote to COMPLETE
          and re-run sync_attachments() to let it decide orphaned_at based on
          whether the attachment is still referenced in the note's raw_content.
        - Missing from R2: nothing was ever uploaded (the presigned URL simply
          expired), so the row is safe to delete outright.

    Args:
        stale_after_hours (int, optional): how many hours a row is allowed to
            sit at PENDING before being checked. Defaults to STALE_PENDING_ATTACHMENT_HOURS.

    Returns:
        dict: counts of attachments healed (promoted to COMPLETE) vs deleted.
    """
    cutoff = timezone.now() - timedelta(hours=stale_after_hours)
    stale = NoteAttachment.objects.filter(
        status=NoteAttachment.UploadStatus.PENDING, created_at__lt=cutoff
    ).select_related("note")

    healed = 0
    deleted = 0

    # Fetches rows from the DB in batches via .iterator() so we can avoid pulling EVERYTHING into memory
    for attachment in stale.iterator():
        try:
            exists = _r2_object_exists(attachment.file.name)
        except ClientError:
            logger.warning(
                "head_object check failed for attachment %s, skipping for this run",
                attachment.pk,
                exc_info=True,
            )
            continue

        if exists:
            attachment.status = NoteAttachment.UploadStatus.COMPLETE
            attachment.save(update_fields=["status"])
            attachment.note.sync_attachments()
            healed += 1
        else:
            if _safe_delete(attachment):
                deleted += 1

    logger.info(
        "Stale PENDING sweep: healed %s, deleted %s (older than %sh)",
        healed,
        deleted,
        stale_after_hours,
    )
    return {"healed": healed, "deleted": deleted}


@shared_task(ignore_result=True)
def sweep_trashed_notes(grace_period_days: int = TRASH_RETENTION_DAYS) -> int:
    """
    Permanently deletes Notes that have been in trash for longer than the
    grace period. Connected NoteAttachment rows are removed automatically via
    on_delete=CASCADE, and each one's R2 object is cleaned up in turn via the
    post_delete signal.
    """
    cutoff = timezone.now() - timedelta(days=grace_period_days)
    trashed_notes = Note.objects.trashed().filter(trashed_at__lt=cutoff)

    total_notes_deleted = 0
    for note in trashed_notes:
        if _safe_delete(note):
            total_notes_deleted += 1

    logger.info(
        "Swept %s trashed notes older than %s days",
        total_notes_deleted,
        grace_period_days,
    )
    return total_notes_deleted


@shared_task(ignore_result=True)
def sweep_orphaned_attachments(grace_period_days: int = TRASH_RETENTION_DAYS) -> int:

    """
    Permanently deletes NoteAttachment rows (and their R2 objects) that have
    been orphaned for longer than the grace period.
    """
    cutoff = timezone.now() - timedelta(days=grace_period_days)
    orphaned = NoteAttachment.objects.filter(
        orphaned_at__isnull=False,
        orphaned_at__lt=cutoff,
    )

    count = 0
    for attachment in orphaned:
        if _safe_delete(attachment):
            count += 1

    logger.info(
        "Swept %s orphaned attachment(s) older than %s days", count, grace_period_days
    )
    return count
