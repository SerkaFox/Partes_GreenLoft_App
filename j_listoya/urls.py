from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('partes.urls')),
]

if 'workdocs' in settings.INSTALLED_APPS:
    urlpatterns.insert(1, path('trabajo/', include('workdocs.urls')))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
