# -*- coding: utf-8 -*-
"""Apoyo de IA en el tablero: lee las tablas del esquema `ia` (las escribe src/modelos_ia.py después de cada
carga) y ofrece piezas comunes: el chip ✦ IA, la nota con la métrica de cada modelo y cargadores en caché.

Si los modelos aún no se han entrenado, todo devuelve tablas vacías y las páginas siguen funcionando."""
import json
import sys

import pandas as pd
import streamlit as st

import comun as c

sys.path.insert(0, str(c.RAIZ / "src"))


@st.cache_data(ttl=60, show_spinner=False)
def t(nombre: str) -> pd.DataFrame:
    """Tabla ia.<nombre>, o vacía si no existe."""
    try:
        if not c.existe(f"ia.{nombre}"):
            return pd.DataFrame()
        return c.tabla(nombre, "ia")
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


def hay() -> bool:
    return not t("modelo").empty


def ficha(modelo: str) -> dict:
    f = t("modelo")
    if f.empty or modelo not in set(f["modelo"]):
        return {}
    r = f[f["modelo"] == modelo].iloc[0].to_dict()
    try:
        r["detalle"] = json.loads(r.get("detalle") or "{}")
    except ValueError:
        r["detalle"] = {}
    return r


# ──────────────────────────────────────────────────────────────────────────────
# Cada modelo explicado en lenguaje de negocio: qué pregunta responde, en qué se fija, cómo llega a su
# opinión, cuándo tenerla en cuenta y cuándo dudar. La confianza se calcula con los resultados reales
# de la última validación (ia.modelo), así que cambia con cada carga.
# ──────────────────────────────────────────────────────────────────────────────
NEGOCIO = {
    "renovacion": {
        "pregunta": "¿Qué tan probable es que esta empresa renueve su membresía?",
        "mira": "Revisó las 503 empresas que ya tuvieron que decidir en el último año (375 renovaron y 128 no) y "
                "aprendió qué tenían en común las que se quedaron: cuántos años llevan afiliadas, su tamaño, su nivel, "
                "su región, si están en comunidades y cuánto participaron en eventos en los 6 meses antes de decidir.",
        "decide": "A cada empresa vigente le compara esos mismos rasgos y da un porcentaje. Los factores «a favor» y "
                  "«en contra» son los rasgos que más la acercan o la alejan de las que renovaron.",
        "usar": "Para decidir a quién llamar primero y con qué argumento: los factores en contra dicen qué atacar.",
        "dudar": "Si la ejecutiva sabe algo que no está en los datos (cambio de gerente, recorte de presupuesto, una "
                 "queja reciente), su criterio pesa más. La asistencia solo existe desde enero de 2026.",
    },
    "perfiles": {
        "pregunta": "¿Qué grupos de afiliadas usan la membresía de forma parecida?",
        "mira": "Cuánto asistió cada afiliada en 12 meses, cuántas personas distintas, a cuántas líneas, qué "
                "beneficios usó y si está en comunidades.",
        "decide": "Junta en un mismo grupo a las que se parecen en eso y le pone un nombre según lo que las distingue "
                  "(por ejemplo «Desconectadas» o «Comprometidas multilínea»).",
        "usar": "Para hablarle distinto a cada grupo: a las desconectadas, reactivarlas; a las comprometidas, pedir "
                "referidos.",
        "dudar": "Una empresa puede estar en el borde entre dos grupos. Los nombres los puso el sistema: si no "
                 "describen bien al grupo, se pueden cambiar.",
    },
    "propension": {
        "pregunta": "¿Cuáles empresas no afiliadas se parecen a las afiliadas?",
        "mira": "Cómo participan en los eventos: cuántas veces asisten, cuántas personas envían, a qué líneas van, "
                "si prefieren lo virtual y si responden encuestas.",
        "decide": "Le da a cada no afiliada un puntaje de 0 a 100 según qué tanto se parece su forma de participar a "
                  "la de las afiliadas actuales.",
        "usar": "Para elegir a quién ofrecerle la membresía primero.",
        "dudar": "No dice que vayan a comprar: no hay historia de quién se afilió después de asistir. Un puntaje alto "
                 "significa que ya se comporta como afiliada.",
    },
    "temas": {
        "pregunta": "¿Qué temas piden los asistentes en sus comentarios?",
        "mira": "Las palabras de cada comentario libre de las encuestas y las de los 12 temas de la encuesta 2026.",
        "decide": "Asigna a cada comentario el tema con el que comparte más palabras clave. Si no se parece a ninguno "
                  "(«excelente evento», «gracias»), lo deja sin tema.",
        "usar": "Para ver qué piden más y compararlo con lo que ACTHO ofrece.",
        "dudar": "Lee palabras, no entiende ironías ni frases complejas. Un comentario puede tocar dos temas y solo "
                 "cuenta los dos más claros.",
    },
    "identidad": {
        "pregunta": "¿A qué empresa pertenece esta respuesta de encuesta?",
        "mira": "La persona que respondió y las empresas con las que esa misma persona se inscribió a eventos.",
        "decide": "Si la encuesta no traía empresa o traía una distinta, sugiere la empresa con la que la persona "
                  "más se ha inscrito.",
        "usar": "Para completar la base antes de calcular satisfacción por empresa.",
        "dudar": "Si la persona cambió de trabajo, la sugerencia puede ser de su empresa anterior: por eso se revisa "
                 "antes de aplicar.",
    },
    "recomendador": {
        "pregunta": "¿Qué le conviene ofrecerle a esta afiliada?",
        "mira": "Los beneficios que incluye su nivel y no ha usado en 12 meses, y los temas que más aprovechan las "
                "empresas de su mismo perfil.",
        "decide": "Propone hasta cuatro cosas: beneficios por activar, un tema que aún no ha explorado y, si aplica, "
                  "una comunidad.",
        "usar": "Como guion para la conversación de la ejecutiva y para el extracto de valor.",
        "dudar": "Todavía no se mide si las recomendaciones funcionan: hay que registrar qué se ofreció y qué se usó.",
    },
    "accion": {
        "pregunta": "¿Qué debería hacer la ejecutiva ahora con esta empresa?",
        "mira": "Cuántos días faltan para el vencimiento, si participó en los últimos 90 días y su probabilidad de "
                "renovar.",
        "decide": "Aplica reglas simples: si vence pronto y la probabilidad es baja, llamar con el extracto; si "
                  "vence pronto y va bien, enviar la propuesta; si no participa, invitarla a un evento.",
        "usar": "Para ordenar el trabajo de la semana.",
        "dudar": "Son reglas, no conocen la historia de la relación. La ejecutiva decide.",
    },
    "eventos": {
        "pregunta": "¿Cuántas personas se inscribirían a este evento y quiénes serían?",
        "mira": "Los eventos que ACTHO ya hizo en 2026 más parecidos al que estás diseñando: misma modalidad, línea, "
                "tema y costo, y fechas cercanas en el año.",
        "decide": "Promedia lo que pasó en los 5 más parecidos (inscritos, % de afiliados, cargos y satisfacción), "
                  "dando más peso a los más parecidos.",
        "usar": "Para dimensionar el lugar, el cupo y la convocatoria, y para comparar alternativas de fecha o formato.",
        "dudar": "Con 33 eventos el rango es amplio. Eventos de alto perfil (un ponente famoso, un tema de coyuntura "
                 "como el salario mínimo) suelen superar lo estimado.",
    },
    "altas": {
        "pregunta": "¿Cuántas empresas nuevas se afiliarán cada mes?",
        "mira": "Las afiliaciones de cada mes desde 2019: la tendencia y los meses que suelen ser más fuertes o "
                "más flojos.",
        "decide": "Proyecta esa tendencia y esa temporada hacia adelante, con un rango de lo que es normal esperar.",
        "usar": "Como referencia para la meta comercial y para ver si un mes va por encima o por debajo de lo normal.",
        "dudar": "Hoy no es más preciso que suponer «lo mismo que el mismo mes del año pasado». No sabe de campañas "
                 "nuevas ni de cambios de precio.",
    },
    "vigentes": {
        "pregunta": "¿Cuántas afiliadas tendremos a diciembre de 2027 si nada cambia?",
        "mira": "La fecha de vencimiento de cada vigente, su probabilidad de renovar y las afiliaciones esperadas.",
        "decide": "Simula 2.000 futuros posibles, en cada uno cada empresa renueva o no según su probabilidad, y "
                  "reporta el resultado típico y el rango.",
        "usar": "Para ver el tamaño del reto: cuánto hay que mejorar la renovación o las ventas para llegar a la meta.",
        "dudar": "Supone que todo sigue igual: cualquier campaña de retención o de ventas cambia el resultado (esa es "
                 "la idea).",
    },
    "control": {
        "pregunta": "¿Este evento o este mes fue realmente distinto o es variación normal?",
        "mira": "La satisfacción de cada evento y el NPS de cada mes, y cuántas respuestas tuvo cada uno.",
        "decide": "Dibuja una franja de lo normal alrededor del promedio histórico. La franja es más ancha cuando "
                  "hubo pocas respuestas, porque ahí un par de opiniones mueven mucho el promedio.",
        "usar": "Para no reaccionar a cambios pequeños y sí revisar los puntos que se salen de la franja.",
        "dudar": "Que algo esté dentro de la franja no significa que esté bien: significa que no cambió.",
    },
}


