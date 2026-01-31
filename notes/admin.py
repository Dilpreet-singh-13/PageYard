from django.contrib import admin

from .models import Note, Group


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_by', 'updated_at')
    readonly_fields = ('created_by', 'id')

    def save_model(self, request, obj: Note, form, change):
        # only add on first creation (it will have no ID)
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


admin.site.register(Group)