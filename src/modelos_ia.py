"""Modelos de apoyo de IA del tablero ACTHO.

Se entrena después de cada carga (setup.py, Airflow o a mano) y escribe sus resultados en el
esquema `ia` de PostgreSQL. El tablero solo lee esas tablas: no entrena nada al abrir una página.

    python src/modelos_ia.py                 # entrena todo con la fecha de corte de la base
    python src/modelos_ia.py --fecha-corte 2026-11-23

Modelos (pestaña donde se ven):
  renovacion   Probabilidad de renovar y factores por empresa        Ficha 360°, Afiliados, Renovación, Pulso
  perfiles     Perfiles de empresas afiliadas (k-means)               Afiliados, Ficha 360°, Segmentos
  propension   Parecido de no afiliadas con las afiliadas             Afiliados, Segmentos
  temas        Tema de cada comentario y de cada evento (TF-IDF)      Experiencias, Planeación, Segmentos
  identidad    Cruces de encuestas sugeridos por persona              Datos y calidad
  recomendador Siguiente paso y beneficios por activar                Ficha 360°, extracto
  eventos      Simulador de inscritos por evento (k vecinos)          Planeación de eventos
  altas        SARIMA de altas mensuales                              Base de afiliados, Dashboard
  vigentes     Proyección de vigentes a dic-2027 (simulación)         Base de afiliados, Dashboard
  control      Gráficos de control de satisfacción y NPS              Experiencias
  arima_*      ARIMA de inscripciones y retiros (se activa con 24 meses de historia)
"""
from __future__ import annotations

import json
import sys
import warnings
from datetime import date, datetime
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
import simulador_eventos as sim  # noqa: E402

ESQUEMA = "ia"
SEMILLA = 42
INICIO_OBSERVACION = pd.Timestamp("2026-01-01")   # la asistencia registrada empieza aquí
VENTANA_PREVIA = 180                               # días de comportamiento antes de la fecha de referencia
MESES_MIN_ARIMA = 24

warnings.filterwarnings("ignore")


# ──────────────────────────────────────────────────────────────────────────────
# Conexión y escritura
# ──────────────────────────────────────────────────────────────────────────────
def conectar():
    import psycopg
    from cargar_postgres import cadena_conexion
    url = cadena_conexion()
    if not url:
        raise SystemExit("No hay conexión configurada (DATABASE_URL o archivo .env).")
    return psycopg.connect(url, autocommit=True)