def _diez(x):
    return max(0, min(10, round(10 * float(x))))


def confianza(modelo: str) -> str:
    """Qué tan confiable resultó el modelo en su última validación, dicho en términos del negocio."""
    f = ficha(modelo)
    if not f or f.get("valor") is None:
        return ""
    v, d = f["valor"], f.get("detalle", {})
    if modelo == "renovacion":
        return (f"Al ponerlo a prueba con empresas que no vio, cuando se compara una que renovó con una que no, le da "
                f"más probabilidad a la que sí renovó en {_diez(v)} de cada 10 casos.")
    if modelo == "propension":
        return (f"Al ponerlo a prueba, distingue a una afiliada de una no afiliada solo por cómo participa en "
                f"{_diez(v)} de cada 10 casos.")
    if modelo == "perfiles":
        nivel = "muy marcados" if v > 0.5 else ("razonablemente distintos" if v > 0.25 else "poco marcados")
        return f"Los grupos son {nivel} entre sí: úsalos como orientación, no como etiquetas fijas."
    if modelo == "temas":
        return f"Revisado a mano en 70 comentarios, acertó el tema en {_diez(v)} de cada 10."
    if modelo == "identidad":
        return f"Cuando ya se conocía la empresa por el correo, coincidió en {round(100 * v)} de cada 100 casos."
    if modelo == "eventos":
        cob = d.get("cobertura_80")
        return (f"Probado con los eventos de 2026 sin mirarlos, en la mitad de ellos se equivocó por menos de "
                f"{round(v)} inscritos, y el rango probable acertó en {_diez(cob)} de cada 10."
                if cob is not None else "")
    if modelo == "altas":
        return (f"En los últimos 12 meses se equivocó en promedio por {v:.0f} afiliaciones al mes"
                + ("." if d.get("gana_linea_base") else ", igual que suponer «lo mismo del año pasado»: tómalo como "
                                                       "referencia, no como meta."))
    if modelo == "vigentes":
        return (f"Resultado típico: {v:,.0f} vigentes; en 8 de cada 10 escenarios queda entre "
                f"{f['linea_base'].split(': ')[-1].rstrip('.')}.").replace(",", ".")
    if modelo == "recomendador":
        return "Todavía no se mide si las recomendaciones funcionan."
    if modelo == "control":
        return "Es una regla estadística estándar: no se entrena, así que no tiene error que medir."
    return ""


