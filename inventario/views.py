"""
Vistas de la aplicación: escáner, ficha de bien, etiquetas en PDF, importación
desde Excel y protocolo de altas, traslados y bajas.
"""
import textwrap

import openpyxl
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .etiquetas import imagen_para_etiqueta
from .forms import AltaBienForm, ImportarExcelForm, SolicitudBajaForm, TrasladoForm
from .importacion import importar_workbook
from .models import Bien, Departamento, EstadoBien, Etiqueta, HistorialMovimiento, TipoMovimiento, Ubicacion
from .permisos import es_administrador, obtener_perfil, requiere_administrador

# Layout de la hoja de etiquetas: rejilla tipo Avery, en mm.
PAGINA_ANCHO, PAGINA_ALTO = A4
MARGEN = 10 * mm
ETIQUETA_ANCHO = 63.5 * mm
ETIQUETA_ALTO = 33.9 * mm
COLUMNAS = 3
FILAS = 8


def _buscar_bien_por_codigo(codigo, user=None):
    """
    Busca un bien a partir de lo que ha leído la pistola: primero como
    código interno de una Etiqueta generada, y si no, como etiqueta CAUCE
    (los equipos CAUCE no tienen Etiqueta propia, ver Bien.requiere_etiqueta_generada).
    Restringido al alcance del usuario (su departamento, o todo si es admin).
    """
    codigo = (codigo or "").strip()
    if not codigo:
        return None
    alcance = _bienes_del_usuario(user) if user is not None else Bien.objects.all()
    etiqueta = Etiqueta.objects.select_related("bien").filter(
        codigo_interno=codigo, bien__in=alcance
    ).first()
    if etiqueta:
        return etiqueta.bien
    return alcance.filter(etiqueta_cauce=codigo).first()


@login_required
def escaner(request):
    """
    Modo de escaneo continuo: un único campo de texto con autofocus donde
    la pistola "teclea" el código y pulsa Enter. Redirige directamente al
    detalle del bien encontrado para encadenar lecturas sin usar el ratón.
    """
    error = None
    if request.method == "POST":
        codigo = request.POST.get("codigo", "")
        bien = _buscar_bien_por_codigo(codigo, user=request.user)
        if bien:
            return redirect("inventario:bien_detalle", pk=bien.pk)
        error = f"No se ha encontrado ningún bien con el código «{codigo}»."
    return render(request, "inventario/escaner.html", {
        "error": error, "es_administrador": es_administrador(request.user),
    })


@login_required
def bien_detalle(request, pk):
    """Ficha de un bien con su historial; solo accesible dentro del alcance del usuario."""
    bien = get_object_or_404(
        _bienes_del_usuario(request.user).prefetch_related("historial"),
        pk=pk,
    )
    return render(request, "inventario/bien_detalle.html", {
        "bien": bien, "es_administrador": es_administrador(request.user),
    })


@login_required
def etiquetas_lote_form(request):
    """Formulario para elegir qué etiquetas imprimir antes de generar el PDF."""
    return render(request, "inventario/etiquetas_lote_form.html", {
        "departamentos": Departamento.objects.filter(activo=True),
    })


def _dibujar_etiqueta(pdf, x, y, etiqueta):
    """Dibuja una etiqueta individual: imagen a la izquierda, texto a la derecha."""
    bien = etiqueta.bien
    # Imagen QR/código de barras generada en memoria para esta etiqueta.
    imagen = ImageReader(imagen_para_etiqueta(etiqueta))

    padding = 2.5 * mm
    lado_imagen = ETIQUETA_ALTO - 2 * padding  # bloque cuadrado disponible a la izquierda

    if etiqueta.tipo == "QR":
        img_ancho = img_alto = lado_imagen
    else:
        # el código de barras es plano: lo centramos verticalmente en el mismo bloque
        img_ancho = lado_imagen
        img_alto = lado_imagen * 0.4

    # Dibuja el código (centrado verticalmente en su bloque).
    pdf.drawImage(
        imagen,
        x + padding, y + padding + (lado_imagen - img_alto) / 2,
        width=img_ancho, height=img_alto,
        preserveAspectRatio=True, mask="auto",
    )

    # Zona de texto: a la derecha de la imagen, hasta el borde de la etiqueta.
    texto_x = x + padding + lado_imagen + 2 * mm
    texto_ancho_disponible = (x + ETIQUETA_ANCHO - padding) - texto_x

    # Código interno en negrita arriba.
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(texto_x, y + ETIQUETA_ALTO - padding - 9, etiqueta.codigo_interno)

    # Descripción del bien ajustada a un máximo de 3 líneas.
    pdf.setFont("Helvetica", 6.5)
    max_chars = max(int(texto_ancho_disponible / (6.5 * 0.5)), 10)
    lineas = textwrap.wrap(bien.descripcion, width=max_chars)[:3]
    for i, linea in enumerate(lineas):
        pdf.drawString(texto_x, y + ETIQUETA_ALTO - padding - 20 - (i * 7), linea)

    # Nombre de la ubicación abajo, recortado al ancho disponible.
    pdf.setFont("Helvetica", 6)
    pdf.drawString(texto_x, y + padding, bien.ubicacion.nombre[:max_chars])


