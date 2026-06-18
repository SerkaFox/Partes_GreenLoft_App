from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/init-data/', views.init_data, name='init_data'),
    path('api/submit/', views.submit_parte, name='submit_parte'),
    path('panel/', views.panel_dashboard, name='panel_dashboard'),
    path('panel/login/', views.panel_login, name='panel_login'),
    path('panel/logout/', views.panel_logout, name='panel_logout'),
    path('panel/tecnicos/', views.panel_tecnicos, name='panel_tecnicos'),
    path('panel/tecnicos/<int:pk>/', views.panel_tecnicos, name='panel_tecnico_edit'),
    path('panel/vehiculos/', views.panel_vehiculos, name='panel_vehiculos'),
    path('panel/vehiculos/<int:pk>/', views.panel_vehiculos, name='panel_vehiculo_edit'),
    path('panel/proyectos/', views.panel_proyectos, name='panel_proyectos'),
    path('panel/proyectos/<int:pk>/', views.panel_proyectos, name='panel_proyecto_edit'),
    path('panel/partes/', views.panel_partes, name='panel_partes'),
    path('panel/partes/<int:pk>/', views.panel_parte_edit, name='panel_parte_edit'),
    path('panel/partes/<int:pk>/resend-email/', views.panel_resend_email, name='panel_resend_email'),
    path('panel/partes/export.csv', views.panel_export_csv, name='panel_export_csv'),
]
