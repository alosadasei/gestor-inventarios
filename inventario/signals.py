"""Señales de Django: acciones automáticas al guardar modelos del inventario."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Bien, BloqueInmovilizado, Etiqueta, HistorialMovimiento, TipoMovimiento

# Prefijo del código interno de la etiqueta según el bloque del bien (p. ej. INF-000012).
PREFIJO_ETIQUETA = {
    BloqueInmovilizado.EQUIPO_INFORMATICO: "INF",
    BloqueInmovilizado.MOBILIARIO: "MOB",
    BloqueInmovilizado.MAQUINARIA: "MAQ",
    BloqueInmovilizado.UTILLAJE: "UTI",
}


@receiver(post_save, sender=Bien)
def al_crear_bien(sender, instance, created, **kwargs):
    """
    Fuente única para todo lo que debe pasar automáticamente al dar de alta
    un bien, sea cual sea la vía (admin, import/export, un comando, una
    vista): generar su etiqueta (si aplica) y dejar constancia en el
    historial. Así ninguna vía de alta puede olvidarse de hacerlo.
    """
    # Solo nos interesa la creación, no las ediciones posteriores.
    if not created:
        return

    # Genera la etiqueta a partir del bloque y el id del bien (relleno a 6 dígitos).
    if instance.requiere_etiqueta_generada and not hasattr(instance, "etiqueta"):
        codigo = f"{PREFIJO_ETIQUETA[instance.bloque]}-{instance.pk:06d}"
        Etiqueta.objects.create(bien=instance, codigo_interno=codigo)

    # Registra el alta en el historial, siempre que se conozca quién la hizo.
    if instance.creado_por_id is not None:
        HistorialMovimiento.objects.create(
            bien=instance, tipo=TipoMovimiento.ALTA, usuario=instance.creado_por,
            ubicacion_destino=instance.ubicacion,
            observaciones="Alta de inventario.",
        )
