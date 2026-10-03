"""Configuración de la aplicación `inventario` para Django."""
from django.apps import AppConfig


class InventarioConfig(AppConfig):
    """Declara la app y registra sus señales al arrancar."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventario'

    def ready(self):
        """Se ejecuta al iniciar Django: importa signals para activar sus receptores."""
        from . import signals  # noqa: F401
