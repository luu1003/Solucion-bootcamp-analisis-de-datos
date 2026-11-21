# -*- coding: utf-8 -*-
"""Pantalla de inicio de sesión del tablero ACTHO (panel morado + franja naranja + tarjeta blanca)."""
from __future__ import annotations

import streamlit as st

import auth
import comun as c

CSS_LOGIN = f"""
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], header[data-testid="stHeader"] {{ display: none !important; }}
.stApp {{ background: #F4F4F6; }}
.block-container {{ max-width: 1440px !important; padding: 2.2rem 2.2rem !important; }}
div.st-key-login_lienzo {{ position: relative; border-radius: 24px; overflow: hidden; min-height: 760px;
  background: linear-gradient(90deg, {c.C['morado']} 0%, {c.C['morado']} 72%, {c.C['naranja']} 72%, {c.C['naranja']} 100%);
  padding: 0 !important; }}
div.st-key-login_lienzo [data-testid="stHorizontalBlock"] {{ min-height: 760px; align-items: center !important; gap: 0 !important; }}
.login-cinta {{ position:absolute; left: 50%; top: -40px; width: 230px; height: 400px; opacity: .95; pointer-events: none; }}
.login-hero {{ padding: 0 2rem 0 9%; position: relative; }}
.login-hero .logo {{ font-size: 2.2rem; font-weight: 600; letter-spacing: -.04em; color: #fff; margin-bottom: 3.2rem; }}
.login-hero .logo span {{ color: {c.C['naranja']}; }}
.login-hero h1 {{ font-size: 5rem !important; line-height: 1.02 !important; font-weight: 700 !important; color: #FFFFFF !important;
  letter-spacing: -.035em; margin: 0 0 1.6rem !important; padding: 0 !important; }}
.login-hero h1 span {{ color: {c.C['naranja']}; }}
.login-hero h2 {{ font-size: 1.45rem !important; font-weight: 600 !important; color: #FFFFFF !important; line-height: 1.3 !important;
  margin: 0 0 .7rem !important; padding: 0 !important; max-width: 560px; }}
.login-hero h2 em {{ font-style: normal; color: {c.C['cian']}; }}
.login-hero p {{ font-size: 1.05rem; color: {c.C['lavanda_2']}; max-width: 560px; line-height: 1.5; margin: 0; }}
.login-pie {{ display:flex; gap: 1.4rem; flex-wrap: wrap; margin-top: 4.5rem; }}
.login-pie span {{ font-size: .72rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: #FFFFFF; }}
div.st-key-login_tarjeta {{ background: #FFFFFF; border-radius: 22px; padding: 2.6rem 2.4rem 1.8rem !important;
  box-shadow: 0 24px 60px rgba(43, 10, 107, .25); margin: 0 9% 0 4%; }}
.login-titulo {{ font-size: 2rem !important; font-weight: 700 !important; color: {c.C['tinta']} !important; margin: 0 !important; line-height: 1.1 !important; }}
.login-sub {{ font-size: .95rem !important; color: {c.C['gris']} !important; margin: .35rem 0 1.4rem !important; }}
div.st-key-login_tarjeta [data-testid="stWidgetLabel"] p {{ text-transform: none !important; letter-spacing: 0 !important;
  font-size: .9rem !important; font-weight: 500 !important; color: {c.C['tinta']} !important; }}
div.st-key-login_tarjeta [data-baseweb="input"] {{ border-radius: 10px !important; background: #fff !important; }}
div.st-key-login_tarjeta [data-baseweb="input"] input {{ padding: .75rem .9rem !important; font-size: .95rem; }}
div.st-key-login_tarjeta [data-testid="stForm"] {{ border: none !important; padding: 0 !important; }}
div.st-key-login_tarjeta [data-testid="stFormSubmitButton"], div.st-key-login_tarjeta [data-testid="stFormSubmitButton"] > div {{ width: 100% !important; }}
div.st-key-login_tarjeta [data-testid="stFormSubmitButton"] button {{ width: 100% !important; background: {c.C['morado']} !important;
  border-color: {c.C['morado']} !important; color: #fff !important; padding: .8rem 1rem !important; font-size: 1rem !important;
  border-radius: 12px !important; box-shadow: 0 6px 16px rgba(91, 0, 217, .28); }}
div.st-key-login_tarjeta [data-testid="stFormSubmitButton"] button:hover {{ background: {c.C['morado_900']} !important; }}
.login-fila {{ display:flex; justify-content: space-between; align-items: center; font-size: .82rem; color: {c.C['tinta']}; margin: .9rem 0 0; }}
.login-fila a, .login-enlace {{ color: {c.C['naranja']} !important; font-weight: 500; text-decoration: none; }}
.login-sep {{ border: none; border-top: 1px solid {c.C['linea']}; margin: 1.3rem 0 .9rem; }}
.login-legal {{ text-align: center; font-size: .7rem; color: {c.C['gris']}; line-height: 1.5; }}
.login-legal u {{ text-decoration: underline; }}
@media (max-width: 1100px) {{
  div.st-key-login_lienzo {{ background: {c.C['morado']}; }}
  .login-hero h1 {{ font-size: 3.2rem !important; }}
  div.st-key-login_tarjeta {{ margin: 1rem 1rem 2rem; }}
}}
</style>
"""


