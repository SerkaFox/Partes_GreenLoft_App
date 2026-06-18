import csv
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .forms import PanelLoginForm, ParteTrabajoForm, ProyectoForm, TecnicoForm, VehiculoForm
from .models import ParteTrabajo, ParteTrabajoFoto, Proyecto, Tecnico, Vehiculo
from .services.google_sheets import append_parte_to_google_sheet

SPECIAL_COMPANEROS = ['Sin acompañante', 'Tecnico de practicas']
MAX_PHOTOS = 8
MAX_PHOTO_SIZE = 12 * 1024 * 1024
ALLOWED_PHOTO_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'}


def index(request):
    return render(request, 'partes/home.html')


def parte_form(request):
    return render(request, 'partes/index.html')


def _safe_login_redirect(request):
    next_url = request.GET.get('next') or request.POST.get('next') or ''
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return next_url
    return reverse('workdocs_dashboard')


@require_GET
def init_data(request):
    proyectos = Proyecto.objects.filter(activo=True)
    obra_map = {p.codigo: {'cliente': p.cliente, 'obra': p.obra} for p in proyectos}
    profile_map = {}
    latest_partes = (
        ParteTrabajo.objects
        .select_related('tecnico', 'matricula', 'proyecto')
        .exclude(tecnico_nombre_snapshot='')
        .order_by('-created_at')
    )
    for parte in latest_partes:
        tecnico_name = parte.tecnico_nombre_snapshot
        if tecnico_name in profile_map:
            continue
        profile_map[tecnico_name] = {
            'hora_llegada': _time(parte.hora_llegada),
            'hora_salida': _time(parte.hora_salida),
            'jornada': parte.jornada,
            'companero': parte.companero_text,
            'matricula': parte.vehiculo_text,
            'conductor': parte.conductor,
            'entrada_obra': _time(parte.entrada_obra),
            'salida_obra': _time(parte.salida_obra),
            'hora_comida': _time(parte.hora_comida),
            'gastos': str(parte.gastos or ''),
            'proyecto_id': parte.id_snapshot,
            'trabajos': parte.trabajos_realizados,
            'admin': parte.trabajos_admin,
            'materiales': parte.materiales_instalados,
        }
    return JsonResponse({
        'tecnicos': list(Tecnico.objects.filter(activo=True, puede_ser_tecnico=True).values_list('nombre', flat=True)),
        'companeros': SPECIAL_COMPANEROS + list(Tecnico.objects.filter(activo=True, puede_ser_companero=True).values_list('nombre', flat=True)),
        'vehiculos': list(Vehiculo.objects.filter(activo=True).values_list('matricula', flat=True)),
        'ids': list(proyectos.values_list('codigo', flat=True)),
        'obraMap': obra_map,
        'profileMap': profile_map,
    })



def _request_data(request):
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        return request.POST, request.FILES.getlist('photos')
    return json.loads(request.body.decode('utf-8')), []


