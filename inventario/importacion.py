"""
inventario/importacion.py

Lógica de importación desde la plantilla Excel del centro (4 hojas, una por
bloque de inmovilizado), compartida entre:
  - el comando de gestión `importar_inventario_inicial` (terminal), y
  - la vista web `importar_excel` (subida desde el navegador).

    EQUIPOS INFORMÁTICOS | Departamento | Ubicación Física Precisa | Etiqueta CAUCE | Número de serie | Tipo | Uso | Estado
    MAQUINARIA           | Departamento | Ubicación Física Precisa | Número de Activo | Categoría | Descripción del Bien | Estado
    MOBILIARIO           | (idénticas columnas que MAQUINARIA)
    UTILLAJE             | (idénticas columnas que MAQUINARIA)

Las columnas Departamento/Ubicación suelen venir con celdas combinadas (solo
rellenas en la primera fila de cada grupo): se arrastra hacia abajo el último
valor no vacío visto en cada columna.
"""

import unicodedata
from collections import defaultdict

from .models import (
    Bien,
    BloqueInmovilizado,
    Departamento,
    EstadoBien,
    TipoEquipoInformatico,
    Ubicacion,
    UsoEquipo,
)

# Nombre de cada hoja del Excel -> bloque de inmovilizado al que corresponde.
HOJAS = {
    "EQUIPOS INFORMÁTICOS": BloqueInmovilizado.EQUIPO_INFORMATICO,
    "MAQUINARIA": BloqueInmovilizado.MAQUINARIA,
    "MOBILIARIO": BloqueInmovilizado.MOBILIARIO,
    "UTILLAJE": BloqueInmovilizado.UTILLAJE,
}


