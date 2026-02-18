from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import NoteForm
from .models import Note, Group


@login_required()
def home_view(request):
    return render(request, 'notes/home_page.html')


@login_required()
def dashboard_view(request):
    recent_notes = Note.objects.filter(created_by=request.user).select_related('group').order_by('-updated_at')[:8]
    starred_notes = Note.objects.filter(created_by=request.user, is_starred=True).select_related('group').order_by(
        '-updated_at')[:8]

    # we extract 8 notes per group FOR all groups
    groups = Group.objects.filter(created_by=request.user).distinct()
    for group in groups:
        # the preview_notes list can be used on the frontend to loop through each note for that group
        group.preview_notes = (
            group.notes.filter(created_by=request.user).order_by("-updated_at")[:8]
        )

    context = {
        'recent_notes': recent_notes,
        'starred_notes': starred_notes,
        'groups_with_notes': groups
    }
    return render(request, 'notes/dashboard.html', context)


@login_required()
def notes_list_view(request):
    notes_queryset = Note.objects.filter(created_by=request.user) \
        .select_related('group') \
        .order_by('-updated_at')

    # show 8 notes per page
    paginator = Paginator(notes_queryset, 8)
    page_number = int(request.GET.get('page', 1))
    page_obj = paginator.get_page(page_number)

    context = {
        "notes_list": page_obj
    }
    # if request is sent by htmx, render the partial, otherwise render the full page
    # this replaces the "load more" div with the next 'n' notes from the paginator & adds a new load more button
    if request.htmx:
        return render(request, 'notes/partials/partial_notes_list.html', context)

    return render(request, 'notes/notes_list.html', context)


@login_required()
def notes_search_view(request):
    # TODO: see if we can optimise the initial loading of all notes objects, instead only load for a specific filter
    # but we would have to handle normal page loading too so yeah...

    user_groups = Group.objects.filter(created_by=request.user)
    user_notes = Note.objects.filter(created_by=request.user).select_related('group').order_by("-updated_at")

    # use search query & apply filters
    q = request.GET.get('q', '').strip()
    group_id = request.GET.get('group')
    is_starred = request.GET.get('is_starred')
    title_only = request.GET.get('title_only')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if q:
        if title_only:
            user_notes = user_notes.filter(title__icontains=q)
        else:
            user_notes = user_notes.filter(Q(title__icontains=q) | Q(raw_content__icontains=q))

    if group_id:
        user_notes = user_notes.filter(group=group_id)

    if is_starred:
        user_notes = user_notes.filter(is_starred=True)

    if start_date:
        user_notes = user_notes.filter(updated_at__date__gte=start_date)
    if end_date:
        user_notes = user_notes.filter(updated_at__date__lte=end_date)

    paginator = Paginator(user_notes, 16)
    page_numer = int(request.GET.get('page', 1))
    notes_page_obj = paginator.get_page(page_numer)

    context = {
        "notes_list": notes_page_obj
    }
    if request.htmx:
        return render(request, 'notes/partials/partial_notes_list.html', context)

    context["user_groups"] = user_groups  # only needed if normal GET request for full page
    return render(request, 'notes/notes_search.html', context)


@login_required()
def create_note_view(request):
    note = Note.objects.create(created_by=request.user)
    return redirect('notes:note_edit_page', note_id=note.id)


@login_required()
@require_http_methods(["DELETE"])
def delete_note_view(request, note_id: str):
    note = get_object_or_404(Note, id=note_id, created_by=request.user)
    note.delete()
    # this makes it so HTMX sends a GET request to the dashboard
    # as normal redirect() would have used sent a DELETE request to the dashboard page instead of GET
    response = HttpResponse(status=204)
    response["HX-Redirect"] = reverse("notes:dashboard")
    return response


@require_http_methods(["GET"])
@login_required()
def note_detail_view(request, note_id: str):
    note: Note = get_object_or_404(Note, id=note_id)

    context = {
        "note": note
    }
    return render(request, 'notes/note_detail.html', context)


@require_http_methods(["GET", "POST"])
@login_required()
def edit_note_page_view(request, note_id: str):
    note: Note = get_object_or_404(Note, id=note_id, created_by=request.user)
    groups = Group.objects.filter(created_by=request.user)

    if request.method == "POST":
        form = NoteForm(request.POST, instance=note)
        if form.is_valid():
            note = form.save()
            # TODO: success toast here
            return redirect('notes:note_detail_page', note_id=note.id)  # redirect prevents duplicate save

    context = {
        "note": note,
        "groups": groups,
        "form": NoteForm(instance=note)  # included for error displaying
    }

    return render(request, 'notes/note_edit.html', context)


@login_required()
@require_http_methods(["POST"])
def toggle_star_view(request, note_id: str):
    note = get_object_or_404(Note, id=note_id, created_by=request.user)

    note.is_starred = not note.is_starred
    note.save()

    return render(request, 'notes/partials/partial_star_button.html', {"note": note})


@login_required()
def group_list_view(request):
    groups = Group.objects.filter(created_by=request.user).order_by("name")
    context = {
        "groups": groups
    }
    return render(request, 'notes/groups.html', context)


@login_required()
@require_http_methods(["POST"])
def group_create_view(request):
    name = request.POST.get('name', 'Untitled')
    # TODO: see if using forms is better here or direct creation is better
    group = Group.objects.create(name=name, created_by=request.user)
    context = {
        'group': group
    }
    return render(request, 'notes/partials/partial_group_item.html', context)


@login_required()
@require_http_methods(["POST"])
def group_edit_view(request, group_id: str):
    """Saves the edited group"""
    group = get_object_or_404(Group, id=group_id)

    new_name = request.POST.get('name', 'untitled').strip()
    if len(new_name) < 1:
        new_name = 'untitled'
    group.name = new_name
    group.save()

    context = {
        "group": group
    }
    return render(request, 'notes/partials/partial_group_item.html', context)


@login_required()
@require_http_methods(["DELETE"])
def group_delete_view(request, group_id: str):
    group = get_object_or_404(Group, id=group_id)
    group.delete()
    return HttpResponse("")  # empty to remove element from DOM


@login_required()
@require_http_methods(["GET"])
def group_search_view(request):
    query = request.GET.get('q', '').strip()
    if query:
        groups = Group.objects.filter(name__icontains=query, created_by=request.user).order_by("name")
    else:
        groups = Group.objects.filter(created_by=request.user)

    context = {
        "groups": groups
    }
    return render(request, 'notes/partials/partial_group_list.html', context)