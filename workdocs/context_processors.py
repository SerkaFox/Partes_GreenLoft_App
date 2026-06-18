from .utils import get_user_role


def workdocs_role(request):
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        return {'role': get_user_role(user)}
    return {'role': ''}
