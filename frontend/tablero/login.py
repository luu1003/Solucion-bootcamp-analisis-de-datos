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
.block-container {{ max-width: 1360px !important; padding: 1.5rem 2rem !important; }}
/* Lienzo: morado a la izquierda, franja naranja a la derecha; la tarjeta queda montada sobre el borde */
div.st-key-login_lienzo {{ position: relative; border-radius: 24px; overflow: hidden; min-height: calc(100vh - 5rem);
  background: linear-gradient(90deg, {c.C['morado']} 0%, {c.C['morado']} 70%, {c.C['naranja']} 70%, {c.C['naranja']} 100%);
  padding: 0 !important; }}
div.st-key-login_lienzo > div > [data-testid="stHorizontalBlock"],
div.st-key-login_lienzo [data-testid="stHorizontalBlock"] {{ min-height: calc(100vh - 5rem); align-items: center !important;
  gap: 0 !important; }}
.login-cinta {{ position:absolute; left: 63%; bottom: -90px; width: 190px; height: 330px; opacity: .9;
  transform: rotate(180deg); pointer-events: none; z-index: 0; }}
/* Columna izquierda: logo → título → mensaje → descripción → módulos → pie */
.login-hero {{ padding: 3rem 2rem 3rem 12%; position: relative; z-index: 1; display: flex; flex-direction: column; }}
.login-logo {{ font-size: 2.1rem !important; font-weight: 600 !important; letter-spacing: -.04em; color: #fff !important; line-height: 1 !important; margin: 0 0 2.2rem !important; }}
.login-logo span {{ color: {c.C['naranja']}; }}
.login-h1 {{ font-size: clamp(2.8rem, 4.6vw, 4.4rem) !important; line-height: 1.02 !important; font-weight: 700 !important;
  color: #FFFFFF !important; letter-spacing: -.035em; margin: 0 0 1.4rem !important; }}
.login-h1 span {{ color: {c.C['naranja']}; }}
.login-lema {{ font-size: 1.35rem !important; font-weight: 600 !important; color: #FFFFFF !important; line-height: 1.3 !important;
  margin: 0 0 .7rem !important; max-width: 520px; }}
.login-lema em {{ font-style: normal; color: {c.C['cian']}; }}
.login-desc {{ font-size: 1rem !important; color: {c.C['lavanda_2']} !important; max-width: 520px; line-height: 1.55 !important;
  margin: 0 0 2rem !important; }}
.login-modulos {{ display:flex; gap: .5rem; flex-wrap: wrap; margin: 0 0 2.6rem; max-width: 560px; }}
.login-modulos span {{ font-size: .74rem; font-weight: 600; color: #FFFFFF; background: rgba(255,255,255,.12);
  border: 1px solid rgba(255,255,255,.22); border-radius: 999px; padding: .38rem .8rem; }}
.login-copy {{ font-size: .72rem !important; letter-spacing: .06em; text-transform: uppercase; color: {c.C['lavanda_2']} !important; margin: 0 !important; }}
/* Tarjeta de acceso */
div.st-key-login_tarjeta {{ position: relative; z-index: 2; background: #FFFFFF; border-radius: 22px;
  padding: 2.4rem 2.2rem 1.6rem !important; box-shadow: 0 24px 60px rgba(43, 10, 107, .28);
  width: auto !important; max-width: 430px; margin: 2rem auto !important; }}
.login-titulo {{ font-size: 1.75rem !important; font-weight: 700 !important; color: {c.C['tinta']} !important; margin: 0 !important;
  line-height: 1.15 !important; }}
.login-sub {{ font-size: .92rem !important; color: {c.C['gris']} !important; margin: .3rem 0 1.3rem !important; }}
div.st-key-login_tarjeta [data-testid="stWidgetLabel"] p {{ text-transform: none !important; letter-spacing: 0 !important;
  font-size: .88rem !important; font-weight: 500 !important; color: {c.C['tinta']} !important; }}
div.st-key-login_tarjeta [data-baseweb="input"] {{ border-radius: 10px !important; background: #fff !important; }}
div.st-key-login_tarjeta [data-baseweb="input"] input {{ padding: .72rem .9rem !important; font-size: .95rem; }}
div.st-key-login_tarjeta [data-testid="stForm"] {{ border: none !important; padding: 0 !important; }}
div.st-key-login_tarjeta [data-testid="stFormSubmitButton"], div.st-key-login_tarjeta [data-testid="stFormSubmitButton"] > div {{ width: 100% !important; }}
div.st-key-login_tarjeta [data-testid="stFormSubmitButton"] button {{ width: 100% !important; background: {c.C['morado']} !important;
  border-color: {c.C['morado']} !important; color: #fff !important; padding: .78rem 1rem !important; font-size: 1rem !important;
  border-radius: 12px !important; box-shadow: 0 6px 16px rgba(91, 0, 217, .28); margin-top: .4rem; }}
div.st-key-login_tarjeta [data-testid="stFormSubmitButton"] button:hover {{ background: {c.C['morado_900']} !important; }}
.login-acceso {{ text-align: center; font-size: .84rem !important; color: {c.C['tinta']} !important; margin: 1rem 0 0 !important; line-height: 1.55 !important; }}
.login-acceso span {{ color: {c.C['naranja_texto']}; font-weight: 600; }}
.login-sep {{ border: none; border-top: 1px solid {c.C['linea']}; margin: 1.1rem 0 .8rem; }}
.login-legal {{ text-align: center; font-size: .72rem !important; color: {c.C['gris']} !important; line-height: 1.5 !important; margin: 0 !important; }}
.login-legal u {{ text-decoration: underline; }}
@media (max-width: 1100px) {{
  div.st-key-login_lienzo {{ background: {c.C['morado']}; }}
  div.st-key-login_lienzo [data-testid="stHorizontalBlock"] {{ flex-direction: column !important; }}
  .login-hero {{ padding: 2.4rem 1.6rem 0; }}
  .login-cinta {{ display: none; }}
  div.st-key-login_tarjeta {{ margin: 1.2rem 1rem 2rem !important; }}
}}
</style>
"""


def pantalla_login():
    st.markdown(CSS_LOGIN, unsafe_allow_html=True)
    estado = st.session_state.setdefault("login_estado", {})
    with st.container(key="login_lienzo"):
        izq, der = st.columns([1.3, 1])
        with izq:
            st.markdown(
                '<div class="login-hero">'
                '<p class="login-logo" aria-label="actho">ac<span>tho</span></p>'
                '<p class="login-h1" role="heading" aria-level="1">¡Bienvenido<br>a ac<span>tho</span>!</p>'
                '<p class="login-lema">Sentimos el pulso de tus afiliados <em>desde un solo lugar.</em></p>'
                '<p class="login-desc">Membresías, renovaciones, participación en experiencias y satisfacción de la base '
                'de afiliados, integradas para actuar a tiempo.</p>'
                '<div class="login-modulos"><span>Afiliados</span><span>Renovación y retención</span>'
                '<span>Experiencias y NPS</span><span>Planeación de eventos</span><span>Apoyo de IA</span></div>'
                '<p class="login-copy">© 2026 ACTHO</p>'
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
            st.markdown('<p class="login-acceso">¿Tu equipo aún no tiene acceso?<br><span>Solicítalo a Dirección Ejecutiva</span></p>'
                        '<hr class="login-sep">'
                        '<p class="login-legal">Al continuar aceptas la <u>Política de tratamiento de datos personales</u> '
                        '(Ley 1581 de 2012) · ES · v1.0</p>', unsafe_allow_html=True)


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
