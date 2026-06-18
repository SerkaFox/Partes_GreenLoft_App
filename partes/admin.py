from django.contrib import admin

from .models import ParteTrabajo, ParteTrabajoFoto, Proyecto, Tecnico, Vehiculo


@admin.register(Tecnico)
class TecnicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ('matricula', 'activo')
    list_filter = ('activo',)
    search_fields = ('matricula',)


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'cliente', 'obra', 'activo')
    list_filter = ('activo',)
    search_fields = ('codigo', 'cliente', 'obra')


@admin.register(ParteTrabajo)
class ParteTrabajoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tecnico', 'jornada', 'cliente', 'obra', 'created_at')
    list_filter = ('jornada', 'fecha', 'created_at')
    search_fields = ('tecnico__nombre', 'cliente', 'obra', 'trabajos', 'materiales')
    readonly_fields = ('created_at', 'pdf_file')


@admin.register(ParteTrabajoFoto)
class ParteTrabajoFotoAdmin(admin.ModelAdmin):
    list_display = ('parte', 'original_name', 'created_at')
    search_fields = ('parte__tecnico_nombre_snapshot', 'original_name')
    readonly_fields = ('created_at',)
