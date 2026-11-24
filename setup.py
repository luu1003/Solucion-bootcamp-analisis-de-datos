#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ACTHO · Tablero integral de afiliados — un solo comando para dejar todo corriendo.

    macOS / Linux:  python3 setup.py
    Windows:        py setup.py

Qué hace (y se salta lo que ya esté listo):
  1. Verifica Python y crea el entorno virtual .venv (si falta o es de otro equipo).
  2. Instala las librerías de requirements.txt (solo si cambiaron).
  3. Configura VS Code para usar .venv.
  4. Prepara PostgreSQL sin preguntar nada, en este orden:
       a) la base de .env / DATABASE_URL, si responde;
       b) Docker Desktop (docker compose up -d postgres), si está abierto;
       c) PostgreSQL instalado en el equipo (Homebrew, Postgres.app…): crea una base propia
          del proyecto (puerto 5433 o el siguiente libre), sin permisos de administrador;
       d) si no hay ninguno, instala PostgreSQL 16 portátil (descarga única de ≈30 MB) y sigue como en c);
       e) si eso falla y Docker Desktop está instalado pero cerrado, lo abre y lo usa.
     Los archivos de PostgreSQL van FUERA del proyecto (macOS: ~/Library/Application Support/ACTHO,
     Windows: %LOCALAPPDATA%\\ACTHO, Linux: ~/.local/share/actho) porque iCloud/OneDrive vuelven
     lentísimo el arranque. Si una versión anterior dejó .pgdata/ en el proyecto, se mueve allá.
  5. Procesa los datos de Datos/ solo si algún archivo cambió desde la última carga
     (limpieza, validación, carga, verificación), recalcula el semáforo de hoy y entrena
     los modelos de IA (src/modelos_ia.py).
  6. Arranca el tablero en http://localhost:8501 y lo abre en Google Chrome.
     Usuario inicial: admin · contraseña: actho.  Ctrl+C para detenerlo.

Opciones:
    --solo-instalar            prepara el entorno y no ejecuta nada más
    --reinstalar               borra y vuelve a crear .venv
    --forzar                   vuelve a procesar los datos aunque no hayan cambiado
    --fecha-corte AAAA-MM-DD   fecha de corte de los indicadores (por defecto, hoy)
    --sin-tablero              procesa los datos pero no abre el tablero
    --sin-navegador            arranca el tablero sin abrir el navegador
    --puerto N                 puerto del tablero (por defecto 8501 o el siguiente libre)
    -y, --si                   (se mantiene por compatibilidad: ya no se pregunta nada)

Solo usa la librería estándar de Python, así que corre antes de instalar nada.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
VENV = RAIZ / ".venv"
PY_MINIMO = (3, 9)
ES_WINDOWS = os.name == "nt"
SISTEMA = platform.system()
PY_VENV = VENV / ("Scripts/python.exe" if ES_WINDOWS else "bin/python")
HASH_REQ = VENV / ".requirements.sha256"
ENV = RAIZ / ".env"



def _carpeta_datos_usuario() -> Path:
    """PostgreSQL guarda sus archivos fuera del proyecto: si el proyecto está en una carpeta sincronizada
    (iCloud Documentos, OneDrive, Dropbox), cada escritura se sincroniza y el servidor tarda minutos en arrancar."""
    if os.environ.get("ACTHO_DATOS"):
        return Path(os.environ["ACTHO_DATOS"])
    if SISTEMA == "Darwin":
        return Path.home() / "Library" / "Application Support" / "ACTHO"
    if ES_WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ACTHO"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "actho"


