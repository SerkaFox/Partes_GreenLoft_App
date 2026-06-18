import uuid
from pathlib import Path

from django.db import models
from django.utils import timezone


class Tecnico(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    email = models.EmailField(blank=True)
    activo = models.BooleanField(default=True)
    puede_ser_tecnico = models.BooleanField(default=True)
    puede_ser_companero = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = 'Trabajador / Técnico'
        verbose_name_plural = 'Trabajadores / Técnicos'

    def __str__(self):
        return self.nombre


class Vehiculo(models.Model):
    matricula = models.CharField(max_length=60, unique=True)
    descripcion = models.CharField(max_length=180, blank=True)
    image = models.ImageField(upload_to='vehicles/', blank=True, null=True)
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'matricula']
        verbose_name = 'Vehículo'
        verbose_name_plural = 'Vehículos'

    def __str__(self):
        return self.matricula


class Proyecto(models.Model):
    codigo = models.CharField(max_length=80, unique=True)
    cliente = models.CharField(max_length=200)
    obra = models.CharField(max_length=250)
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'codigo']
        verbose_name = 'Proyecto/Obra'
        verbose_name_plural = 'Proyectos/Obras'

    def __str__(self):
        return f'{self.codigo} - {self.cliente}'


class ParteTrabajo(models.Model):
    JORNADA_NORMAL = 'normal'
    JORNADA_INTENSIVA = 'intensiva'
    JORNADA_CHOICES = [
        (JORNADA_NORMAL, 'Normal - 1h comida'),
        (JORNADA_INTENSIVA, 'Intensiva'),
    ]

    tecnico = models.ForeignKey(Tecnico, on_delete=models.PROTECT, related_name='partes')
    tecnico_nombre_snapshot = models.CharField(max_length=150, blank=True)
    tecnico_email_snapshot = models.EmailField(blank=True)
    fecha = models.DateField()
    hora_llegada = models.TimeField()
    hora_salida = models.TimeField()
    jornada = models.CharField(max_length=20, choices=JORNADA_CHOICES)
    companero = models.ForeignKey(
        Tecnico,
        on_delete=models.PROTECT,
        related_name='partes_como_companero',
        blank=True,
        null=True,
    )
    companero_text = models.CharField(max_length=150, blank=True)
    matricula = models.ForeignKey(Vehiculo, on_delete=models.PROTECT, blank=True, null=True)
    conductor = models.BooleanField(default=False)
    entrada_obra = models.TimeField(blank=True, null=True)
    salida_obra = models.TimeField(blank=True, null=True)
    hora_comida = models.TimeField(blank=True, null=True)
    gastos = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.PROTECT)
    id_snapshot = models.CharField(max_length=80, blank=True)
    cliente_snapshot = models.CharField(max_length=200, blank=True)
    obra_snapshot = models.CharField(max_length=250, blank=True)
    trabajos_realizados = models.TextField(blank=True)
    trabajos_admin = models.TextField(blank=True)
    materiales_instalados = models.TextField(blank=True)

    # Legacy fields kept for a safe migration from the first version.
    cliente = models.CharField(max_length=200, blank=True)
    obra = models.CharField(max_length=250, blank=True)
    trabajos = models.TextField(blank=True)
    admin = models.TextField(blank=True)
    materiales = models.TextField(blank=True)

    pdf_file = models.FileField(upload_to='partes/', blank=True)
    csv_file = models.FileField(upload_to='partes_csv/', blank=True)
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(blank=True, null=True)
    email_error = models.TextField(blank=True)
    google_sheets_sent = models.BooleanField(default=False)
    google_sheets_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Parte de trabajo'
        verbose_name_plural = 'Partes de trabajo'

    def __str__(self):
        return f'Parte {self.fecha} - {self.tecnico_nombre_snapshot or self.tecnico}'

    @property
    def jornada_label(self):
        return dict(self.JORNADA_CHOICES).get(self.jornada, self.jornada)

    @property
    def vehiculo_text(self):
        return self.matricula.matricula if self.matricula else ''



def parte_photo_upload_to(instance, filename):
    suffix = Path(filename).suffix.lower()[:12] or '.jpg'
    now = instance.created_at or timezone.now()
    return f'parte_photos/{now:%Y/%m/%d}/{uuid.uuid4().hex}{suffix}'


class ParteTrabajoFoto(models.Model):
    parte = models.ForeignKey(ParteTrabajo, on_delete=models.CASCADE, related_name='fotos')
    image = models.ImageField(upload_to=parte_photo_upload_to)
    original_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Foto de parte'
        verbose_name_plural = 'Fotos de partes'

    def __str__(self):
        return f'Foto parte #{self.parte_id}'
