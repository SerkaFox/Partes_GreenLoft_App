from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from partes.forms import VehiculoForm
from partes.models import Vehiculo

from .forms import CommentForm, ProfileForm, TaskFileForm, TaskForm, UserCreateForm, UserEditForm, VoiceReportForm
from .models import Task, TaskEvent, TaskEventRead, TaskFile, TaskVoiceReport, UserProfile
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
    profile = getattr(user, 'work_profile', None)
    vehicle = profile.vehicle if profile and profile.vehicle_id else None
    return {
        'id': user.id,
        'username': user.get_username(),
        'full_name': _display_user(user),
        'role': get_user_role(user),
        'vehicle': _vehicle_payload(vehicle) if vehicle else None,
    }


def _vehicle_payload(vehicle, request=None):
    image_url = ''
    if vehicle.image:
        image_url = request.build_absolute_uri(vehicle.image.url) if request else vehicle.image.url
    return {
        'id': vehicle.id,
        'matricula': vehicle.matricula,
        'descripcion': vehicle.descripcion,
        'image_url': image_url,
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


@require_GET
def vehicle_search(request):
    q = (request.GET.get('q') or '').strip()
    qs = Vehiculo.objects.filter(activo=True)
    if q:
        qs = qs.filter(Q(matricula__icontains=q) | Q(descripcion__icontains=q))
    qs = qs.order_by('orden', 'matricula')[:12]
    return JsonResponse([_vehicle_payload(vehicle, request) for vehicle in qs], safe=False)


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


def _with_comment_count(qs):
    return qs.annotate(
        comment_count=Count('events', filter=Q(events__event_type=TaskEvent.EVENT_COMMENT), distinct=True),
        voice_count=Count('voice_reports', filter=Q(voice_reports__report_type=TaskVoiceReport.TYPE_REPORT), distinct=True),
        file_count=Count('files', distinct=True),
    )


def _attach_unread_counts(tasks, user):
    task_list = list(tasks)
    if not task_list:
        return task_list
    counts = TaskEvent.objects.filter(
        task_id__in=[task.pk for task in task_list],
        event_type=TaskEvent.EVENT_COMMENT,
    ).exclude(user=user).exclude(reads__user=user).values('task_id').annotate(count=Count('id'))
    by_task = {item['task_id']: item['count'] for item in counts}
    for task in task_list:
        task.unread_count = by_task.get(task.pk, 0)
    return task_list


def _can_edit_task(user, task):
    role = get_user_role(user)
    return role == UserProfile.ROLE_ADMIN or (role == UserProfile.ROLE_MANAGER and task.created_by_id == user.id)


def _get_visible_task(user, pk):
    task = get_object_or_404(_visible_tasks(user), pk=pk)
    return task


def _add_event(task, user, event_type, comment=''):
    return TaskEvent.objects.create(task=task, user=user, event_type=event_type, comment=comment)


def _comment_user_url(user):
    role = get_user_role(user)
    if role == UserProfile.ROLE_TECHNICIAN:
        return reverse('workdocs_technician_detail', args=[user.pk])
    return reverse('workdocs_user_edit', args=[user.pk])


def _task_user_url(user, viewer):
    if not _can_manage_users(viewer):
        return ''
    return _comment_user_url(user)


def _unread_event_ids(task, user):
    return set(
        task.events.filter(event_type=TaskEvent.EVENT_COMMENT)
        .exclude(user=user)
        .exclude(reads__user=user)
        .values_list('id', flat=True)
    )


def _mark_task_events_read(task, user):
    unread_ids = _unread_event_ids(task, user)
    TaskEventRead.objects.bulk_create(
        [TaskEventRead(event_id=event_id, user=user) for event_id in unread_ids],
        ignore_conflicts=True,
    )
    return unread_ids


def _chat_items(task, viewer, unread_event_ids=None):
    unread_event_ids = unread_event_ids or set()
    items = []
    comments = task.events.filter(event_type=TaskEvent.EVENT_COMMENT).select_related('user', 'parent_event', 'parent_event__user').prefetch_related('reads')
    for event in comments:
        _ensure_profile(event.user)
        if event.parent_event_id:
            _ensure_profile(event.parent_event.user)
        event.user_url = _task_user_url(event.user, viewer)
        event.is_unread = event.id in unread_event_ids
        event.read_by_others = event.user_id == viewer.id and any(read.user_id != viewer.id for read in event.reads.all())
        items.append({
            'kind': 'comment',
            'created_at': event.created_at,
            'user': event.user,
            'user_url': event.user_url,
            'event': event,
        })
    reports = task.voice_reports.filter(report_type=TaskVoiceReport.TYPE_REPORT).select_related('technician')
    for report in reports:
        _ensure_profile(report.technician)
        items.append({
            'kind': 'voice',
            'created_at': report.created_at,
            'user': report.technician,
            'user_url': _task_user_url(report.technician, viewer),
            'report': report,
        })
    files = task.files.select_related('uploaded_by')
    for item in files:
        _ensure_profile(item.uploaded_by)
        items.append({
            'kind': 'file',
            'created_at': item.created_at,
            'user': item.uploaded_by,
            'user_url': _task_user_url(item.uploaded_by, viewer),
            'file': item,
        })
    return sorted(items, key=lambda item: item['created_at'])


def _events_for_display(task):
    events = []
    seen_status = set()
    for event in task.events.select_related('user')[:120]:
        if event.event_type == TaskEvent.EVENT_STATUS and event.comment in seen_status:
            continue
        if event.event_type == TaskEvent.EVENT_STATUS:
            seen_status.add(event.comment)
        events.append(event)
        if len(events) >= 80:
            break
    return events


def _selected_technicians(form):
    return list(form.cleaned_data.get('technicians') or [])


def _sync_task_technicians(task, technicians):
    task.technicians.set(technicians)
    primary = technicians[0] if technicians else None
    update_fields = []
    if task.assigned_to_id != (primary.id if primary else None):
        task.assigned_to = primary
        update_fields.append('assigned_to')
    if primary and not task.vehicle_id:
        profile = getattr(primary, 'work_profile', None)
        if profile and profile.vehicle_id:
            task.vehicle = profile.vehicle
            update_fields.append('vehicle')
    if update_fields:
        task.save(update_fields=[*update_fields, 'updated_at'])


def _save_uploaded_files(task, user, files, comment=''):
    saved = 0
    voice_saved = 0
    for uploaded in files:
        file_type = detect_file_type(uploaded)
        if file_type == TaskFile.TYPE_AUDIO:
            TaskVoiceReport.objects.create(task=task, technician=user, audio_file=uploaded)
            voice_saved += 1
            continue
        TaskFile.objects.create(
            task=task,
            uploaded_by=user,
            file=uploaded,
            file_type=file_type,
            original_name=uploaded.name[:255],
            comment=comment,
        )
        saved += 1
    if saved:
        _add_event(task, user, TaskEvent.EVENT_FILE, f'{saved} archivo(s) subido(s).')
    if voice_saved:
        _add_event(task, user, TaskEvent.EVENT_AUDIO, f'{voice_saved} audio(s) subido(s).')
    return saved + voice_saved


def _save_description_audio(task, user, uploaded):
    if not uploaded:
        return None
    report = TaskVoiceReport.objects.create(
        task=task,
        technician=user,
        audio_file=uploaded,
        report_type=TaskVoiceReport.TYPE_DESCRIPTION,
    )
    _add_event(task, user, TaskEvent.EVENT_AUDIO, 'Descripción de voz añadida. Se transcribirá automáticamente.')
    return report


def _wants_json(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


@login_required(login_url='/panel/login/')
def dashboard(request):
    role = get_user_role(request.user)
    qs = _visible_tasks(request.user)
    active_statuses = _active_statuses()
    active_tasks = _with_comment_count(qs.filter(status__in=active_statuses))
    context = {
        'role': role,
        'tasks': _attach_unread_counts(active_tasks[:40], request.user),
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
                technician.active_task_titles = list(tech_tasks.order_by('-updated_at').values_list('title', flat=True)[:3])
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
    qs = _with_comment_count(qs)
    return render(request, 'workdocs/task_list.html', {
        'tasks': _attach_unread_counts(qs[:300], request.user),
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
                old_status = task.status
                old_technicians = set(task.technicians.values_list('id', flat=True))
                task = form.save(commit=False)
                technicians = _selected_technicians(form)
                task.save()
                _sync_task_technicians(task, technicians)
                new_technicians = {user.id for user in technicians}
                if old_assignee != task.assigned_to_id or old_technicians != new_technicians:
                    label = ', '.join(_display_user(user) for user in technicians) if technicians else 'Sin asignar'
                    _add_event(task, request.user, TaskEvent.EVENT_ASSIGNED, f'Técnicos asignados: {label}.')
                if old_status != task.status:
                    _add_event(task, request.user, TaskEvent.EVENT_STATUS, f'Estado actualizado: {task.get_status_display()}.')
                _save_description_audio(task, request.user, request.FILES.get('description_audio'))
                if _wants_json(request):
                    return JsonResponse({'ok': True, 'message': 'Guardado automáticamente.'})
                messages.success(request, 'Guardado correctamente.')
                return redirect('workdocs_task_detail', pk=task.pk)
            if _wants_json(request):
                return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
            messages.error(request, 'No se pudo guardar la tarea. Revisa los campos.')
        elif action == 'upload_files':
            uploaded_files = request.FILES.getlist('files')
            if uploaded_files:
                count = _save_uploaded_files(task, request.user, uploaded_files, request.POST.get('comment') if request.POST.get('with_file_comment') else '')
                if _wants_json(request):
                    return JsonResponse({'ok': True, 'message': f'{count} archivo(s) subido(s).'})
                messages.success(request, f'{count} archivo(s) subido(s).')
                return redirect('workdocs_task_detail', pk=task.pk)
            if _wants_json(request):
                return JsonResponse({'ok': False, 'errors': {'files': ['No se ha seleccionado ningún archivo.']}}, status=400)
            messages.error(request, 'No se pudo subir el archivo: no se ha seleccionado ningún archivo.')
        elif action == 'comment':
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                parent = None
                reply_to = request.POST.get('reply_to')
                if reply_to:
                    parent = task.events.filter(pk=reply_to, event_type=TaskEvent.EVENT_COMMENT).first()
                TaskEvent.objects.create(
                    task=task,
                    user=request.user,
                    event_type=TaskEvent.EVENT_COMMENT,
                    comment=comment_form.cleaned_data['comment'],
                    parent_event=parent,
                )
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
                if _wants_json(request):
                    return JsonResponse({'ok': True, 'message': 'Audio subido correctamente.'})
                messages.success(request, 'Audio subido correctamente.')
                return redirect('workdocs_task_detail', pk=task.pk)
            if _wants_json(request):
                return JsonResponse({'ok': False, 'errors': voice_form.errors}, status=400)
            messages.error(request, f'No se pudo subir el audio: {voice_form.errors.as_text()}')

    created_by_url = _task_user_url(task.created_by, request.user)
    technicians_info = [
        {'user': technician, 'url': _task_user_url(technician, request.user)}
        for technician in task.assigned_technicians
    ]
    unread_event_ids = _unread_event_ids(task, request.user)
    chat_items = _chat_items(task, request.user, unread_event_ids)
    TaskEventRead.objects.bulk_create(
        [TaskEventRead(event_id=event_id, user=request.user) for event_id in unread_event_ids],
        ignore_conflicts=True,
    )
    return render(request, 'workdocs/task_detail.html', {
        'task': task,
        'map_coords': f'{task.latitude},{task.longitude}' if task.latitude and task.longitude else '',
        'role': role,
        'can_edit_task': _can_edit_task(request.user, task),
        'created_by_url': created_by_url,
        'technicians_info': technicians_info,
        'vehicle_url': reverse('workdocs_vehicle_edit', args=[task.vehicle_id]) if task.vehicle_id and _can_manage_users(request.user) else '',
        'task_form': TaskForm(instance=task, role=role),
        'file_form': TaskFileForm(),
        'comment_form': CommentForm(),
        'voice_form': VoiceReportForm(),
        'files': task.files.select_related('uploaded_by'),
        'events': _events_for_display(task),
        'chat_items': chat_items,
        'can_manage_users': _can_manage_users(request.user),
        'description_voice_reports': task.voice_reports.filter(report_type=TaskVoiceReport.TYPE_DESCRIPTION).select_related('technician'),
    })


@login_required(login_url='/panel/login/')
@require_POST
def task_comment_reaction(request, pk, event_pk):
    task = _get_visible_task(request.user, pk)
    event = get_object_or_404(task.events.filter(event_type=TaskEvent.EVENT_COMMENT), pk=event_pk)
    emoji = request.POST.get('emoji') or ''
    if emoji not in {'👍', '✅', '👀', '🙏'}:
        raise PermissionDenied
    reactions = dict(event.reactions or {})
    reactions[emoji] = int(reactions.get(emoji, 0)) + 1
    event.reactions = reactions
    event.save(update_fields=['reactions'])
    return redirect('workdocs_task_detail', pk=task.pk)


@login_required(login_url='/panel/login/')
@require_POST
def task_continue(request, pk):
    source = _get_visible_task(request.user, pk)
    if not _can_edit_task(request.user, source):
        raise PermissionDenied
    task = Task.objects.create(
        title=f'{source.title} - continuación',
        description=source.description,
        address=source.address,
        latitude=source.latitude,
        longitude=source.longitude,
        status=Task.STATUS_ASIGNADA if source.assigned_to_id else Task.STATUS_NUEVA,
        created_by=request.user,
        assigned_to=source.assigned_to,
        vehicle=source.vehicle,
        parent_task=source,
    )
    task.technicians.set(source.assigned_technicians)
    _add_event(task, request.user, TaskEvent.EVENT_CREATED, f'Continuación de tarea #{source.pk}.')
    _add_event(source, request.user, TaskEvent.EVENT_STATUS, f'Tarea continuada en #{task.pk}.')
    messages.success(request, 'Continuación creada correctamente.')
    return redirect('workdocs_task_detail', pk=task.pk)


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
        'left_object': 'Salí del objeto',
        'finished': 'Trabajo finalizado correctamente.',
    }
    if action == 'arrived_work':
        task.status = Task.STATUS_EN_CAMINO
        task.started_at = task.started_at or now
    elif action == 'arrived_object':
        task.status = Task.STATUS_EN_OBJETO
        task.arrived_at = task.arrived_at or now
    elif action == 'left_object':
        task.status = Task.STATUS_PENDIENTE_REVISION
        task.finished_at = task.finished_at or now
    elif action == 'finished':
        task.status = Task.STATUS_FINALIZADA
        task.finished_at = task.finished_at or now
    else:
        raise PermissionDenied
    task.save(update_fields=['status', 'started_at', 'arrived_at', 'finished_at', 'updated_at'])
    _add_event(task, request.user, TaskEvent.EVENT_STATUS, labels[action])
    messages.success(request, labels[action])
    return redirect('workdocs_task_detail', pk=task.pk)


@login_required(login_url='/panel/login/')
@require_POST
def task_quick_status(request, pk):
    task = _get_visible_task(request.user, pk)
    if not _can_edit_task(request.user, task):
        raise PermissionDenied
    status = request.POST.get('status')
    valid_statuses = {value for value, _label in Task.STATUS_CHOICES}
    if status not in valid_statuses:
        messages.error(request, 'Estado no válido.')
        return redirect(request.POST.get('next') or 'workdocs_dashboard')
    if task.status != status:
        task.status = status
        task.save(update_fields=['status', 'updated_at'])
        _add_event(task, request.user, TaskEvent.EVENT_STATUS, f'Estado actualizado: {task.get_status_display()}.')
        messages.success(request, 'Estado actualizado correctamente.')
    return redirect(request.POST.get('next') or 'workdocs_dashboard')


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
    state = request.GET.get('state') or 'all'
    if state not in {'all', 'active', 'inactive'}:
        state = 'all'
    form = UserCreateForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Usuario creado correctamente.')
        return redirect('workdocs_users')
    active_statuses = _active_statuses()
    users = User.objects.select_related('work_profile').order_by('username')
    filtered_users = []
    for item in users:
        _ensure_profile(item)
        is_active = item.is_active and item.work_profile.active
        if state == 'active' and not is_active:
            continue
        if state == 'inactive' and is_active:
            continue
        item.active_task_count = Task.objects.filter(Q(assigned_to=item) | Q(technicians=item), status__in=active_statuses).distinct().count()
        filtered_users.append(item)
    return render(request, 'workdocs/users.html', {'users': filtered_users, 'form': form, 'state_filter': state})


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
    state = request.GET.get('state') or 'all'
    if state not in {'all', 'active', 'inactive'}:
        state = 'all'
    vehicle = get_object_or_404(Vehiculo, pk=pk) if pk else None
    form = VehiculoForm(request.POST or None, request.FILES or None, instance=vehicle)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Vehículo guardado correctamente.')
        return redirect('workdocs_vehicles')
    vehicles_qs = Vehiculo.objects.all()
    if state == 'active':
        vehicles_qs = vehicles_qs.filter(activo=True)
    elif state == 'inactive':
        vehicles_qs = vehicles_qs.filter(activo=False)
    return render(request, 'workdocs/vehicles.html', {
        'form': form,
        'vehicles': vehicles_qs,
        'editing': vehicle,
        'state_filter': state,
        'role': get_user_role(request.user),
    })