DATOS_USUARIO = _carpeta_datos_usuario()
PGDATA = DATOS_USUARIO / "pgdata"
PGBIN_PROYECTO = DATOS_USUARIO / "postgres"   # PostgreSQL portátil que instala setup.py si hace falta
LEGADO_PGDATA = RAIZ / ".pgdata"              # ubicación de versiones anteriores (dentro del proyecto)
LEGADO_BIN = RAIZ / ".postgres"
MARCA_CONF = "# --- configuración del proyecto ACTHO (setup.py) ---"
PGSERVER_VERSION = "0.1.4"                    # paquete de PyPI que trae los binarios de PostgreSQL 16
PGSERVER_PLATAFORMAS = {
    ("Darwin", "arm64"): "macosx_11_0_arm64",
    ("Darwin", "x86_64"): "macosx_10_9_x86_64",
    ("Linux", "x86_64"): "manylinux_2_17_x86_64",
    ("Windows", "AMD64"): "win_amd64",
}
PG_PUERTO_LOCAL = 5433
URL_DOCKER = "postgresql://postgres:postgres@localhost:5432/actho"
APP = "frontend/tablero/Inicio.py"

DATOS_REQUERIDOS = [
    "1. Base de datos de afiliados/Base de datos Hackaton_anonimizada.xlsx",
    "2. Registros de participación en actividades/BASE ASISTENCIA A EVENTOS 2026 - EAFIT_anonimizada.xlsx",
    "3. Encuestas y NPS/Eventos Presenciales 2026_anonimizada.xlsx",
    "3. Encuestas y NPS/Eventos Virtuales ACRIP 2026_anonimizada.xlsx",
    "3. Encuestas y NPS/ENCUESTA-POST-EVENTOS (PRESENCIAL Y VIRTUAL)_anonimizada.xlsx",
    "5. Indicadores y reportes actuales/Base de datos afiliados ACTHO_anonimizada.xlsx",
]


# ──────────────────────────────────────────────────────────────────────────────
# Mensajes y utilidades
# ──────────────────────────────────────────────────────────────────────────────
def hablar(nivel, texto):
    print(f"[{nivel:^6}] {texto}", flush=True)


def ok(t): hablar("OK", t)
def aviso(t): hablar("AVISO", t)
def info(t): hablar("...", t)
def salto(t): hablar("SALTO", t)


def fallar(texto, ayuda=""):
    hablar("ERROR", texto)
    if ayuda:
        print("         " + ayuda.replace("\n", "\n         "))
    sys.exit(1)


def preguntar(texto, si_por_defecto=True, auto=False):
    """Pregunta Y/n en la consola. Sin consola interactiva (o con --si) usa la respuesta por defecto."""
    opciones = "[Y/n]" if si_por_defecto else "[y/N]"
    if auto or not sys.stdin or not sys.stdin.isatty():
        info(f"{texto} {opciones} → {'sí' if si_por_defecto else 'no'} (automático)")
        return si_por_defecto
    while True:
        try:
            r = input(f"  [ ? ]   {texto} {opciones} ").strip().lower()
        except EOFError:
            return si_por_defecto
        if r == "":
            return si_por_defecto
        if r in ("y", "yes", "s", "si", "sí"):
            return True
        if r in ("n", "no"):
            return False
        print("          Responde Y (sí) o n (no).")


def ejecutar(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], cwd=RAIZ, **kw)


def entorno(url=None):
    e = dict(os.environ, PYTHONIOENCODING="utf-8")
    if url:
        e["DATABASE_URL"] = url
    return e


# ──────────────────────────────────────────────────────────────────────────────
# 1-3. Python, entorno virtual, librerías y VS Code
# ──────────────────────────────────────────────────────────────────────────────
def venv_funciona():
    if not PY_VENV.exists():
        return False
    try:
        return ejecutar([PY_VENV, "--version"], capture_output=True).returncode == 0
    except OSError:
        return False


def verificar_python():
    v = sys.version_info
    if (v.major, v.minor) < PY_MINIMO:
        fallar(f"Se necesita Python {PY_MINIMO[0]}.{PY_MINIMO[1]} o superior (tienes {v.major}.{v.minor}).",
               "Instálalo desde https://www.python.org/downloads/ y vuelve a correr este archivo.")
    ok(f"Python {v.major}.{v.minor}.{v.micro}")


