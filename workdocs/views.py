from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from partes.forms import VehiculoForm
from partes.models import Vehiculo

from .forms import CommentForm, ProfileForm, TaskFileForm, TaskForm, UserCreateForm, UserEditForm, VoiceReportForm
from .models import Task, TaskEvent, TaskFile, TaskVoiceReport, UserProfile
from .services.transcription import transcribe_audio
from .utils import detect_file_type, get_user_role, is_admin, is_manager, is_technician

User = get_user_model()


def _display_user(user):
    return user.get_full_name() or user.get_username()


def _can_manage_users(user):
    return is_admin(user) or is_manager(user)


def _ensure_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if user.is_superuser and profile.role != UserProfile.ROLE_ADMIN:
        profile.role = UserProfile.ROLE_ADMIN
        profile.active = user.is_active
        profile.save(update_fields=['role', 'active'])
    UserProfile._meta.get_field('user').remote_field.set_cached_value(user, profile)
    return profile


def _technicians():
    return User.objects.filter(work_profile__role=UserProfile.ROLE_TECHNICIAN, work_profile__active=True, is_active=True).order_by('first_name', 'username')


def _user_payload(user):
    return {
        'id': user.id,
        'username': user.get_username(),
        'full_name': _display_user(user),
        'role': get_user_role(user),
    }


@require_GET
def user_search(request):
    q = (request.GET.get('q') or '').strip()
    role = request.GET.get('role') or ''
    if len(q) < 2:
        return JsonResponse([], safe=False)
    qs = User.objects.filter(is_active=True, work_profile__active=True).select_related('work_profile')
    if role == UserProfile.ROLE_TECHNICIAN:
        qs = qs.filter(work_profile__role=UserProfile.ROLE_TECHNICIAN)
    elif role in {'admin_manager', 'administration'}:
        qs = qs.filter(Q(is_superuser=True) | Q(work_profile__role__in=[UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER]))
    qs = qs.filter(
        Q(username__icontains=q)
        | Q(first_name__icontains=q)
        | Q(last_name__icontains=q)
        | Q(email__icontains=q)
    ).order_by('first_name', 'last_name', 'username')[:12]
    return JsonResponse([_user_payload(user) for user in qs], safe=False)


def _visible_tasks(user):
    role = get_user_role(user)
    qs = Task.objects.select_related('created_by', 'assigned_to').prefetch_related('files', 'technicians')
    if role == UserProfile.ROLE_ADMIN:
        return qs
    if role == UserProfile.ROLE_MANAGER:
        return qs.filter(created_by=user)
    return qs.filter(Q(assigned_to=user) | Q(technicians=user)).distinct()


def _active_statuses():
    return [
        Task.STATUS_NUEVA,
        Task.STATUS_ASIGNADA,
        Task.STATUS_EN_CAMINO,
        Task.STATUS_EN_OBJETO,
        Task.STATUS_EN_PROCESO,
        Task.STATUS_PENDIENTE_REVISION,
    ]


def _can_edit_task(user, task):
    role = get_user_role(user)
    return role == UserProfile.ROLE_ADMIN or (role == UserProfile.ROLE_MANAGER and task.created_by_id == user.id)


def _get_visible_task(user, pk):
    task = get_object_or_404(_visible_tasks(user), pk=pk)
    return task


def _add_event(task, user, event_type, comment=''):
    return TaskEvent.objects.create(task=task, user=user, event_type=event_type, comment=comment)


def _selected_technicians(form):
    return list(form.cleaned_data.get('technicians') or [])


def _sync_task_technicians(task, technicians):
    task.technicians.set(technicians)
    primary = technicians[0] if technicians else None
    if task.assigned_to_id != (primary.id if primary else None):
        task.assigned_to = primary
        task.save(update_fields=['assigned_to', 'updated_at'])


def _save_uploaded_files(task, user, files, comment=''):
    saved = 0
    for uploaded in files:
        TaskFile.objects.create(
            task=task,
            uploaded_by=user,
            file=uploaded,
            file_type=detect_file_type(uploaded),
            original_name=uploaded.name[:255],
            comment=comment,
        )
        saved += 1
    if saved:
        _add_event(task, user, TaskEvent.EVENT_FILE, f'{saved} archivo(s) subido(s).')
    return saved


