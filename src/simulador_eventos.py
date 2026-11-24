"""Simulador de eventos: estima inscritos, % de afiliados, cargos y satisfacción de un evento
a partir de los eventos parecidos que ACTHO ya hizo (k vecinos más cercanos).

Lo usan `src/modelos_ia.py` (para medir el error dejando un evento fuera) y la página
Planeación de eventos del tablero. Solo depende de numpy y pandas.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Cuánto pesa cada diferencia entre el evento simulado y uno histórico.
PESOS = {"modalidad": 3.0, "linea_2027": 2.0, "tema": 2.0, "experiencia": 1.0,
         "costo": 1.5, "mes": 0.5, "dia": 0.3}
K = 5
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def distancias(base: pd.DataFrame, q: dict) -> pd.Series:
    d = pd.Series(0.0, index=base.index)
    for col in ["modalidad", "linea_2027", "tema", "experiencia"]:
        if q.get(col) is not None:
            d += PESOS[col] * (base[col].astype(str) != str(q[col])).astype(float)
    if q.get("pct_con_costo") is not None:
        d += PESOS["costo"] * (base["pct_con_costo"].fillna(0) - float(q["pct_con_costo"])).abs()
    if q.get("mes") is not None:
        dm = (base["mes"] - int(q["mes"])).abs()
        d += PESOS["mes"] * np.minimum(dm, 12 - dm) / 6
    if q.get("dia_semana") is not None:
        d += PESOS["dia"] * (base["dia_semana"] != int(q["dia_semana"])).astype(float)
    return d


def vecinos(base: pd.DataFrame, q: dict, k: int = K, excluir=None) -> pd.DataFrame:
    b = base if excluir is None else base[base["evento_id"] != excluir]
    b = b[b["inscritos"] > 0]
    d = distancias(b, q)
    v = b.assign(distancia=d).nsmallest(k, "distancia").copy()
    v["peso"] = 1 / (v["distancia"] + 0.5)
    return v


def _prom(v: pd.DataFrame, col: str):
    x = v[[col, "peso"]].dropna()
    return float(np.average(x[col], weights=x["peso"])) if len(x) else None


def predecir(base: pd.DataFrame, q: dict, residuos=None, k: int = K, excluir=None) -> dict:
    """Devuelve la estimación central y, si se pasan los residuos (en escala log) de la
    validación dejando uno fuera, los rangos de 80 % y 95 %."""
    v = vecinos(base, q, k, excluir)
    centro = float(np.average(np.log1p(v["inscritos"]), weights=v["peso"]))
    r = {"inscritos": float(np.expm1(centro)), "vecinos": v}
    if residuos is not None and len(residuos) >= 5:
        res = np.asarray(residuos, dtype=float)
        for nivel, (a, b) in {"80": (10, 90), "95": (2.5, 97.5)}.items():
            r[f"li{nivel}"] = float(max(0, np.expm1(centro + np.percentile(res, a))))
            r[f"ls{nivel}"] = float(np.expm1(centro + np.percentile(res, b)))
    r["pct_afiliados"] = _prom(v, "pct_afiliados")
    r["satisfaccion"] = _prom(v, "satisfaccion")
    r["empresas"] = _prom(v, "empresas_distintas")
    cargos = [c for c in base.columns if c.startswith("cargo__")]
    r["cargos"] = {c.removeprefix("cargo__"): _prom(v, c) for c in cargos}
    return r