def preparar_entorno(reinstalar):
    if reinstalar and VENV.exists():
        info("Borrando el entorno virtual anterior…")
        shutil.rmtree(VENV, ignore_errors=True)
    if VENV.exists() and not venv_funciona():
        aviso(".venv existe pero no funciona en este equipo (¿se copió de otro?). Se vuelve a crear.")
        shutil.rmtree(VENV, ignore_errors=True)
    if venv_funciona():
        salto("Entorno virtual .venv ya existe")
        return
    info("Creando el entorno virtual .venv…")
    try:
        venv.EnvBuilder(with_pip=True, clear=True).create(VENV)
    except Exception as e:  # noqa: BLE001
        fallar(f"No se pudo crear el entorno virtual: {e}", "En Ubuntu/Debian:  sudo apt install python3-venv")
    ok("Entorno virtual .venv creado")


def instalar_librerias():
    req = RAIZ / "requirements.txt"
    huella = hashlib.sha256(req.read_bytes()).hexdigest()
    if HASH_REQ.exists() and HASH_REQ.read_text().strip() == huella:
        salto("Librerías ya instaladas (requirements.txt no cambió)")
        return
    info("Instalando librerías (la primera vez tarda unos minutos)…")
    ejecutar([PY_VENV, "-m", "pip", "install", "--upgrade", "pip", "--quiet", "--disable-pip-version-check"])
    if ejecutar([PY_VENV, "-m", "pip", "install", "-r", req, "--quiet", "--disable-pip-version-check"]).returncode != 0:
        fallar("Falló la instalación de librerías.", "Revisa tu conexión a internet y vuelve a correr este archivo.")
    r = ejecutar([PY_VENV, "-c", "import pandas, numpy, openpyxl, psycopg, streamlit, plotly, sklearn, statsmodels"], capture_output=True, text=True)
    if r.returncode != 0:
        fallar("Las librerías no quedaron bien instaladas.", r.stderr[-800:] + "\nPrueba:  python3 setup.py --reinstalar")
    HASH_REQ.write_text(huella)
    ok("Librerías instaladas")


def configurar_vscode():
    archivo = RAIZ / ".vscode" / "settings.json"
    ruta = "${workspaceFolder}/.venv/" + ("Scripts/python.exe" if ES_WINDOWS else "bin/python")
    datos = {}
    if archivo.exists():
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except ValueError:
            return
    if datos.get("python.defaultInterpreterPath") == ruta:
        return
    datos["python.defaultInterpreterPath"] = ruta
    datos["python.terminal.activateEnvironment"] = True
    archivo.parent.mkdir(exist_ok=True)
    archivo.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ok("VS Code configurado para usar .venv")


def verificar_datos():
    datos = RAIZ / "Datos"
    faltan = [r for r in DATOS_REQUERIDOS if not (datos / r).exists()]
    if faltan:
        fallar("Faltan archivos del reto en la carpeta Datos/:",
               "\n".join("- " + f for f in faltan) + "\nCopia ahí el paquete del reto (no se sube a GitHub).")
    ok(f"Datos del reto completos ({len(DATOS_REQUERIDOS)} archivos)")


# ──────────────────────────────────────────────────────────────────────────────
# 4. PostgreSQL
# ──────────────────────────────────────────────────────────────────────────────
def url_configurada():
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    if ENV.exists():
        for linea in ENV.read_text(encoding="utf-8").splitlines():
            if linea.strip().startswith("DATABASE_URL="):
                return linea.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def guardar_url(url):
    """Escribe DATABASE_URL en .env conservando las demás líneas."""
    lineas = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else [
        "# Conexión a PostgreSQL del tablero (la crea setup.py). No se sube a GitHub."]
    lineas = [l for l in lineas if not l.strip().startswith("DATABASE_URL=")] + [f"DATABASE_URL={url}"]
    ENV.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def responde(url, espera=0):
    codigo = "import sys, psycopg; psycopg.connect(sys.argv[1], connect_timeout=3).close()"
    fin = time.time() + espera
    while True:
        if ejecutar([PY_VENV, "-c", codigo, url], capture_output=True).returncode == 0:
            return True
        if time.time() >= fin:
            return False
        time.sleep(2)