def _bool_value(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() in {'1', 'true', 'on', 'yes', 'si', 'sí'}


def _validate_photos(photos):
    if not photos:
        return
    if len(photos) > MAX_PHOTOS:
        raise ValueError(f'Máximo {MAX_PHOTOS} fotos por parte')
    for photo in photos:
        if photo.size > MAX_PHOTO_SIZE:
            raise ValueError(f'La foto {photo.name} supera 12 MB')
        if photo.content_type not in ALLOWED_PHOTO_TYPES:
            raise ValueError(f'Formato de foto no permitido: {photo.name}')


def _save_photos(parte, photos):
    saved = 0
    for photo in photos:
        ParteTrabajoFoto.objects.create(
            parte=parte,
            image=photo,
            original_name=photo.name[:255],
        )
        saved += 1
    return saved

def _parse_date(value):
    try:
        return datetime.strptime(value or '', '%Y-%m-%d').date()
    except ValueError:
        raise ValueError('Fecha no válida')


def _parse_time(value, required=False):
    if not value:
        if required:
            raise ValueError('Faltan horarios obligatorios')
        return None
    try:
        parsed = datetime.strptime(value, '%H:%M').time()
    except ValueError:
        raise ValueError('Hora no válida')
    if parsed.minute % 15 != 0:
        raise ValueError('Las horas deben estar en intervalos de 15 minutos')
    return parsed


def _get_active(model, field, value, label, required=True, **extra_filters):
    if not value:
        if required:
            raise ValueError(f'{label} es obligatorio')
        return None
    filters = {field: value, 'activo': True, **extra_filters}
    try:
        return model.objects.get(**filters)
    except model.DoesNotExist:
        raise ValueError(f'{label} no válido')


def _time(value):
    return value.strftime('%H:%M') if value else ''


def _money(value):
    if not value:
        return '0 €'
    if value == value.to_integral_value():
        return f'{int(value)} €'
    return f'{value:.2f} €'


def _empty(value, fallback='---'):
    value = (value or '').strip()
    return value if value else fallback


def safe_pdf_filename(name):
    name = re.sub(r'[\\/:*?"<>|]+', '-', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return f'{name}.pdf'


def pdf_display_name(parte):
    return safe_pdf_filename(
        f'PT de {parte.tecnico_nombre_snapshot} a {parte.fecha.isoformat()} en {parte.id_snapshot} - {parte.cliente_snapshot}'
    )



def save_media_file(file_field, subdir, filename, content):
    target_dir = Path(settings.MEDIA_ROOT) / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    target_path.write_bytes(content)
    file_field.name = f'{subdir}/{filename}'

def build_pdf(parte):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.4 * cm,
        leftMargin=1.4 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle('ParteTitle', parent=styles['Title'], fontSize=18, leading=22, textColor=colors.black, alignment=1, spaceAfter=14)
    section = ParagraphStyle('SectionTitle', parent=styles['Heading2'], fontSize=11, leading=14, textColor=colors.black, spaceBefore=8, spaceAfter=6)
    body = ParagraphStyle('Body', parent=styles['BodyText'], fontSize=9.5, leading=13)

    def p(text):
        return Paragraph(str(text or '').replace('\n', '<br/>'), body)

    hora_comida = 'N/A' if parte.jornada == ParteTrabajo.JORNADA_INTENSIVA else (_time(parte.hora_comida) or '---')
    rows = [
        ['NOMBRE', p(parte.tecnico_nombre_snapshot), 'FECHA', parte.fecha.isoformat()],
        ['INICIO JORNADA', _time(parte.hora_llegada), 'FIN JORNADA', _time(parte.hora_salida)],
        ['TIPO JORNADA', parte.jornada_label, 'VEHÍCULO', parte.vehiculo_text or '---'],
        ['COMPAÑERO', p(parte.companero_text or 'Sin acompañante'), 'CONDUCTOR', 'SÍ' if parte.conductor else 'NO'],
        ['ENTRADA OBRA', _time(parte.entrada_obra) or '---', 'SALIDA OBRA', _time(parte.salida_obra) or '---'],
        ['HORA COMIDA', hora_comida, 'GASTOS', _money(parte.gastos)],
        ['ID', p(parte.id_snapshot), 'CLIENTE', p(parte.cliente_snapshot)],
        ['OBRA', p(parte.obra_snapshot), '', ''],
    ]
    table = Table(rows, colWidths=[3.4 * cm, 5.2 * cm, 3.4 * cm, 5.2 * cm])
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.6, colors.HexColor('#333333')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eeeeee')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#eeeeee')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('SPAN', (1, 7), (3, 7)),
    ]))

    story = [Paragraph('PARTE DE TRABAJO', title), Paragraph('INFORMACIÓN GENERAL', section), table]
    for label, text in [
        ('TRABAJOS REALIZADOS', parte.trabajos_realizados),
        ('TRABAJOS POR ADMINISTRACIÓN', _empty(parte.trabajos_admin)),
        ('MATERIALES INSTALADOS', _empty(parte.materiales_instalados)),
    ]:
        story.extend([Spacer(1, 0.25 * cm), Paragraph(label, section), Paragraph(_empty(text), body)])
    doc.build(story)
    return buffer.getvalue()


