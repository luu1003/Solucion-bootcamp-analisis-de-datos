# -*- coding: utf-8 -*-
"""
Autenticación del tablero ACTHO.

* Las contraseñas no se guardan en texto plano: se guarda su derivación PBKDF2-SHA256
  (310.000 iteraciones, sal aleatoria por usuario).
* Usuario inicial (temporal, para el reto):  admin / actho   ← cámbialo antes de compartir el tablero.
* Para agregar o cambiar usuarios sin tocar el código, crea .streamlit/secrets.toml (no se sube a GitHub):

      [usuarios.ana]
      nombre = "Ana Gómez"
      rol = "Ejecutiva de cuenta"
      sal = "<hex>"
      hash = "<hex>"

  y genera sal y hash con:   python frontend/tablero/auth.py nueva-clave
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sys
import time

ITERACIONES = 310_000
MAX_INTENTOS = 5
BLOQUEO_SEG = 60

# Usuario administrador inicial (contraseña: actho)
USUARIOS_BASE = {
    "admin": {
        "nombre": "Administrador",
        "rol": "Administrador",
        "sal": "9991ab50aba37584b04e51173e5e01a0",
        "hash": "b1b41cfa8a863cac8444a94eefc19d4562f49dcb3f764e8fef5c3fab9553303a",
    },
}


def derivar(clave: str, sal_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), bytes.fromhex(sal_hex), ITERACIONES).hex()


def usuarios() -> dict:
    """Usuarios base más los definidos en .streamlit/secrets.toml (sección [usuarios])."""
    todos = dict(USUARIOS_BASE)
    try:
        import streamlit as st
        extra = st.secrets.get("usuarios", {})
        for u, d in extra.items():
            todos[str(u).lower()] = dict(d)
    except Exception:  # noqa: BLE001  (sin secrets.toml)
        pass
    return todos


def verificar(usuario: str, clave: str) -> dict | None:
    """Devuelve los datos del usuario si la contraseña es correcta; si no, None."""
    datos = usuarios().get((usuario or "").strip().lower())
    if not datos or not clave:
        # Derivación de relleno para no revelar por el tiempo de respuesta si el usuario existe.
        derivar(clave or "x", "00" * 16)
        return None
    if hmac.compare_digest(derivar(clave, datos["sal"]), datos["hash"]):
        return {"usuario": usuario.strip().lower(), "nombre": datos.get("nombre", usuario), "rol": datos.get("rol", "")}
    return None


def bloqueado(estado: dict) -> int:
    """Segundos de bloqueo restantes tras varios intentos fallidos (0 si puede intentar)."""
    hasta = estado.get("bloqueo_hasta", 0)
    return max(0, int(hasta - time.time()))


def registrar_fallo(estado: dict):
    estado["intentos"] = estado.get("intentos", 0) + 1
    if estado["intentos"] >= MAX_INTENTOS:
        estado["bloqueo_hasta"] = time.time() + BLOQUEO_SEG
        estado["intentos"] = 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python frontend/tablero/auth.py <contraseña>")
    sal = secrets.token_hex(16)
    print(f'sal = "{sal}"\nhash = "{derivar(sys.argv[1], sal)}"')
