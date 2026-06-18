from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import UserProfile
from .utils import get_user_role


def role_required(*roles, redirect_technician=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            role = get_user_role(request.user)
            if role in roles:
                return view_func(request, *args, **kwargs)
            if redirect_technician and role == UserProfile.ROLE_TECHNICIAN:
                return redirect('workdocs_dashboard')
            raise PermissionDenied
        return wrapper
    return decorator


def admin_or_manager_required(view_func):
    return role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER, redirect_technician=True)(view_func)


def technician_redirect_if_panel(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and get_user_role(request.user) == UserProfile.ROLE_TECHNICIAN:
            return redirect('workdocs_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
