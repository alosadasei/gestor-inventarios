#!/bin/bash
# Comando de inicio de Azure App Service (configurar en Configuración >
# Configuración general > Comando de inicio: "bash startup.sh").
# Se ejecuta en cada arranque/reinicio del contenedor.
set -e

echo "Aplicando migraciones..."
python manage.py migrate --noinput

echo "Recolectando estáticos..."
python manage.py collectstatic --noinput

echo "Arrancando Gunicorn..."
gunicorn --bind=0.0.0.0 --timeout 600 --workers 3 config.wsgi:application
