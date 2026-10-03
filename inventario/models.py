"""
Modelos de datos - App de Inventario

Bloques de inmovilizado: EQUIPOS INFORMÁTICOS, MOBILIARIO, MAQUINARIA, UTILLAJE.
Un único modelo `Bien` centraliza el inventario (facilita filtros y búsquedas
multicriterio transversales), con un subconjunto de campos específico para
equipos informáticos (CAUCE / NO CAUCE, tipo, uso).
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
import secrets


# ---------------------------------------------------------------------------
# Organización: departamentos y ubicaciones
# ---------------------------------------------------------------------------

class Departamento(models.Model):
    """Departamento del centro propietario de bienes y ubicaciones."""
    nombre = models.CharField(max_length=150, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        """Representación en texto usada en el admin y las listas."""
        return self.nombre


class Ubicacion(models.Model):
    """Aula, taller u otra dependencia física, adscrita a un departamento."""
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT, related_name="ubicaciones"
    )
    nombre = models.CharField(max_length=150, help_text="Ej: Aula 434, Taller Informática")

    class Meta:
        unique_together = ("departamento", "nombre")
        ordering = ["departamento__nombre", "nombre"]

    def __str__(self):
        """Representación en texto usada en el admin y las listas."""
        return f"{self.nombre} ({self.departamento.nombre})"


# ---------------------------------------------------------------------------
# Perfil de usuario / roles
# ---------------------------------------------------------------------------

class PerfilUsuario(models.Model):
    """
    Extiende el usuario de Django con su rol y, si procede, el departamento
    al que queda restringido su acceso.

    - Administrador: es_administrador=True, departamento=None -> acceso global.
    - Usuario de departamento: es_administrador=False, departamento=<FK obligatoria>.
    """
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil_inventario"
    )
    es_administrador = models.BooleanField(default=False)
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT, null=True, blank=True,
        related_name="usuarios"
    )

    def clean(self):
        """Validación del modelo antes de guardar."""
        if not self.es_administrador and self.departamento is None:
            raise ValidationError(
                "Un usuario de departamento debe tener un departamento asignado."
            )
        if not self.usuario.email:
            raise ValidationError(
                "El usuario debe tener un correo electrónico: se usa para el "
                "código de acceso y para restablecer la contraseña."
            )

    def __str__(self):
        """Representación en texto usada en el admin y las listas."""
        rol = "Administrador" if self.es_administrador else f"Depto. {self.departamento}"
        return f"{self.usuario.get_username()} — {rol}"


# ---------------------------------------------------------------------------
# Bien inventariable
# ---------------------------------------------------------------------------

class BloqueInmovilizado(models.TextChoices):
    """Bloques de inmovilizado: una hoja del Excel por cada uno."""
    EQUIPO_INFORMATICO = "EQUIPO_INFORMATICO", "Equipo informático"
    MOBILIARIO = "MOBILIARIO", "Mobiliario"
    MAQUINARIA = "MAQUINARIA", "Maquinaria"
    UTILLAJE = "UTILLAJE", "Utillaje"


class EstadoBien(models.TextChoices):
    """Estados posibles de un bien."""
    OPERATIVO = "OPERATIVO", "Operativo"
    NO_OPERATIVO = "NO_OPERATIVO", "No operativo"
    EN_REPARACION = "EN_REPARACION", "En reparación"
    EN_ALMACEN = "EN_ALMACEN", "En almacén"
    BAJA = "BAJA", "Baja"


class TipoEquipoInformatico(models.TextChoices):
    """Tipos de equipo del bloque de equipos informáticos."""
    ORDENADOR = "ORDENADOR", "Ordenador"
    MONITOR = "MONITOR", "Monitor"
    PORTATIL = "PORTATIL", "Portátil"
    IMPRESORA = "IMPRESORA", "Impresora"
    ESCANER = "ESCANER", "Escáner"
    PROYECTOR = "PROYECTOR", "Proyector"
    CARRO = "CARRO", "Carro"
    PANTALLA_DIGITAL = "PANTALLA_DIGITAL", "Pantalla digital"
    OTROS = "OTROS", "Otros"


class UsoEquipo(models.TextChoices):
    """Uso de un equipo: docente o de alumnado."""
    DOCENTE = "DOCENTE", "Docente"
    ALUMNADO = "ALUMNADO", "Alumnado"


class MotivoBaja(models.TextChoices):
    """Motivos por los que se solicita una baja."""
    ROTURA_IRREPARABLE = "ROTURA_IRREPARABLE", "Rotura irreparable"
    OBSOLESCENCIA = "OBSOLESCENCIA", "Obsolescencia"
    PERDIDA = "PERDIDA", "Pérdida"
    DEVOLUCION_CAUCE = "DEVOLUCION_CAUCE", "Devolución CAUCE"


class Bien(models.Model):
    """Tabla general de inventario: un registro por bien, de cualquier bloque."""

    bloque = models.CharField(max_length=30, choices=BloqueInmovilizado.choices)
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT, related_name="bienes"
    )
    ubicacion = models.ForeignKey(
        Ubicacion, on_delete=models.PROTECT, related_name="bienes"
    )
    descripcion = models.CharField(max_length=255)
    categoria = models.CharField(
        max_length=100, blank=True,
        help_text="Mobiliario/Maquinaria/Utillaje: Asientos, Mesas, Almacenaje, Otros..."
    )
    numero_activo_serie = models.CharField(
        max_length=100, blank=True,
        help_text="Número de activo (mobiliario/maquinaria/utillaje) o número de serie (equipos)"
    )
    estado = models.CharField(
        max_length=20, choices=EstadoBien.choices, default=EstadoBien.OPERATIVO
    )
    fecha_alta = models.DateField(auto_now_add=True)

    # --- Campos específicos de EQUIPO_INFORMATICO ---
    es_cauce = models.BooleanField(
        default=False,
        help_text="Marca si el equipo es CAUCE (numeración oficial externa) o NO CAUCE"
    )
    etiqueta_cauce = models.CharField(
        max_length=100, blank=True, help_text="Solo si es_cauce=True"
    )
    tipo_equipo = models.CharField(
        max_length=30, choices=TipoEquipoInformatico.choices, blank=True
    )
    uso = models.CharField(max_length=20, choices=UsoEquipo.choices, blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="bienes_creados", null=True, blank=True
    )

    class Meta:
        ordering = ["departamento__nombre", "ubicacion__nombre", "descripcion"]
        indexes = [
            models.Index(fields=["bloque"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["numero_activo_serie"]),
            models.Index(fields=["etiqueta_cauce"]),
        ]

    def clean(self):
        """Validación del modelo antes de guardar."""
        if self.bloque == BloqueInmovilizado.EQUIPO_INFORMATICO:
            if self.es_cauce and not self.etiqueta_cauce:
                raise ValidationError("Un equipo CAUCE requiere etiqueta_cauce.")
            if not self.tipo_equipo:
                raise ValidationError("Los equipos informáticos requieren tipo_equipo.")
        else:
            if self.es_cauce or self.etiqueta_cauce:
                raise ValidationError("es_cauce/etiqueta_cauce solo aplican a equipos informáticos.")
        if self.ubicacion.departamento_id != self.departamento_id:
            raise ValidationError("La ubicación debe pertenecer al departamento indicado.")

    @property
    def requiere_etiqueta_generada(self):
        """Todo el inventario lleva QR/código de barras propio, salvo los CAUCE."""
        return not (self.bloque == BloqueInmovilizado.EQUIPO_INFORMATICO and self.es_cauce)

    @property
    def tiene_baja_pendiente(self):
        """True si el último movimiento registrado es una solicitud de baja sin resolver."""
        ultimo = self.historial.first()  # HistorialMovimiento.Meta.ordering = ["-fecha"]
        return bool(ultimo and ultimo.tipo == TipoMovimiento.BAJA_SOLICITADA)

    def __str__(self):
        """Representación en texto usada en el admin y las listas."""
        return f"[{self.get_bloque_display()}] {self.descripcion} — {self.numero_activo_serie or self.etiqueta_cauce}"


# ---------------------------------------------------------------------------
# Etiquetado (QR / código de barras)
# ---------------------------------------------------------------------------

class TipoEtiqueta(models.TextChoices):
    """Formato de la etiqueta: QR o código de barras."""
    QR = "QR", "Código QR"
    CODE128 = "CODE128", "Código de barras (Code 128)"


class Etiqueta(models.Model):
    """
    Identificador interno generado por el sistema, codificado en QR/código de
    barras. Solo existe para bienes NO CAUCE (ver Bien.requiere_etiqueta_generada).
    """
    bien = models.OneToOneField(Bien, on_delete=models.CASCADE, related_name="etiqueta")
    codigo_interno = models.CharField(max_length=50, unique=True, editable=False)
    tipo = models.CharField(max_length=10, choices=TipoEtiqueta.choices, default=TipoEtiqueta.QR)
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    impresa = models.BooleanField(default=False)
    fecha_ultima_impresion = models.DateTimeField(null=True, blank=True)

    def clean(self):
        """Validación del modelo antes de guardar."""
        if not self.bien.requiere_etiqueta_generada:
            raise ValidationError("Los bienes CAUCE no llevan etiqueta generada por el sistema.")

    def __str__(self):
        """Representación en texto usada en el admin y las listas."""
        return self.codigo_interno


# ---------------------------------------------------------------------------
# Auditoría: altas, bajas y traslados
# ---------------------------------------------------------------------------

class TipoMovimiento(models.TextChoices):
    """Tipos de entrada del historial de un bien (alta, traslado, bajas)."""
    ALTA = "ALTA", "Alta"
    TRASLADO = "TRASLADO", "Traslado"
    CAMBIO_ESTADO = "CAMBIO_ESTADO", "Cambio de estado"
    BAJA_SOLICITADA = "BAJA_SOLICITADA", "Baja solicitada"
    BAJA_APROBADA = "BAJA_APROBADA", "Baja aprobada"
    BAJA_RECHAZADA = "BAJA_RECHAZADA", "Baja rechazada"
    CONFIRMACION_CHEQUEO = "CONFIRMACION_CHEQUEO", "Confirmación en chequeo anual"


class HistorialMovimiento(models.Model):
    """Registro inmutable de cada acción sobre un bien (auditoría completa)."""
    bien = models.ForeignKey(Bien, on_delete=models.PROTECT, related_name="historial")
    tipo = models.CharField(max_length=30, choices=TipoMovimiento.choices)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="movimientos_inventario"
    )
    fecha = models.DateTimeField(auto_now_add=True)
    ubicacion_origen = models.ForeignKey(
        Ubicacion, on_delete=models.PROTECT, null=True, blank=True,
        related_name="movimientos_origen"
    )
    ubicacion_destino = models.ForeignKey(
        Ubicacion, on_delete=models.PROTECT, null=True, blank=True,
        related_name="movimientos_destino"
    )
    motivo_baja = models.CharField(
        max_length=30, choices=MotivoBaja.choices, blank=True
    )
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha"]
        indexes = [models.Index(fields=["bien", "fecha"])]

    def __str__(self):
        """Representación en texto usada en el admin y las listas."""
        return f"{self.get_tipo_display()} — {self.bien} ({self.fecha:%d/%m/%Y %H:%M})"


# ---------------------------------------------------------------------------
# Chequeo anual (módulo de carga/validación Excel)
# ---------------------------------------------------------------------------

class EstadoChequeo(models.TextChoices):
    """Estado de un chequeo anual (abierto o cerrado)."""
    ABIERTO = "ABIERTO", "Abierto"
    PENDIENTE_VALIDACION = "PENDIENTE_VALIDACION", "Pendiente de validación"
    CERRADO = "CERRADO", "Cerrado"


class ChequeoAnual(models.Model):
    """Campaña anual de revisión de inventario para un departamento."""
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT, related_name="chequeos"
    )
    anio = models.PositiveIntegerField()
    estado = models.CharField(
        max_length=25, choices=EstadoChequeo.choices, default=EstadoChequeo.ABIERTO
    )
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    plantilla_prerellenada = models.FileField(
        upload_to="chequeos/plantillas/", null=True, blank=True
    )
    archivo_subido = models.FileField(
        upload_to="chequeos/subidas/", null=True, blank=True
    )
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="chequeos_validados"
    )

    class Meta:
        unique_together = ("departamento", "anio")
        ordering = ["-anio", "departamento__nombre"]

    def __str__(self):
        """Representación en texto usada en el admin y las listas."""
        return f"Chequeo {self.anio} — {self.departamento}"


class LineaChequeo(models.Model):
    """
    Resultado por bien dentro de un chequeo anual: confirmado, no encontrado
    o nuevo (dado de alta durante la revisión).
    """
    class Resultado(models.TextChoices):
        """Resultado posible de la comprobación de un bien."""
        CONFIRMADO = "CONFIRMADO", "Confirmado"
        FALTANTE = "FALTANTE", "Faltante"
        NUEVO = "NUEVO", "Nuevo"

    chequeo = models.ForeignKey(ChequeoAnual, on_delete=models.CASCADE, related_name="lineas")
    bien = models.ForeignKey(
        Bien, on_delete=models.CASCADE, related_name="lineas_chequeo", null=True, blank=True
    )
    resultado = models.CharField(max_length=15, choices=Resultado.choices)

    class Meta:
        unique_together = ("chequeo", "bien")


# ---------------------------------------------------------------------------
# Verificación por correo (segundo factor de acceso)
# ---------------------------------------------------------------------------

class CodigoVerificacion(models.Model):
    """
    Código de un solo uso enviado por correo como segundo factor de acceso.
    Se guarda hasheado (nunca en claro) y caduca a los pocos minutos.
    """

    MINUTOS_VALIDEZ = 10  # tiempo de vida del código
    MAX_INTENTOS = 5      # intentos permitidos antes de invalidarlo

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="codigos_verificacion",
    )
    codigo_hash = models.CharField(max_length=128)
    creado = models.DateTimeField(auto_now_add=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    usado = models.BooleanField(default=False)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        """Representación en texto usada en el admin y las listas."""
        return f"Código de {self.usuario} ({self.creado:%d/%m/%Y %H:%M})"

    @classmethod
    def generar_para(cls, usuario):
        """
        Invalida los códigos previos sin usar del usuario y crea uno nuevo.
        Devuelve (objeto, codigo_en_claro); el código en claro no se guarda,
        solo su hash, así que hay que capturarlo aquí para poder enviarlo.
        """
        cls.objects.filter(usuario=usuario, usado=False).update(usado=True)
        codigo = f"{secrets.randbelow(1_000_000):06d}"
        obj = cls.objects.create(usuario=usuario, codigo_hash=make_password(codigo))
        return obj, codigo

    @property
    def caducado(self):
        """True si el código ha superado su tiempo de validez."""
        return timezone.now() > self.creado + timedelta(minutes=self.MINUTOS_VALIDEZ)

    def verificar(self, codigo_introducido):
        """
        Comprueba el código consumiendo un intento. Devuelve (ok, motivo),
        donde motivo es uno de: 'ok', 'usado', 'caducado', 'intentos', 'incorrecto'.
        """
        if self.usado:
            return False, "usado"
        if self.caducado:
            return False, "caducado"
        if self.intentos >= self.MAX_INTENTOS:
            return False, "intentos"

        self.intentos += 1
        if check_password(codigo_introducido, self.codigo_hash):
            self.usado = True
            self.save(update_fields=["intentos", "usado"])
            return True, "ok"

        self.save(update_fields=["intentos"])
        return False, "incorrecto"
