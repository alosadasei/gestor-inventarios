"""
Generación de las imágenes de las etiquetas (QR / Code128).

El valor codificado es siempre el `codigo_interno` en texto plano (nunca una
URL): así una pistola lectora, que emula un teclado, escribe directamente el
código en cualquier campo de búsqueda — incluido el de "escaneo continuo"
(ver `views.escaner`).
"""

import io

import barcode
import qrcode
from barcode.writer import ImageWriter

from .models import TipoEtiqueta

# Clase de código de barras Code128, resuelta una sola vez al importar el módulo.
_CODE128 = barcode.get_barcode_class("code128")


def generar_imagen_qr(dato: str) -> io.BytesIO:
    """Devuelve un PNG en memoria con el código QR de `dato`."""
    buf = io.BytesIO()
    imagen = qrcode.make(dato, box_size=8, border=2)
    imagen.save(buf, format="PNG")
    buf.seek(0)
    return buf


def generar_imagen_codigo_barras(dato: str) -> io.BytesIO:
    """Devuelve un PNG en memoria con el código de barras Code128 de `dato` (sin texto debajo)."""
    buf = io.BytesIO()
    codigo = _CODE128(dato, writer=ImageWriter())
    codigo.write(buf, options={"write_text": False, "module_height": 10, "quiet_zone": 2})
    buf.seek(0)
    return buf


def imagen_para_etiqueta(etiqueta) -> io.BytesIO:
    """Despacha según `etiqueta.tipo` y devuelve un PNG en memoria."""
    if etiqueta.tipo == TipoEtiqueta.QR:
        return generar_imagen_qr(etiqueta.codigo_interno)
    return generar_imagen_codigo_barras(etiqueta.codigo_interno)
