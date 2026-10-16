from django.http import HttpResponseForbidden
from functools import wraps

def management_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Check if user is staff or has the 'Management' role
        if request.user.is_authenticated and (request.user.is_staff or getattr(request.user, 'role', None) == 'Management'):
            return view_func(request, *args, **kwargs)
        
        # Throw a 403 Forbidden error if they shouldn't be here
        return HttpResponseForbidden("You do not have permission to access this management view.")
        
    return _wrapped_view