def send_parte_email(parte):
    if not parte.tecnico_email_snapshot:
        parte.email_error = 'El técnico no tiene email configurado.'
        parte.email_sent = False
        parte.save(update_fields=['email_error', 'email_sent', 'updated_at'])
        return False, parte.email_error
    if not settings.EMAIL_HOST:
        parte.email_error = 'SMTP no configurado.'
        parte.email_sent = False
        parte.save(update_fields=['email_error', 'email_sent', 'updated_at'])
        return False, parte.email_error
    try:
        message = EmailMessage(
            subject=f'Parte de trabajo - {parte.fecha.isoformat()} - {parte.tecnico_nombre_snapshot}',
            body='Adjuntamos el parte de trabajo generado.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[parte.tecnico_email_snapshot],
        )
        message.attach(pdf_display_name(parte), parte.pdf_file.read(), 'application/pdf')
        message.send(fail_silently=False)
        parte.email_sent = True
        parte.email_sent_at = timezone.now()
        parte.email_error = ''
        parte.save(update_fields=['email_sent', 'email_sent_at', 'email_error', 'updated_at'])
        return True, ''
    except Exception as exc:  # noqa: BLE001 - error is persisted for panel review.
        parte.email_sent = False
        parte.email_error = str(exc)
        parte.save(update_fields=['email_sent', 'email_error', 'updated_at'])
        return False, parte.email_error


def _csv_row(parte, request=None):
    pdf_url = parte.pdf_file.url if parte.pdf_file else ''
    if request and pdf_url:
        pdf_url = request.build_absolute_uri(pdf_url)
    return [
        parte.fecha.isoformat(),
        parte.tecnico_nombre_snapshot,
        parte.tecnico_email_snapshot,
        _time(parte.hora_llegada),
        _time(parte.hora_salida),
        parte.jornada_label,
        parte.vehiculo_text,
        parte.companero_text,
        'SÍ' if parte.conductor else 'NO',
        _time(parte.entrada_obra),
        _time(parte.salida_obra),
        'N/A' if parte.jornada == ParteTrabajo.JORNADA_INTENSIVA else _time(parte.hora_comida),
        str(parte.gastos),
        parte.id_snapshot,
        parte.cliente_snapshot,
        parte.obra_snapshot,
        parte.trabajos_realizados,
        parte.trabajos_admin,
        parte.materiales_instalados,
        pdf_url,
        timezone.localtime(parte.created_at).strftime('%Y-%m-%d %H:%M:%S'),
    ]


def generate_csv_file(parte):
    output = StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(CSV_HEADERS)
    writer.writerow(_csv_row(parte))
    return output.getvalue().encode('utf-8-sig')


CSV_HEADERS = [
    'fecha', 'tecnico', 'email', 'inicio_jornada', 'fin_jornada', 'tipo_jornada', 'vehiculo',
    'companero', 'conductor', 'entrada_obra', 'salida_obra', 'hora_comida', 'gastos',
    'id_proyecto', 'cliente', 'obra', 'trabajos_realizados', 'trabajos_admin',
    'materiales_instalados', 'pdf_url', 'created_at',
]


