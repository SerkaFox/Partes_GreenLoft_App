from .models import TaskFile, UserProfile


def get_user_role(user):
    if not user.is_authenticated:
        return ''
    if user.is_superuser:
        UserProfile.objects.update_or_create(user=user, defaults={'role': UserProfile.ROLE_ADMIN})
        return UserProfile.ROLE_ADMIN
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile.role


def is_admin(user):
    return get_user_role(user) == UserProfile.ROLE_ADMIN


def is_manager(user):
    return get_user_role(user) == UserProfile.ROLE_MANAGER


def is_technician(user):
    return get_user_role(user) == UserProfile.ROLE_TECHNICIAN


def detect_file_type(uploaded_file):
    content_type = (getattr(uploaded_file, 'content_type', '') or '').lower()
    name = (getattr(uploaded_file, 'name', '') or '').lower()
    if content_type.startswith('image/'):
        return TaskFile.TYPE_PHOTO
    if content_type == 'application/pdf' or name.endswith('.pdf'):
        return TaskFile.TYPE_PDF
    if content_type.startswith('video/'):
        return TaskFile.TYPE_VIDEO
    if content_type.startswith('audio/'):
        return TaskFile.TYPE_AUDIO
    if any(name.endswith(ext) for ext in ('.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv')):
        return TaskFile.TYPE_DOCUMENT
    return TaskFile.TYPE_OTHER
