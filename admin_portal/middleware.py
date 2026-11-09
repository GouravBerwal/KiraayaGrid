from django.shortcuts import redirect
from django.http import JsonResponse
from django.contrib import messages


class AdminSuperuserMiddleware:
    """
    Strict security & access control middleware:
    1. Admin Portal: ONLY authenticated users with is_superuser=True can access.
    2. Owner Portal: Authenticated users with role='OWNER' (or is_superuser).
    3. Tenant Portal: Authenticated users with role='TENANT' (or is_superuser).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        resolver_match = getattr(request, 'resolver_match', None)
        if not resolver_match:
            return None

        app_name = resolver_match.app_name

        # 1. Admin Portal -> STRICT SUPERUSER ONLY
        if app_name == 'admin_portal':
            if not request.user.is_authenticated or not request.user.is_superuser:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/api/'):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Superuser privileges required to access Admin Portal.'
                    }, status=403)
                messages.error(request, "Access restricted: Only verified Superusers can access the Admin Portal. Please log in with your Super Admin credentials.")
                return redirect(f"/auth/?role=ADMIN&next={request.path}")

        # 2. Owner Portal -> OWNER or Superuser
        elif app_name == 'owner_portal':
            if not request.user.is_authenticated or (getattr(request.user, 'role', '') != 'OWNER' and not request.user.is_superuser):
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/api/'):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Host authentication required.'
                    }, status=401)
                messages.error(request, "Please log in to your Host Account to access Owner Workbench.")
                return redirect(f"/auth/?role=OWNER&next={request.path}")

        # 3. Tenant Portal -> TENANT or Superuser
        elif app_name == 'tenant_portal':
            if not request.user.is_authenticated or (getattr(request.user, 'role', '') != 'TENANT' and not request.user.is_superuser):
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/api/'):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Resident authentication required.'
                    }, status=401)
                messages.error(request, "Please log in to your Resident Account to access Tenant Portal.")
                return redirect(f"/auth/?role=TENANT&next={request.path}")

        return None
