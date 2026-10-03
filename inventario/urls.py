"""Rutas de la app `inventario` (se montan en la raíz desde config/urls.py)."""
from django.urls import path

from . import views

# Espacio de nombres: permite usar {% url 'inventario:escaner' %} en las plantillas.
app_name = "inventario"

urlpatterns = [
    path("escaner/", views.escaner, name="escaner"),
    path("bienes/<int:pk>/", views.bien_detalle, name="bien_detalle"),
    path("bienes/nuevo/", views.alta_bien, name="alta_bien"),
    path("importar-excel/", views.importar_excel, name="importar_excel"),
    path("bienes/<int:pk>/trasladar/", views.traslado_bien, name="traslado_bien"),
    path("bienes/<int:pk>/solicitar-baja/", views.solicitar_baja_bien, name="solicitar_baja_bien"),
    path("bajas-pendientes/", views.bajas_pendientes, name="bajas_pendientes"),
    path("bajas-pendientes/<int:pk>/resolver/", views.resolver_baja, name="resolver_baja"),
    path("etiquetas/lote/", views.etiquetas_lote_form, name="etiquetas_lote_form"),
    path("etiquetas/lote/pdf/", views.etiquetas_pdf_lote, name="etiquetas_pdf_lote"),
    path("etiquetas/<int:etiqueta_id>/pdf/", views.etiqueta_pdf_individual, name="etiqueta_pdf_individual"),
    path("ajax/ubicaciones/", views.ubicaciones_por_departamento, name="ubicaciones_por_departamento"),
]
