from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from notes.models import Note, Group


@login_required
def profile_view(request):
    context = {
        'note_count': Note.objects.filter(created_by=request.user).count(),
        'group_count': Group.objects.filter(created_by=request.user).count(),
    }
    return render(request, 'profile.html', context)


@login_required()
@require_http_methods(["DELETE"])
def delete_account_view(request):
    user = request.user
    logout(request)
    user.delete()

    messages.success(request, "Your account and all associated data have been permanently deleted.")

    return redirect('notes:home')