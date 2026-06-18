import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_ADMIN = 'admin'
    ROLE_MANAGER = 'manager'
    ROLE_TECHNICIAN = 'technician'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MANAGER, 'Manager'),
        (ROLE_TECHNICIAN, 'Technician'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='work_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_TECHNICIAN)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    vehicle = models.ForeignKey('partes.Vehiculo', blank=True, null=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = 'Perfil de trabajo'
        verbose_name_plural = 'Perfiles de trabajo'

    def __str__(self):
        return f'{self.user.get_username()} - {self.get_role_display()}'


def _safe_upload_path(prefix, filename):
    suffix = Path(filename).suffix.lower()[:16]
    return f'{prefix}/{timezone.now():%Y/%m/%d}/{uuid.uuid4().hex}{suffix}'


def task_file_upload_to(instance, filename):
    return _safe_upload_path('workdocs/files', filename)


def voice_report_upload_to(instance, filename):
    return _safe_upload_path('workdocs/audio', filename)


class Task(models.Model):
    STATUS_NUEVA = 'NUEVA'
    STATUS_ASIGNADA = 'ASIGNADA'
    STATUS_EN_CAMINO = 'EN_CAMINO'
    STATUS_EN_OBJETO = 'EN_OBJETO'
    STATUS_EN_PROCESO = 'EN_PROCESO'
    STATUS_PENDIENTE_REVISION = 'PENDIENTE_REVISION'
    STATUS_FINALIZADA = 'FINALIZADA'
    STATUS_CANCELADA = 'CANCELADA'
    STATUS_CHOICES = [
        (STATUS_NUEVA, 'Nueva'),
        (STATUS_ASIGNADA, 'Asignada'),
        (STATUS_EN_CAMINO, 'En camino'),
        (STATUS_EN_OBJETO, 'En objeto'),
        (STATUS_EN_PROCESO, 'En proceso'),
        (STATUS_PENDIENTE_REVISION, 'Pendiente revisión'),
        (STATUS_FINALIZADA, 'Finalizada'),
        (STATUS_CANCELADA, 'Cancelada'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_NUEVA)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_work_tasks')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assigned_work_tasks',
        blank=True,
        null=True,
    )
    technicians = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='technician_tasks',
        blank=True,
        limit_choices_to={'work_profile__role': UserProfile.ROLE_TECHNICIAN},
    )
    vehicle = models.ForeignKey('partes.Vehiculo', blank=True, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(blank=True, null=True)
    arrived_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-updated_at', '-created_at']
        verbose_name = 'Tarea'
        verbose_name_plural = 'Tareas'

    def __str__(self):
        return self.title

    @property
    def has_new_documents(self):
        return self.files.filter(created_at__gte=self.updated_at).exists()

    @property
    def is_open(self):
        return self.status not in {self.STATUS_FINALIZADA, self.STATUS_CANCELADA}

    @property
    def assigned_technicians(self):
        technicians = list(self.technicians.all())
        if self.assigned_to and self.assigned_to not in technicians:
            technicians.insert(0, self.assigned_to)
        return technicians


class TaskFile(models.Model):
    TYPE_PHOTO = 'photo'
    TYPE_PDF = 'pdf'
    TYPE_VIDEO = 'video'
    TYPE_DOCUMENT = 'document'
    TYPE_AUDIO = 'audio'
    TYPE_OTHER = 'other'
    FILE_TYPE_CHOICES = [
        (TYPE_PHOTO, 'Foto'),
        (TYPE_PDF, 'PDF'),
        (TYPE_VIDEO, 'Vídeo'),
        (TYPE_DOCUMENT, 'Documento'),
        (TYPE_AUDIO, 'Audio'),
        (TYPE_OTHER, 'Otro'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='files')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='uploaded_task_files')
    file = models.FileField(upload_to=task_file_upload_to)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default=TYPE_OTHER)
    original_name = models.CharField(max_length=255, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Archivo de tarea'
        verbose_name_plural = 'Archivos de tareas'

    def __str__(self):
        return self.original_name or self.file.name

    @property
    def is_image(self):
        return self.file_type == self.TYPE_PHOTO

    @property
    def is_audio(self):
        return self.file_type == self.TYPE_AUDIO

    @property
    def is_video(self):
        return self.file_type == self.TYPE_VIDEO


class TaskVoiceReport(models.Model):
    TRANSCRIPT_PENDING = 'pending'
    TRANSCRIPT_PROCESSING = 'processing'
    TRANSCRIPT_DONE = 'done'
    TRANSCRIPT_ERROR = 'error'
    TRANSCRIPT_CHOICES = [
        (TRANSCRIPT_PENDING, 'Pendiente'),
        (TRANSCRIPT_PROCESSING, 'Transcribiendo'),
        (TRANSCRIPT_DONE, 'Hecho'),
        (TRANSCRIPT_ERROR, 'Error'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='voice_reports')
    technician = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='voice_reports')
    audio_file = models.FileField(upload_to=voice_report_upload_to)
    transcript_text = models.TextField(blank=True)
    transcript_status = models.CharField(max_length=20, choices=TRANSCRIPT_CHOICES, default=TRANSCRIPT_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Informe de voz'
        verbose_name_plural = 'Informes de voz'

    def __str__(self):
        return f'Informe de voz #{self.pk} - {self.task}'


class TaskEvent(models.Model):
    EVENT_CREATED = 'created'
    EVENT_ASSIGNED = 'assigned'
    EVENT_STATUS = 'status'
    EVENT_FILE = 'file'
    EVENT_COMMENT = 'comment'
    EVENT_AUDIO = 'audio'
    EVENT_CHOICES = [
        (EVENT_CREATED, 'Creada'),
        (EVENT_ASSIGNED, 'Asignada'),
        (EVENT_STATUS, 'Estado'),
        (EVENT_FILE, 'Archivo'),
        (EVENT_COMMENT, 'Comentario'),
        (EVENT_AUDIO, 'Audio'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='events')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='task_events')
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Evento de tarea'
        verbose_name_plural = 'Eventos de tareas'

    def __str__(self):
        return f'{self.get_event_type_display()} - {self.task}'