def docker_disponible():
    if not shutil.which("docker"):
        return False
    return ejecutar(["docker", "info"], capture_output=True).returncode == 0


def postgres_docker():
    info("Levantando PostgreSQL con Docker (docker compose up -d postgres)…")
    if ejecutar(["docker", "compose", "up", "-d", "postgres"], capture_output=True).returncode != 0:
        return None
    return URL_DOCKER if responde(URL_DOCKER, espera=90) else None


def carpeta_bin_postgres():
    candidatos = [str(PGBIN_PROYECTO / "pgserver" / "pginstall" / "bin")]
    if shutil.which("pg_ctl"):
        candidatos.append(str(Path(shutil.which("pg_ctl")).parent))
    if SISTEMA == "Darwin":
        candidatos += sorted(glob.glob("/opt/homebrew/opt/postgresql@*/bin"), reverse=True)
        candidatos += sorted(glob.glob("/usr/local/opt/postgresql@*/bin"), reverse=True)
        candidatos += ["/opt/homebrew/bin", "/usr/local/bin", "/Applications/Postgres.app/Contents/Versions/latest/bin"]
    elif ES_WINDOWS:
        candidatos += sorted(glob.glob(r"C:\Program Files\PostgreSQL\*\bin"), reverse=True)
    else:
        candidatos += sorted(glob.glob("/usr/lib/postgresql/*/bin"), reverse=True)
    candidatos.append(str(LEGADO_BIN / "pgserver" / "pginstall" / "bin"))
    ext = ".exe" if ES_WINDOWS else ""
    for c in candidatos:
        b = Path(c)
        if (b / f"pg_ctl{ext}").exists() and (b / f"initdb{ext}").exists():
            if ejecutar([b / f"postgres{ext}", "--version"], capture_output=True).returncode == 0:
                return b
    return None


def instalar_postgres_portatil():
    """Descarga PostgreSQL 16 (binarios del paquete pgserver de PyPI) en la carpeta de datos del usuario.
    No pide permisos de administrador y no toca el sistema."""
    import zipfile
    clave = (SISTEMA, "arm64" if platform.machine().lower() in ("arm64", "aarch64") and SISTEMA == "Darwin"
             else platform.machine())
    plataforma = PGSERVER_PLATAFORMAS.get(clave)
    if not plataforma:
        aviso(f"No hay PostgreSQL portátil para {SISTEMA} {platform.machine()}.")
        return None
    descarga = DATOS_USUARIO / "descarga"
    shutil.rmtree(descarga, ignore_errors=True)
    info("Descargando PostgreSQL 16 (≈30 MB, una sola vez)…")
    r = ejecutar([PY_VENV, "-m", "pip", "download", f"pgserver=={PGSERVER_VERSION}", "--no-deps",
                  "--only-binary=:all:", "--python-version", "3.12", "--platform", plataforma,
                  "-d", descarga, "-q", "--disable-pip-version-check"], capture_output=True, text=True)
    ruedas = sorted(descarga.glob("pgserver-*.whl"))
    if r.returncode != 0 or not ruedas:
        aviso("No se pudo descargar PostgreSQL: " + (r.stderr or r.stdout)[-300:])
        return None
    info(f"Instalando PostgreSQL en {PGBIN_PROYECTO} …")
    shutil.rmtree(PGBIN_PROYECTO, ignore_errors=True)
    # Se extrae el paquete completo: las librerías compartidas viven junto a pginstall/
    # (pgserver.libs/ en Linux, pgserver/.dylibs/ en macOS) y los binarios las buscan por ruta relativa.
    with zipfile.ZipFile(ruedas[0]) as z:
        for item in z.infolist():
            if item.is_dir() or not item.filename.startswith(("pgserver/", "pgserver.libs/")):
                continue
            destino = PGBIN_PROYECTO / item.filename
            destino.parent.mkdir(parents=True, exist_ok=True)
            with z.open(item) as origen, open(destino, "wb") as f:
                shutil.copyfileobj(origen, f)
            if not ES_WINDOWS:
                modo = (item.external_attr >> 16) & 0o777
                os.chmod(destino, modo or (0o755 if "/bin/" in item.filename or ".so" in item.filename
                                           or item.filename.endswith(".dylib") else 0o644))
    shutil.rmtree(descarga, ignore_errors=True)
    bindir = PGBIN_PROYECTO / "pgserver" / "pginstall" / "bin"
    ext = ".exe" if ES_WINDOWS else ""
    v = ejecutar([bindir / f"postgres{ext}", "--version"], capture_output=True, text=True)
    if v.returncode != 0:
        aviso("PostgreSQL se descargó pero no arranca en este equipo: " + (v.stderr or v.stdout)[-300:])
        return None
    ok(f"Instalado {v.stdout.strip()}")
    return bindir