@login_required
def etiquetas_pdf_lote(request):
    """
    Genera un PDF con una rejilla de etiquetas (QR o código de barras) para
    las etiquetas que cumplan los filtros. Marca cada una como impresa.
    """
    etiquetas = Etiqueta.objects.select_related("bien", "bien__departamento", "bien__ubicacion")

    # Filtros opcionales recibidos por query string desde el formulario.
    departamento_id = request.GET.get("departamento")
    ubicacion_id = request.GET.get("ubicacion")
    bloque = request.GET.get("bloque")
    solo_pendientes = request.GET.get("solo_pendientes") == "on"

    if departamento_id:
        etiquetas = etiquetas.filter(bien__departamento_id=departamento_id)
    if ubicacion_id:
        etiquetas = etiquetas.filter(bien__ubicacion_id=ubicacion_id)
    if bloque:
        etiquetas = etiquetas.filter(bien__bloque=bloque)
    if solo_pendientes:
        etiquetas = etiquetas.filter(impresa=False)

    etiquetas = list(etiquetas.order_by("bien__ubicacion__nombre", "codigo_interno"))
    if not etiquetas:
        return HttpResponse("No hay etiquetas que coincidan con los filtros seleccionados.", status=404)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="etiquetas_inventario.pdf"'
    pdf = canvas.Canvas(response, pagesize=A4)

    # Coloca cada etiqueta en la rejilla; al llenar una página se pasa a la siguiente.
    for i, etiqueta in enumerate(etiquetas):
        pos_en_pagina = i % (COLUMNAS * FILAS)
        if pos_en_pagina == 0 and i > 0:
            pdf.showPage()
        col = pos_en_pagina % COLUMNAS
        fila = pos_en_pagina // COLUMNAS
        x = MARGEN + col * ETIQUETA_ANCHO
        y = PAGINA_ALTO - MARGEN - (fila + 1) * ETIQUETA_ALTO
        _dibujar_etiqueta(pdf, x, y, etiqueta)

    pdf.showPage()
    pdf.save()

    # Marca las etiquetas como impresas para poder filtrar las pendientes después.
    ahora = timezone.now()
    Etiqueta.objects.filter(pk__in=[e.pk for e in etiquetas]).update(
        impresa=True, fecha_ultima_impresion=ahora
    )
    return response


@login_required
def etiqueta_pdf_individual(request, etiqueta_id):
    """Reimpresión de una sola etiqueta (p. ej. una etiqueta deteriorada)."""
    etiqueta = get_object_or_404(Etiqueta, pk=etiqueta_id)
    # Un PDF del tamaño exacto de una etiqueta, mostrado en el navegador.

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{etiqueta.codigo_interno}.pdf"'
    pdf = canvas.Canvas(response, pagesize=(ETIQUETA_ANCHO, ETIQUETA_ALTO))
    _dibujar_etiqueta(pdf, 0, 0, etiqueta)
    pdf.save()

    etiqueta.impresa = True
    etiqueta.fecha_ultima_impresion = timezone.now()
    etiqueta.save(update_fields=["impresa", "fecha_ultima_impresion"])
    return response