def _save_description_audio(task, user, uploaded):
    if not uploaded:
        return None
    report = TaskVoiceReport.objects.create(task=task, technician=user, audio_file=uploaded)
    _add_event(task, user, TaskEvent.EVENT_AUDIO, 'Descripción de voz añadida.')
    transcribe_audio(report.pk)
    return report


@login_required(login_url='/panel/login/')
def dashboard(request):
    role = get_user_role(request.user)
    qs = _visible_tasks(request.user)
    active_statuses = _active_statuses()
    active_tasks = qs.filter(status__in=active_statuses)
    context = {
        'role': role,
        'tasks': active_tasks[:40],
        'active_count': qs.filter(status__in=active_statuses).count(),
        'finished_count': qs.filter(status=Task.STATUS_FINALIZADA).count(),
        'pending_count': qs.exclude(status__in=[Task.STATUS_FINALIZADA, Task.STATUS_CANCELADA]).count(),
        'new_documents_count': TaskFile.objects.filter(task__in=qs).count(),
        'technicians': [],
    }
    if role in {UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER}:
        today = timezone.localdate()
        technician_scope = active_tasks.filter(Q(created_at__date=today) | Q(updated_at__date=today) | Q(status__in=active_statuses))
        technicians = []
        for technician in _technicians():
            tech_tasks = technician_scope.filter(Q(assigned_to=technician) | Q(technicians=technician)).distinct()
            active_count = tech_tasks.count()
            if active_count:
                technician.active_tasks = active_count
                technician.last_activity = tech_tasks.aggregate(last_activity=Max('updated_at'))['last_activity']
                technicians.append(technician)
        context['technicians'] = technicians
    return render(request, 'workdocs/dashboard.html', context)


@login_required(login_url='/panel/login/')
def technician_detail(request, pk):
    if not (is_admin(request.user) or is_manager(request.user)):
        raise PermissionDenied
    technician = get_object_or_404(_technicians(), pk=pk)
    qs = _visible_tasks(request.user).filter(Q(assigned_to=technician) | Q(technicians=technician)).select_related('created_by', 'assigned_to').distinct()
    active_tasks = qs.filter(status__in=_active_statuses())
    events = TaskEvent.objects.filter(task__in=qs).select_related('task', 'user')[:80]
    return render(request, 'workdocs/technician_detail.html', {
        'technician': technician,
        'tasks': active_tasks,
        'all_tasks': qs[:80],
        'events': events,
        'role': get_user_role(request.user),
    })


@login_required(login_url='/panel/login/')
def task_list(request):
    qs = _visible_tasks(request.user)
    status = request.GET.get('status') or ''
    documents = request.GET.get('documents') or ''
    technician = request.GET.get('technician') or ''
    q = request.GET.get('q') or ''
    if status == 'pending':
        qs = qs.exclude(status__in=[Task.STATUS_FINALIZADA, Task.STATUS_CANCELADA])
    elif status == 'finished':
        qs = qs.filter(status=Task.STATUS_FINALIZADA)
    elif status == 'active':
        qs = qs.filter(status__in=_active_statuses())
    elif status:
        qs = qs.filter(status=status)
    if documents:
        qs = qs.filter(files__isnull=False).distinct()
    if technician and (is_admin(request.user) or is_manager(request.user)):
        qs = qs.filter(Q(assigned_to_id=technician) | Q(technicians__id=technician)).distinct()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(address__icontains=q) | Q(description__icontains=q))
    return render(request, 'workdocs/task_list.html', {
        'tasks': qs[:300],
        'statuses': Task.STATUS_CHOICES,
        'technicians': _technicians(),
        'filters': {'status': status, 'documents': documents, 'technician': technician, 'q': q},
        'role': get_user_role(request.user),
    })