def leer(conn, sql: str) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [d.name for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def _tipo(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_integer_dtype(s):
        return "bigint"
    if pd.api.types.is_float_dtype(s):
        return "double precision"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "date"
    return "text"


def escribir(conn, nombre: str, df: pd.DataFrame):
    """Reemplaza la tabla ia.<nombre> en una sola transacción (el tablero nunca la ve a medias)."""
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.date
    def tipo(c):
        x = df[c].dropna()
        return "date" if len(x) and isinstance(x.iloc[0], date) and not isinstance(x.iloc[0], datetime) \
            else _tipo(df[c])
    cols = ", ".join(f'"{c}" {tipo(c)}' for c in df.columns)
    buf = StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="\\N")
    with conn.transaction():
        conn.execute(f"DROP TABLE IF EXISTS {ESQUEMA}.{nombre}")
        conn.execute(f"CREATE TABLE {ESQUEMA}.{nombre} ({cols})")
        with conn.cursor().copy(f"COPY {ESQUEMA}.{nombre} FROM STDIN WITH (FORMAT csv, NULL '\\N')") as cp:
            cp.write(buf.getvalue())


FICHAS: list[dict] = []


def ficha(modelo, nombre, pestanas, objetivo, metodo, datos, n, metrica, valor, linea_base, limitaciones,
          estado="Activo", extra=None):
    FICHAS.append({"modelo": modelo, "nombre": nombre, "pestanas": pestanas, "objetivo": objetivo,
                   "metodo": metodo, "datos": datos, "n": int(n), "metrica": metrica,
                   "valor": None if valor is None else round(float(valor), 3),
                   "linea_base": linea_base, "limitaciones": limitaciones, "estado": estado,
                   "detalle": json.dumps(extra or {}, ensure_ascii=False, default=str)})


# ──────────────────────────────────────────────────────────────────────────────
# Datos
# ──────────────────────────────────────────────────────────────────────────────
def cargar(conn) -> dict:
    d = {
        "e360": leer(conn, "SELECT * FROM actho.v_empresa_360"),
        "emp": leer(conn, "SELECT * FROM actho.dim_empresa"),
        "asis": leer(conn, """SELECT a.*, e.fecha, e.linea_2027, e.experiencia, e.modalidad, e.nombre AS evento
                              FROM actho.fact_asistencia a JOIN actho.dim_evento e USING (evento_id)"""),
        "eventos": leer(conn, "SELECT * FROM actho.dim_evento"),
        "enc": leer(conn, "SELECT * FROM actho.fact_encuesta_evento"),
        "temas_etq": leer(conn, "SELECT * FROM actho.fact_encuesta_temas"),
        "personas": leer(conn, "SELECT * FROM actho.dim_persona"),
        "uso": leer(conn, "SELECT * FROM actho.fact_uso_beneficio"),
        "catalogo": leer(conn, "SELECT * FROM actho.dim_servicio"),
        "benef": leer(conn, "SELECT * FROM actho.v_empresa_beneficios"),
        "mov": leer(conn, "SELECT * FROM actho.v_movimiento_mensual"),
    }
    for k, cols in {"e360": ["fecha_afiliacion", "fecha_expiracion", "fecha_corte"],
                    "emp": ["fecha_afiliacion", "fecha_expiracion"], "asis": ["fecha"], "eventos": ["fecha"],
                    "enc": ["fecha_respuesta"], "uso": ["fecha"]}.items():
        for c in cols:
            d[k][c] = pd.to_datetime(d[k][c], errors="coerce")
    for c in ["satisfaccion_promedio", "nps", "pct_aprovechamiento"]:
        d["e360"][c] = pd.to_numeric(d["e360"][c], errors="coerce")
    for c in ["satisfaccion_prom", "nps_puntaje", "evento_id"]:
        d["enc"][c] = pd.to_numeric(d["enc"][c], errors="coerce")
    return d


# ──────────────────────────────────────────────────────────────────────────────
# 1. Probabilidad de renovar
# ──────────────────────────────────────────────────────────────────────────────
ETIQUETAS_RENOV = {
    "antiguedad": "Años como afiliada",
    "tam_grande": "Empresa grande", "tam_mediana": "Empresa mediana", "tam_peq": "Empresa pequeña o micro",
    "tam_sd": "Tamaño sin dato en el CRM",
    "tipo_consultora": "Afiliada como consultora", "tipo_persona": "Afiliada como persona natural",
    "premium": "Categoría Premium o Elite",
    "reg_bogota": "Sede en Bogotá", "reg_antioquia": "Sede en Antioquia",
    "comunidades": "Vinculada a comunidades",
    "exposicion": "Meses con asistencia observable",
    "participacion": "Inscripciones en los 6 meses previos",
    "personas": "Personas distintas en los 6 meses previos",
    "sin_participacion": "Ningún evento en los 6 meses previos",
}


def _rasgos_renovacion(base: pd.DataFrame, asis: pd.DataFrame, ref_col: str) -> pd.DataFrame:
    """Rasgos medidos ANTES de la fecha de referencia de cada empresa (sin fuga temporal)."""
    X = pd.DataFrame(index=base.index)
    ref = base[ref_col]
    X["antiguedad"] = ((ref - base["fecha_afiliacion"]).dt.days / 365.25).clip(0, 30).fillna(3)
    t = base["tamano_empresa"].fillna("Sin dato")
    X["tam_grande"] = (t == "Grande").astype(int)
    X["tam_mediana"] = (t == "Mediana").astype(int)
    X["tam_peq"] = t.isin(["Pequeña", "Micro"]).astype(int)
    X["tam_sd"] = (t == "Sin dato").astype(int)
    X["tipo_consultora"] = (base["tipo_membresia"] == "Consultoras").astype(int)
    X["tipo_persona"] = (base["tipo_membresia"] == "Persona natural").astype(int)
    X["premium"] = base["categoria_membresia"].isin(["Premium", "Elite"]).astype(int)
    X["reg_bogota"] = (base["region"] == "Bogotá").astype(int)
    X["reg_antioquia"] = (base["region"] == "Antioquia").astype(int)
    X["comunidades"] = (base["n_comunidades"].fillna(0) > 0).astype(int)
    # Comportamiento en la ventana previa, recortada a lo que el registro de asistencia alcanza a ver
    ini = (ref - pd.Timedelta(days=VENTANA_PREVIA)).clip(lower=INICIO_OBSERVACION)
    expo = ((ref - ini).dt.days).clip(lower=0)
    X["exposicion"] = (expo / 30.4).round(1)
    a = asis[["empresa_id", "persona_id", "fecha"]].merge(
        pd.DataFrame({"empresa_id": base["empresa_id"], "ini": ini, "ref": ref}), on="empresa_id")
    a = a[(a["fecha"] >= a["ini"]) & (a["fecha"] < a["ref"])]
    g = a.groupby("empresa_id").agg(insc=("fecha", "size"), pers=("persona_id", "nunique"))
    X["participacion"] = np.log1p(base["empresa_id"].map(g["insc"]).fillna(0).values)
    X["personas"] = np.log1p(base["empresa_id"].map(g["pers"]).fillna(0).values)
    X["sin_participacion"] = ((X["participacion"] == 0) & (X["exposicion"] >= 2)).astype(int)
    return X


ESTATICAS = ["antiguedad", "tam_grande", "tam_mediana", "tam_peq", "tam_sd", "tipo_consultora", "tipo_persona",
             "premium", "reg_bogota", "reg_antioquia", "comunidades"]
CONDUCTA = ["participacion", "sin_participacion"]


def _ajustar_renovacion(X, y, C=0.5, estaticas=None):
    """Dos etapas para no confundir 'tener asistencia observable' con 'no renovar':
    1) logística con rasgos estáticos sobre todas las empresas con desenlace;
    2) ajuste por conducta (inscripciones en los 6 meses previos) solo con las empresas cuya ventana previa
       cae dentro del registro de asistencia, usando la etapa 1 como desplazamiento (offset)."""
    import statsmodels.api as sm
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    est = estaticas or ESTATICAS
    sc = StandardScaler().fit(X[est])
    lr = LogisticRegression(C=C, max_iter=2000).fit(sc.transform(X[est]), y)
    logit_s = lr.decision_function(sc.transform(X[est]))
    obs = (X["exposicion"] >= 1).values
    B = X.loc[obs, CONDUCTA]
    glm = sm.GLM(y[obs], B, family=sm.families.Binomial(), offset=logit_s[obs]).fit_regularized(alpha=0.02, L1_wt=0)
    return {"sc": sc, "lr": lr, "beta": np.asarray(glm.params), "n_obs": int(obs.sum()), "est": est}


def _predecir_renovacion(m, X, con_conducta=True):
    z = m["sc"].transform(X[m["est"]])
    logit = m["lr"].decision_function(z)
    if con_conducta:
        logit = logit + np.where((X["exposicion"] >= 1).values, X[CONDUCTA].values @ m["beta"], 0)
    return 1 / (1 + np.exp(-logit))


def modelo_renovacion(d: dict, corte: pd.Timestamp) -> dict:
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.model_selection import RepeatedStratifiedKFold

    e = d["e360"]
    etq = e[e["renovacion_aprox"].notna()].copy().reset_index(drop=True)
    etq["y"] = (etq["renovacion_aprox"] == "Renovó").astype(int)
    # Fecha de referencia: cuándo se decidió la renovación
    venc = etq["fecha_expiracion"]
    etq["ref"] = pd.to_datetime(np.where(etq["y"] == 1, venc - pd.DateOffset(years=1), venc))
    etq["ref"] = etq["ref"].fillna(corte - pd.Timedelta(days=365)).clip(upper=corte)
    X = _rasgos_renovacion(etq, d["asis"], "ref")
    y = etq["y"].values
    obs = (X["exposicion"] >= 1).values

    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=10, random_state=SEMILLA)
    aucs, aucs_est, aucs_obs, aucs_sin_crm = [], [], [], []
    p_oof = np.zeros(len(y))
    sin_crm = [c for c in ESTATICAS if c not in ("tam_sd", "comunidades")]
    for i, (tr, te) in enumerate(cv.split(X, y)):
        m = _ajustar_renovacion(X.iloc[tr], y[tr])
        p = _predecir_renovacion(m, X.iloc[te])
        aucs.append(roc_auc_score(y[te], p))
        aucs_est.append(roc_auc_score(y[te], _predecir_renovacion(m, X.iloc[te], False)))
        o = obs[te]
        if o.sum() > 5 and len(set(y[te][o])) > 1:
            aucs_obs.append(roc_auc_score(y[te][o], p[o]))
        if i < 5:
            p_oof[te] = p
        m2 = _ajustar_renovacion(X.iloc[tr], y[tr], estaticas=sin_crm)
        aucs_sin_crm.append(roc_auc_score(y[te], _predecir_renovacion(m2, X.iloc[te])))
    brier = brier_score_loss(y, p_oof)
    brier_base = brier_score_loss(y, np.full(len(y), y.mean()))

    modelo = _ajustar_renovacion(X, y)
    sc, lr, beta = modelo["sc"], modelo["lr"], modelo["beta"]
    coef = pd.DataFrame({"variable": ESTATICAS + CONDUCTA,
                         "etiqueta": [ETIQUETAS_RENOV[c] for c in ESTATICAS + CONDUCTA],
                         "coeficiente": np.r_[lr.coef_[0], beta * X.loc[obs, CONDUCTA].std().values],
                         "etapa": ["Rasgos de la empresa"] * len(ESTATICAS) + ["Conducta reciente"] * len(CONDUCTA)})
    coef["razon_momios"] = np.exp(coef["coeficiente"])
    coef = coef.reindex(coef["coeficiente"].abs().sort_values(ascending=False).index)

    # Puntuar la cartera vigente hoy (todas con 6 meses de asistencia observable)
    vig = e[(e["es_vigente"] == 1) & (e["en_crm"] == 1)].copy().reset_index(drop=True)
    vig["ref"] = corte
    Xv = _rasgos_renovacion(vig, d["asis"], "ref")
    p = _predecir_renovacion(modelo, Xv)
    contrib = pd.DataFrame(sc.transform(Xv[ESTATICAS]) * lr.coef_[0], columns=ESTATICAS)
    media_obs = X.loc[obs, CONDUCTA].mean()
    for j, c in enumerate(CONDUCTA):
        contrib[c] = (Xv[c] - media_obs[c]).values * beta[j]
    filas_f, tops = [], []
    for i, emp in enumerate(vig["empresa_id"]):
        c = contrib.iloc[i]
        visibles = [k for k in c.index if k == "antiguedad" or (k == "participacion" and Xv.iloc[i][k] > 0)
                    or (k != "participacion" and Xv.iloc[i][k] == 1)]
        c = c[visibles]
        c = c[c.abs() > 0.05].sort_values()
        neg = [_txt_factor(k, Xv.iloc[i][k]) for k in c.index[:3] if c[k] < 0]
        pos = [_txt_factor(k, Xv.iloc[i][k]) for k in c.index[::-1][:3] if c[k] > 0]
        tops.append((" · ".join(pos), " · ".join(neg)))
        for k, v in c.items():
            filas_f.append({"empresa_id": emp, "factor": ETIQUETAS_RENOV[k], "efecto": round(float(v), 3),
                            "valor": _valor_factor(k, Xv.iloc[i][k])})
    banda = pd.cut(p, [-0.01, 0.5, 0.75, 1.01], labels=["En riesgo", "Incierta", "Probable"]).astype(str)
    score = pd.DataFrame({"empresa_id": vig["empresa_id"], "p_renovar": p.round(3), "banda": banda,
                          "a_favor": [t[0] for t in tops], "en_contra": [t[1] for t in tops],
                          "semaforo": vig["semaforo"], "fecha_expiracion": vig["fecha_expiracion"]})
    ficha("renovacion", "Probabilidad de renovar", "Ficha 360°, Afiliados, Renovación, Pulso",
          "Ordenar la cartera vigente por probabilidad de renovar y explicar por qué",
          "Regresión logística en dos etapas: rasgos de la empresa con todas las empresas con desenlace, y un "
          f"ajuste por conducta reciente con las {modelo['n_obs']} cuya ventana previa cae en el registro de "
          "asistencia. Factores = aporte de cada variable al puntaje.",
          f"{len(etq)} empresas con desenlace conocido en los últimos 12 meses ({int(y.sum())} renovaron, "
          f"{int(len(y) - y.sum())} no). Comportamiento medido solo antes de su fecha de referencia.",
          len(etq), "AUC (validación cruzada 5×10)", np.mean(aucs),
          f"Azar = 0,50. Solo rasgos de la empresa: {np.mean(aucs_est):.2f}. En empresas con conducta observable: "
          f"{np.mean(aucs_obs):.2f}. Brier {brier:.3f} frente a {brier_base:.3f} con la tasa promedio.",
          "La asistencia solo existe desde ene-2026: las que renovaron a fin de 2025 no tienen conducta previa "
          "observable, por eso la conducta se estima aparte con las que sí. 'Tamaño sin dato' y 'comunidades' "
          "vienen del CRM actual y pueden reflejar en parte la cancelación: sin ellas el AUC es "
          f"{np.mean(aucs_sin_crm):.2f}. Sirve para ordenar la cartera, no para decidir por la ejecutiva.",
          extra={"auc_std": float(np.std(aucs)), "auc_solo_estaticas": float(np.mean(aucs_est)),
                 "auc_observables": float(np.mean(aucs_obs)), "auc_sin_variables_crm": float(np.mean(aucs_sin_crm)),
                 "n_observables": modelo["n_obs"], "brier": brier, "brier_base": brier_base,
                 "tasa_base": float(y.mean()), "puntuadas": len(vig), "p_media_cartera": float(p.mean())})
    return {"score": score, "factores": pd.DataFrame(filas_f), "coef": coef}


def _txt_factor(k, v):
    if k == "participacion":
        n = int(round(np.expm1(v)))
        return f"{n} inscripciones en 6 meses"
    if k == "antiguedad":
        n = int(round(v))
        return "Menos de un año como afiliada" if n < 1 else f"{n} año{'s' if n != 1 else ''} como afiliada"
    if k == "sin_participacion":
        return "Ningún evento en 6 meses"
    return ETIQUETAS_RENOV[k]


def _valor_factor(k, v):
    if k == "antiguedad":
        return f"{v:.1f} años"
    if k in ("participacion", "personas"):
        return f"{int(round(np.expm1(v)))}"
    if k == "exposicion":
        return f"{v:.0f} meses"
    return "Sí" if v else "No"


# ──────────────────────────────────────────────────────────────────────────────
# 2. Perfiles de afiliadas (k-means)
# ──────────────────────────────────────────────────────────────────────────────
def _rasgos_uso(d: dict, ids: pd.Series, corte) -> pd.DataFrame:
    a = d["asis"][d["asis"]["fecha"] >= corte - pd.Timedelta(days=365)]
    a = a[a["empresa_id"].isin(ids)]
    g = a.groupby("empresa_id")
    f = pd.DataFrame(index=ids.values)
    f["inscripciones"] = g.size()
    f["personas"] = g["persona_id"].nunique()
    f["eventos"] = g["evento_id"].nunique()
    f["lineas"] = g["linea_2027"].nunique()
    for linea, col in [("Anticipar", "sh_anticipar"), ("Pares", "sh_pares"), ("Foro", "sh_foro"),
                       ("Evento grande", "sh_grande")]:
        f[col] = a[a["linea_2027"] == linea].groupby("empresa_id").size() / f["inscripciones"]
    f["sh_virtual"] = a[a["modalidad"] == "Virtual"].groupby("empresa_id").size() / f["inscripciones"]
    f["sh_directivos"] = a[a["nivel_cargo"].isin(["Alta dirección (C-level / VP)", "Dirección / Gerencia"])
                           ].groupby("empresa_id").size() / f["inscripciones"]
    return f.fillna(0)


NOMBRES_PERFIL = {
    "Desconectadas": "Casi no aparecen en eventos ni usan beneficios en el último año",
    "Fieles a lo legal": "Su participación se concentra en Actho Legislativo y webinars normativos",
    "Comprometidas multilínea": "Varias personas, varias líneas: aprovechan buena parte de la membresía",
    "Vinculadas por comunidad": "Están en comunidades pero asisten poco a eventos",
    "Directivas en espacios de pares": "Van perfiles directivos a Pares, Foros y eventos presenciales",
    "Participación ocasional": "Uno o dos eventos al año, sin un patrón marcado",
}


def modelo_perfiles(d: dict, corte) -> dict:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    e = d["e360"]
    vig = e[(e["es_vigente"] == 1) & (e["en_crm"] == 1)].reset_index(drop=True)
    f = _rasgos_uso(d, vig["empresa_id"], corte)
    f["servicios"] = vig.set_index("empresa_id")["servicios_12m"].reindex(f.index).fillna(0).values
    f["comunidades"] = vig.set_index("empresa_id")["n_comunidades"].reindex(f.index).fillna(0).values
    Z = f.copy()
    for c in ["inscripciones", "personas", "eventos"]:
        Z[c] = np.log1p(Z[c])
    sc = StandardScaler().fit(Z)
    Zs = sc.transform(Z)
    sil = {}
    for k in range(3, 7):
        km = KMeans(k, n_init=20, random_state=SEMILLA).fit(Zs)
        sil[k] = silhouette_score(Zs, km.labels_)
    k = max(sil, key=sil.get)
    km = KMeans(k, n_init=20, random_state=SEMILLA).fit(Zs)
    f["cluster"] = km.labels_
    cent = f.groupby("cluster").mean()
    # Nombrar cada grupo con el arquetipo que mejor describe su centro
    rel = (cent - f.drop(columns="cluster").mean()) / f.drop(columns="cluster").std().replace(0, 1)
    puntos = pd.DataFrame({
        "Desconectadas": -rel["inscripciones"] - rel["servicios"] - rel["comunidades"],
        "Fieles a lo legal": rel["sh_anticipar"] + 0.5 * rel["sh_virtual"],
        "Comprometidas multilínea": rel["lineas"] + rel["personas"] + rel["inscripciones"],
        "Vinculadas por comunidad": rel["comunidades"] - rel["inscripciones"],
        "Directivas en espacios de pares": rel["sh_pares"] + rel["sh_foro"] + rel["sh_directivos"],
        "Participación ocasional": -rel.abs().mean(axis=1) * 2,
    })
    nombre = {}
    libres = list(puntos.columns)
    for cl in puntos.max(axis=1).sort_values(ascending=False).index:
        mejor = puntos.loc[cl, libres].idxmax()
        nombre[cl] = mejor
        libres.remove(mejor)
    dist = km.transform(Zs).min(axis=1)
    perfil = pd.DataFrame({"empresa_id": f.index, "perfil": f["cluster"].map(nombre).values,
                           "cercania": (1 / (1 + dist)).round(3)})
    res = cent.copy()
    res["perfil"] = [nombre[c] for c in res.index]
    res["descripcion"] = res["perfil"].map(NOMBRES_PERFIL)
    res["empresas"] = f.groupby("cluster").size()
    # Tasa de renovación y probabilidad media por perfil, para leer cada grupo
    res = res.reset_index(drop=True).round(2)
    # Empresas parecidas: las 5 más cercanas en el mismo espacio de rasgos
    from sklearn.neighbors import NearestNeighbors
    nn = NearestNeighbors(n_neighbors=6).fit(Zs)
    dd, ii = nn.kneighbors(Zs)
    par = [{"empresa_id": f.index[i], "parecida_id": f.index[j], "orden": r, "similitud": round(1 / (1 + dd[i, r]), 3)}
           for i in range(len(f)) for r, j in enumerate(ii[i]) if r > 0]
    ficha("perfiles", "Perfiles de afiliadas", "Afiliados, Ficha 360°, Segmentos",
          "Agrupar la cartera vigente por cómo usa la membresía para hablarle a cada grupo distinto",
          f"k-means sobre {Z.shape[1]} rasgos de uso de los últimos 12 meses; k elegido por silueta",
          f"{len(f)} afiliadas vigentes", len(f), f"Silueta (k={k})", sil[k],
          "Silueta > 0,25 indica grupos razonablemente separados; > 0,5, muy separados.",
          "Los nombres de los perfiles se asignan con reglas sobre el centro de cada grupo; revísalos con "
          "el equipo. Con un año de asistencia los perfiles pueden cambiar mucho al llegar más datos.",
          extra={"silueta_por_k": sil})
    return {"perfil": perfil, "resumen": res, "parecidas": pd.DataFrame(par)}


