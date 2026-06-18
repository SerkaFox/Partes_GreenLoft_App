from io import BytesIO
from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from partes.models import Vehiculo

from .models import Task, TaskEvent, TaskFile, TaskVoiceReport, UserProfile

User = get_user_model()


def _resized_image(uploaded, max_size=(512, 512)):
    if not uploaded:
        return uploaded
    image = Image.open(uploaded)
    image = ImageOps.exif_transpose(image)
    if image.mode not in ('RGB', 'L'):
        background = Image.new('RGB', image.size, '#ffffff')
        if image.mode in ('RGBA', 'LA'):
            background.paste(image, mask=image.getchannel('A'))
        else:
            background.paste(image)
        image = background
    else:
        image = image.convert('RGB')
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, format='JPEG', quality=82, optimize=True)
    name = f'{Path(uploaded.name).stem[:80]}.jpg'
    return ContentFile(output.getvalue(), name=name)


class BootstrapMixin:
    def _bootstrap(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault('class', 'form-control')
            else:
                widget.attrs.setdefault('class', 'form-control')


class TaskForm(BootstrapMixin, forms.ModelForm):
    technicians = forms.ModelMultipleChoiceField(
        label='Técnicos asignados',
        queryset=User.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'technicians-select d-none'}),
    )

    class Meta:
        model = Task
        fields = ['title', 'description', 'address', 'latitude', 'longitude', 'assigned_to', 'technicians', 'vehicle', 'status']
        labels = {
            'title': 'Título',
            'description': 'Descripción',
            'address': 'Dirección o nombre del lugar',
            'latitude': 'Latitud',
            'longitude': 'Longitud',
            'assigned_to': 'Técnico asignado',
            'vehicle': 'Vehículo',
            'status': 'Estado',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'assigned_to': forms.HiddenInput(),
            'vehicle': forms.Select(attrs={'class': 'vehicle-select d-none'}),
        }

    def __init__(self, *args, **kwargs):
        role = kwargs.pop('role', '')
        super().__init__(*args, **kwargs)
        self._bootstrap()
        technicians = User.objects.filter(work_profile__role=UserProfile.ROLE_TECHNICIAN, is_active=True).order_by('first_name', 'username')
        self.fields['assigned_to'].queryset = technicians
        self.fields['technicians'].queryset = technicians
        self.fields['vehicle'].queryset = Vehiculo.objects.filter(activo=True).order_by('orden', 'matricula')
        self.fields['assigned_to'].required = False
        self.fields['vehicle'].required = False
        self.fields['technicians'].label_from_instance = lambda user: user.get_full_name() or user.get_username()
        self.fields['assigned_to'].label_from_instance = lambda user: user.get_full_name() or user.get_username()
        self.fields['vehicle'].label_from_instance = lambda vehicle: f'{vehicle.matricula} {vehicle.descripcion}'.strip()
        if self.instance and self.instance.pk and not self.is_bound:
            selected = list(self.instance.technicians.all())
            if self.instance.assigned_to and self.instance.assigned_to not in selected:
                selected.insert(0, self.instance.assigned_to)
            self.fields['technicians'].initial = selected
        if role == UserProfile.ROLE_TECHNICIAN:
            for field in self.fields.values():
                field.disabled = True

    def save(self, commit=True):
        task = super().save(commit=False)
        technicians = list(self.cleaned_data.get('technicians') or [])
        task.assigned_to = technicians[0] if technicians else None
        if commit:
            task.save()
            self.save_m2m()
            task.technicians.set(technicians)
        return task


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class TaskFileForm(BootstrapMixin, forms.ModelForm):
    files = forms.FileField(
        label='Archivos',
        widget=MultiFileInput(attrs={'multiple': True}),
        required=True,
    )

    class Meta:
        model = TaskFile
        fields = ['comment']
        labels = {'comment': 'Comentario'}
        widgets = {'comment': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bootstrap()


class CommentForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = TaskEvent
        fields = ['comment']
        labels = {'comment': 'Comentario'}
        widgets = {'comment': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bootstrap()


class VoiceReportForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = TaskVoiceReport
        fields = ['audio_file']
        labels = {'audio_file': 'Audio'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bootstrap()
        self.fields['audio_file'].widget.attrs.update({'accept': 'audio/*'})


class ProfileForm(BootstrapMixin, forms.Form):
    first_name = forms.CharField(label='Nombre', required=False)
    last_name = forms.CharField(label='Apellidos', required=False)
    email = forms.EmailField(label='Email', required=False)
    avatar = forms.ImageField(label='Avatar', required=False)
    description = forms.CharField(label='Descripción', required=False, widget=forms.Textarea(attrs={'rows': 4}))
    password = forms.CharField(label='Nueva contraseña', required=False, widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        super().__init__(*args, **kwargs)
        self.fields['first_name'].initial = self.user.first_name
        self.fields['last_name'].initial = self.user.last_name
        self.fields['email'].initial = self.user.email
        self.fields['description'].initial = self.profile.description
        self._bootstrap()

    def save(self):
        self.user.first_name = self.cleaned_data.get('first_name', '')
        self.user.last_name = self.cleaned_data.get('last_name', '')
        self.user.email = self.cleaned_data.get('email', '')
        password = self.cleaned_data.get('password')
        if password:
            self.user.set_password(password)
        self.user.save()
        self.profile.description = self.cleaned_data.get('description', '')
        if self.cleaned_data.get('avatar'):
            self.profile.avatar = _resized_image(self.cleaned_data['avatar'])
        self.profile.save()
        return self.user


class UserCreateForm(BootstrapMixin, forms.Form):
    username = forms.CharField(label='Usuario')
    first_name = forms.CharField(label='Nombre', required=False)
    last_name = forms.CharField(label='Apellidos', required=False)
    email = forms.EmailField(label='Email', required=False)
    role = forms.ChoiceField(label='Rol', choices=UserProfile.ROLE_CHOICES)
    avatar = forms.ImageField(label='Avatar', required=False)
    description = forms.CharField(label='Descripción', required=False, widget=forms.Textarea(attrs={'rows': 3}))
    active = forms.BooleanField(label='Activo', required=False, initial=True)
    vehicle = forms.ModelChoiceField(label='Vehículo', queryset=None, required=False)
    password = forms.CharField(label='Contraseña', widget=forms.PasswordInput, initial='111')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehicle'].queryset = self._vehicle_queryset()
        self._bootstrap()

    def _vehicle_queryset(self):
        vehicle_field = UserProfile._meta.get_field('vehicle')
        return vehicle_field.remote_field.model.objects.all()

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este usuario ya existe.')
        return username

    def save(self):
        active = self.cleaned_data.get('active', True)
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data.get('first_name', ''),
            last_name=self.cleaned_data.get('last_name', ''),
            email=self.cleaned_data.get('email', ''),
            is_active=active,
        )
        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'role': self.cleaned_data['role'],
                'avatar': _resized_image(self.cleaned_data.get('avatar')),
                'description': self.cleaned_data.get('description', ''),
                'active': active,
                'vehicle': self.cleaned_data.get('vehicle'),
            },
        )
        return user


class UserEditForm(BootstrapMixin, forms.Form):
    username = forms.CharField(label='Usuario')
    first_name = forms.CharField(label='Nombre', required=False)
    last_name = forms.CharField(label='Apellidos', required=False)
    email = forms.EmailField(label='Email', required=False)
    role = forms.ChoiceField(label='Rol', choices=UserProfile.ROLE_CHOICES)
    avatar = forms.ImageField(label='Avatar', required=False)
    description = forms.CharField(label='Descripción', required=False, widget=forms.Textarea(attrs={'rows': 4}))
    active = forms.BooleanField(label='Activo', required=False)
    vehicle = forms.ModelChoiceField(label='Vehículo', queryset=None, required=False)
    password = forms.CharField(label='Nueva contraseña', required=False, widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        self.actor = kwargs.pop('actor', None)
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        super().__init__(*args, **kwargs)
        self.fields['vehicle'].queryset = UserProfile._meta.get_field('vehicle').remote_field.model.objects.all()
        if not self.is_bound:
            self.fields['username'].initial = self.user.username
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email
            self.fields['role'].initial = self.profile.role
            self.fields['description'].initial = self.profile.description
            self.fields['active'].initial = self.profile.active and self.user.is_active
            self.fields['vehicle'].initial = self.profile.vehicle
        self._bootstrap()

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.exclude(pk=self.user.pk).filter(username=username).exists():
            raise forms.ValidationError('Este usuario ya existe.')
        return username

    def clean_active(self):
        active = self.cleaned_data.get('active', False)
        if self.actor and self.actor.pk == self.user.pk and not active:
            raise forms.ValidationError('No puedes desactivar tu propia cuenta.')
        return active

    def save(self):
        active = self.cleaned_data.get('active', False)
        self.user.username = self.cleaned_data['username']
        self.user.first_name = self.cleaned_data.get('first_name', '')
        self.user.last_name = self.cleaned_data.get('last_name', '')
        self.user.email = self.cleaned_data.get('email', '')
        self.user.is_active = active
        password = self.cleaned_data.get('password')
        if password:
            self.user.set_password(password)
        self.user.save()
        self.profile.role = self.cleaned_data['role']
        self.profile.description = self.cleaned_data.get('description', '')
        self.profile.active = active
        self.profile.vehicle = self.cleaned_data.get('vehicle')
        if self.cleaned_data.get('avatar'):
            self.profile.avatar = _resized_image(self.cleaned_data['avatar'])
        self.profile.save()
        return self.user
