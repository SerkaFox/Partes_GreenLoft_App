from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm

from .models import Task, TaskEvent, TaskFile, TaskVoiceReport, UserProfile

User = get_user_model()


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
    class Meta:
        model = Task
        fields = ['title', 'description', 'address', 'latitude', 'longitude', 'assigned_to', 'status']
        labels = {
            'title': 'Título',
            'description': 'Descripción',
            'address': 'Dirección',
            'latitude': 'Latitud',
            'longitude': 'Longitud',
            'assigned_to': 'Técnico asignado',
            'status': 'Estado',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'latitude': forms.NumberInput(attrs={'step': '0.0000001'}),
            'longitude': forms.NumberInput(attrs={'step': '0.0000001'}),
        }

    def __init__(self, *args, **kwargs):
        role = kwargs.pop('role', '')
        super().__init__(*args, **kwargs)
        self._bootstrap()
        technicians = User.objects.filter(work_profile__role=UserProfile.ROLE_TECHNICIAN, is_active=True).order_by('first_name', 'username')
        self.fields['assigned_to'].queryset = technicians
        self.fields['assigned_to'].required = False
        if role == UserProfile.ROLE_TECHNICIAN:
            for field in self.fields.values():
                field.disabled = True


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


class UserCreateForm(BootstrapMixin, forms.Form):
    username = forms.CharField(label='Usuario')
    first_name = forms.CharField(label='Nombre', required=False)
    email = forms.EmailField(label='Email', required=False)
    role = forms.ChoiceField(label='Rol', choices=UserProfile.ROLE_CHOICES)
    password = forms.CharField(label='Contraseña', widget=forms.PasswordInput, initial='111')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bootstrap()

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este usuario ya existe.')
        return username

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data.get('first_name', ''),
            email=self.cleaned_data.get('email', ''),
        )
        UserProfile.objects.create(user=user, role=self.cleaned_data['role'])
        return user


class WorkPasswordChangeForm(BootstrapMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bootstrap()
