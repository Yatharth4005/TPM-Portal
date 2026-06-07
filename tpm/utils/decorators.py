# tpm/utils/decorators.py

from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)
        if not request.user.is_admin():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper

def dept_access_required(view_func):
    """Admin passes through. USER must own the requested dept_id."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)
        dept_id = kwargs.get('dept_id')
        if not request.user.is_admin():
            if request.user.department_id != dept_id:
                raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper
