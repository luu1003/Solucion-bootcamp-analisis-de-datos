#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preparación del proyecto · Reto ACTHO (Tablero integral de afiliados)

Deja el proyecto listo para correr en cualquier equipo (macOS, Windows o Linux):
  1. Verifica la versión de Python.
  2. Crea el entorno virtual .venv (si falta, está dañado o viene de otro sistema).
  3. Instala las librerías de requirements.txt (solo si cambiaron).
  4. Configura VS Code para usar ese entorno.
  5. Verifica que estén los archivos de la carpeta Datos/.
  6. Ejecuta los pasos del proyecto (ver PASOS), salvo que pidas solo instalar:
     limpieza de datos y, si hay conexión configurada en .env, carga a PostgreSQL.

Uso (desde la carpeta del proyecto):
    macOS / Linux:  python3 setup.py
    Windows:        py setup.py        (o: python setup.py)

Opciones:
    --solo-instalar            prepara el entorno y no ejecuta el proyecto
    --reinstalar               borra y vuelve a crear .venv desde cero
    --fecha-corte AAAA-MM-DD   fecha de corte para la limpieza (por defecto, hoy)
    --sin-postgres             no cargar a PostgreSQL aunque haya conexión configurada

PostgreSQL (opcional):
    1. Ten un servidor PostgreSQL. Con Docker:  docker compose up -d
    2. Copia .env.ejemplo como .env y revisa DATABASE_URL.
    3. Corre de nuevo este archivo: crea el esquema 'actho' y carga las tablas.

Solo usa la librería estándar de Python, así que corre antes de instalar nada.
Este archivo se actualiza a medida que avanza el proyecto: los pasos nuevos se
agregan a PASOS y las librerías nuevas a requirements.txt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
VENV = RAIZ / ".venv"
PY_MINIMO = (3, 9)
ES_WINDOWS = os.name == "nt"
PY_VENV = VENV / ("Scripts/python.exe" if ES_WINDOWS else "bin/python")
HASH_REQ = VENV / ".requirements.sha256"

# Archivos de datos que necesita el proyecto (relativos a Datos/).
DATOS_REQUERIDOS = [
    "1. Base de datos de afiliados/Base de datos Hackaton_anonimizada.xlsx",
    "2. Registros de participación en actividades/BASE ASISTENCIA A EVENTOS 2026 - EAFIT_anonimizada.xlsx",
    "3. Encuestas y NPS/Eventos Presenciales 2026_anonimizada.xlsx",
    "3. Encuestas y NPS/Eventos Virtuales ACRIP 2026_anonimizada.xlsx",
    "3. Encuestas y NPS/ENCUESTA-POST-EVENTOS (PRESENCIAL Y VIRTUAL)_anonimizada.xlsx",
    "5. Indicadores y reportes actuales/Base de datos afiliados ACTHO_anonimizada.xlsx",
]

# Pasos del proyecto, en orden. Agregar aquí los pasos nuevos (indicadores, semáforo, tablero…).
PASOS = [
    {
        "nombre": "Limpieza y unificación de datos",
        "script": "src/limpieza_datos.py",
        "usa_fecha_corte": True,
        "requiere_datos": True,
    },
    {
        "nombre": "Carga a PostgreSQL",
        "script": "src/cargar_postgres.py",
        "opcional_postgres": True,  # solo corre si hay conexión en .env o DATABASE_URL
    },
]


# ──────────────────────────────────────────────────────────────────────────────
def hablar(nivel, texto):
    print(f"[{nivel:^6}] {texto}", flush=True)


def ok(t): hablar("OK", t)
def aviso(t): hablar("AVISO", t)
def info(t): hablar("...", t)


def fallar(texto, ayuda=""):
    hablar("ERROR", texto)
    if ayuda:
        print("         " + ayuda.replace("\n", "\n         "))
    sys.exit(1)


def ejecutar(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], cwd=RAIZ, **kw)


def venv_funciona():
    """True si el Python del entorno existe y arranca (un .venv de otro sistema no arranca)."""
    if not PY_VENV.exists():
        return False
    try:
        return ejecutar([PY_VENV, "--version"], capture_output=True).returncode == 0
    except OSError:
        return False


# ──────────────────────────────────────────────────────────────────────────────
def verificar_python():
    v = sys.version_info
    if (v.major, v.minor) < PY_MINIMO:
        fallar(f"Se necesita Python {PY_MINIMO[0]}.{PY_MINIMO[1]} o superior (tienes {v.major}.{v.minor}).",
               "Instálalo desde https://www.python.org/downloads/ y vuelve a correr este archivo.")
    ok(f"Python {v.major}.{v.minor}.{v.micro} en {sys.executable}")


def preparar_entorno(reinstalar):
    if reinstalar and VENV.exists():
        info("Borrando el entorno virtual anterior…")
        shutil.rmtree(VENV, ignore_errors=True)
    if VENV.exists() and not venv_funciona():
        aviso(".venv existe pero no funciona en este equipo (¿se creó en otro sistema?). Se vuelve a crear.")
        shutil.rmtree(VENV, ignore_errors=True)
    if not venv_funciona():
        info("Creando el entorno virtual .venv (puede tardar un minuto)…")
        try:
            venv.EnvBuilder(with_pip=True, clear=True).create(VENV)
        except Exception as e:  # noqa: BLE001
            fallar(f"No se pudo crear el entorno virtual: {e}",
                   "En Ubuntu/Debian instala el módulo con:  sudo apt install python3-venv")
        if not venv_funciona():
            fallar("El entorno virtual se creó pero no arranca.")
    ok("Entorno virtual .venv listo")


