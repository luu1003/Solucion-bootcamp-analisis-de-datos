# -*- coding: utf-8 -*-
"""
Extracto de valor por afiliado · ACTHO

Una página HTML autocontenida (se abre en cualquier navegador y se imprime o guarda como PDF) con lo que
la empresa usó de su afiliación en los últimos 12 meses: experiencias, personas de su equipo, beneficios
del nivel 2027 usados y pendientes, su voz en las encuestas y sugerencias para el próximo año.

Pensado para la reunión de renovación de la ejecutiva de cuenta. No incluye datos personales: solo
conteos por nivel de cargo y nombres de eventos.
"""
from __future__ import annotations

import html
import io
import zipfile

import pandas as pd

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
INCLUIDO = {"Conectar": "incluido_conectar", "Crecer": "incluido_crecer", "Liderar": "incluido_liderar"}


def _e(v) -> str:
    return html.escape("" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))


def _fecha(f) -> str:
    if f is None or pd.isna(f):
        return "—"
    f = pd.Timestamp(f)
    return f"{f.day} {MESES[f.month - 1]} {f.year}"


def _n(v, dec=0) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
*{box-sizing:border-box} body{margin:0;background:#EEF6F5;font-family:Poppins,'Segoe UI',Arial,sans-serif;color:#1B1235}
.hoja{max-width:860px;margin:24px auto;background:#fff;border-radius:20px;overflow:hidden}
.banda{background:#5B00D9;color:#fff;padding:28px 36px 24px;position:relative}
.logo{font-size:30px;font-weight:600;letter-spacing:-1px}.logo span{color:#FF5A0F}
.lema{color:#8AE6F7;font-size:13px;font-weight:500;margin-top:2px}
.banda h1{margin:18px 0 4px;font-size:28px;line-height:1.15}
.banda .sub{color:#E9DDFF;font-size:14px}
.cinta{position:absolute;right:30px;top:-20px;width:110px;height:200px}
.cuerpo{padding:24px 36px 8px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:22px}
.k{background:#F6F2FF;border-radius:14px;padding:14px}
.k .et{font-size:11px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:#5E5876}
.k .va{font-size:28px;font-weight:700;margin-top:4px}
.k .no{font-size:12px;color:#5E5876}
h2{font-size:17px;color:#5B00D9;margin:22px 0 2px}
.h2sub{font-size:12px;color:#C2410C;margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#5E5876;border-bottom:1px solid #E4E1EC;padding:6px 8px}
td{border-bottom:1px solid #E4E1EC;padding:7px 8px;vertical-align:top}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.lista{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.item{border:1px solid #E4E1EC;border-radius:12px;padding:10px 12px;font-size:13px;display:flex;gap:10px;align-items:flex-start}
.item b{display:block;font-weight:600}.item small{color:#5E5876}
.marca{flex:none;width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px}
.m-si{background:#5B00D9;color:#fff}.m-no{background:#FFF0E8;color:#A8360A}.m-nd{background:#F1EFF5;color:#5E5876}
td.f{white-space:nowrap}
.sugerencia{background:#FFF0E8;border-left:4px solid #FF5A0F;border-radius:10px;padding:10px 14px;margin-bottom:8px;font-size:13px}
.voz{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.pie{margin-top:26px;padding:16px 36px 22px;border-top:1px solid #E4E1EC;font-size:11px;color:#5E5876;display:flex;justify-content:space-between;gap:16px}
.pie b{color:#5B00D9}
.boton{position:fixed;right:24px;bottom:24px;background:#D14800;color:#fff;border:none;border-radius:999px;padding:12px 22px;
  font:600 14px Poppins,Arial,sans-serif;cursor:pointer;box-shadow:0 8px 20px rgba(209,72,0,.3)}
.boton:focus-visible{outline:3px solid #5B00D9;outline-offset:2px}
.vacio{color:#5E5876;font-size:13px;font-style:italic}
@media print{body{background:#fff}.hoja{margin:0;border-radius:0;max-width:none}.boton{display:none}
  .banda,.k,.m-si,.m-no,.sugerencia{-webkit-print-color-adjust:exact;print-color-adjust:exact} h2{break-after:avoid} table,.item{break-inside:avoid}}
@page{size:A4;margin:12mm}
@media (max-width:700px){.kpis{grid-template-columns:repeat(2,1fr)}.lista,.voz{grid-template-columns:1fr}}
"""

CINTA = ('<svg class="cinta" viewBox="0 0 170 300" fill="none" aria-hidden="true"><path d="M160 -10C60 50 30 140 95 172'
         'C160 204 172 118 118 118C64 118 48 230 150 320" stroke="#FF5A0F" stroke-width="18" stroke-linecap="round"/></svg>')


def html_extracto(emp: pd.Series, uso: pd.DataFrame, asis: pd.DataFrame, enc: pd.DataFrame,
                  cat: pd.DataFrame, corte) -> str:
    """emp: fila de v_empresa_360. uso / asis / enc: filas de esa empresa. cat: dim_servicio."""
    corte = pd.Timestamp(corte)
    desde = corte - pd.Timedelta(days=365)
    nivel = emp.get("nivel_2027")
    u = uso.copy()
    if len(u):
        u["fecha"] = pd.to_datetime(u["fecha"])
        u = u[(u["es_fechado"] == 0) | ((u["fecha"] > desde) & (u["fecha"] <= corte))]
    a = asis.copy()
    if len(a):
        a["fecha_evento"] = pd.to_datetime(a["fecha_evento"])
        a = a[(a["fecha_evento"] > desde) & (a["fecha_evento"] <= corte)]

    # Beneficios del nivel
    col = INCLUIDO.get(nivel)
    incluidos = cat[cat[col] == 1] if col and col in cat else cat.iloc[0:0]
    usados = set(u["servicio_id"]) if len(u) else set()
    medibles = set(cat[cat["fuente_dato"].isin(["Asistencia", "CRM y asistencia"])]["servicio_id"]) | usados
    n_inc = sum(1 for s in incluidos["servicio_id"] if s in medibles)
    n_us = sum(1 for s in incluidos["servicio_id"] if s in usados)

    kpis = [
        ("Experiencias", _n(a["evento_id"].nunique() if len(a) else 0), "eventos con tu equipo en 12 meses"),
        ("Personas de tu equipo", _n(a["persona_id"].nunique() if len(a) else 0), "participaron al menos una vez"),
        ("Beneficios usados", _n(u["servicio_id"].nunique() if len(u) else 0), "servicios distintos de la oferta"),
        ("Aprovechamiento", f"{n_us}/{n_inc}" if n_inc else "—", f"beneficios medibles de {_e(nivel)}"),
    ]
    k_html = "".join(f'<div class="k"><div class="et">{_e(t)}</div><div class="va">{v}</div><div class="no">{n}</div></div>'
                     for t, v, n in kpis)

    # Lo que usaste
    if len(u):
        res = (u.groupby(["servicio", "linea_servicio"])
                .agg(usos=("cantidad", "sum"), ultimo=("fecha", "max"), fuentes=("fuente", lambda s: ", ".join(sorted(set(s)))))
                .reset_index().sort_values("usos", ascending=False))
        filas = "".join(f'<tr><td><b>{_e(r.servicio)}</b></td><td>{_e(r.linea_servicio)}</td><td class="num">{_n(r.usos)}</td>'
                        f'<td>{"vigente" if r.fuentes.startswith("CRM") else _fecha(r.ultimo)}</td><td><small>{_e(r.fuentes)}</small></td></tr>'
                        for r in res.itertuples())
        usado_html = (f'<table><thead><tr><th>Beneficio</th><th>Línea</th><th style="text-align:right">Usos</th>'
                      f'<th>Último uso</th><th>Fuente</th></tr></thead><tbody>{filas}</tbody></table>')
    else:
        usado_html = '<p class="vacio">No hay usos registrados en los últimos 12 meses.</p>'

    # Experiencias
    if len(a):
        ex = (a.groupby(["fecha_evento", "evento", "linea_2027"]).agg(personas=("persona_id", "nunique"))
               .reset_index().sort_values("fecha_evento", ascending=False))
        filas = "".join(f'<tr><td class="f">{_fecha(r.fecha_evento)}</td><td>{_e(r.evento)}</td><td>{_e(r.linea_2027)}</td>'
                        f'<td class="num">{_n(r.personas)}</td></tr>' for r in ex.itertuples())
        exp_html = (f'<table><thead><tr><th>Fecha</th><th>Experiencia</th><th>Línea</th><th style="text-align:right">Personas</th>'
                    f'</tr></thead><tbody>{filas}</tbody></table>')
        cargos = a[a["nivel_cargo"] != "Sin dato"].groupby("nivel_cargo")["persona_id"].nunique().sort_values(ascending=False)
        equipo = " · ".join(f"{_e(k)}: <b>{_n(v)}</b>" for k, v in cargos.items()) or "Sin nivel de cargo registrado"
    else:
        exp_html, equipo = '<p class="vacio">Tu equipo no registra asistencias en los últimos 12 meses.</p>', ""

    # Beneficios del nivel
    items = []
    for r in incluidos.itertuples():
        if r.servicio_id in usados:
            m, txt = '<span class="marca m-si" aria-label="Usado">✓</span>', "Usado"
        elif r.servicio_id in medibles:
            m, txt = '<span class="marca m-no" aria-label="Disponible">!</span>', "Disponible, aún sin usar"
        else:
            m, txt = '<span class="marca m-nd" aria-label="Sin registro">·</span>', "Incluido (aún no se registra su uso)"
        cond = f" · {_e(r.condicion)}" if isinstance(r.condicion, str) and r.condicion else ""
        items.append(f'<div class="item">{m}<div><b>{_e(r.servicio)}</b><small>{txt}{cond}</small></div></div>')
    nivel_html = f'<div class="lista">{"".join(items)}</div>' if items else \
        '<p class="vacio">Este tipo de afiliación tiene una oferta propia, fuera de los niveles 2027.</p>'

    # Voz
    sat = enc["satisfaccion_general"].fillna(enc["satisfaccion_prom"]).mean() if len(enc) else None
    nps_n = enc["nps_puntaje"].notna().sum() if len(enc) else 0
    nps = (100 * ((enc["nps_categoria"] == "Promotor").sum() - (enc["nps_categoria"] == "Detractor").sum()) / nps_n) if nps_n else None
    temas = enc["temas_solicitados"].dropna() if "temas_solicitados" in enc else pd.Series(dtype=str)
    temas = [t for t in temas if isinstance(t, str) and len(t) > 3][:3]
    voz_html = (f'<div class="voz"><div class="k"><div class="et">Satisfacción</div><div class="va">{_n(sat, 2)}</div>'
                f'<div class="no">de 5 · {_n(len(enc))} respuestas</div></div>'
                f'<div class="k"><div class="et">NPS de eventos</div><div class="va">{_n(nps)}</div><div class="no">{_n(nps_n)} respuestas</div></div>'
                f'<div class="k"><div class="et">Temas que pidieron</div><div class="no" style="margin-top:6px">'
                + ("<br>".join(f"«{_e(t[:90])}»" for t in temas) or "Sin temas registrados") + "</div></div></div>")

    # Sugerencias
    pendientes = sorted([r for r in incluidos.itertuples() if r.servicio_id not in usados],
                        key=lambda r: (r.servicio_id not in medibles, r.servicio_id))[:3]
    sug = [f'<div class="sugerencia"><b>{_e(r.servicio)}</b>: {_e(r.descripcion)}.</div>' for r in pendientes]
    if (emp.get("personas_distintas") or 0) <= 1:
        sug.append('<div class="sugerencia"><b>Más personas de tu equipo</b>: la afiliación es de la empresa; '
                   'invita a otros niveles del área de talento humano a las próximas experiencias.</div>')
    sug_html = "".join(sug) or '<p class="vacio">Tu equipo ya usa todos los beneficios medibles de tu nivel.</p>'

    vence = _fecha(emp.get("fecha_expiracion"))
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Extracto de valor · {_e(emp['empresa_id'])}</title><style>{CSS}</style></head>
<body><main class="hoja">
<header class="banda">{CINTA}<div class="logo">ac<span>tho</span></div><div class="lema">Del saber al acto</div>
<h1>Extracto de valor de tu afiliación</h1>
<div class="sub">{_e(emp['empresa_id'])} · Nivel {_e(nivel)} · Afiliada desde {_fecha(emp.get('fecha_afiliacion'))} · Vence {vence}
 · Ejecutiva: {_e(emp.get('ejecutiva'))}</div></header>
<section class="cuerpo">
<div class="kpis">{k_html}</div>
<h2>Lo que usaste en los últimos 12 meses</h2><p class="h2sub">Del {_fecha(desde)} al {_fecha(corte)}</p>{usado_html}
<h2>Experiencias de tu equipo</h2><p class="h2sub">{equipo}</p>{exp_html}
<h2>Tus beneficios del nivel {_e(nivel)}</h2><p class="h2sub">Lo que incluye tu afiliación y qué tanto lo aprovechaste</p>{nivel_html}
<h2>Tu voz</h2><p class="h2sub">Lo que tu equipo nos dijo en las encuestas de eventos</p>{voz_html}
<h2>Lo que viene para ti</h2><p class="h2sub">Beneficios incluidos que todavía puedes aprovechar</p>{sug_html}
</section>
<footer class="pie"><div><b>Sentimos el pulso.</b> Lo convertimos en acción.</div>
<div>Datos al {_fecha(corte)} · Tablero Integral de Afiliados ACTHO</div></footer>
</main>
<button class="boton" onclick="window.print()">Imprimir o guardar como PDF</button>
</body></html>"""


def zip_extractos(empresas: pd.DataFrame, uso: pd.DataFrame, asis: pd.DataFrame, enc: pd.DataFrame,
                  cat: pd.DataFrame, corte) -> bytes:
    """Un HTML por empresa dentro de un ZIP (para la campaña de renovación)."""
    buf = io.BytesIO()
    u_g = dict(tuple(uso.groupby("empresa_id"))) if len(uso) else {}
    a_g = dict(tuple(asis.groupby("empresa_id"))) if len(asis) else {}
    e_g = dict(tuple(enc.groupby("empresa_id"))) if len(enc) else {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for _, emp in empresas.iterrows():
            i = emp["empresa_id"]
            z.writestr(f"extracto_{i}.html", html_extracto(emp, u_g.get(i, uso.iloc[0:0]), a_g.get(i, asis.iloc[0:0]),
                                                           e_g.get(i, enc.iloc[0:0]), cat, corte))
    return buf.getvalue()