def ubicaciones_por_departamento(request):
    """Endpoint auxiliar (AJAX) para rellenar el <select> de ubicaciones."""
    departamento_id = request.GET.get("departamento")
    ubicaciones = Ubicacion.objects.filter(departamento_id=departamento_id).values("id", "nombre")
    return render(request, "inventario/_opciones_ubicacion.html", {"ubicaciones": ubicaciones})


@login_required
def importar_excel(request):
    """
    Importación masiva desde un Excel con el mismo formato que la plantilla
    del centro (una hoja por bloque). Un administrador puede importar
    cualquier departamento presente en el archivo; un usuario de
    departamento solo puede importar filas de su propio departamento
    (las demás se descartan con aviso, ver `importacion.importar_workbook`).
    """
    perfil = obtener_perfil(request.user)
    departamento_fijo = None
    if not es_administrador(request.user):
        if perfil is None or perfil.departamento is None:
            messages.error(request, "Tu usuario no tiene un departamento asignado.")
            return redirect("inventario:escaner")
        departamento_fijo = perfil.departamento

    resultado = None

    if request.method == "POST":
        form = ImportarExcelForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                wb = openpyxl.load_workbook(form.cleaned_data["archivo"], data_only=True)
            except Exception:
                form.add_error("archivo", "No se ha podido leer el archivo. ¿Es un .xlsx válido?")
            else:
                # Se importa dentro de un savepoint: en modo simulación se deshace al final.
                with transaction.atomic():
                    sid = transaction.savepoint()
                    resultado = importar_workbook(wb, request.user, departamento_fijo=departamento_fijo)
                    if form.cleaned_data["dry_run"]:
                        transaction.savepoint_rollback(sid)
                    else:
                        transaction.savepoint_commit(sid)
                        messages.success(
                            request,
                            f"Importación completada: {resultado.total_creados} bienes creados."
                        )
    else:
        form = ImportarExcelForm()

    return render(request, "inventario/importar_excel.html", {
        "form": form, "resultado": resultado,
    })


# ---------------------------------------------------------------------------
# Protocolo de altas, traslados y bajas
# ---------------------------------------------------------------------------

def _bienes_del_usuario(user):
    """Un administrador ve todo el inventario; un usuario de departamento, solo el suyo."""
    qs = Bien.objects.select_related("departamento", "ubicacion")
    if es_administrador(user):
        return qs
    perfil = obtener_perfil(user)
    if perfil is None:
        return qs.none()
    return qs.filter(departamento=perfil.departamento)


@login_required
def alta_bien(request):
    """
    Alta manual de un bien. Un usuario de departamento solo puede darlo de
    alta en su propio departamento; un administrador elige cualquiera.
    """
    perfil = obtener_perfil(request.user)
    if es_administrador(request.user):
        departamentos = Departamento.objects.filter(activo=True)
        departamento_id = request.POST.get("departamento") or request.GET.get("departamento")
        departamento = Departamento.objects.filter(pk=departamento_id).first() if departamento_id else None
    else:
        if perfil is None:
            messages.error(request, "Tu usuario no tiene un departamento asignado.")
            return redirect("inventario:escaner")
        departamentos = None
        departamento = perfil.departamento

    if request.method == "POST":
        form = AltaBienForm(request.POST, departamento=departamento)
        if departamento is None:
            form.add_error(None, "Selecciona un departamento.")
        elif form.is_valid():
            bien = form.save(commit=False)
            bien.creado_por = request.user
            bien.save()
            messages.success(request, f"Bien «{bien.descripcion}» dado de alta correctamente.")
            return redirect("inventario:bien_detalle", pk=bien.pk)
    else:
        form = AltaBienForm(departamento=departamento)

    return render(request, "inventario/alta_bien.html", {
        "form": form, "departamentos": departamentos, "departamento_seleccionado": departamento,
    })


