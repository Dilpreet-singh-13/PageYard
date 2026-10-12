import json
from django.http import HttpResponse
from pathlib import Path
from .models import NoteAttachment
from botocore.exceptions import ClientError
from django.conf import settings
from .storage import get_r2_client


def _str_to_bool(val) -> bool:
    if val is None:
        return False
    return True if val.lower() in ("1", "true", "yes", "on", "y") else False


def htmx_toast(message, level="error", status=422):
    """Return an empty HTMX response that triggers a client-side toast."""
    response = HttpResponse(status=status)
    # HX-trigger sends both camelCase and kebab-case events and alpine listens to lowercase events by
    # default hence why we wrote show-toast instead of showToast
    response["HX-Trigger"] = json.dumps(
        {"showToast": {"message": message, "level": level}}
    )
    return response


def build_attachment_key(
    *,
    user_id: str,
    note_id: str,
    attachment_id: str,
    filename: str,
) -> str:
    """Builds the object key used for storing a NoteAttachment in object storage.

    Keys are organized by user and note to simplify exports, cleanup, and
    browsing within the bucket. The attachment UUID is used as the filename to
    guarantee uniqueness, while the original file extension is preserved.

    Example:
        public/images/[user_id]/[note_id]/[attachment_id].png

    Args:
        user_id (str): id of user creating the request
        note_id (str): id of the note where this image is being embedded/attached to
        attachment_id (str): unique uuid for the attachment
        filename (str): original file name of the file

    Returns:
        object key (str): objet key of the attachment
    """
    ext = Path(filename).suffix.lower()
    if not ext:
        raise ValueError("Uploaded filename must contain an extension.")

    return f"public/images/{user_id}/{note_id}/{attachment_id}{ext}"


def _r2_object_exists(key: str) -> bool:
    client = get_r2_client()
    try:
        client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise  # auth/network errors shouldn't be silently treated as "missing"


# Unused right now
# def escape_markdown_text(text: str) -> str:
#     """Escape characters that would break m arkdown image alt-text syntax."""
#     return text.replace("[", "\\[").replace("]", "\\]")