# ──────────────────────────────────────────────────────────────────────────────
# 3. Propensión de no afiliadas (parecido a afiliadas)
# ──────────────────────────────────────────────────────────────────────────────
def modelo_propension(d: dict, corte) -> pd.DataFrame:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import cross_val_predict, StratifiedKFold

    e = d["e360"]
    asist = d["asis"]
    con_asis = asist["empresa_id"].dropna().unique()
    base = e[e["empresa_id"].isin(con_asis)].copy()
    base["y"] = (base["es_vigente"] == 1).astype(int)
    base = base[(base["y"] == 1) | (base["en_crm"] == 0)].reset_index(drop=True)
    f = _rasgos_uso(d, base["empresa_id"], corte + pd.Timedelta(days=1))
    enc = d["enc"].groupby("empresa_id").agg(sat=("satisfaccion_prom", "mean"), resp=("encuesta_id", "size"))
    f["respondio_encuesta"] = base["empresa_id"].map(enc["resp"]).fillna(0).gt(0).astype(int).values
    f["satisfaccion"] = base["empresa_id"].map(enc["sat"]).fillna(0).values
    X, y = f.values, base["y"].values
    rf = RandomForestClassifier(300, min_samples_leaf=5, random_state=SEMILLA, class_weight="balanced")
    p_cv = cross_val_predict(rf, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=SEMILLA),
                             method="predict_proba")[:, 1]
    auc = roc_auc_score(y, p_cv)
    no_af = base["y"] == 0
    # Para las no afiliadas usamos la predicción fuera de muestra (no se vieron a sí mismas)
    out = pd.DataFrame({"empresa_id": base.loc[no_af, "empresa_id"], "puntaje": (p_cv[no_af] * 100).round(0),
                        "inscripciones": f.loc[no_af.values, "inscripciones"].values,
                        "personas": f.loc[no_af.values, "personas"].values,
                        "directivos_pct": (f.loc[no_af.values, "sh_directivos"].values * 100).round(0)})
    out["banda"] = pd.cut(out["puntaje"], [-1, 40, 65, 101], labels=["Baja", "Media", "Alta"]).astype(str)
    out = out.sort_values("puntaje", ascending=False)
    imp = pd.Series(rf.fit(X, y).feature_importances_, index=f.columns).sort_values(ascending=False)
    ficha("propension", "Parecido con afiliadas (no afiliadas)", "Afiliados, Segmentos",
          "Priorizar a qué empresas no afiliadas que ya asisten conviene ofrecerles la membresía",
          "Bosque aleatorio que distingue afiliadas de no afiliadas por su forma de participar; "
          "el puntaje de cada no afiliada es fuera de muestra",
          f"{len(base)} empresas con asistencia en 2026 ({int(y.sum())} afiliadas, {int((1 - y).sum())} no)",
          len(base), "AUC (validación cruzada 5 pliegues)", auc, "Azar = 0,50.",
          "No es probabilidad de compra: no hay historia de conversiones. Mide cuánto se parece una empresa a "
          "las afiliadas actuales. No usa el costo del evento ni la marca de afiliado para no hacer trampa.",
          extra={"importancias": imp.round(3).to_dict()})
    return out


# ──────────────────────────────────────────────────────────────────────────────
# 4. Temas (TF-IDF)
# ──────────────────────────────────────────────────────────────────────────────
SEMILLAS_TEMA = {
    "Legislación laboral y reforma laboral":
        "legislación laboral reforma laboral ley norma normativa decreto jurídico derecho laboral actualización "
        "legal reglamento interno trabajo jurisprudencia fuero despido contratación aprendices sena acoso laboral "
        "sexual comité convivencia disciplinario procesos disciplinarios salario mínimo jornada impuestos "
        "pensión prepensión discapacidad cumplimiento",
    "Relaciones laborales y sindicales":
        "sindicato sindicatos sindicales negociación colectiva convención colectiva relaciones laborales pliego "
        "huelga diálogo social",
    "Nómina, compensación y beneficios":
        "nómina compensación salarial salario remuneración beneficios pagos en especie compensación variable "
        "bandas salariales proyecciones salariales incentivos fidelización",
    "Analítica de personas y datos en TH":
        "analítica people analytics datos indicadores métricas talento humano tablero medición kpi",
    "Inteligencia artificial aplicada a talento humano":
        "inteligencia artificial ia herramientas de ia automatización tecnología digital chatgpt algoritmos",
    "Liderazgo y desarrollo de líderes":
        "liderazgo líderes líder jefes conversaciones difíciles sucesión planes de sucesión transformacional "
        "gerencia mandos medios",
    "Cultura organizacional y gestión del cambio":
        "cultura organizacional gestión del cambio cambio transformación innovación mentalidad propósito "
        "agilidad herramientas ágiles clima",
    "Bienestar y salud mental en el trabajo":
        "bienestar salud mental felicidad emocional estrés cuidado equilibrio inclusión diversidad equidad "
        "personas ser",
    "Aprendizaje, formación y desarrollo":
        "aprendizaje formación capacitación desarrollo entrenamiento habilidades storytelling upskilling",
    "Gestión del desempeño":
        "desempeño evaluación de desempeño feedback retroalimentación objetivos productividad resultados metas "
        "top talents",
    "Seguridad y salud en el trabajo (SST)":
        "sst sg-sst seguridad industrial accidentalidad accidentes de trabajo arl ergonomía higiene industrial "
        "copasst brigadas emergencias",
    "Atracción, selección y marca empleadora":
        "selección reclutamiento atracción marca empleadora contratación talento vacantes procesos de selección",
}
SIN_TEMA = "Sin tema"
SEMILLA_COMENTARIO = ("gracias excelente espacio evento muy bueno interesante me encantó felicitaciones todo bien "
                      "ninguno no aplica si buen espacio emotivo presentación dinámicas puntual auditorio "
                      "maravilloso valioso agradezco")
UMBRAL_TEMA = 0.12


def _norm(t: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


class ClasificadorTemas:
    def __init__(self, extra_textos: dict[str, list[str]] | None = None):
        from sklearn.feature_extraction.text import TfidfVectorizer
        docs = {t: s for t, s in SEMILLAS_TEMA.items()}
        for t, lst in (extra_textos or {}).items():
            if t in docs:
                docs[t] += " " + " ".join(lst)
        docs[SIN_TEMA] = SEMILLA_COMENTARIO
        self.temas = list(docs)
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self.vec_w = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True)
        cuerpo = [_norm(docs[t]) for t in self.temas]
        self.P = self.vec.fit_transform(cuerpo)
        self.Pw = self.vec_w.fit_transform(cuerpo)

    def puntajes(self, textos) -> np.ndarray:
        from sklearn.metrics.pairwise import cosine_similarity
        T = [_norm(t) for t in textos]
        return 0.5 * cosine_similarity(self.vec.transform(T), self.P) + \
            0.5 * cosine_similarity(self.vec_w.transform(T), self.Pw)

    def clasificar(self, textos) -> pd.DataFrame:
        S = self.puntajes(textos)
        filas = []
        for i, t in enumerate(textos):
            orden = np.argsort(-S[i])
            mejor, seg = orden[0], orden[1]
            tema = self.temas[mejor]
            sim_ = float(S[i, mejor])
            if len(_norm(t).strip(" -.")) < 4 or sim_ < UMBRAL_TEMA:
                tema = SIN_TEMA
            segundo = self.temas[seg] if S[i, seg] >= max(UMBRAL_TEMA, 0.8 * sim_) and self.temas[seg] != SIN_TEMA else None
            filas.append({"tema": tema, "similitud": round(sim_, 3),
                          "tema_2": segundo if tema != SIN_TEMA else None})
        return pd.DataFrame(filas)