@require_POST
def submit_parte(request):
    try:
        data, photos = _request_data(request)
        expected_password = settings.WORKPART_VALIDATION_PASSWORD
        password = data.get('password', '')
        if len(password) != 6 or not expected_password or password != expected_password:
            return JsonResponse({'ok': False, 'error': 'Contraseña de validación incorrecta'}, status=400)

        fecha = _parse_date(data.get('fecha'))
        jornada = data.get('jornada') or ParteTrabajo.JORNADA_NORMAL
        if fecha.weekday() == 4:
            jornada = ParteTrabajo.JORNADA_INTENSIVA
        if jornada not in {ParteTrabajo.JORNADA_NORMAL, ParteTrabajo.JORNADA_INTENSIVA}:
            raise ValueError('Jornada no válida')

        tecnico = _get_active(Tecnico, 'nombre', data.get('tecnico'), 'Técnico', puede_ser_tecnico=True)
        companero_value = (data.get('companero') or 'Sin acompañante').strip()
        companero = None
        if companero_value and companero_value not in SPECIAL_COMPANEROS:
            companero = _get_active(Tecnico, 'nombre', companero_value, 'Compañero', required=False, puede_ser_companero=True)
            companero_value = companero.nombre if companero else 'Sin acompañante'
        vehiculo = _get_active(Vehiculo, 'matricula', data.get('matricula'), 'Matrícula', required=False)
        proyecto = _get_active(Proyecto, 'codigo', data.get('proyecto_id'), 'Id proyecto')

        gastos = Decimal('0')
        hora_comida = None
        if jornada != ParteTrabajo.JORNADA_INTENSIVA:
            try:
                gastos = Decimal(str(data.get('gastos') or '0')).quantize(Decimal('0.01'))
            except InvalidOperation:
                raise ValueError('Gastos no válido')
            hora_comida = _parse_time(data.get('hora_comida'))

        trabajos = (data.get('trabajos') or '').strip()
        if not trabajos:
            raise ValueError('Trabajos realizados es obligatorio')
        _validate_photos(photos)

        parte = ParteTrabajo.objects.create(
            tecnico=tecnico,
            tecnico_nombre_snapshot=tecnico.nombre,
            tecnico_email_snapshot=tecnico.email,
            fecha=fecha,
            hora_llegada=_parse_time(data.get('hora_llegada'), required=True),
            hora_salida=_parse_time(data.get('hora_salida'), required=True),
            jornada=jornada,
            companero=companero,
            companero_text=companero_value or 'Sin acompañante',
            matricula=vehiculo,
            conductor=_bool_value(data.get('conductor')),
            entrada_obra=_parse_time(data.get('entrada_obra')),
            salida_obra=_parse_time(data.get('salida_obra')),
            hora_comida=hora_comida,
            gastos=gastos,
            proyecto=proyecto,
            id_snapshot=proyecto.codigo,
            cliente_snapshot=proyecto.cliente,
            obra_snapshot=proyecto.obra,
            trabajos_realizados=trabajos,
            trabajos_admin=(data.get('admin') or '').strip(),
            materiales_instalados=(data.get('materiales') or '').strip(),
            cliente=proyecto.cliente,
            obra=proyecto.obra,
            trabajos=trabajos,
            admin=(data.get('admin') or '').strip(),
            materiales=(data.get('materiales') or '').strip(),
        )
        photo_count = _save_photos(parte, photos)
        save_media_file(parte.pdf_file, 'partes', pdf_display_name(parte), build_pdf(parte))
        save_media_file(parte.csv_file, 'partes_csv', f'parte_{parte.id}.csv', generate_csv_file(parte))
        parte.save(update_fields=['pdf_file', 'csv_file', 'updated_at'])

        email_ok, email_error = send_parte_email(parte)
        try:
            append_parte_to_google_sheet(parte)
        except Exception as exc:  # noqa: BLE001
            parte.google_sheets_error = str(exc)
            parte.save(update_fields=['google_sheets_error', 'updated_at'])

        response = {'ok': True, 'pdfUrl': parte.pdf_file.url, 'photoCount': photo_count}
        if not email_ok:
            response['warning'] = email_error
        return JsonResponse(response)
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON no válido'}, status=400)


def panel_login(request):
    if request.user.is_authenticated:
        return redirect(_safe_login_redirect(request))
    form = PanelLoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(request, username=form.cleaned_data['username'], password=form.cleaned_data['password'])
        if user and user.is_active:
            login(request, user)
            return redirect(_safe_login_redirect(request))
        messages.error(request, 'Usuario o contraseña incorrectos.')
    return render(request, 'partes/panel/login.html', {'form': form, 'next': request.GET.get('next', '')})


def panel_logout(request):
    logout(request)
    return redirect('panel_login')


