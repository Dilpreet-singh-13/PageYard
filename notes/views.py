from django.contrib.postgres import search
import logging
import json
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Q, F
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.db.utils import IntegrityError
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.conf import settings
from botocore.exceptions import ClientError

from .storage import get_r2_client
from .forms import NoteForm, TagForm
from .models import Note, Tag, NoteAttachment
from .utils import _str_to_bool, htmx_toast, build_attachment_key
from .constants import (
    NOTES_PER_PAGE,
    SEARCH_NOTES_PER_PAGE,
    TAG_SEARCH_LIMIT,
    TRASH_RETENTION_DAYS,
)

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # to keep in sync with imageMaxSize in note_edit.html


def home_view(request):
    return render(request, "notes/home_page.html")


def privacy_policy_view(request):
    return render(request, "notes/privacy_policy.html")


@login_required()
def dashboard_view(request):
    logger.debug("Dashboard loaded for user %s", request.user.id)
    user_notes = Note.objects.by_user(request.user).active()

    recent_notes = (
        user_notes
        .prefetch_related("tags")
        .order_by("-updated_at")[:8]
    )
    starred_notes = (
        user_notes
        .filter(is_starred=True)
        .prefetch_related("tags")
        .order_by("-updated_at")[:8]
    )

    context = {
        "recent_notes": recent_notes,
        "starred_notes": starred_notes,
        "note_count": user_notes.count(),
        "starred_count": user_notes.filter(is_starred=True).count(),
        "tag_count": Tag.objects.filter(created_by=request.user).count(),
    }
    return render(request, "notes/dashboard.html", context)


