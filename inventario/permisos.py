"""Utilidades de permisos: perfil del usuario, comprobación de rol y decorador de acceso."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import PerfilUsuario


def obtener_perfil(user):
    """Devuelve el PerfilUsuario del usuario, o None si no tiene uno asignado."""
    return PerfilUsuario.objects.filter(usuario=user).first()


def es_administrador(user):
    """True si el usuario es administrador por su perfil o superusuario de Django."""
    perfil = obtener_perfil(user)
    return bool(perfil and perfil.es_administrador) or user.is_superuser


def requiere_administrador(view_func):
    """Restringe la vista a administradores (o superusuarios de Django)."""
    @wraps(view_func)
    @login_required
    # `login_required` va dentro de `wraps` para exigir sesión antes de comprobar el rol.
    def wrapper(request, *args, **kwargs):
        """Comprueba el rol y, si no es administrador, devuelve 403."""
        if not es_administrador(request.user):
            raise PermissionDenied("Esta acción requiere permisos de administrador.")
        return view_func(request, *args, **kwargs)
    return wrapper