def pantalla_login():
    st.markdown(CSS_LOGIN, unsafe_allow_html=True)
    estado = st.session_state.setdefault("login_estado", {})
    with st.container(key="login_lienzo"):
        st.markdown(f'<img class="login-cinta" src="{c.CINTA_URI}" alt="">', unsafe_allow_html=True)
        izq, der = st.columns([1.35, 1])
        with izq:
            st.markdown(
                '<div class="login-hero">'
                '<div class="logo">ac<span>tho</span></div>'
                '<h1>¡Bienvenido<br>a ac<span>tho</span>!</h1>'
                '<h2>Sentimos el pulso de tus afiliados <em>desde un solo lugar.</em></h2>'
                '<p>Membresías, renovaciones, participación en experiencias y satisfacción de la base de afiliados, '
                'integradas para actuar a tiempo.</p>'
                '<div class="login-pie"><span>Afiliados</span><span>Renovación y retención</span>'
                '<span>Experiencias y NPS</span><span>© 2026 ACTHO</span></div>'
                '</div>', unsafe_allow_html=True)
        with der, st.container(key="login_tarjeta"):
            st.markdown('<p class="login-titulo">Iniciar sesión</p>'
                        '<p class="login-sub">Accede al tablero integral de afiliados.</p>', unsafe_allow_html=True)
            espera = auth.bloqueado(estado)
            with st.form("form_login", border=False, clear_on_submit=False):
                usuario = st.text_input("Usuario o correo", key="login_usuario", autocomplete="username")
                clave = st.text_input("Contraseña", type="password", key="login_clave", autocomplete="current-password")
                enviar = st.form_submit_button("Iniciar sesión", disabled=espera > 0, **c.ancho(st.form_submit_button))
            if espera:
                st.warning(f"Demasiados intentos fallidos. Intenta de nuevo en {espera} segundos.")
            if enviar:
                datos = auth.verificar(usuario, clave)
                if datos:
                    estado.clear()
                    st.session_state["sesion"] = datos
                    st.session_state.pop("login_clave", None)
                    st.rerun()
                else:
                    auth.registrar_fallo(estado)
                    st.error("Usuario o contraseña incorrectos.")
            st.markdown('<div class="login-fila"><span>¿Tu equipo aún no tiene acceso?</span>'
                        '<span class="login-enlace">Solicítalo a Dirección Ejecutiva</span></div>'
                        '<hr class="login-sep">'
                        '<div class="login-legal">Al continuar aceptas la <u>Política de tratamiento de datos personales</u> '
                        '(Ley 1581 de 2012).<br>ES · v1.0</div>', unsafe_allow_html=True)


def requerir_sesion() -> dict:
    """Muestra el login si no hay sesión y detiene la página; si la hay, devuelve el usuario."""
    sesion = st.session_state.get("sesion")
    if not sesion:
        pantalla_login()
        st.stop()
    return sesion


def cerrar_sesion():
    for k in ("sesion", "login_usuario", "login_clave", "empresa_sel"):
        st.session_state.pop(k, None)
    st.rerun()