@login_required()
def notes_list_view(request):
    notes_queryset = (
        Note.objects.by_user(request.user)
        .active()
        .prefetch_related("tags")
        .order_by("-updated_at")
    )

    # show NOTES_PER_PAGE notes per page
    paginator = Paginator(notes_queryset, NOTES_PER_PAGE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {"notes_list": page_obj}
    # if request is sent by htmx, render the partial, otherwise render the full page
    # this replaces the "load more" div with the next 'n' notes from the paginator & adds a new load more button
    if request.htmx:
        return render(request, "notes/partials/partial_notes_list.html", context)

    return render(request, "notes/notes_list.html", context)


@login_required()
def notes_search_view(request):
    """
    Search notes dynamically using PostgreSQL full-text search when available,
    or falling back to case-insensitive icontains matching for SQLite and other backends.
    """
    user_notes = (
        Note.objects.by_user(request.user)
        .active()
        .prefetch_related("tags")
        .order_by("-updated_at")
    )

    q = request.GET.get("q", "").strip()
    tag_id = request.GET.get("tag")
    is_starred = _str_to_bool(request.GET.get("is_starred"))
    title_only = _str_to_bool(request.GET.get("title_only"))
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    logger.debug("User %s searched notes with query '%s'", request.user.id, q)

    if q:
        if connection.vendor == "postgresql":
            if title_only:
                # Bypass the combined vector and do a text search on the title
                user_notes = user_notes.filter(title__search=q).order_by("-updated_at")
            else:
                # PostgreSQL GIN-indexed full-text search with rank scoring
                search_query = SearchQuery(q)
                user_notes = (
                    user_notes
                    .filter(search_vector=search_query)
                    .annotate(rank=SearchRank(F("search_vector"), search_query))
                    .order_by("-rank", "-updated_at")
                )
        else:
            # SQLite / standard DB fallback
            if title_only:
                user_notes = user_notes.filter(title__icontains=q)
            else:
                user_notes = user_notes.filter(
                    Q(title__icontains=q) | Q(raw_content__icontains=q)
                )

    if tag_id:
        user_notes = user_notes.filter(tags=tag_id)

    if is_starred:
        user_notes = user_notes.filter(is_starred=True)

    if start_date:
        user_notes = user_notes.filter(updated_at__date__gte=start_date)
    if end_date:
        user_notes = user_notes.filter(updated_at__date__lte=end_date)

    paginator = Paginator(user_notes, SEARCH_NOTES_PER_PAGE)
    notes_page_obj = paginator.get_page(request.GET.get("page", 1))

    context = {"notes_list": notes_page_obj}

    if request.htmx:
        return render(request, "notes/partials/partial_notes_list.html", context)

    context["user_tags"] = Tag.objects.filter(created_by=request.user)
    return render(request, "notes/notes_search.html", context)


@login_required()
def create_note_view(request):
    note = Note.objects.create(created_by=request.user)
    logger.info("User %s created a new note (ID: %s)", request.user, note.id)
    return redirect("notes:note_edit_page", note_id=note.id)


@login_required()
@require_http_methods(["DELETE"])
def delete_note_view(request, note_id: str):
    note = get_object_or_404(Note, id=note_id, created_by=request.user)
    redirect_url = (
        reverse("notes:note_trash_list_page")
        if note.is_trashed
        else reverse("notes:dashboard")
    )
    try:
        note.delete()
    except Exception:
        logger.exception("Failed to delete note %s", note_id)
        messages.error(request, "Could not delete note. Please try again.")
        response = HttpResponse(status=500)
        response["HX-Redirect"] = reverse(
            "notes:note_detail_page", kwargs={"note_id": note_id}
        )
        return response

    messages.success(request, "Note deleted successfully.")
    response = HttpResponse(status=204)
    response["HX-Redirect"] = redirect_url
    return response


@login_required()
@require_http_methods(["GET"])
def note_detail_view(request, note_id: str):
    # NOT IMPLEMENTED: ownership (rwequest.user == note.created.by) is not checked here so we can simply send the link and anyone can open that note
    # this hasn't been done as it would require makign sure the star button also only appers when is_owner == true and the star button is almost on every page...
    note: Note = get_object_or_404(Note, id=note_id, created_by=request.user)
    is_owner = note.created_by == request.user

    context = {
        "note": note,
        "is_owner": is_owner,
    }
    return render(request, "notes/note_detail.html", context)


@login_required()
@require_http_methods(["GET", "POST"])
def edit_note_page_view(request, note_id: str):
    note: Note = get_object_or_404(Note, id=note_id, created_by=request.user)
    tags = Tag.objects.filter(created_by=request.user)

    if request.method == "POST":
        form = NoteForm(request.POST, instance=note)
        if form.is_valid():
            note = form.save()

            # "raw_content" or any field here should be actually present in the model (ie Note)
            # so keep in sync with models.py
            if "raw_content" in form.changed_data:
                try:
                    note.sync_attachments()
                except Exception:
                    # we only log the exception but not fail the request!
                    # Future TODO: should we also save this somewhere to sync it up later?
                    # maybe put in a celery queue? or adding everything to celery queues will just bloat everything and we can
                    # simply assume it will work the next time someone saves the note
                    logger.exception("Attachment sync failed for note %s", note.id)

            logger.info("User %s updated note (ID: %s)", request.user.id, note.id)
            messages.success(request, "Note saved successfully.")
            return redirect("notes:note_detail_page", note_id=note.id)
        else:
            messages.error(request, "Could not save note. Please fix the errors below.")
    else:
        form = NoteForm(instance=note)

    context = {
        "note": note,
        "tags": tags,
        "form": form,
    }

    return render(request, "notes/note_edit.html", context)


@login_required()
@require_http_methods(["POST"])
def toggle_star_view(request, note_id: str):
    note = get_object_or_404(Note, id=note_id, created_by=request.user)
    try:
        note.is_starred = not note.is_starred
        note.save(update_fields=["is_starred", "updated_at"])
    except Exception:
        logger.exception("Failed to toggle star for note %s", note_id)
        return htmx_toast("Could not update star status. Please try again.")

    return render(request, "notes/partials/partial_star_button.html", {"note": note})


@login_required()
def note_trash_view(request, note_id: str):
    note = get_object_or_404(Note, id=note_id, created_by=request.user)

    try:
        note.trash()
        logger.info("User %s trashed note (ID: %s)", request.user.id, note.id)
    except Exception:
        logger.exception("Failed to trash note %s", note_id)
        return htmx_toast("Note could not be trashed. Please try again later")

    messages.success(
        request,
        f"Note added to trash successfully. You can recover it from the bin anytime for {TRASH_RETENTION_DAYS} days.",
    )
    response = HttpResponse(status=204)
    response["HX-Redirect"] = reverse("notes:dashboard")
    return response


@login_required()
def trash_list_view(request):
    trashed_notes = Note.objects.by_user(request.user).trashed()
    return render(request, "notes/trash.html", {"trashed_notes": trashed_notes})


@login_required()
@require_http_methods(["POST"])
def empty_trash_view(request):
    try:
        count, _ = Note.objects.by_user(request.user).trashed().delete()
        logger.info("User %s emptied trash (%s notes deleted)", request.user.id, count)
    except Exception:
        logger.exception("Failed to empty trash for user %s", request.user)
        return htmx_toast("Could not empty the bin. Please try again later.")

    messages.success(request, f"{count} note(s) permanently deleted.")
    response = HttpResponse(status=204)
    response["HX-Redirect"] = reverse("notes:note_trash_list_page")
    return response


@login_required()
@require_http_methods(["POST"])
def restore_note_view(request, note_id: str):
    note = get_object_or_404(
        Note, id=note_id, created_by=request.user, status=Note.Status.TRASH
    )
    try:
        note.restore()
        logger.info("User %s restored note (ID: %s)", request.user.id, note.id)
    except Exception:
        logger.exception("Failed to restore note %s", note_id)
        return htmx_toast("Note could not be restored. Please try again later.")

    messages.success(request, f"'{note.title}' restored successfully.")
    response = HttpResponse(status=204)
    response["HX-Redirect"] = reverse("notes:note_trash_list_page")
    return response


@login_required()
@require_http_methods(["GET"])
def note_tag_search_view(request, note_id: str):
    note = get_object_or_404(Note, id=note_id, created_by=request.user)
    query = request.GET.get("q", "").strip()

    existing_tag_ids = note.tags.values_list("id", flat=True)
    candidate_tags = Tag.objects.filter(created_by=request.user).exclude(
        id__in=existing_tag_ids
    )

    exact_match = False
    if query:
        candidate_tags = candidate_tags.filter(name__icontains=query)
        exact_match = Tag.objects.filter(
            created_by=request.user, name__iexact=query
        ).exists()

    context = {
        "note": note,
        "matching_tags": candidate_tags.order_by("name")[:TAG_SEARCH_LIMIT],
        "query": query,
        "exact_match": exact_match,
    }
    return render(request, "notes/partials/partial_tag_suggestions.html", context)


@login_required()
@require_http_methods(["POST"])
def note_tag_add_view(request, note_id: str):
    note = get_object_or_404(Note, id=note_id, created_by=request.user)

    tag_id = request.POST.get("tag_id", "").strip()
    tag_name = request.POST.get("tag_name", "").strip()

    tag = None
    if tag_id:
        tag = get_object_or_404(Tag, id=tag_id, created_by=request.user)
    elif tag_name:
        # case-insensitive dedup so "Chemistry" and "chemistry" don't split into two tags
        tag = Tag.objects.filter(created_by=request.user, name__iexact=tag_name).first()
        if tag is None:
            form = TagForm({"name": tag_name[:50]})
            if form.is_valid():
                try:
                    tag = form.save(commit=False)
                    tag.created_by = request.user
                    tag.save()
                except Exception:
                    logger.exception(
                        "Failed to create tag '%s' for note %s", tag_name, note_id
                    )
                    tag = None

    if tag is not None:
        note.tags.add(tag)
        logger.info("User %s added tag %s to note %s", request.user.id, tag.id, note.id)

    context = {"note": note, "is_owner": True}
    return render(request, "notes/partials/partial_note_tags.html", context)


@login_required()
@require_http_methods(["DELETE"])
def note_tag_remove_view(request, note_id: str, tag_id: str):
    note = get_object_or_404(Note, id=note_id, created_by=request.user)
    tag = get_object_or_404(Tag, id=tag_id, created_by=request.user)

    note.tags.remove(tag)
    logger.info("User %s removed tag %s from note %s", request.user.id, tag.id, note.id)
    return HttpResponse("")  # empty body removes the chip from the DOM


@login_required()
def tag_list_view(request):
    tags = Tag.objects.filter(created_by=request.user).order_by("name")
    context = {"tags": tags}
    return render(request, "notes/tags.html", context)


@login_required()
@require_http_methods(["POST"])
def tag_create_view(request):
    form = TagForm(request.POST)
    if not form.is_valid():
        error_msg = form.errors.get("name", ["Invalid tag name."])[0]
        logger.warning("Tag creation failed for user %s: %s", request.user.id, error_msg)
        return htmx_toast(error_msg)
    try:
        tag = form.save(commit=False)
        tag.created_by = request.user
        tag.save()
        logger.info("User %s created tag '%s' (ID: %s)", request.user.id, tag.name, tag.id)
    except IntegrityError:
        return htmx_toast(f"A tag named '{form.cleaned_data['name']}' already exists.")
    except Exception:
        logger.exception("Failed to create tag")
        return htmx_toast("Could not create tag. Please try again.")

    context = {"tag": tag}
    return render(request, "notes/partials/partial_tag_item.html", context)


@login_required()
@require_http_methods(["POST"])
def tag_edit_view(request, tag_id: str):
    tag = get_object_or_404(Tag, id=tag_id, created_by=request.user)
    form = TagForm(request.POST, instance=tag)

    if not form.is_valid():
        error_msg = form.errors.get("name", ["Invalid tag name."])[0]
        logger.warning("Tag edit failed for tag %s by user %s: %s", tag_id, request.user.id, error_msg)
        return htmx_toast(error_msg)

    try:
        tag = form.save()
        logger.info("User %s updated tag %s to name '%s'", request.user.id, tag.id, tag.name)
    except IntegrityError:
        return htmx_toast(f"A tag named '{form.cleaned_data['name']}' already exists.")
    except Exception:
        logger.exception("Failed to edit tag %s", tag_id)
        return htmx_toast("Could not update tag. Please try again.")

    context = {"tag": tag}
    return render(request, "notes/partials/partial_tag_item.html", context)


@login_required()
@require_http_methods(["DELETE"])
def tag_delete_view(request, tag_id: str):
    tag = get_object_or_404(Tag, id=tag_id, created_by=request.user)
    try:
        tag.delete()
        logger.info("User %s deleted tag (ID: %s)", request.user, tag.id)
    except Exception:
        logger.exception("Failed to delete tag %s", tag_id)
        return htmx_toast("Could not delete tag. Please try again.")

    return HttpResponse("")  # empty to remove element from DOM


@login_required()
@require_http_methods(["GET"])
def tag_search_view(request):
    query = request.GET.get("q", "").strip()
    if query:
        tags = Tag.objects.filter(
            name__icontains=query, created_by=request.user
        ).order_by("name")
    else:
        tags = Tag.objects.filter(created_by=request.user)

    context = {"tags": tags}
    return render(request, "notes/partials/partial_tag_list.html", context)


@login_required()
@require_POST
def note_attachment_presign(request, note_id: str):
    note = get_object_or_404(Note, id=note_id, created_by=request.user)

    try:
        body: dict = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        logger.warning(
            "Presign request from user %s had malformed JSON body", request.user.id
        )
        return JsonResponse({"error": "invalidRequest"}, status=400)

    filename: str = body.get("filename", "")
    mime_type: str = body.get("mime_type", "")

    try:
        file_size: int = int(body["size"])
    except (TypeError, ValueError, KeyError):
        logger.warning(
            "Presign request from user %s missing or invalid 'size' field",
            request.user.id,
        )
        return JsonResponse({"error": "invalidFileSize"}, status=400)

    if not filename:
        logger.warning("Presign request from user %s missing filename", request.user.id)
        return JsonResponse({"error": "noFileGiven"}, status=400)
    if mime_type not in ALLOWED_IMAGE_TYPES:
        logger.warning(
            "Presign request from user %s rejected: disallowed mime type '%s'",
            request.user.id,
            mime_type,
        )
        return JsonResponse({"error": "typeNotAllowed"}, status=415)
    if file_size > MAX_IMAGE_SIZE:
        logger.warning(
            "Presign request from user %s rejected: file too large (%d bytes)",
            request.user.id,
            file_size,
        )
        return JsonResponse({"error": "fileTooLarge"}, status=413)

    attachment = NoteAttachment.objects.create(
        note=note,
        uploaded_by=request.user,
        original_filename=filename,
        file_size=file_size,
        mime_type=mime_type,
    )

    object_key: str = build_attachment_key(
        user_id=request.user.id,
        note_id=note.id,
        attachment_id=attachment.id,
        filename=filename,
    )

    attachment.file.name = object_key
    attachment.save(update_fields=["file"])

    client = get_r2_client()

    try:
        upload_url: str = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                "Key": object_key,
                "ContentType": mime_type,
            },
            ExpiresIn=settings.AWS_ATTACHMENT_UPLOAD_EXPIRY,
        )
    except Exception:
        logger.exception(
            "Failed to generate presigned URL for attachment %s (note %s, user %s)",
            attachment.id,
            note_id,
            request.user.id,
        )
        attachment.delete()
        return JsonResponse({"error": "presignFailed"}, status=500)

    logger.info(
        "Presigned PUT URL generated: attachment %s for note %s by user %s",
        attachment.id,
        note_id,
        request.user.id,
    )

    complete_url = reverse(
        "notes:note_attachment_complete", kwargs={"attachment_id": attachment.id}
    )

    return JsonResponse(
        {
            "attachment_id": str(
                attachment.id
            ),  # not needed right now, might be neded for future features
            "upload_url": upload_url,
            "public_url": attachment.file.url,
            "complete_url": complete_url,
        }
    )