def modelo_temas(d: dict) -> dict:
    enc = d["enc"]
    # Textos "Otro: ..." de la encuesta estructurada sirven para enriquecer las semillas
    etq = d["temas_etq"]
    extra = etq[etq["detalle"].notna() & (etq["tema"] != "Otro")].groupby("tema")["detalle"].apply(list).to_dict()
    clf = ClasificadorTemas(extra)
    txt = enc[enc["temas_solicitados"].notna()][["encuesta_id", "persona_id", "empresa_id", "evento_id",
                                                 "fecha_respuesta", "temas_solicitados"]].copy()
    txt["temas_solicitados"] = txt["temas_solicitados"].str.strip()
    r = clf.clasificar(txt["temas_solicitados"].tolist())
    txt = pd.concat([txt.reset_index(drop=True), r], axis=1)
    txt["origen"] = "Modelo (TF-IDF)"
    # Validación contra textos etiquetados a mano
    val = pd.read_csv(RAIZ / "src" / "recursos" / "temas_validacion.csv")
    v = val.merge(txt[["encuesta_id", "tema", "tema_2"]], on="encuesta_id", how="left")
    v["ok"] = [str(t) in a.split("|") or (str(t2) in a.split("|")) for t, t2, a in
               zip(v["tema"], v["tema_2"], v["temas_aceptados"])]
    v["ok_top1"] = [str(t) in a.split("|") for t, a in zip(v["tema"], v["temas_aceptados"])]
    acc = v["ok_top1"].mean()
    con_tema = v["temas_aceptados"] != SIN_TEMA
    acc_tema = v.loc[con_tema, "ok_top1"].mean()
    # Base: asignar siempre el tema más frecuente
    base = (v["temas_aceptados"].str.split("|").apply(lambda a: "Legislación laboral y reforma laboral" in a)).mean()
    # Etiquetas estructuradas (encuesta post-evento 2026)
    etq_m = etq[etq["tema"] != "Otro"].merge(enc[["encuesta_id", "persona_id", "empresa_id", "evento_id",
                                                     "fecha_respuesta"]], on="encuesta_id", how="left")
    etq_m = etq_m.assign(temas_solicitados=etq_m["tema"], similitud=1.0, tema_2=None, origen="Etiqueta de la encuesta")
    solicitudes = pd.concat([txt, etq_m[txt.columns]], ignore_index=True)
    # Tema de cada evento a partir de su nombre
    ev = d["eventos"].copy()
    rev = clf.clasificar((ev["nombre"] + " " + ev["experiencia"].fillna("")).tolist())
    ev["tema"] = rev["tema"].values
    ev.loc[ev["tema"] == SIN_TEMA, "tema"] = "General / tendencias"
    ev["similitud_tema"] = rev["similitud"].values
    ev["origen_tema"] = "Modelo (TF-IDF)"
    # Correcciones a mano (las mantiene el equipo de ACTHO en src/recursos/temas_eventos.csv)
    ruta = RAIZ / "src" / "recursos" / "temas_eventos.csv"
    if ruta.exists():
        for _, c in pd.read_csv(ruta).iterrows():
            m = ev["nombre"].str.contains(str(c["nombre_contiene"]), case=False, regex=False, na=False)
            ev.loc[m, ["tema", "origen_tema"]] = [c["tema"], "Corregido a mano"]
    # Oferta frente a demanda
    sol = solicitudes[solicitudes["tema"] != SIN_TEMA]
    sol = pd.concat([sol[["tema", "encuesta_id"]], sol[sol["tema_2"].notna()][["tema_2", "encuesta_id"]]
                    .rename(columns={"tema_2": "tema"})])
    dem = sol.groupby("tema").size().rename("solicitudes")
    of = ev.groupby("tema").agg(eventos=("evento_id", "size"), inscritos=("inscritos", "sum"))
    dd = pd.concat([dem, of], axis=1).fillna(0).reset_index().rename(columns={"index": "tema"})
    dd["pct_demanda"] = (100 * dd["solicitudes"] / max(dd["solicitudes"].sum(), 1)).round(1)
    dd["pct_oferta"] = (100 * dd["eventos"] / max(dd["eventos"].sum(), 1)).round(1)
    dd["brecha"] = (dd["pct_demanda"] - dd["pct_oferta"]).round(1)
    dd = dd.sort_values("brecha", ascending=False)
    cobertura = (txt["tema"] != SIN_TEMA).mean()
    ficha("temas", "Temas de los comentarios y de los eventos", "Experiencias, Planeación de eventos, Segmentos",
          "Saber qué temas piden los asistentes y compararlo con lo que ACTHO ofrece",
          "TF-IDF (caracteres y palabras) contra una descripción de cada uno de los 12 temas de la encuesta "
          "2026; si nada se parece lo suficiente queda 'Sin tema'. No usa un modelo de lenguaje externo.",
          f"{len(txt)} textos libres de encuestas + {len(etq_m)} temas marcados en la encuesta post-evento; "
          f"validado con {len(v)} textos etiquetados a mano",
          len(txt), "Aciertos en el primer tema (validación manual)", acc,
          f"Asignar siempre 'Legislación' acertaría {base:.0%}. Solo en textos con tema: {acc_tema:.0%}.",
          "Las palabras semilla se escribieron mirando una muestra de comentarios, así que la cifra puede ser "
          "optimista. Un texto puede tocar varios temas: se guarda un segundo tema cuando aplica. Para más "
          "precisión, etiquetar 200 textos más o usar un modelo de lenguaje.",
          extra={"cobertura": float(cobertura), "n_validacion": len(v), "aciertos_top2": float(v["ok"].mean())})
    return {"textos": solicitudes, "eventos": ev[["evento_id", "tema", "similitud_tema", "origen_tema"]], "demanda": dd,
            "clasificador": clf}


# ──────────────────────────────────────────────────────────────────────────────
# 5. Interés por tema de cada persona (para convocar)
# ──────────────────────────────────────────────────────────────────────────────
def interes_personas(d: dict, temas: dict) -> pd.DataFrame:
    a = d["asis"].merge(temas["eventos"][["evento_id", "tema"]], on="evento_id")
    p = a.groupby(["persona_id", "tema"]).size().rename("asistencias").reset_index()
    s = temas["textos"]
    s = s[(s["tema"] != SIN_TEMA) & s["persona_id"].notna()].groupby(["persona_id", "tema"]).size().rename("pedidos")
    x = p.merge(s.reset_index(), on=["persona_id", "tema"], how="outer").fillna(0)
    x["puntaje"] = x["asistencias"] + 2 * x["pedidos"]
    per = d["personas"][["persona_id", "empresa_id", "nivel_cargo", "autoriza_datos"]]
    x = x.merge(per, on="persona_id", how="left")
    vig = d["e360"].set_index("empresa_id")["es_vigente"]
    x["es_afiliada"] = x["empresa_id"].map(vig).fillna(0).astype(int)
    return x.sort_values("puntaje", ascending=False)


# ──────────────────────────────────────────────────────────────────────────────
# 6. Resolución de identidad (cruces de encuestas sugeridos)
# ──────────────────────────────────────────────────────────────────────────────
def modelo_identidad(d: dict) -> pd.DataFrame:
    enc = d["enc"]
    a = d["asis"]
    emp_p = a.groupby("persona_id")["empresa_id"].agg(lambda s: s.value_counts().index[0] if s.notna().any() else None)
    n_emp = a.groupby("persona_id")["empresa_id"].nunique()
    x = enc[["encuesta_id", "respuesta_id", "persona_id", "empresa_id", "tipo_cruce", "metodo_asignacion_empresa"]].copy()
    x["empresa_por_persona"] = x["persona_id"].map(emp_p)
    x["empresas_de_la_persona"] = x["persona_id"].map(n_emp).fillna(0).astype(int)
    exact = x[(x["tipo_cruce"] == "Exacto") & x["empresa_por_persona"].notna()]
    acuerdo = (exact["empresa_id"] == exact["empresa_por_persona"]).mean() if len(exact) else None
    sug = x[(x["tipo_cruce"] != "Exacto") & x["empresa_por_persona"].notna() &
            (x["empresa_id"].isna() | (x["empresa_id"] != x["empresa_por_persona"]))].copy()
    sug["motivo"] = np.where(sug["empresa_id"].isna(), "La encuesta no traía empresa; la persona sí asistió con una",
                             "La empresa asignada por nombre o dominio no coincide con la de su asistencia")
    sug["confianza"] = np.where(sug["empresas_de_la_persona"] > 1, "Media", "Alta")
    # Personas que aparecen en varias empresas en la asistencia: posible cambio de empleo o error de digitación
    varias = a.groupby("persona_id")["empresa_id"].agg(lambda s: ", ".join(sorted(s.dropna().unique())))
    varias = varias[n_emp.reindex(varias.index) > 1].reset_index().rename(columns={"empresa_id": "empresas"})
    varias["motivo"] = "La misma persona aparece inscrita por varias empresas"
    out = pd.concat([
        sug[["respuesta_id", "persona_id", "empresa_id", "empresa_por_persona", "tipo_cruce", "motivo", "confianza"]]
        .rename(columns={"empresa_id": "empresa_actual", "empresa_por_persona": "empresa_sugerida"}),
        varias.assign(respuesta_id=None, empresa_actual=varias["empresas"], empresa_sugerida=None,
                      tipo_cruce="Asistencia", confianza="Revisar")[
            ["respuesta_id", "persona_id", "empresa_actual", "empresa_sugerida", "tipo_cruce", "motivo", "confianza"]],
    ], ignore_index=True)
    ficha("identidad", "Cruces sugeridos de personas y empresas", "Datos y calidad",
          "Completar la empresa de encuestas que no la traían y detectar personas registradas en varias empresas",
          "Regla por identificador de persona: la empresa con la que más asistió esa persona",
          f"{len(enc)} respuestas de encuestas y {a['persona_id'].nunique()} personas en asistencia",
          len(enc), "Acuerdo con los cruces exactos por correo", acuerdo,
          f"Se validó sobre {len(exact)} respuestas cruzadas por correo exacto.",
          "Los nombres y correos se eliminaron al anonimizar, así que no se puede hacer coincidencia difusa de "
          "nombres: solo se usa el identificador de persona. Las sugerencias se revisan antes de aplicarlas.",
          extra={"sugerencias": int(len(sug)), "personas_varias_empresas": int(len(varias))})
    return out