@login_required(login_url='/panel/login/')
def task_create(request):
    if is_technician(request.user):
        raise PermissionDenied
    form = TaskForm(request.POST or None, role=get_user_role(request.user))
    file_form = TaskFileForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        task = form.save(commit=False)
        task.created_by = request.user
        technicians = _selected_technicians(form)
        if task.assigned_to and task.status == Task.STATUS_NUEVA:
            task.status = Task.STATUS_ASIGNADA
        task.save()
        _sync_task_technicians(task, technicians)
        _add_event(task, request.user, TaskEvent.EVENT_CREATED, 'Tarea creada.')
        if technicians:
            _add_event(task, request.user, TaskEvent.EVENT_ASSIGNED, f'Técnicos asignados: {", ".join(_display_user(user) for user in technicians)}.')
        _save_uploaded_files(task, request.user, request.FILES.getlist('files'), request.POST.get('comment', ''))
        _save_description_audio(task, request.user, request.FILES.get('description_audio'))
        messages.success(request, 'Guardado correctamente.')
        return redirect('workdocs_task_detail', pk=task.pk)
    return render(request, 'workdocs/task_form.html', {'form': form, 'file_form': file_form, 'title': 'Crear tarea'})


@login_required(login_url='/panel/login/')
def task_detail(request, pk):
    task = _get_visible_task(request.user, pk)
    role = get_user_role(request.user)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_task':
            if not _can_edit_task(request.user, task):
                raise PermissionDenied
            form = TaskForm(request.POST, instance=task, role=role)
            if form.is_valid():
                old_assignee = task.assigned_to_id
                old_technicians = set(task.technicians.values_list('id', flat=True))
                task = form.save(commit=False)
                technicians = _selected_technicians(form)
                task.save()
                _sync_task_technicians(task, technicians)
                new_technicians = {user.id for user in technicians}
                if old_assignee != task.assigned_to_id or old_technicians != new_technicians:
                    label = ', '.join(_display_user(user) for user in technicians) if technicians else 'Sin asignar'
                    _add_event(task, request.user, TaskEvent.EVENT_ASSIGNED, f'Técnicos asignados: {label}.')
                _add_event(task, request.user, TaskEvent.EVENT_STATUS, f'Estado actualizado: {task.get_status_display()}.')
                _save_description_audio(task, request.user, request.FILES.get('description_audio'))
                messages.success(request, 'Guardado correctamente.')
                return redirect('workdocs_task_detail', pk=task.pk)
        elif action == 'upload_files':
            file_form = TaskFileForm(request.POST, request.FILES)
            if file_form.is_valid():
                count = _save_uploaded_files(task, request.user, request.FILES.getlist('files'), file_form.cleaned_data.get('comment', ''))
                messages.success(request, f'{count} archivo(s) subido(s).')
                return redirect('workdocs_task_detail', pk=task.pk)
        elif action == 'comment':
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                _add_event(task, request.user, TaskEvent.EVENT_COMMENT, comment_form.cleaned_data['comment'])
                messages.success(request, 'Comentario añadido.')
                return redirect('workdocs_task_detail', pk=task.pk)
        elif action == 'voice':
            voice_form = VoiceReportForm(request.POST, request.FILES)
            if voice_form.is_valid():
                report = voice_form.save(commit=False)
                report.task = task
                report.technician = request.user
                report.save()
                _add_event(task, request.user, TaskEvent.EVENT_AUDIO, 'Informe de voz subido.')
                transcribe_audio(report.pk)
                messages.success(request, 'Audio subido correctamente.')
                return redirect('workdocs_task_detail', pk=task.pk)

    return render(request, 'workdocs/task_detail.html', {
        'task': task,
        'map_coords': f'{task.latitude},{task.longitude}' if task.latitude and task.longitude else '',
        'role': role,
        'can_edit_task': _can_edit_task(request.user, task),
        'task_form': TaskForm(instance=task, role=role),
        'file_form': TaskFileForm(),
        'comment_form': CommentForm(),
        'voice_form': VoiceReportForm(),
        'files': task.files.select_related('uploaded_by'),
        'events': task.events.select_related('user')[:80],
        'voice_reports': task.voice_reports.select_related('technician'),
    })


@login_required(login_url='/panel/login/')
@require_POST
def technician_status(request, pk, action):
    task = _get_visible_task(request.user, pk)
    if not is_technician(request.user):
        raise PermissionDenied
    now = timezone.now()
    labels = {
        'arrived_work': 'He llegado al trabajo',
        'arrived_object': 'He llegado al objeto',
        'finished': 'Trabajo finalizado correctamente.',
    }
    if action == 'arrived_work':
        task.status = Task.STATUS_EN_CAMINO
        task.started_at = task.started_at or now
    elif action == 'arrived_object':
        task.status = Task.STATUS_EN_OBJETO
        task.arrived_at = task.arrived_at or now
    elif action == 'finished':
        task.status = Task.STATUS_PENDIENTE_REVISION
        task.finished_at = task.finished_at or now
    else:
        raise PermissionDenied
    task.save(update_fields=['status', 'started_at', 'arrived_at', 'finished_at', 'updated_at'])
    _add_event(task, request.user, TaskEvent.EVENT_STATUS, labels[action])
    messages.success(request, labels[action])
    return redirect('workdocs_task_detail', pk=task.pk)


