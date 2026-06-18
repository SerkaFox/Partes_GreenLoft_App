from django import forms

from .models import ParteTrabajo, Proyecto, Tecnico, Vehiculo


class PanelLoginForm(forms.Form):
    username = forms.CharField(label='Usuario', widget=forms.HiddenInput)
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Introduce tu contraseña',
            'autocomplete': 'current-password',
        }),
    )


class TecnicoForm(forms.ModelForm):
    class Meta:
        model = Tecnico
        fields = ['nombre', 'email', 'activo', 'puede_ser_tecnico', 'puede_ser_companero', 'orden']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_ser_tecnico': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_ser_companero': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class VehiculoForm(forms.ModelForm):
    class Meta:
        model = Vehiculo
        fields = ['matricula', 'descripcion', 'image', 'activo', 'orden']
        widgets = {
            'matricula': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProyectoForm(forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = ['codigo', 'cliente', 'obra', 'activo', 'orden']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'obra': forms.TextInput(attrs={'class': 'form-control'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ParteTrabajoForm(forms.ModelForm):
    class Meta:
        model = ParteTrabajo
        fields = [
            'tecnico', 'fecha', 'hora_llegada', 'hora_salida', 'jornada', 'companero_text',
            'matricula', 'conductor', 'entrada_obra', 'salida_obra', 'hora_comida', 'gastos',
            'proyecto', 'trabajos_realizados', 'trabajos_admin', 'materiales_instalados',
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hora_llegada': forms.TimeInput(attrs={'type': 'time', 'step': 900, 'class': 'form-control'}),
            'hora_salida': forms.TimeInput(attrs={'type': 'time', 'step': 900, 'class': 'form-control'}),
            'entrada_obra': forms.TimeInput(attrs={'type': 'time', 'step': 900, 'class': 'form-control'}),
            'salida_obra': forms.TimeInput(attrs={'type': 'time', 'step': 900, 'class': 'form-control'}),
            'hora_comida': forms.TimeInput(attrs={'type': 'time', 'step': 900, 'class': 'form-control'}),
            'gastos': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'trabajos_realizados': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'trabajos_admin': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'materiales_instalados': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'conductor': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
