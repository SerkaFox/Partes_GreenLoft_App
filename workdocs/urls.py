from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='workdocs_dashboard'),
    path('api/users/search/', views.user_search, name='workdocs_user_search'),
    path('tareas/', views.task_list, name='workdocs_task_list'),
    path('tareas/nueva/', views.task_create, name='workdocs_task_create'),
    path('tareas/<int:pk>/', views.task_detail, name='workdocs_task_detail'),
    path('tareas/<int:pk>/quick-status/', views.task_quick_status, name='workdocs_task_quick_status'),
    path('tareas/<int:pk>/estado/<slug:action>/', views.technician_status, name='workdocs_technician_status'),
    path('tecnicos/<int:pk>/', views.technician_detail, name='workdocs_technician_detail'),
    path('perfil/', views.profile, name='workdocs_profile'),
    path('usuarios/', views.user_list, name='workdocs_users'),
    path('usuarios/<int:pk>/editar/', views.user_edit, name='workdocs_user_edit'),
    path('usuarios/<int:pk>/toggle-active/', views.user_toggle_active, name='workdocs_user_toggle_active'),
    path('usuarios/<int:pk>/tareas/', views.user_tasks, name='workdocs_user_tasks'),
    path('vehiculos/', views.vehicles, name='workdocs_vehicles'),
    path('vehiculos/<int:pk>/', views.vehicles, name='workdocs_vehicle_edit'),
]
