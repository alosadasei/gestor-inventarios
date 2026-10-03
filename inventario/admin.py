"""
Configuración del panel de administración de Django para todos los modelos
del inventario (departamentos, ubicaciones, bienes, etiquetas, chequeos...).
"""
from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from import_export.admin import ImportExportModelAdmin

from .models import (
    Departamento,
    Ubicacion,
    PerfilUsuario,
    Bien,
    Etiqueta,
    HistorialMovimiento,
    ChequeoAnual,
    LineaChequeo,
)
from .resources import BienResource

# Modelo de usuario activo en el proyecto (el de Django por defecto).
User = get_user_model()


class UserCreationFormConEmail(UserCreationForm):
    """El formulario de alta de UserCreationForm no trae email; lo añadimos."""
    email = forms.EmailField(required=True, label="Correo electrónico")

    class Meta(UserCreationForm.Meta):
        fields = (*UserCreationForm.Meta.fields, "email")


class UserAdminEmailObligatorio(UserAdmin):
    """
    El correo es imprescindible: se usa para el código de acceso (2FA) y
    para restablecer la contraseña, así que lo exigimos tanto al crear
    como al editar cualquier usuario desde el admin.
    """
    # Formulario de alta con el campo de correo obligatorio.
    add_form = UserCreationFormConEmail
    # Campos que se piden en la pantalla "añadir usuario".
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2"),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        """Marca el correo como obligatorio también en el formulario de edición."""
        form = super().get_form(request, obj, **kwargs)
        if "email" in form.base_fields:
            form.base_fields["email"].required = True
        return form


# Sustituimos el admin de usuarios por defecto por la variante con correo obligatorio.
admin.site.unregister(User)
admin.site.register(User, UserAdminEmailObligatorio)


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    """Listado y búsqueda de departamentos."""
    list_display = ("nombre", "activo")
    search_fields = ("nombre",)


@admin.register(Ubicacion)
class UbicacionAdmin(admin.ModelAdmin):
    """Ubicaciones (aulas, talleres...) filtrables por departamento."""
    list_display = ("nombre", "departamento")
    list_filter = ("departamento",)
    search_fields = ("nombre",)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    """Perfil que asocia a cada usuario un rol (administrador o no) y un departamento."""
    list_display = ("usuario", "es_administrador", "departamento")
    list_filter = ("es_administrador", "departamento")


@admin.register(Bien)
class BienAdmin(ImportExportModelAdmin):
    """Gestión de bienes con importación/exportación a Excel/CSV desde el admin."""
    resource_classes = [BienResource]
    list_display = (
        "descripcion", "bloque", "departamento", "ubicacion",
        "estado", "es_cauce", "numero_activo_serie", "fecha_alta",
    )
    list_filter = ("bloque", "estado", "departamento", "es_cauce")
    search_fields = ("descripcion", "numero_activo_serie", "etiqueta_cauce")

    def save_model(self, request, obj, form, change):
        """Al crear un bien desde el admin, registra al usuario actual como creador."""
        if not change and not obj.creado_por_id:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    def get_resource_kwargs(self, request, *args, **kwargs):
        """Pasa el usuario que importa al recurso, para fijar `creado_por` en las altas."""
        kwargs = super().get_resource_kwargs(request, *args, **kwargs)
        kwargs["usuario_import"] = request.user
        return kwargs


@admin.register(Etiqueta)
class EtiquetaAdmin(admin.ModelAdmin):
    """Consulta de etiquetas generadas y su estado de impresión."""
    list_display = ("codigo_interno", "bien", "tipo", "impresa", "fecha_generacion")
    list_filter = ("tipo", "impresa")
    search_fields = ("codigo_interno",)


@admin.register(HistorialMovimiento)
class HistorialMovimientoAdmin(admin.ModelAdmin):
    """Trazabilidad de altas, traslados y bajas, navegable por fecha."""
    list_display = ("bien", "tipo", "usuario", "fecha")
    list_filter = ("tipo",)
    date_hierarchy = "fecha"


@admin.register(ChequeoAnual)
class ChequeoAnualAdmin(admin.ModelAdmin):
    """Chequeos anuales de inventario por departamento."""
    list_display = ("departamento", "anio", "estado", "fecha_apertura", "fecha_cierre")
    list_filter = ("estado", "anio")


@admin.register(LineaChequeo)
class LineaChequeoAdmin(admin.ModelAdmin):
    """Resultado del chequeo de cada bien dentro de un chequeo anual."""
    list_display = ("chequeo", "bien", "resultado")
    list_filter = ("resultado",)