@login_required()
@require_POST
def note_attachment_complete(request, attachment_id: str):
    attachment: NoteAttachment = get_object_or_404(
        NoteAttachment, id=attachment_id, uploaded_by=request.user
    )

    if attachment.status != NoteAttachment.UploadStatus.PENDING:
        logger.warning(
            "Complete called on non-PENDING attachment %s (status=%s) by user %s",
            attachment_id,
            attachment.status,
            request.user.id,
        )
        return JsonResponse({"error": "alreadyCompleted"}, status=400)

    client = get_r2_client()

    try:
        client.head_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=attachment.file.name
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("404", "NoSuchKey", "NotFound"):
            logger.warning(
                "Complete called but file not found in R2 for attachment %s (key=%s)",
                attachment_id,
                attachment.file.name,
            )
            return JsonResponse({"error": "uploadMissing"}, status=400)

        logger.exception(
            "Unexpected R2 error during head_object for attachment %s", attachment_id
        )
        raise

    attachment.status = NoteAttachment.UploadStatus.COMPLETE
    attachment.save(update_fields=["status"])

    logger.info(
        "Attachment %s marked COMPLETE for note %s by user %s",
        attachment_id,
        attachment.note_id,
        request.user.id,
    )

    return JsonResponse(
        {
            "url": attachment.file.url,
            # unused right now, no alt text supported by easyMDE right now
            # "markdown": f"![{escape_markdown_alt(attachment.original_filename)}]({attachment.file.url})",
        }
    )
