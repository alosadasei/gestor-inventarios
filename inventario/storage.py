"""
inventario/storage.py

Django solo antepone el SCRIPT_NAME a STATIC_URL / MEDIA_URL cuando esos
ajustes son rutas relativas, y además cachea el resultado la primera vez que se
leen (al arrancar el proceso, cuando todavía no hay petición ni prefijo). Como
aquí el prefijo llega por cabecera en cada petición (ver
inventario.middleware.ScriptNameMiddleware), lo añadimos al construir cada URL.
"""

from django.core.files.storage import FileSystemStorage
from django.urls import get_script_prefix
from whitenoise.storage import CompressedManifestStaticFilesStorage


def _con_prefijo(url):
    """Antepone a `url` la subruta actual, si la hay."""
    prefijo = get_script_prefix().rstrip('/')
    if prefijo and url.startswith('/') and not url.startswith(prefijo + '/'):
        return prefijo + url
    return url


class ScriptPrefixStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Estáticos (WhiteNoise) servidos bajo la subruta."""

    def url(self, name):
        """URL del estático con el prefijo de subruta de la petición actual."""
        return _con_prefijo(super().url(name))


class ScriptPrefixMediaStorage(FileSystemStorage):
    """Archivos subidos por los usuarios (plantillas Excel del chequeo anual) servidos bajo la subruta."""

    def url(self, name):
        """URL del archivo subido con el prefijo de subruta de la petición actual."""
        return _con_prefijo(super().url(name))
