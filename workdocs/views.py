from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import CommentForm, TaskFileForm, TaskForm, UserCreateForm, VoiceReportForm, WorkPasswordChangeForm
from .models import Task, TaskEvent, TaskFile, TaskVoiceReport, UserProfile
from .services.transcription import transcribe_audio
from .utils import detect_file_type, get_user_role, is_admin, is_manager, is_technician

User = get_user_model()


def _display_user(user):
    return user.get_full_name() or user.get_username()


def _technicians():
    return User.objects.filter(work_profile__role=UserProfile.ROLE_TECHNICIAN, is_active=True).order_by('first_name', 'username')


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
    qs = User.objects.filter(is_active=True).select_related('work_profile')
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
    qs = Task.objects.select_related('created_by', 'assigned_to').prefetch_related('files')
    if role == UserProfile.ROLE_ADMIN:
        return qs
    if role == UserProfile.ROLE_MANAGER:
        return qs.filter(created_by=user)
    return qs.filter(assigned_to=user)


def _can_edit_task(user, task):
    role = get_user_role(user)
    return role == UserProfile.ROLE_ADMIN or (role == UserProfile.ROLE_MANAGER and task.created_by_id == user.id)


def _get_visible_task(user, pk):
    task = get_object_or_404(_visible_tasks(user), pk=pk)
    return task


def _add_event(task, user, event_type, comment=''):
    return TaskEvent.objects.create(task=task, user=user, event_type=event_type, comment=comment)


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


@login_required(login_url='/panel/login/')
def dashboard(request):
    role = get_user_role(request.user)
    qs = _visible_tasks(request.user)
    active_statuses = [
        Task.STATUS_NUEVA,
        Task.STATUS_ASIGNADA,
        Task.STATUS_EN_CAMINO,
        Task.STATUS_EN_OBJETO,
        Task.STATUS_EN_PROCESO,
        Task.STATUS_PENDIENTE_REVISION,
    ]
    context = {
        'role': role,
        'tasks': qs[:40],
        'active_count': qs.filter(status__in=active_statuses).count(),
        'finished_count': qs.filter(status=Task.STATUS_FINALIZADA).count(),
        'pending_count': qs.exclude(status__in=[Task.STATUS_FINALIZADA, Task.STATUS_CANCELADA]).count(),
        'new_documents_count': TaskFile.objects.filter(task__in=qs).count(),
        'technicians': [],
    }
    if role == UserProfile.ROLE_ADMIN:
        context['technicians'] = _technicians().annotate(active_tasks=Count(
            'assigned_work_tasks',
            filter=Q(assigned_work_tasks__status__in=active_statuses),
        ))
    return render(request, 'workdocs/dashboard.html', context)


@login_required(login_url='/panel/login/')
def task_list(request):
    qs = _visible_tasks(request.user)
    status = request.GET.get('status') or ''
    technician = request.GET.get('technician') or ''
    q = request.GET.get('q') or ''
    if status:
        qs = qs.filter(status=status)
    if technician and (is_admin(request.user) or is_manager(request.user)):
        qs = qs.filter(assigned_to_id=technician)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(address__icontains=q) | Q(description__icontains=q))
    return render(request, 'workdocs/task_list.html', {
        'tasks': qs[:300],
        'statuses': Task.STATUS_CHOICES,
        'technicians': _technicians(),
        'filters': {'status': status, 'technician': technician, 'q': q},
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
        if task.assigned_to and task.status == Task.STATUS_NUEVA:
            task.status = Task.STATUS_ASIGNADA
        task.save()
        _add_event(task, request.user, TaskEvent.EVENT_CREATED, 'Tarea creada.')
        if task.assigned_to:
            _add_event(task, request.user, TaskEvent.EVENT_ASSIGNED, f'Técnico asignado: {_display_user(task.assigned_to)}.')
        _save_uploaded_files(task, request.user, request.FILES.getlist('files'), request.POST.get('comment', ''))
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
                task = form.save()
                if old_assignee != task.assigned_to_id and task.assigned_to:
                    _add_event(task, request.user, TaskEvent.EVENT_ASSIGNED, f'Técnico asignado: {_display_user(task.assigned_to)}.')
                _add_event(task, request.user, TaskEvent.EVENT_STATUS, f'Estado actualizado: {task.get_status_display()}.')
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
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.user.is_superuser and profile_obj.role != UserProfile.ROLE_ADMIN:
        profile_obj.role = UserProfile.ROLE_ADMIN
        profile_obj.save(update_fields=['role'])
    form = WorkPasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Contraseña cambiada correctamente.')
        return redirect('workdocs_profile')
    return render(request, 'workdocs/profile.html', {'profile': profile_obj, 'form': form, 'role': get_user_role(request.user)})


@login_required(login_url='/panel/login/')
def user_list(request):
    if not is_admin(request.user):
        raise PermissionDenied
    form = UserCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Usuario creado correctamente.')
        return redirect('workdocs_users')
    users = User.objects.select_related('work_profile').order_by('username')
    return render(request, 'workdocs/users.html', {'users': users, 'form': form})
