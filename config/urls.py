"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from inventario import auth_views as inventario_auth_views
from inventario.forms import NuevaPasswordForm, RecuperarPasswordForm

# Tabla de rutas del proyecto: el admin, la autenticación y las rutas de la app.
urlpatterns = [
    path('admin/', admin.site.urls),

    # --- Login en dos pasos (contraseña + código por correo) ---
    path(
        'accounts/login/',
        inventario_auth_views.LoginUsuarioView.as_view(),
        name='login',
    ),
    path('accounts/login/verificar/', inventario_auth_views.verificar_codigo_view, name='verificar_codigo'),
    path('accounts/login/reenviar/', inventario_auth_views.reenviar_codigo_view, name='reenviar_codigo'),
    path(
        'accounts/logout/',
        auth_views.LogoutView.as_view(next_page='login'),
        name='logout',
    ),

    # --- Recuperación de contraseña (por correo) ---
    path(
        'accounts/password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='inventario/password_reset_form.html',
            email_template_name='inventario/password_reset_email.txt',
            subject_template_name='inventario/password_reset_subject.txt',
            form_class=RecuperarPasswordForm,
        ),
        name='password_reset',
    ),
    path(
        'accounts/password-reset/enviado/',
        auth_views.PasswordResetDoneView.as_view(template_name='inventario/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'accounts/password-reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='inventario/password_reset_confirm.html',
            form_class=NuevaPasswordForm,
        ),
        name='password_reset_confirm',
    ),
    path(
        'accounts/password-reset/completado/',
        auth_views.PasswordResetCompleteView.as_view(template_name='inventario/password_reset_complete.html'),
        name='password_reset_complete',
    ),

    # Rutas de la aplicación y, para la raíz del sitio, redirección al escáner.
    path('', include('inventario.urls')),
    path('', RedirectView.as_view(pattern_name='inventario:escaner', permanent=False)),
]