@login_required(login_url='/panel/login/')
def profile(request):
    profile_obj = _ensure_profile(request.user)
    form = ProfileForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Perfil actualizado correctamente.')
        return redirect('workdocs_profile')
    return render(request, 'workdocs/profile.html', {'profile': profile_obj, 'form': form, 'role': get_user_role(request.user)})


@login_required(login_url='/panel/login/')
def user_list(request):
    if not _can_manage_users(request.user):
        raise PermissionDenied
    form = UserCreateForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Usuario creado correctamente.')
        return redirect('workdocs_users')
    active_statuses = _active_statuses()
    users = User.objects.select_related('work_profile').order_by('username')
    for item in users:
        _ensure_profile(item)
        item.active_task_count = Task.objects.filter(Q(assigned_to=item) | Q(technicians=item), status__in=active_statuses).distinct().count()
    return render(request, 'workdocs/users.html', {'users': users, 'form': form})


@login_required(login_url='/panel/login/')
def user_edit(request, pk):
    if not _can_manage_users(request.user):
        raise PermissionDenied
    user = get_object_or_404(User.objects.select_related('work_profile'), pk=pk)
    _ensure_profile(user)
    form = UserEditForm(request.POST or None, request.FILES or None, user=user, actor=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Usuario actualizado correctamente.')
        return redirect('workdocs_users')
    return render(request, 'workdocs/user_edit.html', {'edited_user': user, 'form': form, 'role': get_user_role(request.user)})


@login_required(login_url='/panel/login/')
@require_POST
def user_toggle_active(request, pk):
    if not _can_manage_users(request.user):
        raise PermissionDenied
    user = get_object_or_404(User.objects.select_related('work_profile'), pk=pk)
    profile_obj = _ensure_profile(user)
    if user.pk == request.user.pk and user.is_active and profile_obj.active:
        messages.error(request, 'No puedes desactivar tu propia cuenta.')
        return redirect('workdocs_users')
    next_active = not (user.is_active and profile_obj.active)
    user.is_active = next_active
    user.save(update_fields=['is_active'])
    profile_obj.active = next_active
    profile_obj.save(update_fields=['active'])
    messages.success(request, 'Usuario activado correctamente.' if next_active else 'Usuario desactivado correctamente.')
    return redirect('workdocs_users')


@login_required(login_url='/panel/login/')
def user_tasks(request, pk):
    if not _can_manage_users(request.user):
        raise PermissionDenied
    user = get_object_or_404(User.objects.select_related('work_profile'), pk=pk)
    profile_obj = _ensure_profile(user)
    tasks = _visible_tasks(request.user).filter(Q(assigned_to=user) | Q(technicians=user)).select_related('created_by', 'assigned_to').distinct()
    active_tasks = tasks.filter(status__in=_active_statuses())
    finished_tasks = tasks.filter(status__in=[Task.STATUS_FINALIZADA, Task.STATUS_CANCELADA])
    events = TaskEvent.objects.filter(task__in=tasks).select_related('task', 'user')[:80]
    return render(request, 'workdocs/user_tasks.html', {
        'staff_user': user,
        'staff_profile': profile_obj,
        'active_tasks': active_tasks,
        'finished_tasks': finished_tasks,
        'events': events,
        'role': get_user_role(request.user),
    })


@login_required(login_url='/panel/login/')
def vehicles(request, pk=None):
    if not _can_manage_users(request.user):
        raise PermissionDenied
    vehicle = get_object_or_404(Vehiculo, pk=pk) if pk else None
    form = VehiculoForm(request.POST or None, request.FILES or None, instance=vehicle)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Vehículo guardado correctamente.')
        return redirect('workdocs_vehicles')
    return render(request, 'workdocs/vehicles.html', {
        'form': form,
        'vehicles': Vehiculo.objects.all(),
        'editing': vehicle,
        'role': get_user_role(request.user),
    })