# ──────────────────────────────────────────────────────────────────────────────
# 7. Recomendador y siguiente mejor acción
# ──────────────────────────────────────────────────────────────────────────────
NIVEL_COL = {"Conectar": "incluido_conectar", "Crecer": "incluido_crecer", "Liderar": "incluido_liderar"}


def recomendador(d: dict, renov: dict, perfiles: dict, temas: dict, corte) -> dict:
    e = d["e360"]
    vig = e[(e["es_vigente"] == 1) & (e["en_crm"] == 1)][["empresa_id", "nivel_2027", "semaforo", "dias_a_vencer",
                                                          "participa_en_ventana", "n_comunidades"]]
    cat = d["catalogo"]
    usados = d["uso"][d["uso"]["fecha"] >= corte - pd.Timedelta(days=365)].groupby("empresa_id")["servicio_id"].agg(set)
    per = perfiles["perfil"].set_index("empresa_id")["perfil"]
    # Temas que más piden / asisten las empresas del mismo perfil
    at = d["asis"].merge(temas["eventos"], on="evento_id")
    at["perfil"] = at["empresa_id"].map(per)
    tema_perfil = at.dropna(subset=["perfil"]).groupby(["perfil", "tema"]).size().rename("n").reset_index()
    tema_emp = at.groupby("empresa_id")["tema"].agg(set)
    filas = []
    for _, r in vig.iterrows():
        recs = []
        col = NIVEL_COL.get(r["nivel_2027"])
        usa = usados.get(r["empresa_id"], set())
        if col:
            sin_usar = cat[(cat[col] == 1) & (cat["medible"] == 1) & ~cat["servicio_id"].isin(usa)]
            for _, s in sin_usar.head(2).iterrows():
                recs.append(("Beneficio por activar", s["servicio"],
                             f"Incluido en {r['nivel_2027']} y sin uso en 12 meses"))
        p = per.get(r["empresa_id"])
        if p is not None:
            vistos = tema_emp.get(r["empresa_id"], set())
            cand = tema_perfil[(tema_perfil["perfil"] == p) & ~tema_perfil["tema"].isin(vistos)
                               & (tema_perfil["tema"] != "General / tendencias")].nlargest(1, "n")
            for _, c in cand.iterrows():
                recs.append(("Tema que le puede interesar", c["tema"],
                             f"Es de los más vistos por empresas del perfil '{p}' y aún no ha ido"))
        if r["n_comunidades"] == 0 and r["nivel_2027"] in ("Crecer", "Liderar"):
            recs.append(("Comunidad", "Invitar a una comunidad", "Su nivel incluye comunidades y no está en ninguna"))
        for i, (t, rec, mot) in enumerate(recs[:4], 1):
            filas.append({"empresa_id": r["empresa_id"], "orden": i, "tipo": t, "recomendacion": rec, "motivo": mot})
    rec = pd.DataFrame(filas)
    # Siguiente mejor acción para la ejecutiva
    sc = renov["score"].set_index("empresa_id")
    acc = []
    for _, r in vig.iterrows():
        p = sc["p_renovar"].get(r["empresa_id"], np.nan)
        dias = r["dias_a_vencer"]
        part = bool(r["participa_en_ventana"])
        if pd.notna(dias) and dias <= 60 and p < 0.6:
            a, m = "Llamar esta semana con el extracto de valor", "Vence pronto y la probabilidad de renovar es baja"
        elif pd.notna(dias) and dias <= 60:
            a, m = "Enviar propuesta de renovación", "Vence en los próximos 60 días y la relación se ve sana"
        elif not part and p < 0.75:
            a, m = "Invitar a un evento del tema que más le interesa", "No ha participado en la ventana reciente"
        elif not part:
            a, m = "Recordarle beneficios incluidos sin usar", "No ha participado últimamente pero suele renovar"
        else:
            a, m = "Mantener: pedir testimonio o referido", "Participa y tiene buena probabilidad de renovar"
        acc.append({"empresa_id": r["empresa_id"], "accion": a, "motivo": m})
    ficha("recomendador", "Recomendaciones y siguiente mejor acción", "Ficha 360°, extracto de valor",
          "Decir a cada afiliada qué beneficio activar y qué tema le puede servir, y a la ejecutiva qué hacer",
          "Contenido: beneficios del nivel sin usar + temas más vistos por su perfil que aún no ha visto; "
          "acción por reglas sobre vencimiento, participación y probabilidad de renovar",
          f"{len(vig)} afiliadas vigentes", len(vig), "Empresas con al menos una recomendación",
          rec["empresa_id"].nunique() / max(len(vig), 1), "—",
          "Aún no se mide si las recomendaciones funcionan: para eso hay que registrar si la empresa usó lo "
          "recomendado (la plantilla de uso de beneficios lo permite).")
    return {"rec": rec, "accion": pd.DataFrame(acc)}


# ──────────────────────────────────────────────────────────────────────────────
# 8. Eventos (base del simulador)
# ──────────────────────────────────────────────────────────────────────────────
def base_eventos(d: dict, temas: dict) -> pd.DataFrame:
    ev = d["eventos"].merge(temas["eventos"], on="evento_id")
    a = d["asis"]
    g = a.groupby("evento_id")
    ev["pct_afiliados"] = ev["evento_id"].map(g["empresa_afiliada_vigente"].mean() * 100)
    ev["pct_con_costo"] = ev["evento_id"].map(a.assign(c=(a["costo"] == "Con costo").astype(float))
                                              .groupby("evento_id")["c"].mean())
    cargos = pd.crosstab(a["evento_id"], a["nivel_cargo"], normalize="index") * 100
    for c in cargos.columns:
        ev["cargo__" + c] = ev["evento_id"].map(cargos[c])
    s = d["enc"].dropna(subset=["evento_id"]).groupby("evento_id").agg(
        satisfaccion=("satisfaccion_prom", "mean"), respuestas=("encuesta_id", "size"),
        nps=("nps_puntaje", lambda x: 100 * ((x >= 9).mean() - (x <= 6).mean()) if x.notna().any() else np.nan))
    ev = ev.merge(s, left_on="evento_id", right_index=True, how="left")
    ev["mes"] = ev["fecha"].dt.month
    ev["dia_semana"] = ev["fecha"].dt.dayofweek
    return ev


def modelo_eventos(ev: pd.DataFrame) -> pd.DataFrame:
    b = ev[ev["inscritos"] > 0].copy()
    filas = []
    for _, r in b.iterrows():
        q = r.to_dict()
        p = sim.predecir(b, q, excluir=r["evento_id"])
        base = b[(b["evento_id"] != r["evento_id"]) & (b["modalidad"] == r["modalidad"])]["inscritos"].median()
        filas.append({"evento_id": r["evento_id"], "real": r["inscritos"], "estimado": round(p["inscritos"], 1),
                      "linea_base": base, "residuo_log": np.log1p(r["inscritos"]) - np.log1p(p["inscritos"])})
    bt = pd.DataFrame(filas)
    mae = (bt["real"] - bt["estimado"]).abs().median()
    mae_b = (bt["real"] - bt["linea_base"]).abs().median()
    ape = ((bt["real"] - bt["estimado"]).abs() / bt["real"]).median()
    res = bt["residuo_log"].values
    lo, hi = np.percentile(res, [10, 90])
    cob = ((np.log1p(bt["real"]) >= np.log1p(bt["estimado"]) + lo) &
           (np.log1p(bt["real"]) <= np.log1p(bt["estimado"]) + hi)).mean()
    ficha("eventos", "Simulador de inscritos por evento", "Planeación de eventos",
          "Estimar inscritos, % de afiliados, cargos y satisfacción de un evento antes de hacerlo",
          f"{sim.K} eventos más parecidos (modalidad, línea, tema, experiencia, costo, mes y día), "
          "promedio ponderado en escala logarítmica; rango a partir de los errores dejando un evento fuera",
          f"{len(b)} eventos de 2026 con inscritos", len(b), "Error absoluto mediano (inscritos)", mae,
          f"Usar la mediana de su modalidad: {mae_b:.0f}. Error relativo mediano del modelo: {ape:.0%}. "
          f"El rango de 80 % contuvo el valor real en {cob:.0%} de los eventos.",
          "Con 33 eventos el rango es amplio a propósito: los eventos grandes (Semana del Talento, webinars de "
          "salario mínimo) son difíciles de anticipar. El rango se vuelve más útil con cada evento que se "
          "registre. No hay datos de ciudad ni de precio exacto por evento.",
          extra={"error_rel_mediano": float(ape), "cobertura_80": float(cob), "mae_base": float(mae_b)})
    return bt


