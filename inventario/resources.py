"""
Recursos de django-import-export.

Pensado para el uso continuo (chequeo anual, altas/bajas puntuales por Excel
desde el admin), no para la carga inicial masiva desde las 4 plantillas del
centro: eso lo cubre el comando `importar_inventario_inicial`, que respeta
el formato exacto de las plantillas entregadas por el centro (una hoja por
bloque, con sus propias columnas y celdas combinadas).
"""

from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from .models import Bien, Departamento, Ubicacion


class BienResource(resources.ModelResource):
    """Define cómo se importa/exporta un Bien (columnas y relaciones por nombre)."""
    # Departamento y ubicación se identifican por su nombre en el Excel, no por id.
    departamento = fields.Field(
        column_name="Departamento",
        attribute="departamento",
        widget=ForeignKeyWidget(Departamento, field="nombre"),
    )
    ubicacion = fields.Field(
        column_name="Ubicación",
        attribute="ubicacion",
        widget=ForeignKeyWidget(Ubicacion, field="nombre"),
    )

    class Meta:
        # Columnas incluidas y su orden en la exportación; `id` identifica filas existentes.
        model = Bien
        fields = (
            "id", "bloque", "departamento", "ubicacion", "descripcion",
            "categoria", "numero_activo_serie", "estado", "fecha_alta",
            "es_cauce", "etiqueta_cauce", "tipo_equipo", "uso",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True  # no reescribe filas sin cambios
        report_skipped = True

    def __init__(self, usuario_import=None, **kwargs):
        super().__init__(**kwargs)
        # Usuario que realiza la importación; se guarda como creador de los bienes nuevos.
        self.usuario_import = usuario_import

    def before_save_instance(self, instance, row, **kwargs):
        """Asigna el creador a los bienes nuevos justo antes de guardarlos."""
        if not instance.creado_por_id:
            instance.creado_por = self.usuario_import

    def before_import_row(self, row, **kwargs):
        """
        Al editar/reimportar desde el admin, la Ubicación debe existir ya
        dentro del Departamento indicado (no se crean ubicaciones nuevas
        por esta vía para evitar duplicados por errores de tecleo).
        """
        departamento_nombre = row.get("Departamento")
        ubicacion_nombre = row.get("Ubicación")
        if departamento_nombre and ubicacion_nombre:
            Ubicacion.objects.get_or_create(
                departamento=Departamento.objects.get_or_create(nombre=departamento_nombre)[0],
                nombre=ubicacion_nombre,
            )
