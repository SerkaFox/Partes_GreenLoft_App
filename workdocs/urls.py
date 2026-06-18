from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='workdocs_dashboard'),
    path('tareas/', views.task_list, name='workdocs_task_list'),
    path('tareas/nueva/', views.task_create, name='workdocs_task_create'),
    path('tareas/<int:pk>/', views.task_detail, name='workdocs_task_detail'),
    path('tareas/<int:pk>/estado/<slug:action>/', views.technician_status, name='workdocs_technician_status'),
    path('perfil/', views.profile, name='workdocs_profile'),
    path('usuarios/', views.user_list, name='workdocs_users'),
]