def _pg(bindir, nombre):
    return str(bindir / (nombre + (".exe" if ES_WINDOWS else "")))


def _cola_log(n=12):
    log = PGDATA / "servidor.log"
    if not log.exists():
        return ""
    lineas = log.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(lineas[-n:])


def _puerto_conf():
    conf = PGDATA / "postgresql.conf"
    if conf.exists():
        for linea in reversed(conf.read_text(encoding="utf-8", errors="ignore").splitlines()):
            if linea.strip().startswith("port ="):
                try:
                    return int(linea.split("=", 1)[1].split("#")[0].strip())
                except ValueError:
                    break
    return PG_PUERTO_LOCAL


def _fijar_puerto(puerto):
    conf = PGDATA / "postgresql.conf"
    texto = conf.read_text(encoding="utf-8", errors="ignore")
    if MARCA_CONF in texto:
        texto = texto[:texto.index(MARCA_CONF)].rstrip("\n") + "\n"
    # Solo TCP en localhost: no depende de carpetas de sockets del sistema ni de permisos de administrador.
    # synchronous_commit = off: más rápido en equipos personales; la base se reconstruye desde Datos/.
    texto += (f"\n{MARCA_CONF}\nport = {puerto}\nlisten_addresses = 'localhost'\nunix_socket_directories = ''\n"
              "synchronous_commit = off\nmax_connections = 50\n")
    conf.write_text(texto, encoding="utf-8")


def _puerto_ocupado(p):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", p)) == 0


def _servidor_vivo(bindir):
    return ejecutar([_pg(bindir, "pg_ctl"), "status", "-D", PGDATA], capture_output=True).returncode == 0


def _detener(bindir, datos):
    """Detiene un servidor de una carpeta de datos (rápido y, si no responde, inmediato)."""
    for modo, espera in (("fast", "30"), ("immediate", "30")):
        r = ejecutar([_pg(bindir, "pg_ctl"), "stop", "-D", datos, "-m", modo, "-w", "-t", espera],
                     capture_output=True, text=True)
        if r.returncode == 0 or "no server running" in (r.stderr + r.stdout).lower():
            return True
    pid = datos / "postmaster.pid"
    if pid.exists() and not ES_WINDOWS:
        try:
            os.kill(int(pid.read_text().splitlines()[0]), signal.SIGQUIT)
            time.sleep(3)
            return True
        except (OSError, ValueError, IndexError):
            pass
    return False


def migrar_legado(bindir):
    """Versiones anteriores guardaban la base dentro del proyecto (.pgdata/). Si el proyecto está en una
    carpeta sincronizada (iCloud, OneDrive, Dropbox), PostgreSQL tarda minutos en arrancar: se mueve fuera."""
    if not (LEGADO_PGDATA / "PG_VERSION").exists():
        return
    if (PGDATA / "PG_VERSION").exists():
        if (LEGADO_PGDATA / "postmaster.pid").exists():
            _detener(bindir, LEGADO_PGDATA)     # el servidor viejo ocuparía el puerto
        return
    info("Moviendo la base de PostgreSQL fuera de la carpeta del proyecto (evita la lentitud de iCloud)…")
    _detener(bindir, LEGADO_PGDATA)
    PGDATA.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(LEGADO_PGDATA), str(PGDATA))
        for f in ("postmaster.pid", "postmaster.opts"):
            (PGDATA / f).unlink(missing_ok=True)
        ok(f"Base movida a {PGDATA}")
    except OSError as e:
        aviso(f"No se pudo mover la base anterior ({e}); se crea una nueva (los datos se recargan desde Datos/).")
        shutil.rmtree(PGDATA, ignore_errors=True)


