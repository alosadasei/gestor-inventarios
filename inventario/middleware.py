"""
inventario/middleware.py
"""

from django.urls import set_script_prefix


class ScriptNameMiddleware:
    """
    Permite servir la aplicación bajo una subruta (p. ej.
    https://dominio.example/inventario/) sin fijar el prefijo en la
    configuración.

    El proxy inverso que publica la subruta debe enviar la cabecera
    ``X-Script-Name`` con el prefijo (``/inventario``). A partir de ella se
    ajusta ``SCRIPT_NAME``, que es lo que Django usa para construir las URLs:
    con eso ``{% url %}``, los ``redirect()`` y ``reverse()`` generan rutas ya
    prefijadas.

    Se hace dinámicamente (en vez de con ``FORCE_SCRIPT_NAME``) porque el mismo
    backend puede seguir siendo accesible en su URL original (azurewebsites.net)
    sin prefijo: si no llega la cabecera, todo funciona como siempre.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """Procesa la petición: aplica el prefijo si llega la cabecera y continúa la cadena."""
        script_name = request.META.get('HTTP_X_SCRIPT_NAME', '').rstrip('/')

        if script_name:
            request.META['SCRIPT_NAME'] = script_name

            # El handler WSGI fija el prefijo de las URLs (a partir del
            # SCRIPT_NAME original) ANTES de ejecutar los middlewares, así que
            # hay que rehacerlo aquí para que reverse() lo tenga en cuenta.
            set_script_prefix(script_name)

            # Si el proxy reenvía la ruta completa sin quitar el prefijo, lo
            # eliminamos aquí; el URLconf del proyecto no conoce ese prefijo.
            path_info = request.META.get('PATH_INFO', '')
            if path_info.startswith(script_name):
                request.META['PATH_INFO'] = path_info[len(script_name):] or '/'

            # request.path / path_info se calculan en __init__ de la request,
            # antes de pasar por aquí: hay que rehacerlos con los META nuevos.
            request.path_info = request.META['PATH_INFO']
            request.path = script_name + request.path_info

        return self.get_response(request)
