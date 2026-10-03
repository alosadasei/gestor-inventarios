"""Formularios de la aplicación: acceso, recuperación de contraseña, altas, traslados, bajas e importación."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm

from .models import Bien, BloqueInmovilizado, MotivoBaja, TipoEquipoInformatico, Ubicacion, UsoEquipo


def _aplicar_clases_bootstrap(form):
    """Aplica las clases Bootstrap: form-control / form-select / form-check-input."""
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "form-check-input")
        elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
            widget.attrs.setdefault("class", "form-select")
        else:
            widget.attrs.setdefault("class", "form-control")


class LoginForm(AuthenticationForm):
    """Formulario de usuario y contraseña (primer factor) con estilo Bootstrap."""
    username = forms.CharField(
        label="Usuario",
        widget=forms.TextInput(attrs={"autofocus": True, "class": "form-control", "placeholder": "usuario"}),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "••••••••"}),
    )


class VerificarCodigoForm(forms.Form):
    """Código de 6 dígitos enviado por correo (segundo factor de acceso)."""
    codigo = forms.CharField(
        label="Código de verificación",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "••••••",
            "inputmode": "numeric",
            "autocomplete": "one-time-code",
            "autofocus": True,
        }),
        help_text="Introduce el código de 6 dígitos que te hemos enviado por correo.",
    )

    def clean_codigo(self):
        """Rechaza códigos con caracteres que no sean dígitos."""
        codigo = self.cleaned_data.get("codigo", "").strip()
        if not codigo.isdigit():
            raise forms.ValidationError("El código solo puede contener dígitos.")
        return codigo


class NuevaPasswordForm(SetPasswordForm):
    """Fijar una contraseña nueva tras seguir el enlace de recuperación."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password2"].label = "Confirmar nueva contraseña"
        _aplicar_clases_bootstrap(self)


class RecuperarPasswordForm(PasswordResetForm):
    """Solicitud de recuperación de contraseña, con estilo Bootstrap."""
    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={
            "autofocus": True,
            "class": "form-control",
            "placeholder": "tucorreo@ejemplo.com",
        }),
    )


class AltaBienForm(forms.ModelForm):
    """
    Alta manual de un bien. `departamento` llega ya resuelto desde la vista
    (el propio del usuario, o el elegido por un administrador) y se usa
    para restringir el queryset de `ubicacion` a las suyas.
    """

    class Meta:
        model = Bien
        fields = [
            "bloque", "ubicacion", "descripcion", "categoria",
            "numero_activo_serie", "estado",
            "es_cauce", "etiqueta_cauce", "tipo_equipo", "uso",
        ]
        labels = {
            "bloque": "Bloque de inmovilizado",
            "ubicacion": "Ubicación",
            "descripcion": "Descripción",
            "categoria": "Categoría",
            "numero_activo_serie": "Número de activo / serie",
            "estado": "Estado",
            "es_cauce": "¿Es CAUCE?",
            "etiqueta_cauce": "Etiqueta CAUCE",
            "tipo_equipo": "Tipo de equipo",
            "uso": "Uso",
        }

    def __init__(self, *args, departamento=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Se conserva el departamento para asignarlo al guardar (no es un campo del formulario).
        self.departamento = departamento
        if departamento is not None:
            self.instance.departamento = departamento
            self.fields["ubicacion"].queryset = Ubicacion.objects.filter(departamento=departamento)
        # Campos opcionales a nivel de formulario; `clean` decide cuáles exigir según el bloque.
        self.fields["etiqueta_cauce"].required = False
        self.fields["tipo_equipo"].required = False
        self.fields["uso"].required = False
        self.fields["categoria"].required = False
        self.fields["numero_activo_serie"].required = False
        _aplicar_clases_bootstrap(self)

    def clean(self):
        """Valida los campos propios de equipos informáticos y vacía los que no aplican al resto de bloques."""
        cleaned = super().clean()
        bloque = cleaned.get("bloque")
        if bloque == BloqueInmovilizado.EQUIPO_INFORMATICO:
            if not cleaned.get("tipo_equipo"):
                self.add_error("tipo_equipo", "Obligatorio para equipos informáticos.")
            if cleaned.get("es_cauce") and not cleaned.get("etiqueta_cauce"):
                self.add_error("etiqueta_cauce", "Obligatoria si el equipo es CAUCE.")
        else:
            cleaned["es_cauce"] = False
            cleaned["etiqueta_cauce"] = ""
            cleaned["tipo_equipo"] = ""
            cleaned["uso"] = ""
        return cleaned

    def save(self, commit=True):
        """Guarda el bien asignándole el departamento recibido de la vista."""
        bien = super().save(commit=False)
        bien.departamento = self.departamento
        if commit:
            bien.save()
        return bien


class BusquedaBienForm(forms.Form):
    """Localizar un bien por código escaneado o eligiéndolo de una lista."""
    codigo = forms.CharField(required=False, label="Código escaneado")
    bien = forms.ModelChoiceField(
        queryset=Bien.objects.none(), required=False, label="O selecciona un bien"
    )

    def __init__(self, *args, queryset_bienes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bien"].queryset = queryset_bienes if queryset_bienes is not None else Bien.objects.all()
        _aplicar_clases_bootstrap(self)


class TrasladoForm(forms.Form):
    """Elección de la nueva ubicación (limitada por la vista) y observaciones del traslado."""
    nueva_ubicacion = forms.ModelChoiceField(queryset=Ubicacion.objects.none(), label="Nueva ubicación")
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, queryset_ubicaciones=None, **kwargs):
        super().__init__(*args, **kwargs)
        if queryset_ubicaciones is not None:
            self.fields["nueva_ubicacion"].queryset = queryset_ubicaciones
        _aplicar_clases_bootstrap(self)


class SolicitudBajaForm(forms.Form):
    """Motivo y observaciones de una solicitud de baja."""
    motivo_baja = forms.ChoiceField(choices=MotivoBaja.choices, label="Motivo")
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_clases_bootstrap(self)


class ImportarExcelForm(forms.Form):
    """Subida del Excel de importación, con opción de simular antes de guardar."""
    archivo = forms.FileField(
        label="Archivo Excel (.xlsx)",
        help_text="Debe tener las hojas EQUIPOS INFORMÁTICOS, MAQUINARIA, MOBILIARIO y UTILLAJE, "
                   "como la plantilla del centro.",
    )
    dry_run = forms.BooleanField(
        label="Solo simular (no guardar nada todavía)",
        required=False,
        initial=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_clases_bootstrap(self)

    def clean_archivo(self):
        """Solo admite archivos con extensión .xlsx."""
        archivo = self.cleaned_data["archivo"]
        if not archivo.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("El archivo debe ser un .xlsx.")
        return archivo