def _esperar_conexion(puerto, segundos=600):
    """Espera a que el servidor acepte conexiones, mostrando avance si tarda (recuperación tras un apagado)."""
    url = f"postgresql://postgres@localhost:{puerto}/postgres"
    inicio = time.time()
    ultimo = inicio
    while time.time() - inicio < segundos:
        if responde(url):
            return True
        if time.time() - ultimo > 20:
            ultimo = time.time()
            cola = _cola_log(1)
            info(f"PostgreSQL sigue arrancando ({int(time.time() - inicio)} s)… {cola[-110:]}")
        time.sleep(2)
    return False


def postgres_local(bindir: Path):
    migrar_legado(bindir)
    PGDATA.parent.mkdir(parents=True, exist_ok=True)
    if not (PGDATA / "PG_VERSION").exists():
        shutil.rmtree(PGDATA, ignore_errors=True)
        info(f"Creando la base PostgreSQL del proyecto en {PGDATA}…")
        r = ejecutar([_pg(bindir, "initdb"), "-D", PGDATA, "-U", "postgres", "--auth=trust", "-E", "UTF8",
                      "--locale=C"], capture_output=True, text=True)
        if r.returncode != 0:
            aviso("initdb no pudo crear la base: " + (r.stderr or r.stdout)[-400:])
            if "root" in (r.stderr or ""):
                aviso("PostgreSQL no se puede iniciar como administrador (root). Corre setup.py con tu usuario normal.")
            return None
        _fijar_puerto(PG_PUERTO_LOCAL)
    elif MARCA_CONF not in (PGDATA / "postgresql.conf").read_text(encoding="utf-8", errors="ignore"):
        _fijar_puerto(PG_PUERTO_LOCAL)
    puerto = _puerto_conf()
    if not _servidor_vivo(bindir):
        if _puerto_ocupado(puerto):
            nuevo = puerto_libre(puerto + 1)
            aviso(f"El puerto {puerto} lo usa otro programa; PostgreSQL del proyecto usará el {nuevo}.")
            puerto = nuevo
            _fijar_puerto(puerto)
        info(f"Iniciando PostgreSQL local en el puerto {puerto}…")
        r = ejecutar([_pg(bindir, "pg_ctl"), "start", "-D", PGDATA, "-l", PGDATA / "servidor.log", "-w", "-t", "120"],
                     capture_output=True, text=True)
        if r.returncode != 0 and not _servidor_vivo(bindir):
            aviso("No arrancó PostgreSQL local:\n" + ((r.stderr or r.stdout)[-300:] + "\n" + _cola_log()).strip())
            return None
    if not _esperar_conexion(puerto):
        aviso("PostgreSQL no aceptó conexiones a tiempo:\n" + _cola_log())
        return None
    crear = ("import sys, psycopg; c = psycopg.connect(sys.argv[1], autocommit=True);"
             "c.execute('CREATE DATABASE actho') if not c.execute(\"SELECT 1 FROM pg_database WHERE datname='actho'\")"
             ".fetchone() else None")
    r = ejecutar([PY_VENV, "-c", crear, f"postgresql://postgres@localhost:{puerto}/postgres"],
                 capture_output=True, text=True)
    if r.returncode != 0:
        aviso("No se pudo crear la base 'actho': " + r.stderr[-300:])
    url = f"postgresql://postgres@localhost:{puerto}/actho"
    return url if responde(url, espera=20) else None


