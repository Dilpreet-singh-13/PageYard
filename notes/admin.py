from django.contrib import admin

from .models import Note, Tag, NoteAttachment


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("title", "created_by", "updated_at")
    readonly_fields = ("created_by", "id")

    # so creating notes will work directly from the admin dashbaord
    def save_model(self, request, obj: Note, form, change):
        # only add on first creation (it will have no ID)
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(NoteAttachment)
class NoteAttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "note", "status", "orphaned_at", "created_at")
    list_filter = ("status", "orphaned_at")
    search_fields = ("original_filename", "note__title")
    readonly_fields = ("id", "created_at", "file_size", "mime_type")


admin.site.register(Tag)