def instalar_librerias():
    req = RAIZ / "requirements.txt"
    if not req.exists():
        fallar("No existe requirements.txt en la carpeta del proyecto.")
    huella = hashlib.sha256(req.read_bytes()).hexdigest()
    if HASH_REQ.exists() and HASH_REQ.read_text().strip() == huella:
        ok("Librerías al día (requirements.txt no cambió)")
        return
    info("Instalando librerías de requirements.txt…")
    ejecutar([PY_VENV, "-m", "pip", "install", "--upgrade", "pip", "--quiet", "--disable-pip-version-check"])
    r = ejecutar([PY_VENV, "-m", "pip", "install", "-r", req, "--quiet", "--disable-pip-version-check"])
    if r.returncode != 0:
        fallar("Falló la instalación de librerías.", "Revisa tu conexión a internet y vuelve a correr este archivo.")
    HASH_REQ.write_text(huella)
    ok("Librerías instaladas")


def verificar_librerias():
    codigo = ("import importlib.metadata as m;"
              "print(', '.join(f'{n} {m.version(n)}' for n in ['pandas','numpy','openpyxl','psycopg']))")
    r = ejecutar([PY_VENV, "-c", codigo], capture_output=True, text=True)
    if r.returncode != 0:
        fallar("Las librerías no quedaron instaladas correctamente.", "Corre:  python setup.py --reinstalar")
    ok("Verificadas: " + r.stdout.strip())


def configurar_vscode():
    carpeta = RAIZ / ".vscode"
    archivo = carpeta / "settings.json"
    ruta = "${workspaceFolder}/.venv/" + ("Scripts/python.exe" if ES_WINDOWS else "bin/python")
    datos = {}
    if archivo.exists():
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except ValueError:
            aviso("No se tocó .vscode/settings.json (tiene comentarios). Elige el intérprete en "
                  "VS Code: Ctrl/Cmd+Shift+P → 'Python: Select Interpreter' → .venv")
            return
    datos["python.defaultInterpreterPath"] = ruta
    datos["python.terminal.activateEnvironment"] = True
    carpeta.mkdir(exist_ok=True)
    archivo.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ok("VS Code configurado para usar .venv (si estaba abierto, recarga la ventana)")


def verificar_datos():
    """Devuelve True si están todos los archivos de datos."""
    datos = RAIZ / "Datos"
    if not datos.exists():
        aviso("No existe la carpeta Datos/. Copia ahí el paquete del reto (no se sube a GitHub).")
        return False
    faltan = [r for r in DATOS_REQUERIDOS if not (datos / r).exists()]
    if faltan:
        aviso("Faltan archivos en Datos/:")
        for f in faltan:
            print("           - " + f)
        return False
    ok(f"Datos completos ({len(DATOS_REQUERIDOS)} archivos requeridos)")
    return True


def hay_conexion_postgres():
    if os.environ.get("DATABASE_URL") or (os.environ.get("PGDATABASE") and os.environ.get("PGUSER")):
        return True
    env = RAIZ / ".env"
    if env.exists():
        for linea in env.read_text(encoding="utf-8").splitlines():
            if linea.strip().startswith(("DATABASE_URL=", "PGDATABASE=")) and linea.split("=", 1)[1].strip():
                return True
    return False


def correr_pasos(fecha_corte, hay_datos, sin_postgres=False):
    entorno = dict(os.environ, PYTHONIOENCODING="utf-8")
    for n, paso in enumerate(PASOS, 1):
        titulo = f"Paso {n}/{len(PASOS)}: {paso['nombre']}"
        if paso.get("requiere_datos") and not hay_datos:
            aviso(f"{titulo} — omitido (faltan datos).")
            continue
        if paso.get("opcional_postgres"):
            if sin_postgres:
                aviso(f"{titulo} — omitido (--sin-postgres).")
                continue
            if not hay_conexion_postgres():
                aviso(f"{titulo} — omitido: no hay conexión configurada. Copia .env.ejemplo como .env "
                      "(y si usas Docker: docker compose up -d).")
                continue
        info(titulo)
        cmd = [PY_VENV, paso["script"]]
        if paso.get("usa_fecha_corte") and fecha_corte:
            cmd += ["--fecha-corte", fecha_corte]
        if ejecutar(cmd, env=entorno).returncode != 0:
            if paso.get("opcional_postgres"):
                aviso("La carga a PostgreSQL no se completó (mira el mensaje de arriba). "
                      "Los CSV limpios siguen disponibles en salida/.")
                continue
            fallar(f"El paso '{paso['nombre']}' terminó con error.")
        ok(f"{paso['nombre']} terminado")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Prepara el proyecto ACTHO en este equipo")
    ap.add_argument("--solo-instalar", action="store_true", help="no ejecutar los pasos del proyecto")
    ap.add_argument("--reinstalar", action="store_true", help="borrar y recrear .venv")
    ap.add_argument("--fecha-corte", default=None, help="AAAA-MM-DD")
    ap.add_argument("--sin-postgres", action="store_true", help="no cargar a PostgreSQL")
    args = ap.parse_args()

    print("\n=== Preparación del proyecto ACTHO ===\n")
    verificar_python()
    preparar_entorno(args.reinstalar)
    instalar_librerias()
    verificar_librerias()
    configurar_vscode()
    (RAIZ / "salida").mkdir(exist_ok=True)
    hay_datos = verificar_datos()

    if not args.solo_instalar:
        print()
        correr_pasos(args.fecha_corte, hay_datos, args.sin_postgres)

    activar = r".venv\Scripts\activate" if ES_WINDOWS else "source .venv/bin/activate"
    print(f"\nListo. Para trabajar a mano:  {activar}   y luego   python src/limpieza_datos.py")
    print("Resultados en la carpeta salida/.\n")


if __name__ == "__main__":
    main()
