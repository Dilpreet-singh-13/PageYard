from django.urls import path

from . import views

app_name = "notes"
urlpatterns = [
    path('', views.home_view, name='home'),
    path('notes/', views.dashboard_view, name='dashboard'),
    path('notes/all/', views.notes_list_view, name='all_notes_view'),
    path('notes/search/', views.notes_search_view, name='notes_search_page'),
    path('notes/new/', views.create_note_view, name='new_note_page'),
    path('notes/<str:note_id>/', views.note_detail_view, name='note_detail_page'),
    path('notes/<str:note_id>/edit/', views.edit_note_page_view, name='note_edit_page'),
    path('notes/<str:note_id>/delete/', views.delete_note_view, name='note_delete_page'),
    path('notes/<str:note_id>/toggle-star/', views.toggle_star_view, name='toggle_star_page'),
    path('groups/', views.group_list_view, name='group_list_page'),
    path('groups/new/', views.group_create_view, name='group_create_page'),
    path('groups/search/', views.group_search_view, name='group_search_page'),
    path('groups/<str:group_id>/edit/', views.group_edit_view, name='group_edit_page'),
    path('groups/<str:group_id>/delete/', views.group_delete_view, name='group_delete_page'),

]