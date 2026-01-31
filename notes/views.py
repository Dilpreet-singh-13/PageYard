from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods

from .forms import NoteForm
from .models import Note, Group


# Create your views here.
def home_view(request):
    return render(request, 'notes/home_page.html')


@login_required()
def dashboard_view(request):
    recent_notes = Note.objects.filter(created_by=request.user).select_related('group').order_by('-updated_at')[:8]
    context = {
        'recent_notes': recent_notes,
    }
    return render(request, 'notes/dashboard.html', context)


@login_required()
def notes_list_view(request):
    notes_queryset = Note.objects.filter(created_by=request.user) \
        .select_related('group') \
        .order_by('-updated_at')

    # show 8 notes per page
    paginator = Paginator(notes_queryset, 8)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "notes_list": page_obj
    }
    # if request is sent by htmx, render the partial, otherwise render the full page
    # this replaces the "load more" div with the next 'n' notes from the paginator & adds a new load more button
    if request.htmx:
        return render(request, 'notes/partial_notes_list.html', context)

    return render(request, 'notes/notes_list.html', context)


@login_required()
def create_note_view(request):
    note = Note.objects.create(created_by=request.user)
    return redirect('notes:note_edit_page', note_id=note.id)


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
    note: Note = get_object_or_404(Note, id=note_id)
    groups = Group.objects.all()

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
def group_list_view(request):
    groups = Group.objects.all()
    context = {
        "groups": groups
    }
    return render(request, 'notes/groups.html', context)


@login_required()
@require_http_methods(["POST"])
def group_create_view(request):
    name = request.POST.get('name', 'Untitled')
    # TODO: see if using forms is better here or direct creation is better
    group = Group.objects.create(name=name)
    context = {
        'group': group
    }
    return render(request, 'notes/partial_group_item.html', context)


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
    return render(request, 'notes/partial_group_item.html', context)


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
        groups = Group.objects.filter(name__icontains=query).order_by("name")
    else:
        groups = Group.objects.all()

    context = {
        "groups": groups
    }
    return render(request, 'notes/partial_group_list.html', context)