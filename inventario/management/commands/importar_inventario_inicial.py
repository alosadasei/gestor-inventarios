"""
Carga inicial del inventario a partir de la plantilla Excel entregada por el
centro (PLANTILLA_INVENTARIO.xlsx). La lógica de parseo vive en
`inventario/importacion.py`, compartida con la vista web `importar_excel`.

Uso:
    python manage.py importar_inventario_inicial ruta/al/archivo.xlsx --usuario admin
    python manage.py importar_inventario_inicial ruta/al/archivo.xlsx --usuario admin --dry-run
"""

import openpyxl
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventario.importacion import importar_workbook


class Command(BaseCommand):
    """Comando de Django que carga el inventario inicial desde un Excel."""
    help = "Carga inicial del inventario desde la plantilla Excel de 4 hojas del centro."

    def add_arguments(self, parser):
        """Declara los argumentos de línea de comandos."""
        parser.add_argument("archivo", type=str, help="Ruta al .xlsx con las 4 hojas")
        parser.add_argument(
            "--usuario", type=str, required=True,
            help="Username que queda registrado como autor de las altas"
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Procesa y valida el archivo pero no guarda nada en la base de datos"
        )

    def handle(self, *args, **options):
        """Ejecuta la importación y muestra un resumen por terminal."""
        ruta = options["archivo"]
        dry_run = options["dry_run"]

        User = get_user_model()
        try:
            usuario = User.objects.get(username=options["usuario"])
        except User.DoesNotExist:
            raise CommandError(f"No existe ningún usuario con username='{options['usuario']}'")

        try:
            wb = openpyxl.load_workbook(ruta, data_only=True)
        except FileNotFoundError:
            raise CommandError(f"No se encuentra el archivo: {ruta}")

        # Todo ocurre en una transacción; con --dry-run se deshace al terminar.
        with transaction.atomic():
            sid = transaction.savepoint()
            resultado = importar_workbook(wb, usuario)
            if dry_run:
                transaction.savepoint_rollback(sid)
                self.stdout.write(self.style.WARNING("\nDRY-RUN activo: no se ha guardado nada."))
            else:
                transaction.savepoint_commit(sid)

        # Resumen de lo ocurrido.
        self.stdout.write("")
        for bloque_nombre in ("EQUIPO_INFORMATICO", "MOBILIARIO", "MAQUINARIA", "UTILLAJE"):
            self.stdout.write(f"  {bloque_nombre}: {resultado.stats[bloque_nombre]} bienes creados")
        self.stdout.write(f"  Filas omitidas (incompletas): {resultado.stats['omitidas']}")
        self.stdout.write(f"  Errores de validación: {resultado.stats['errores']}")
        if resultado.avisos:
            self.stdout.write(self.style.WARNING("\nAvisos:"))
            for aviso in resultado.avisos:
                self.stdout.write(f"  - {aviso}")