@login_required(login_url='/panel/login/')
def panel_dashboard(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    return render(request, 'partes/panel/dashboard.html', {
        'partes_today': ParteTrabajo.objects.filter(fecha=today).count(),
        'partes_month': ParteTrabajo.objects.filter(fecha__gte=month_start, fecha__lte=today).count(),
        'latest_partes': ParteTrabajo.objects.select_related('tecnico', 'matricula', 'proyecto')[:20],
    })


def _list_edit(request, model, form_class, template, title, redirect_name, pk=None):
    instance = get_object_or_404(model, pk=pk) if pk else None
    form = form_class(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Guardado correctamente.')
        return redirect(redirect_name)
    return render(request, template, {
        'title': title,
        'items': model.objects.all(),
        'form': form,
        'editing': instance,
    })


@login_required(login_url='/panel/login/')
def panel_tecnicos(request, pk=None):
    return _list_edit(request, Tecnico, TecnicoForm, 'partes/panel/tecnicos.html', 'Técnicos', 'panel_tecnicos', pk)


@login_required(login_url='/panel/login/')
def panel_vehiculos(request, pk=None):
    return _list_edit(request, Vehiculo, VehiculoForm, 'partes/panel/vehiculos.html', 'Vehículos', 'panel_vehiculos', pk)


@login_required(login_url='/panel/login/')
def panel_proyectos(request, pk=None):
    return _list_edit(request, Proyecto, ProyectoForm, 'partes/panel/proyectos.html', 'Obras / Proyectos', 'panel_proyectos', pk)


@login_required(login_url='/panel/login/')
def panel_partes(request):
    qs = ParteTrabajo.objects.select_related('tecnico', 'matricula', 'proyecto')
    date_from = request.GET.get('date_from') or ''
    date_to = request.GET.get('date_to') or ''
    tecnico = request.GET.get('tecnico') or ''
    vehiculo = request.GET.get('vehiculo') or ''
    cliente = request.GET.get('cliente') or ''
    if date_from:
        qs = qs.filter(fecha__gte=date_from)
    if date_to:
        qs = qs.filter(fecha__lte=date_to)
    if tecnico:
        qs = qs.filter(tecnico_id=tecnico)
    if vehiculo:
        qs = qs.filter(matricula_id=vehiculo)
    if cliente:
        qs = qs.filter(cliente_snapshot__icontains=cliente)
    return render(request, 'partes/panel/partes.html', {
        'items': qs[:300],
        'tecnicos': Tecnico.objects.all(),
        'vehiculos': Vehiculo.objects.all(),
        'filters': {'date_from': date_from, 'date_to': date_to, 'tecnico': tecnico, 'vehiculo': vehiculo, 'cliente': cliente},
    })


@login_required(login_url='/panel/login/')
def panel_parte_edit(request, pk):
    parte = get_object_or_404(ParteTrabajo, pk=pk)
    form = ParteTrabajoForm(request.POST or None, instance=parte)
    if request.method == 'POST' and form.is_valid():
        parte = form.save(commit=False)
        parte.tecnico_nombre_snapshot = parte.tecnico.nombre
        parte.tecnico_email_snapshot = parte.tecnico.email
        parte.id_snapshot = parte.proyecto.codigo
        parte.cliente_snapshot = parte.proyecto.cliente
        parte.obra_snapshot = parte.proyecto.obra
        parte.cliente = parte.cliente_snapshot
        parte.obra = parte.obra_snapshot
        parte.trabajos = parte.trabajos_realizados
        parte.admin = parte.trabajos_admin
        parte.materiales = parte.materiales_instalados
        parte.save()
        save_media_file(parte.pdf_file, 'partes', pdf_display_name(parte), build_pdf(parte))
        save_media_file(parte.csv_file, 'partes_csv', f'parte_{parte.id}.csv', generate_csv_file(parte))
        parte.save(update_fields=['pdf_file', 'csv_file', 'updated_at'])
        messages.success(request, 'Parte actualizado.')
        return redirect('panel_partes')
    return render(request, 'partes/panel/parte_form.html', {'form': form, 'parte': parte})


@login_required(login_url='/panel/login/')
def panel_resend_email(request, pk):
    parte = get_object_or_404(ParteTrabajo, pk=pk)
    ok, error = send_parte_email(parte)
    if ok:
        messages.success(request, 'Email enviado correctamente.')
    else:
        messages.error(request, f'No se pudo enviar el email: {error}')
    return redirect('panel_partes')


@login_required(login_url='/panel/login/')
def panel_export_csv(request):
    qs = ParteTrabajo.objects.select_related('tecnico', 'matricula', 'proyecto')
    date_from = request.GET.get('date_from') or ''
    date_to = request.GET.get('date_to') or ''
    if date_from:
        qs = qs.filter(fecha__gte=date_from)
    if date_to:
        qs = qs.filter(fecha__lte=date_to)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="partes_export.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(CSV_HEADERS)
    for parte in qs:
        writer.writerow(_csv_row(parte, request=request))
    return response
