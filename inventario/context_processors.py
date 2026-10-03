"""
inventario/context_processors.py
Variables globales disponibles en todos los templates sin necesidad de
pasarlas manualmente desde cada vista.
"""
from .permisos import es_administrador, obtener_perfil


def rol_usuario(request):
    """Expone en las plantillas si el usuario es administrador y su departamento."""
    if not request.user.is_authenticated:
        return {}

    perfil = obtener_perfil(request.user)
    return {
        'es_administrador': es_administrador(request.user),
        'dpto_usuario': perfil.departamento if perfil else None,
    }
