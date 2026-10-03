# Inventarios

Aplicación Django para el control de inventario del centro: equipos informáticos
(CAUCE / NO CAUCE), mobiliario, maquinaria y utillaje. Gestión por departamentos
y ubicaciones, etiquetado con QR/código de barras, protocolo de altas/bajas/
traslados, chequeo anual por departamento y trazabilidad completa de movimientos.

## Estructura

- `config/` — configuración del proyecto Django.
- `inventario/` — app principal (modelos, admin, vistas).

## Puesta en marcha (desarrollo)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # ajustar valores si hace falta
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Variables de entorno

Ver `.env.example`. En producción, `DJANGO_SECRET_KEY` y `DJANGO_ALLOWED_HOSTS`
deben configurarse en el App Service (no en el repositorio).

## Estado del proyecto

En desarrollo inicial. Modelos de datos definidos en `inventario/models.py`
a partir del documento funcional y las plantillas Excel de carga inicial
proporcionadas por el centro.