def abrir_docker_desktop():
    """Si Docker está instalado pero cerrado, lo abre y espera a que responda."""
    if not shutil.which("docker") and not (SISTEMA == "Darwin" and Path("/Applications/Docker.app").exists()):
        return False
    if SISTEMA == "Darwin":
        ejecutar(["open", "-a", "Docker"], capture_output=True)
    elif ES_WINDOWS:
        exe = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe"
        if exe.exists():
            subprocess.Popen([str(exe)])
    else:
        return False
    info("Abriendo Docker Desktop (hasta 2 minutos)…")
    fin = time.time() + 120
    while time.time() < fin:
        if docker_disponible():
            return True
        time.sleep(3)
    return False


def _listo(u, bindir=None, donde=""):
    guardar_url(u)
    ok(f"PostgreSQL listo ({u.split('@')[-1]}{donde})")
    return u, bindir


def asegurar_postgres(auto=False):
    """Prueba, en orden, hasta dejar una base funcionando. No pregunta nada: instala lo que falte."""
    url = url_configurada()
    if (LEGADO_BIN / "pgserver").exists() and not PGBIN_PROYECTO.exists():
        try:
            PGBIN_PROYECTO.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(LEGADO_BIN), str(PGBIN_PROYECTO))
            ok(f"PostgreSQL portátil movido fuera del proyecto ({PGBIN_PROYECTO})")
        except OSError:
            pass
    if (LEGADO_PGDATA / "PG_VERSION").exists():
        # Base de una versión anterior dentro del proyecto: se mueve fuera antes de usarla
        bindir = carpeta_bin_postgres()
        u = postgres_local(bindir) if bindir else None
        if u:
            return _listo(u, bindir, f", datos en {PGDATA}")
    if url and responde(url):
        salto("PostgreSQL ya está disponible (" + url.split("@")[-1] + ")")
        return url, None
    if url and url != URL_DOCKER and "localhost" not in url and "127.0.0.1" not in url:
        aviso(f"La base configurada en .env ({url.split('@')[-1]}) no responde; se usa una local.")
    intentos = []
    if (url == URL_DOCKER or url is None) and docker_disponible():
        u = postgres_docker()
        if u:
            return _listo(u, None, ", Docker")
        intentos.append("Docker está abierto pero el contenedor de PostgreSQL no arrancó")
    bindir = carpeta_bin_postgres()
    if bindir:
        u = postgres_local(bindir)
        if u:
            return _listo(u, bindir, f", datos en {PGDATA}")
        intentos.append(f"PostgreSQL de {bindir} no arrancó")
    if not (PGBIN_PROYECTO / "pgserver" / "pginstall" / "bin").exists():
        info("No hay PostgreSQL en este equipo: se instala uno portátil (sin permisos de administrador).")
        bindir = instalar_postgres_portatil()
        if bindir:
            u = postgres_local(bindir)
            if u:
                return _listo(u, bindir, f", datos en {PGDATA}")
            intentos.append("el PostgreSQL portátil no arrancó")
        else:
            intentos.append("no se pudo descargar el PostgreSQL portátil")
    if not docker_disponible() and abrir_docker_desktop():
        u = postgres_docker()
        if u:
            return _listo(u, None, ", Docker")
    instr = {"Darwin": "Opción 1: instala Docker Desktop y ábrelo.\n"
                       "Opción 2: brew install postgresql@16   (o instala Postgres.app)",
             "Windows": "Opción 1: instala Docker Desktop y ábrelo.\n"
                        "Opción 2: instala PostgreSQL 16 desde https://www.postgresql.org/download/windows/"}
    fallar("No hay PostgreSQL disponible para el tablero. Se intentó: " + "; ".join(intentos or ["nada aplicable"]),
           instr.get(SISTEMA, "Instala Docker o PostgreSQL 16 (sudo apt install postgresql).") +
           f"\nRegistro del servidor: {PGDATA / 'servidor.log'}\nLuego vuelve a correr:  python3 setup.py")