# ──────────────────────────────────────────────────────────────────────────────
# 9. Series de tiempo: SARIMA de altas, proyección de vigentes, ARIMA con compuerta
# ──────────────────────────────────────────────────────────────────────────────
def _serie_altas(d: dict, corte) -> pd.Series:
    e = d["emp"]
    e = e[e["origen"] == "CRM"]
    fin = (corte.to_period("M") - 1)   # el mes de corte está incompleto
    s = e["fecha_afiliacion"].dropna().dt.to_period("M").value_counts()
    idx = pd.period_range("2019-01", fin, freq="M")
    return s.reindex(idx, fill_value=0).astype(float)


def _ajustar_sarima(y: pd.Series):
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    mejor = None
    for p in (0, 1):
        for dd in (0, 1):
            for q in (0, 1):
                for P in (0, 1):
                    for Q in (0, 1):
                        try:
                            m = SARIMAX(y, order=(p, dd, q), seasonal_order=(P, 0, Q, 12),
                                        trend="c" if dd == 0 else "n",
                                        enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
                        except Exception:  # noqa: BLE001
                            continue
                        if np.isfinite(m.aic) and (mejor is None or m.aic < mejor[0]):
                            mejor = (m.aic, (p, dd, q), (P, 0, Q, 12))
    return mejor


def modelo_altas(d: dict, corte) -> dict:
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    y = _serie_altas(d, corte)
    y.index = y.index.to_timestamp()
    # Prueba: entrenar sin los últimos 12 meses y comparar contra dos líneas base
    tr, te = y.iloc[:-12], y.iloc[-12:]
    aic, orden, est = _ajustar_sarima(tr)
    m_tr = SARIMAX(tr, order=orden, seasonal_order=est, trend="c" if orden[1] == 0 else "n",
                   enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
    f_te = m_tr.get_forecast(12).predicted_mean.clip(lower=0)
    mae = (te - f_te.values).abs().mean()
    mae_est = (te - tr.iloc[-12:].values).abs().mean()           # mismo mes del año anterior
    mae_media = (te - tr.iloc[-12:].mean()).abs().mean()          # promedio de los últimos 12 meses
    # Modelo final con toda la serie
    aic, orden, est = _ajustar_sarima(y)
    m = SARIMAX(y, order=orden, seasonal_order=est, trend="c" if orden[1] == 0 else "n",
                enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
    h = 14   # hasta dic-2027
    fc = m.get_forecast(h)
    media = fc.predicted_mean.clip(lower=0)
    ci80, ci95 = fc.conf_int(alpha=0.2).clip(lower=0), fc.conf_int(alpha=0.05).clip(lower=0)
    ajuste = m.fittedvalues.clip(lower=0)
    real = pd.DataFrame({"serie": "altas", "mes": y.index, "real": y.values, "pronostico": ajuste.values,
                         "tipo": "historia"})
    pron = pd.DataFrame({"serie": "altas", "mes": media.index, "real": np.nan, "pronostico": media.values,
                         "li80": ci80.iloc[:, 0].values, "ls80": ci80.iloc[:, 1].values,
                         "li95": ci95.iloc[:, 0].values, "ls95": ci95.iloc[:, 1].values, "tipo": "pronostico"})
    gana = mae < min(mae_est, mae_media)
    ficha("altas", "Pronóstico de altas mensuales (SARIMA)", "Base de afiliados, Dashboard",
          "Anticipar cuántas empresas nuevas se afilian cada mes hasta dic-2027",
          f"SARIMA{orden}×{est[:3]}₁₂ elegido por AIC entre 32 combinaciones; rangos de 80 % y 95 %",
          f"Altas mensuales del CRM ene-2019 a {y.index[-1]:%b-%Y} ({len(y)} meses)", len(y),
          "Error absoluto medio en los últimos 12 meses (altas/mes)", mae,
          f"Mismo mes del año anterior: {mae_est:.1f}. Promedio de los últimos 12 meses: {mae_media:.1f}. "
          + ("El SARIMA gana a ambas líneas base." if gana else
             "El SARIMA NO gana a todas las líneas base: úsalo como referencia, no como meta."),
          "Las altas son pocas por mes (≈5-10), así que el rango es ancho. Solo cuenta empresas que siguen en el "
          "CRM (las que se borraron no aparecen). El mes de corte se excluye por estar incompleto.",
          extra={"aic": aic, "orden": orden, "estacional": est, "mae_media": mae_media, "mae_estacional": mae_est,
                 "gana_linea_base": bool(gana)})
    return {"serie": pd.concat([real, pron], ignore_index=True), "media": media, "ci80": ci80}


def proyeccion_vigentes(d: dict, renov: dict, altas: dict, corte, n_sim=2000) -> pd.DataFrame:
    rng = np.random.default_rng(SEMILLA)
    e = d["e360"]
    vig = e[(e["es_vigente"] == 1) & (e["en_crm"] == 1)][["empresa_id", "fecha_expiracion"]].merge(
        renov["score"][["empresa_id", "p_renovar"]], on="empresa_id", how="left")
    vig["p_renovar"] = vig["p_renovar"].fillna(renov["score"]["p_renovar"].mean())
    meses = pd.period_range(corte.to_period("M"), "2027-12", freq="M")
    venc = vig["fecha_expiracion"].dt.to_period("M")
    venc = venc.where(venc >= meses[0], meses[0]).fillna(pd.Period("2099-12", "M"))   # vencidas: se deciden ya
    media = altas["media"]
    sd = ((altas["ci80"].iloc[:, 1] - altas["ci80"].iloc[:, 0]) / (2 * 1.2816)).clip(lower=0.5)
    alt_mu = {pd.Timestamp(p).to_period("M"): (media.iloc[i], sd.iloc[i]) for i, p in enumerate(media.index)}
    tray = np.zeros((n_sim, len(meses)))
    p = vig["p_renovar"].values
    for s in range(n_sim):
        vivo = np.ones(len(vig), dtype=bool)
        renueva = rng.random(len(vig)) < p
        total_altas = 0
        for j, mes in enumerate(meses):
            vence = (venc == mes).values
            vivo &= ~(vence & ~renueva)
            mu, sg = alt_mu.get(mes, (0, 0))
            if mes > meses[0]:
                total_altas += max(0, round(rng.normal(mu, sg)))
            tray[s, j] = vivo.sum() + total_altas
    out = pd.DataFrame({"serie": "vigentes", "mes": [m.to_timestamp() for m in meses],
                        "pronostico": np.median(tray, 0), "li80": np.percentile(tray, 10, 0),
                        "ls80": np.percentile(tray, 90, 0), "li95": np.percentile(tray, 2.5, 0),
                        "ls95": np.percentile(tray, 97.5, 0), "tipo": "pronostico"})
    out.loc[0, ["pronostico", "li80", "ls80", "li95", "ls95"]] = len(vig)
    # Renovación esperada de lo que vence entre hoy y dic-2026 y en 2027
    v26 = vig[vig["fecha_expiracion"] <= pd.Timestamp("2026-12-31")]
    v27 = vig[(vig["fecha_expiracion"] > pd.Timestamp("2026-12-31")) & (vig["fecha_expiracion"] <= pd.Timestamp("2027-12-31"))]
    ficha("vigentes", "Proyección de afiliadas vigentes a dic-2027", "Base de afiliados, Dashboard",
          "Ver hacia dónde va la cartera si se mantienen las renovaciones y las altas esperadas",
          f"Simulación de {n_sim} escenarios: cada vigente renueva o no en su mes de vencimiento según su "
          "probabilidad de renovar, y se suman las altas del SARIMA con su incertidumbre",
          f"{len(vig)} afiliadas vigentes al corte", len(vig), "Vigentes esperadas a dic-2027 (mediana)",
          out["pronostico"].iloc[-1],
          f"Rango de 80 %: {out['li80'].iloc[-1]:.0f} a {out['ls80'].iloc[-1]:.0f}.",
          "Supone que las empresas que renuevan en 2027 no vuelven a vencer antes de dic-2027 y que las altas "
          "nuevas no se cancelan dentro del periodo. Hereda las limitaciones del modelo de renovación.",
          extra={"renov_esperada_2026": float(v26["p_renovar"].mean()) if len(v26) else None,
                 "vencen_2026": len(v26), "renov_esperada_2027": float(v27["p_renovar"].mean()) if len(v27) else None,
                 "vencen_2027": len(v27)})
    return out


def arima_con_compuerta(d: dict, corte) -> pd.DataFrame:
    """Inscripciones y retiros mensuales: solo se modelan si hay 24 meses de historia."""
    from statsmodels.tsa.arima.model import ARIMA
    fin = corte.to_period("M") - 1
    a = d["asis"]["fecha"].dt.to_period("M").value_counts()
    ins = a.reindex(pd.period_range(a.index.min(), fin, freq="M"), fill_value=0)
    mov = d["mov"].copy()
    mov["mes"] = pd.to_datetime(mov["mes"]).dt.to_period("M")
    ret = mov.set_index("mes")["retiros"].astype(float)
    ret = ret[ret.index <= fin]
    filas = []
    for nombre, serie, etq in [("arima_inscripciones", ins, "Inscripciones mensuales a eventos"),
                               ("arima_retiros", ret, "Retiros mensuales (vencimientos no renovados)")]:
        n = len(serie)
        if n >= MESES_MIN_ARIMA:
            m = ARIMA(serie.astype(float).values, order=(1, 0, 1)).fit()
            fc = m.get_forecast(12)
            ci = fc.conf_int(alpha=0.2)
            idx = pd.period_range(fin + 1, periods=12, freq="M")
            filas.append(pd.DataFrame({"serie": nombre.removeprefix("arima_"), "mes": idx.to_timestamp(),
                                       "pronostico": fc.predicted_mean.clip(min=0), "li80": ci[:, 0].clip(min=0),
                                       "ls80": ci[:, 1], "tipo": "pronostico"}))
            estado = "Activo"
        else:
            estado = f"En espera: hay {n} meses y se necesitan {MESES_MIN_ARIMA}"
        hist = pd.DataFrame({"serie": nombre.removeprefix("arima_"), "mes": serie.index.to_timestamp(),
                             "real": serie.values.astype(float), "tipo": "historia"})
        filas.append(hist)
        ficha(nombre, f"ARIMA de {etq.lower()}", "Base de afiliados, Experiencias",
              f"Pronosticar {etq.lower()}", "ARIMA(1,0,1); se activa solo con 24 meses o más de historia",
              f"{etq}: {n} meses", n, "Meses disponibles", n, f"Mínimo requerido: {MESES_MIN_ARIMA}",
              "Con menos de dos años no se puede separar la estacionalidad del ruido; el modelo se activa solo "
              "cuando llegue suficiente historia.", estado=estado)
    return pd.concat(filas, ignore_index=True)


# ──────────────────────────────────────────────────────────────────────────────
# 10. Gráficos de control
# ──────────────────────────────────────────────────────────────────────────────
def graficos_control(d: dict) -> pd.DataFrame:
    enc = d["enc"]
    filas = []
    s = enc.dropna(subset=["evento_id", "satisfaccion_prom"])
    centro, sd = s["satisfaccion_prom"].mean(), s["satisfaccion_prom"].std()
    ev = d["eventos"].set_index("evento_id")
    for eid, g in s.groupby("evento_id"):
        n = len(g)
        if n < 5:
            continue
        lim = 3 * sd / np.sqrt(n)
        v = g["satisfaccion_prom"].mean()
        filas.append({"serie": "satisfaccion_evento", "periodo": ev.loc[eid, "fecha"], "etiqueta": ev.loc[eid, "nombre"],
                      "valor": v, "n": n, "centro": centro, "lci": centro - lim, "lcs": min(5, centro + lim),
                      "fuera": "Bajo el límite" if v < centro - lim else ("Sobre el límite" if v > centro + lim else "")})
    x = enc.dropna(subset=["nps_puntaje", "fecha_respuesta"]).copy()
    x["mes"] = x["fecha_respuesta"].dt.to_period("M").dt.to_timestamp()
    x["pro"] = (x["nps_puntaje"] >= 9).astype(float)
    x["det"] = (x["nps_puntaje"] <= 6).astype(float)
    pp, pd_ = x["pro"].mean(), x["det"].mean()
    c = 100 * (pp - pd_)
    var1 = pp + pd_ - (pp - pd_) ** 2
    for mes, g in x.groupby("mes"):
        n = len(g)
        if n < 5:
            continue
        lim = 300 * np.sqrt(var1 / n)
        v = 100 * (g["pro"].mean() - g["det"].mean())
        filas.append({"serie": "nps_mensual", "periodo": mes, "etiqueta": mes.strftime("%Y-%m"), "valor": v, "n": n,
                      "centro": c, "lci": max(-100, c - lim), "lcs": min(100, c + lim),
                      "fuera": "Bajo el límite" if v < c - lim else ("Sobre el límite" if v > c + lim else "")})
    out = pd.DataFrame(filas)
    ficha("control", "Gráficos de control de satisfacción y NPS", "Experiencias y NPS",
          "Distinguir un evento o mes realmente malo de la variación normal",
          "Límites a ±3 errores estándar alrededor del promedio histórico; el ancho depende de cuántas "
          "respuestas tuvo cada punto",
          f"{len(s)} encuestas con evento y {len(x)} con NPS", len(s), "Puntos fuera de control",
          (out["fuera"] != "").sum() if len(out) else 0, "—",
          "Solo se grafican eventos o meses con 5 respuestas o más. Fuera de control no es culpa: es una señal "
          "para revisar qué pasó.")
    return out


# ──────────────────────────────────────────────────────────────────────────────
def entrenar(fecha_corte=None) -> dict:
    t0 = datetime.now()
    FICHAS.clear()
    conn = conectar()
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {ESQUEMA}")
    if fecha_corte is None:
        fc = leer(conn, "SELECT fecha FROM actho.config_parametro WHERE clave = 'fecha_corte'")
        fecha_corte = fc.iloc[0, 0] if len(fc) else date.today()
    corte = pd.Timestamp(str(fecha_corte))
    d = cargar(conn)

    renov = modelo_renovacion(d, corte)
    perf = modelo_perfiles(d, corte)
    prop = modelo_propension(d, corte)
    temas = modelo_temas(d)
    inter = interes_personas(d, temas)
    ident = modelo_identidad(d)
    rec = recomendador(d, renov, perf, temas, corte)
    ev = base_eventos(d, temas)
    bt = modelo_eventos(ev)
    altas = modelo_altas(d, corte)
    vig = proyeccion_vigentes(d, renov, altas, corte)
    arimas = arima_con_compuerta(d, corte)
    ctrl = graficos_control(d)

    tablas = {
        "renovacion": renov["score"], "renovacion_factor": renov["factores"], "renovacion_coef": renov["coef"],
        "perfil": perf["perfil"], "perfil_resumen": perf["resumen"], "empresa_parecida": perf["parecidas"],
        "propension": prop, "tema_texto": temas["textos"].drop(columns=["fecha_respuesta"]),
        "tema_evento": temas["eventos"], "tema_demanda": temas["demanda"], "interes_persona": inter,
        "identidad": ident, "recomendacion": rec["rec"], "accion": rec["accion"],
        "evento_base": ev, "evento_backtest": bt,
        "pronostico": pd.concat([altas["serie"], vig, arimas], ignore_index=True),
        "control": ctrl,
    }
    fichas = pd.DataFrame(FICHAS)
    fichas["entrenado"] = datetime.now().isoformat(timespec="seconds")
    fichas["fecha_corte"] = str(corte.date())
    tablas["modelo"] = fichas
    for nombre, df in tablas.items():
        escribir(conn, nombre, df)
    conn.execute("""CREATE SCHEMA IF NOT EXISTS historial;
        CREATE TABLE IF NOT EXISTS historial.plan_evento (
            plan_id serial PRIMARY KEY, creado timestamp DEFAULT now(), creado_por text,
            nombre text NOT NULL, fecha date, modalidad text, linea_2027 text, experiencia text, tema text,
            costo text, cupo integer, estimado numeric, li80 numeric, ls80 numeric, pct_afiliados numeric,
            satisfaccion numeric, parametros jsonb, evento_id_real integer, notas text)""")
    seg = (datetime.now() - t0).total_seconds()
    return {"fecha_corte": str(corte.date()), "segundos": round(seg, 1),
            "modelos": fichas[["modelo", "metrica", "valor", "estado"]].to_dict("records")}


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    arg = sys.argv[1:]
    fc = arg[arg.index("--fecha-corte") + 1] if "--fecha-corte" in arg else None
    r = entrenar(fc)
    print(f"Modelos entrenados con corte {r['fecha_corte']} en {r['segundos']} s")
    for m in r["modelos"]:
        print(f"  {m['modelo']:<22} {m['metrica']:<55} {m['valor']!s:<8} {m['estado']}")