@login_required
def traslado_bien(request, pk):
    """Traslado de un bien a otra ubicación (dentro de su mismo departamento)."""
    bien = get_object_or_404(_bienes_del_usuario(request.user), pk=pk)
    # Solo se ofrecen ubicaciones del mismo departamento, salvo la actual.
    ubicaciones = Ubicacion.objects.filter(departamento=bien.departamento).exclude(pk=bien.ubicacion_id)

    if request.method == "POST":
        form = TrasladoForm(request.POST, queryset_ubicaciones=ubicaciones)
        if form.is_valid():
            # Guardamos el origen antes de cambiarlo para dejarlo en el historial.
            origen = bien.ubicacion
            bien.ubicacion = form.cleaned_data["nueva_ubicacion"]
            bien.save(update_fields=["ubicacion"])
            HistorialMovimiento.objects.create(
                bien=bien, tipo=TipoMovimiento.TRASLADO, usuario=request.user,
                ubicacion_origen=origen, ubicacion_destino=bien.ubicacion,
                observaciones=form.cleaned_data["observaciones"],
            )
            messages.success(request, f"Bien trasladado a {bien.ubicacion}.")
            return redirect("inventario:bien_detalle", pk=bien.pk)
    else:
        form = TrasladoForm(queryset_ubicaciones=ubicaciones)

    return render(request, "inventario/traslado_bien.html", {"bien": bien, "form": form})


@login_required
def solicitar_baja_bien(request, pk):
    """
    Primer paso del protocolo de baja: cualquier usuario con acceso al bien
    puede solicitarla, indicando el motivo. Queda pendiente hasta que un
    administrador la resuelva (ver `resolver_baja`).
    """
    bien = get_object_or_404(_bienes_del_usuario(request.user), pk=pk)

    if bien.estado == EstadoBien.BAJA:
        messages.info(request, "Este bien ya está dado de baja.")
        return redirect("inventario:bien_detalle", pk=bien.pk)
    if bien.tiene_baja_pendiente:
        messages.info(request, "Ya hay una solicitud de baja pendiente para este bien.")
        return redirect("inventario:bien_detalle", pk=bien.pk)

    if request.method == "POST":
        form = SolicitudBajaForm(request.POST)
        if form.is_valid():
            HistorialMovimiento.objects.create(
                bien=bien, tipo=TipoMovimiento.BAJA_SOLICITADA, usuario=request.user,
                motivo_baja=form.cleaned_data["motivo_baja"],
                observaciones=form.cleaned_data["observaciones"],
            )
            messages.success(request, "Solicitud de baja enviada. Queda pendiente de aprobación.")
            return redirect("inventario:bien_detalle", pk=bien.pk)
    else:
        form = SolicitudBajaForm()

    return render(request, "inventario/solicitar_baja.html", {"bien": bien, "form": form})


@requiere_administrador
def bajas_pendientes(request):
    """Listado, solo para administradores, de bienes con baja solicitada sin resolver."""
    bienes = [b for b in Bien.objects.select_related("departamento", "ubicacion") if b.tiene_baja_pendiente]
    return render(request, "inventario/bajas_pendientes.html", {"bienes": bienes})


@requiere_administrador
def resolver_baja(request, pk):
    """Aprueba o rechaza la solicitud de baja pendiente de un bien."""
    bien = get_object_or_404(Bien, pk=pk)
    # Última solicitud de baja registrada (el historial viene ordenado de más reciente a más antigua).
    solicitud = bien.historial.filter(tipo=TipoMovimiento.BAJA_SOLICITADA).first()

    if request.method == "POST":
        decision = request.POST.get("decision")
        # Aprobar marca el bien como baja; rechazar solo deja constancia en el historial.
        if decision == "aprobar":
            bien.estado = EstadoBien.BAJA
            bien.save(update_fields=["estado"])
            HistorialMovimiento.objects.create(
                bien=bien, tipo=TipoMovimiento.BAJA_APROBADA, usuario=request.user,
                motivo_baja=solicitud.motivo_baja if solicitud else "",
            )
            messages.success(request, f"Baja de «{bien.descripcion}» aprobada.")
        elif decision == "rechazar":
            HistorialMovimiento.objects.create(
                bien=bien, tipo=TipoMovimiento.BAJA_RECHAZADA, usuario=request.user,
                observaciones=request.POST.get("motivo_rechazo", ""),
            )
            messages.success(request, f"Solicitud de baja de «{bien.descripcion}» rechazada.")
        return redirect("inventario:bajas_pendientes")

    return render(request, "inventario/resolver_baja.html", {"bien": bien, "solicitud": solicitud})