# ──────────────────────────────────────────────────────────────────────────────
# 5. Datos
# ──────────────────────────────────────────────────────────────────────────────
def procesar_datos(url, fecha_corte, forzar):
    cmd = [PY_VENV, "src/ingesta_control.py", "ingesta"]
    if fecha_corte:
        cmd += ["--fecha-corte", fecha_corte]
    if forzar:
        cmd.append("--forzar")
    info("Revisando si los datos cambiaron…")
    r = ejecutar(cmd, env=entorno(url), capture_output=True, text=True)
    salida = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        fallar("Falló el procesamiento de los datos.", salida[-2500:])
    for linea in salida.splitlines():
        if linea.startswith("Datos al día"):
            salto("Datos al día: ningún archivo cambió desde la última carga")
        elif linea.startswith("Datos procesados"):
            ok(linea)
        elif linea.startswith("Semáforo al"):
            ok(linea)
        elif linea.startswith("Modelos de IA"):
            (aviso if "no se entrenaron" in linea else ok)(linea)


# ──────────────────────────────────────────────────────────────────────────────
# 6. Tablero
# ──────────────────────────────────────────────────────────────────────────────
def puerto_libre(desde):
    for p in range(desde, desde + 30):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return desde


def esperar_tablero(url, proceso, segundos=90):
    fin = time.time() + segundos
    while time.time() < fin:
        if proceso.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url + "/_stcore/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(1)
    return False


def abrir_en_chrome(url):
    try:
        if SISTEMA == "Darwin":
            if ejecutar(["open", "-a", "Google Chrome", url], capture_output=True).returncode == 0:
                return "Google Chrome"
        elif ES_WINDOWS:
            for exe in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")]:
                if os.path.exists(exe):
                    subprocess.Popen([exe, url])
                    return "Google Chrome"
        else:
            for exe in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
                if shutil.which(exe):
                    subprocess.Popen([exe, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return "Google Chrome"
    except Exception:  # noqa: BLE001
        pass
    webbrowser.open(url)
    return "el navegador predeterminado (no encontré Google Chrome)"


def correr_tablero(url_bd, puerto, abrir):
    p = puerto_libre(puerto)
    url = f"http://localhost:{p}"
    info(f"Arrancando el tablero en {url}…")
    proc = subprocess.Popen([str(PY_VENV), "-m", "streamlit", "run", APP, "--server.port", str(p),
                             "--server.headless", "true", "--server.address", "localhost",
                             "--browser.gatherUsageStats", "false"],
                            cwd=RAIZ, env=entorno(url_bd))
    if not esperar_tablero(url, proc):
        proc.terminate()
        fallar("El tablero no arrancó. Revisa el mensaje de arriba.")
    ok(f"Tablero listo en {url}")
    if abrir:
        ok(f"Abierto en {abrir_en_chrome(url)}")
    print(f"\n   Usuario: admin   ·   Contraseña: actho\n   Para detener el tablero: Ctrl+C\n", flush=True)
    try:
        proc.wait()
    except KeyboardInterrupt:
        print()
        info("Deteniendo el tablero…")
        proc.send_signal(signal.SIGINT) if not ES_WINDOWS else proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Deja el tablero ACTHO corriendo en este equipo")
    ap.add_argument("--solo-instalar", action="store_true")
    ap.add_argument("--reinstalar", action="store_true")
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--fecha-corte", default=None)
    ap.add_argument("--sin-tablero", action="store_true")
    ap.add_argument("--sin-navegador", action="store_true")
    ap.add_argument("--puerto", type=int, default=8501)
    ap.add_argument("-y", "--si", action="store_true", help="responde sí a las preguntas (instalar PostgreSQL)")
    args = ap.parse_args()

    print("\n=== ACTHO · Tablero integral de afiliados ===\n")
    verificar_python()
    preparar_entorno(args.reinstalar)
    instalar_librerias()
    configurar_vscode()
    if args.solo_instalar:
        print("\nEntorno listo.\n")
        return
    verificar_datos()
    url_bd, _ = asegurar_postgres(auto=args.si)
    procesar_datos(url_bd, args.fecha_corte, args.forzar)
    if args.sin_tablero:
        print("\nDatos listos. Para abrir el tablero:  python3 setup.py\n")
        return
    correr_tablero(url_bd, args.puerto, not args.sin_navegador)


if __name__ == "__main__":
    main()
