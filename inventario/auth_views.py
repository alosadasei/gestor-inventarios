"""
inventario/auth_views.py
Login en dos pasos: contraseña (primer factor) + código de 6 dígitos
enviado por correo (segundo factor). La recuperación de contraseña usa
las vistas propias de Django (ver urls.py), solo con formularios y
plantillas propias.
"""
import logging

from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from .forms import LoginForm, VerificarCodigoForm
from .models import CodigoVerificacion

logger = logging.getLogger(__name__)

# Claves de sesión donde guardamos, de forma temporal, al usuario que ha
# superado el primer factor (contraseña) y está pendiente de verificar el
# código por correo, junto con el 'next' original para no perderlo.
SESSION_PRE_2FA_USER_ID = "pre_2fa_user_id"
SESSION_PRE_2FA_NEXT = "pre_2fa_next"


def _enviar_codigo_2fa(usuario, codigo):
    """Envía por correo el código de verificación de un solo uso."""
    try:
        send_mail(
            subject="Tu código de acceso · Inventario",
            message=(
                f"Hola, {usuario.get_full_name() or usuario.username}:\n\n"
                f"Tu código de verificación para iniciar sesión es:\n\n"
                f"    {codigo}\n\n"
                f"El código caduca en {CodigoVerificacion.MINUTOS_VALIDEZ} minutos. "
                f"Si no has intentado acceder, ignora este mensaje.\n\n"
                f"Un saludo,\n"
                f"El equipo de Inventario"
            ),
            from_email=None,  # usa DEFAULT_FROM_EMAIL
            recipient_list=[usuario.email],
        )
    except Exception:
        logger.error("Fallo al enviar el código de verificación por correo", exc_info=True)


class LoginUsuarioView(LoginView):
    """
    Primer factor (usuario + contraseña). Si son correctos NO inicia
    sesión todavía: genera un código, lo envía por correo y redirige a
    la verificación del segundo factor.
    """
    template_name = "inventario/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        """Contraseña correcta: envía el código por correo y pasa al segundo paso."""
        usuario = form.get_user()

        if not usuario.email:
            form.add_error(
                None,
                "Tu cuenta no tiene un correo electrónico configurado. "
                "Pide a un administrador que te lo añada antes de poder acceder.",
            )
            return self.form_invalid(form)

        _, codigo = CodigoVerificacion.generar_para(usuario)
        _enviar_codigo_2fa(usuario, codigo)

        self.request.session[SESSION_PRE_2FA_USER_ID] = usuario.pk
        self.request.session[SESSION_PRE_2FA_NEXT] = self.get_success_url()
        return redirect("verificar_codigo")


def _usuario_pendiente(request):
    """Devuelve el usuario que ha pasado la contraseña y espera el código, o None."""
    # Import local para no cargar el modelo de usuario al importar el módulo.
    from django.contrib.auth import get_user_model
    pk = request.session.get(SESSION_PRE_2FA_USER_ID)
    if not pk:
        return None
    return get_user_model().objects.filter(pk=pk, is_active=True).first()


def verificar_codigo_view(request):
    """Segundo factor: valida el código de 6 dígitos y, si es correcto, inicia la sesión."""
    usuario = _usuario_pendiente(request)
    if not usuario:
        return redirect("login")

    if request.method == "POST":
        form = VerificarCodigoForm(request.POST)
        if form.is_valid():
            codigo_obj = (
                CodigoVerificacion.objects
                .filter(usuario=usuario, usado=False)
                .order_by("-creado")
                .first()
            )
            if codigo_obj is None:
                form.add_error("codigo", "No hay ningún código activo. Solicita uno nuevo.")
            else:
                ok, motivo = codigo_obj.verificar(form.cleaned_data["codigo"])
                if ok:
                    # Código válido: ahora sí se crea la sesión autenticada y se limpia el estado temporal.
                    login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
                    next_url = request.session.pop(SESSION_PRE_2FA_NEXT, "/")
                    request.session.pop(SESSION_PRE_2FA_USER_ID, None)
                    return redirect(next_url)

                mensajes = {
                    "caducado": "El código ha caducado. Solicita uno nuevo.",
                    "usado": "Este código ya se ha utilizado. Solicita uno nuevo.",
                    "intentos": "Demasiados intentos fallidos. Solicita un código nuevo.",
                    "incorrecto": "Código incorrecto. Revisa el correo e inténtalo de nuevo.",
                }
                form.add_error("codigo", mensajes.get(motivo, "Código no válido."))
    else:
        form = VerificarCodigoForm()

    return render(request, "inventario/verificar_codigo.html", {
        "form": form, "email": usuario.email,
    })


def reenviar_codigo_view(request):
    """Genera y envía un código nuevo al usuario pendiente de verificar (solo por POST)."""
    if request.method != "POST":
        return redirect("verificar_codigo")

    usuario = _usuario_pendiente(request)
    if not usuario:
        return redirect("login")

    _, codigo = CodigoVerificacion.generar_para(usuario)
    _enviar_codigo_2fa(usuario, codigo)
    return render(request, "inventario/verificar_codigo.html", {
        "form": VerificarCodigoForm(), "email": usuario.email, "reenviado": True,
    })