def _normalizar(valor):
    """'Pantallas digitales' -> 'PANTALLAS DIGITALES' (sin acentos, mayúsculas)."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto.upper()


# Textos del Excel (ya normalizados) -> tipo de equipo informático.
TIPO_EQUIPO_MAP = {
    "ORDENADOR": TipoEquipoInformatico.ORDENADOR,
    "MONITOR": TipoEquipoInformatico.MONITOR,
    "PORTATIL": TipoEquipoInformatico.PORTATIL,
    "IMPRESORA": TipoEquipoInformatico.IMPRESORA,
    "ESCANER": TipoEquipoInformatico.ESCANER,
    "PROYECTOR": TipoEquipoInformatico.PROYECTOR,
    "CARRO": TipoEquipoInformatico.CARRO,
    "CARROS": TipoEquipoInformatico.CARRO,
    "PANTALLA DIGITAL": TipoEquipoInformatico.PANTALLA_DIGITAL,
    "PANTALLAS DIGITALES": TipoEquipoInformatico.PANTALLA_DIGITAL,
    "OTROS": TipoEquipoInformatico.OTROS,
}

# Textos del Excel (ya normalizados) -> estado del bien.
ESTADO_MAP = {
    "OPERATIVO": EstadoBien.OPERATIVO,
    "NO OPERATIVO": EstadoBien.NO_OPERATIVO,
    "EN REPARACION": EstadoBien.EN_REPARACION,
    "EN ALMACEN": EstadoBien.EN_ALMACEN,
    "BAJA": EstadoBien.BAJA,
}

# Textos del Excel (ya normalizados) -> uso del equipo.
USO_MAP = {
    "DOCENTE": UsoEquipo.DOCENTE,
    "ALUMNADO": UsoEquipo.ALUMNADO,
}


class ResultadoImportacion:
    """Contenedor simple de estadísticas y avisos de una importación."""

    def __init__(self):
        # Contadores por bloque, más "omitidas" y "errores".
        self.stats = defaultdict(int)
        # Mensajes legibles para mostrar al usuario tras la importación.
        self.avisos = []

    @property
    def total_creados(self):
        """Suma de bienes creados en los cuatro bloques."""
        return sum(self.stats[b] for b in (
            "EQUIPO_INFORMATICO", "MOBILIARIO", "MAQUINARIA", "UTILLAJE"
        ))


def _get_ubicacion(dep_nombre, ubic_nombre, departamento_fijo=None):
    """
    Obtiene (o crea) el departamento y la ubicación indicados en la fila.
    Si `departamento_fijo` viene informado (importación acotada a un único
    departamento, p. ej. para un usuario no administrador), se usa ese
    departamento en vez del nombre leído de la celda, y se avisa si no coinciden.
    """
    if departamento_fijo is not None:
        departamento = departamento_fijo
    else:
        departamento, _ = Departamento.objects.get_or_create(nombre=dep_nombre.strip())
    ubicacion, _ = Ubicacion.objects.get_or_create(
        departamento=departamento, nombre=ubic_nombre.strip()
    )
    return departamento, ubicacion


def _crear_bien(usuario, resultado, **kwargs):
    """Valida y guarda un bien; si no es válido lo descarta y lo anota como error."""
    bien = Bien(creado_por=usuario, **kwargs)
    try:
        bien.full_clean()
    except Exception as exc:
        resultado.stats["errores"] += 1
        resultado.avisos.append(
            f"Fila descartada por error de validación ({kwargs.get('descripcion')}): {exc}"
        )
        return
    bien.save()
    resultado.stats[kwargs["bloque"]] += 1


def _procesar_equipos(hoja, usuario, resultado, departamento_fijo=None):
    """Recorre la hoja de equipos informáticos y crea un bien por cada fila válida."""
    last_dep = last_ubic = None
    for fila in hoja.iter_rows(min_row=2, values_only=True):
        # Se rellena con None por si la fila trae menos columnas de las esperadas.
        dep_cell, ubic_cell, etiqueta_cauce, num_serie, tipo, uso, estado = (
            list(fila) + [None] * (7 - len(fila))
        )[:7]

        # Celdas combinadas: si viene vacía, se hereda el valor de la fila anterior.
        dep_nombre = str(dep_cell).strip() if dep_cell else last_dep
        ubic_nombre = str(ubic_cell).strip() if ubic_cell else last_ubic
        last_dep, last_ubic = dep_nombre, ubic_nombre

        # Fila sin identificador propio (serie/etiqueta) -> no es un bien real
        # (p.ej. filas de referencia de la plantilla vacía), se omite.
        if not tipo or not dep_nombre or not ubic_nombre or not (etiqueta_cauce or num_serie):
            if tipo:
                resultado.stats["omitidas"] += 1
            continue

        # Importación acotada: descarta las filas de otros departamentos.
        if departamento_fijo is not None and _normalizar(dep_nombre) != _normalizar(departamento_fijo.nombre):
            resultado.stats["omitidas"] += 1
            resultado.avisos.append(
                f"Fila de '{dep_nombre}' omitida: solo puedes importar bienes de tu departamento ({departamento_fijo.nombre})."
            )
            continue

        departamento, ubicacion = _get_ubicacion(dep_nombre, ubic_nombre, departamento_fijo)

        tipo_key = TIPO_EQUIPO_MAP.get(_normalizar(tipo))
        if tipo_key is None:
            resultado.avisos.append(f"Tipo de equipo no reconocido: '{tipo}' -> se guarda como OTROS")
            tipo_key = TipoEquipoInformatico.OTROS

        estado_key = ESTADO_MAP.get(_normalizar(estado), EstadoBien.OPERATIVO)
        uso_key = USO_MAP.get(_normalizar(uso), "")
        etiqueta_cauce_val = str(etiqueta_cauce).strip() if etiqueta_cauce else ""

        _crear_bien(
            usuario, resultado,
            bloque=BloqueInmovilizado.EQUIPO_INFORMATICO,
            departamento=departamento, ubicacion=ubicacion,
            descripcion=dict(TipoEquipoInformatico.choices)[tipo_key],
            numero_activo_serie=str(num_serie).strip() if num_serie else "",
            estado=estado_key,
            es_cauce=bool(etiqueta_cauce_val),
            etiqueta_cauce=etiqueta_cauce_val,
            tipo_equipo=tipo_key,
            uso=uso_key,
        )


def _procesar_generico(hoja, bloque, usuario, resultado, departamento_fijo=None):
    """Recorre una hoja de maquinaria, mobiliario o utillaje (mismas columnas) y crea los bienes."""
    last_dep = last_ubic = None
    for fila in hoja.iter_rows(min_row=2, values_only=True):
        # Se rellena con None por si la fila trae menos columnas de las esperadas.
        dep_cell, ubic_cell, num_activo, categoria, descripcion, estado = (
            list(fila) + [None] * (6 - len(fila))
        )[:6]

        dep_nombre = str(dep_cell).strip() if dep_cell else last_dep
        ubic_nombre = str(ubic_cell).strip() if ubic_cell else last_ubic
        last_dep, last_ubic = dep_nombre, ubic_nombre

        # Sin descripción no hay bien identificable (filas de referencia
        # de categorías de la plantilla vacía se omiten).
        if not descripcion or not dep_nombre or not ubic_nombre:
            if categoria and not descripcion:
                resultado.stats["omitidas"] += 1
            continue

        if departamento_fijo is not None and _normalizar(dep_nombre) != _normalizar(departamento_fijo.nombre):
            resultado.stats["omitidas"] += 1
            resultado.avisos.append(
                f"Fila de '{dep_nombre}' omitida: solo puedes importar bienes de tu departamento ({departamento_fijo.nombre})."
            )
            continue

        departamento, ubicacion = _get_ubicacion(dep_nombre, ubic_nombre, departamento_fijo)
        estado_key = ESTADO_MAP.get(_normalizar(estado), EstadoBien.OPERATIVO)

        # Excel guarda los números como decimales (123.0): se muestran como enteros.
        if isinstance(num_activo, float) and num_activo.is_integer():
            num_activo = int(num_activo)

        _crear_bien(
            usuario, resultado,
            bloque=bloque,
            departamento=departamento, ubicacion=ubicacion,
            descripcion=str(descripcion).strip(),
            categoria=str(categoria).strip() if categoria else "",
            numero_activo_serie=str(num_activo).strip() if num_activo else "",
            estado=estado_key,
        )


def importar_workbook(wb, usuario, departamento_fijo=None):
    """
    Procesa un Workbook de openpyxl ya cargado (4 hojas, una por bloque).

    `departamento_fijo`: si se pasa un Departamento, todas las filas se
    importan a ese departamento (usado cuando un usuario no administrador
    hace la importación); las filas de otros departamentos se descartan
    con aviso en vez de crear un departamento nuevo.

    Devuelve un ResultadoImportacion con `.stats` y `.avisos`.
    """
    resultado = ResultadoImportacion()

    for nombre_hoja, bloque in HOJAS.items():
        if nombre_hoja not in wb.sheetnames:
            resultado.avisos.append(f"Hoja '{nombre_hoja}' no encontrada en el archivo; se omite.")
            continue
        hoja = wb[nombre_hoja]
        if bloque == BloqueInmovilizado.EQUIPO_INFORMATICO:
            _procesar_equipos(hoja, usuario, resultado, departamento_fijo)
        else:
            _procesar_generico(hoja, bloque, usuario, resultado, departamento_fijo)

    return resultado