def desc(modelo: str) -> str:
    """Texto corto para el ícono ⓘ: qué pregunta responde, cómo llega a su opinión y qué tan confiable es."""
    n = NEGOCIO.get(modelo)
    if not n:
        return ("Modelos entrenados con los datos de cada carga. Ordenan y explican para apoyar la decisión; no "
                "deciden por el equipo. Explicación completa en Datos y calidad → Modelos de IA.")
    return f"{n['pregunta']} {n['decide']} {confianza(modelo)}".strip()


def explicacion(modelo: str) -> dict:
    """Explicación completa para las fichas de Datos y calidad."""
    n = dict(NEGOCIO.get(modelo, {}))
    n["confianza"] = confianza(modelo)
    return n


def info(modelo: str) -> str:
    """Ícono ⓘ con la explicación corta del modelo (HTML para poner junto a un título o texto)."""
    return c._icono_ayuda(desc(modelo), "i", "info")


def chip(texto: str = "IA") -> str:
    return c.chip(texto, "IA")


def _num(v, dec=2):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def nota(modelo: str, extra: str = ""):
    """Línea pequeña bajo un resultado de IA: qué modelo es y, en palabras de negocio, qué tan confiable es."""
    f = ficha(modelo)
    if not f:
        return
    conf = confianza(modelo)
    st.markdown(f'<div class="nota-ia">{chip()} &nbsp;<b>{c._e(f["nombre"])}</b>{info(modelo)}'
                f'{" · " + c._e(conf) if conf else ""}{" · " + extra if extra else ""}'
                ' · <i>cómo piensa: Datos y calidad → Modelos de IA</i></div>', unsafe_allow_html=True)


def sin_modelos():
    st.info("Los modelos de IA todavía no están listos. Si acabas de correr `python3 setup.py`, se están entrenando en "
            "segundo plano: esta sección aparece sola al terminar (recarga la página en un par de minutos).",
            icon=":material/auto_awesome:")


# ── Cargadores ya preparados ─────────────────────────────────────────────────
def renovacion() -> pd.DataFrame:
    return t("renovacion")


def perfiles() -> pd.DataFrame:
    return t("perfil")


def propension() -> pd.DataFrame:
    return t("propension")


def pronostico(serie: str) -> pd.DataFrame:
    p = t("pronostico")
    if p.empty:
        return p
    p = p[p["serie"] == serie].copy()
    p["mes"] = pd.to_datetime(p["mes"])
    return p.sort_values("mes")


def con_ia(e: pd.DataFrame) -> pd.DataFrame:
    """Agrega a una tabla de empresas la probabilidad de renovar, el perfil y la propensión."""
    out = e.copy()
    r, p, pr = renovacion(), perfiles(), propension()
    if not r.empty:
        out = out.merge(r[["empresa_id", "p_renovar", "banda", "a_favor", "en_contra"]], on="empresa_id", how="left")
    if not p.empty:
        out = out.merge(p[["empresa_id", "perfil"]], on="empresa_id", how="left")
    if not pr.empty:
        out = out.merge(pr[["empresa_id", "puntaje"]].rename(columns={"puntaje": "propension"}), on="empresa_id",
                        how="left")
    return out


BANDA_COLOR = {"En riesgo": c.C["naranja"], "Incierta": c.C["lavanda_graf"], "Probable": c.C["morado"]}
ORDEN_BANDA = ["En riesgo", "Incierta", "Probable"]
