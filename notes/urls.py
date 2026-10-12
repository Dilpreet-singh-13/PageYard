from django.urls import path

from . import views

app_name = "notes"
urlpatterns = [
    path('', views.home_view, name='home'),
    path('privacy-policy/', views.privacy_policy_view, name='privacy_policy_page'),
    path('pages/', views.dashboard_view, name='dashboard'),
    path('pages/all/', views.notes_list_view, name='all_notes_view'),
    path('pages/search/', views.notes_search_view, name='notes_search_page'),
    path('pages/new/', views.create_note_view, name='new_note_page'),
    path('pages/trash/', views.trash_list_view, name="note_trash_list_page"),
    path('pages/trash/empty/', views.empty_trash_view, name="empty_trash_page"),
    path('pages/<str:note_id>/', views.note_detail_view, name='note_detail_page'),
    path('pages/<str:note_id>/toggle-star/', views.toggle_star_view, name='toggle_star_page'),
    path('pages/<str:note_id>/tags/search/', views.note_tag_search_view, name='note_tag_search_page'),
    path('pages/<str:note_id>/tags/add/', views.note_tag_add_view, name='note_tag_add_page'),
    path('pages/<str:note_id>/tags/<str:tag_id>/remove/', views.note_tag_remove_view, name='note_tag_remove_page'),
    path('pages/<str:note_id>/edit/', views.edit_note_page_view, name='note_edit_page'),
    path('pages/<str:note_id>/trash/', views.note_trash_view, name="trash_note_page"),
    path('pages/<str:note_id>/restore/', views.restore_note_view, name="restore_note_page"),
    path('pages/<str:note_id>/delete/', views.delete_note_view, name='note_delete_page'),
    path("attachments/<str:note_id>/presign/", views.note_attachment_presign, name="note_attachment_presign"),
    path("attachments/<str:attachment_id>/complete/", views.note_attachment_complete, name="note_attachment_complete"),
    path('tags/', views.tag_list_view, name='tag_list_page'),
    path('tags/new/', views.tag_create_view, name='tag_create_page'),
    path('tags/search/', views.tag_search_view, name='tag_search_page'),
    path('tags/<str:tag_id>/edit/', views.tag_edit_view, name='tag_edit_page'),
    path('tags/<str:tag_id>/delete/', views.tag_delete_view, name='tag_delete_page'),

]