-- ════════════════════════════════════════════════════════════════════════════
-- Vistas del dashboard principal · Reto ACTHO
-- Se ejecuta automáticamente al final de src/cargar_postgres.py.
-- Todas las vistas usan la fecha de corte y los umbrales de actho.config_parametro.
-- Para cambiar un umbral de forma permanente, edítalo aquí (el esquema se recrea en cada carga).
-- ════════════════════════════════════════════════════════════════════════════

-- 1. Parámetros ---------------------------------------------------------------
CREATE TABLE actho.config_parametro (
    clave       text PRIMARY KEY,
    valor       numeric,
    fecha       date,
    descripcion text
);
INSERT INTO actho.config_parametro (clave, valor, fecha, descripcion) VALUES
 ('fecha_corte',                   NULL, NULL, 'Fecha de referencia del tablero (la fija cargar_postgres.py; vacía = hoy)'),
 ('ventana_participacion_dias',    90,   NULL, 'Días hacia atrás para considerar que un afiliado participa (último trimestre)'),
 ('ventana_satisfaccion_dias',     365,  NULL, 'Días hacia atrás de encuestas para la satisfacción por empresa'),
 ('ventana_detractor_dias',        180,  NULL, 'Días hacia atrás para considerar un detractor como reciente'),
 ('umbral_satisfaccion_baja',      4.0,  NULL, 'Satisfacción promedio (1-5) por debajo de la cual se considera baja'),
 ('umbral_satisfaccion_detractor', 3.0,  NULL, 'Calificación 1-5 que cuenta como detractor (encuestas sin NPS)'),
 ('pts_vencida',                   3,    NULL, 'Puntos de riesgo: membresía vencida o en periodo de gracia'),
 ('pts_vence_30',                  3,    NULL, 'Puntos de riesgo: vence en 0-30 días'),
 ('pts_vence_60',                  2,    NULL, 'Puntos de riesgo: vence en 31-60 días'),
 ('pts_vence_90',                  1,    NULL, 'Puntos de riesgo: vence en 61-90 días'),
 ('pts_sin_participacion',         2,    NULL, 'Puntos de riesgo: sin asistencias en la ventana de participación'),
 ('pts_sin_participacion_12m',     1,    NULL, 'Puntos adicionales: tampoco asistió en los últimos 12 meses'),
 ('pts_satisfaccion_baja',         2,    NULL, 'Puntos de riesgo: satisfacción promedio baja'),
 ('pts_detractor',                 3,    NULL, 'Puntos de riesgo: detractor reciente (NPS 0-6 o calificación baja)'),
 ('umbral_rojo',                   5,    NULL, 'Puntaje desde el cual el semáforo es rojo'),
 ('umbral_amarillo',               3,    NULL, 'Puntaje desde el cual el semáforo es amarillo'),
 ('dias_nuevo_afiliado',           90,   NULL, 'Antigüedad máxima para considerar a un afiliado como nuevo');

CREATE VIEW actho.v_parametros AS
SELECT
    coalesce(max(fecha) FILTER (WHERE clave = 'fecha_corte'), current_date)        AS fecha_corte,
    max(valor) FILTER (WHERE clave = 'ventana_participacion_dias')::int             AS ventana_participacion_dias,
    max(valor) FILTER (WHERE clave = 'ventana_satisfaccion_dias')::int              AS ventana_satisfaccion_dias,
    max(valor) FILTER (WHERE clave = 'ventana_detractor_dias')::int                 AS ventana_detractor_dias,
    max(valor) FILTER (WHERE clave = 'umbral_satisfaccion_baja')                    AS umbral_satisfaccion_baja,
    max(valor) FILTER (WHERE clave = 'umbral_satisfaccion_detractor')               AS umbral_satisfaccion_detractor,
    max(valor) FILTER (WHERE clave = 'pts_vencida')::int                            AS pts_vencida,
    max(valor) FILTER (WHERE clave = 'pts_vence_30')::int                           AS pts_vence_30,
    max(valor) FILTER (WHERE clave = 'pts_vence_60')::int                           AS pts_vence_60,
    max(valor) FILTER (WHERE clave = 'pts_vence_90')::int                           AS pts_vence_90,
    max(valor) FILTER (WHERE clave = 'pts_sin_participacion')::int                  AS pts_sin_participacion,
    max(valor) FILTER (WHERE clave = 'pts_sin_participacion_12m')::int              AS pts_sin_participacion_12m,
    max(valor) FILTER (WHERE clave = 'pts_satisfaccion_baja')::int                  AS pts_satisfaccion_baja,
    max(valor) FILTER (WHERE clave = 'pts_detractor')::int                          AS pts_detractor,
    max(valor) FILTER (WHERE clave = 'umbral_rojo')::int                            AS umbral_rojo,
    max(valor) FILTER (WHERE clave = 'umbral_amarillo')::int                        AS umbral_amarillo,
    max(valor) FILTER (WHERE clave = 'dias_nuevo_afiliado')::int                    AS dias_nuevo_afiliado
FROM actho.config_parametro;

-- 2. Detalle para el tablero (una fila por inscripción / respuesta) ------------
CREATE VIEW actho.v_asistencia_detalle AS
SELECT a.asistencia_id, a.evento_id, ev.nombre AS evento, ev.fecha AS fecha_evento,
       to_char(ev.fecha, 'YYYY-MM') AS anio_mes, ev.linea_2027, ev.experiencia, ev.modalidad,
       a.empresa_id, a.persona_id, a.nivel_cargo, a.costo, a.autoriza_datos,
       CASE WHEN a.empresa_afiliada_vigente = 1 THEN 'Afiliada' ELSE 'No afiliada' END AS condicion_empresa,
       e.nivel_2027, e.tipo_membresia, e.sector, e.ciudad, e.tamano_empresa, j.nombre AS ejecutiva
FROM actho.fact_asistencia a
JOIN actho.dim_evento ev USING (evento_id)
JOIN actho.dim_empresa e USING (empresa_id)
LEFT JOIN actho.dim_ejecutiva j ON j.ejecutiva_id = e.ejecutiva_id;

CREATE VIEW actho.v_encuesta_detalle AS
SELECT r.encuesta_id, r.origen_encuesta, r.modalidad, r.fecha_respuesta::date AS fecha_respuesta,
       to_char(r.fecha_respuesta, 'YYYY-MM') AS anio_mes, r.evento_id, ev.nombre AS evento, ev.linea_2027,
       r.empresa_id, r.persona_id, r.tipo_cruce, r.satisfaccion_prom, r.satisfaccion_general,
       r.calif_expositor, r.calif_contenido, r.calif_espacio, r.calif_convocatoria,
       r.nps_puntaje, r.nps_categoria,
       e.nivel_2027, e.sector, e.ciudad, j.nombre AS ejecutiva,
       CASE WHEN e.es_vigente = 1 THEN 'Afiliada' ELSE 'No afiliada / sin identificar' END AS condicion_empresa
FROM actho.fact_encuesta_evento r
LEFT JOIN actho.dim_evento ev USING (evento_id)
LEFT JOIN actho.dim_empresa e USING (empresa_id)
LEFT JOIN actho.dim_ejecutiva j ON j.ejecutiva_id = e.ejecutiva_id;

-- 3. Métricas por empresa -------------------------------------------------------
CREATE VIEW actho.v_empresa_actividad AS
SELECT a.empresa_id,
       count(*)                                                                    AS inscripciones_total,
       count(*) FILTER (WHERE ev.fecha >  p.fecha_corte - p.ventana_participacion_dias
                          AND ev.fecha <= p.fecha_corte)                           AS inscripciones_ventana,
       count(*) FILTER (WHERE ev.fecha >  p.fecha_corte - 365
                          AND ev.fecha <= p.fecha_corte)                           AS inscripciones_12m,
       count(DISTINCT a.evento_id)                                                 AS eventos_distintos,
       count(DISTINCT a.persona_id)                                                AS personas_distintas,
       count(DISTINCT a.nivel_cargo) FILTER (WHERE a.nivel_cargo <> 'Sin dato')    AS niveles_cargo_distintos,
       count(DISTINCT ev.linea_2027)                                               AS lineas_distintas,
       max(ev.fecha)                                                               AS ultima_asistencia
FROM actho.fact_asistencia a
JOIN actho.dim_evento ev USING (evento_id)
CROSS JOIN actho.v_parametros p
GROUP BY a.empresa_id;

CREATE VIEW actho.v_empresa_satisfaccion AS
SELECT r.empresa_id,
       count(*)                                                                    AS respuestas_ventana,
       round(avg(coalesce(r.satisfaccion_general, r.satisfaccion_prom)), 2)        AS satisfaccion_promedio,
       count(r.nps_puntaje)                                                        AS respuestas_nps,
       round(100.0 * (count(*) FILTER (WHERE r.nps_categoria = 'Promotor')
                    - count(*) FILTER (WHERE r.nps_categoria = 'Detractor'))
             / nullif(count(r.nps_puntaje), 0), 1)                                 AS nps,
       bool_or(r.fecha_respuesta::date > p.fecha_corte - p.ventana_detractor_dias
               AND (r.nps_categoria = 'Detractor'
                    OR coalesce(r.satisfaccion_general, r.satisfaccion_prom) <= p.umbral_satisfaccion_detractor))
                                                                                   AS detractor_reciente,
       bool_or(r.nps_categoria = 'Promotor')                                       AS tiene_promotor,
       max(r.fecha_respuesta)::date                                                AS ultima_respuesta
FROM actho.fact_encuesta_evento r
CROSS JOIN actho.v_parametros p
WHERE r.empresa_id IS NOT NULL
  AND r.fecha_respuesta::date >  p.fecha_corte - p.ventana_satisfaccion_dias
  AND r.fecha_respuesta::date <= p.fecha_corte
GROUP BY r.empresa_id;

-- 4. Empresa 360 + semáforo de riesgo (tabla principal del tablero) ------------
CREATE VIEW actho.v_empresa_360 AS
WITH base AS (
    SELECT e.*, j.nombre AS ejecutiva, p.*,
           (e.fecha_expiracion - p.fecha_corte)                         AS dias_vence,
           coalesce(a.inscripciones_total, 0)                           AS inscripciones_total,
           coalesce(a.inscripciones_ventana, 0)                         AS inscripciones_ventana,
           coalesce(a.inscripciones_12m, 0)                             AS inscripciones_12m,
           coalesce(a.eventos_distintos, 0)                             AS eventos_distintos,
           coalesce(a.personas_distintas, 0)                            AS personas_distintas,
           coalesce(a.lineas_distintas, 0)                              AS lineas_distintas,
           a.ultima_asistencia,
           s.respuestas_ventana, s.satisfaccion_promedio, s.nps,
           coalesce(s.detractor_reciente, false)                        AS detractor_reciente,
           coalesce(s.tiene_promotor, false)                            AS tiene_promotor
    FROM actho.dim_empresa e
    CROSS JOIN actho.v_parametros p
    LEFT JOIN actho.dim_ejecutiva j ON j.ejecutiva_id = e.ejecutiva_id
    LEFT JOIN actho.v_empresa_actividad a ON a.empresa_id = e.empresa_id
    LEFT JOIN actho.v_empresa_satisfaccion s ON s.empresa_id = e.empresa_id
), puntos AS (
    SELECT b.*,
           CASE WHEN b.es_vigente = 0 THEN 0
                WHEN b.dias_vence < 0 OR b.estado_membresia = 'Periodo de gracia' THEN b.pts_vencida
                WHEN b.dias_vence <= 30 THEN b.pts_vence_30
                WHEN b.dias_vence <= 60 THEN b.pts_vence_60
                WHEN b.dias_vence <= 90 THEN b.pts_vence_90
                ELSE 0 END                                                AS pts_vencimiento,
           CASE WHEN b.es_vigente = 0 OR b.inscripciones_ventana > 0 THEN 0
                ELSE b.pts_sin_participacion
                     + CASE WHEN b.inscripciones_12m = 0 THEN b.pts_sin_participacion_12m ELSE 0 END
                END                                                       AS pts_participacion,
           CASE WHEN b.es_vigente = 0 THEN 0
                WHEN b.detractor_reciente THEN b.pts_detractor
                WHEN b.satisfaccion_promedio < b.umbral_satisfaccion_baja THEN b.pts_satisfaccion_baja
                ELSE 0 END                                                AS pts_satisfaccion
    FROM base b
)
SELECT empresa_id, en_crm, origen, estado_membresia, es_activo, es_vigente,
       nivel_2027, tipo_membresia, categoria_membresia, sector, subsector, tamano_empresa, rango_empleados,
       ciudad, departamento, region, ejecutiva_id, ejecutiva,
       fecha_afiliacion, fecha_expiracion,
       CASE WHEN es_vigente = 1 THEN dias_vence END                       AS dias_a_vencer,
       CASE WHEN es_vigente = 0 THEN 'No aplica'
            WHEN fecha_expiracion IS NULL THEN 'Sin fecha'
            WHEN dias_vence < 0 THEN 'Vencida'
            WHEN dias_vence <= 30 THEN '0-30 días'
            WHEN dias_vence <= 60 THEN '31-60 días'
            WHEN dias_vence <= 90 THEN '61-90 días'
            ELSE 'Más de 90 días' END                                     AS rango_vencimiento,
       (es_vigente = 1 AND fecha_afiliacion > fecha_corte - dias_nuevo_afiliado) AS es_nuevo_afiliado,
       inscripciones_total, inscripciones_ventana, inscripciones_12m, eventos_distintos,
       personas_distintas, lineas_distintas, ultima_asistencia,
       (inscripciones_ventana > 0)                                        AS participa_en_ventana,
       respuestas_ventana, satisfaccion_promedio, nps, detractor_reciente, tiene_promotor,
       n_comunidades, vinculado_comunidades,
       pts_vencimiento, pts_participacion, pts_satisfaccion,
       pts_vencimiento + pts_participacion + pts_satisfaccion             AS puntaje_riesgo,
       CASE WHEN es_vigente = 0 THEN 'No aplica'
            WHEN pts_vencimiento + pts_participacion + pts_satisfaccion >= umbral_rojo THEN 'Rojo'
            WHEN pts_vencimiento + pts_participacion + pts_satisfaccion >= umbral_amarillo THEN 'Amarillo'
            ELSE 'Verde' END                                              AS semaforo,
       nullif(concat_ws(' · ',
            CASE WHEN pts_vencimiento > 0 THEN
                 CASE WHEN dias_vence < 0 OR estado_membresia = 'Periodo de gracia' THEN 'Membresía vencida'
                      ELSE 'Vence en ' || dias_vence || ' días' END END,
            CASE WHEN pts_participacion > 0 THEN
                 CASE WHEN inscripciones_12m = 0 THEN 'Sin participación en 12 meses'
                      ELSE 'Sin participación en ' || ventana_participacion_dias || ' días' END END,
            CASE WHEN pts_satisfaccion > 0 THEN
                 CASE WHEN detractor_reciente THEN 'Detractor reciente'
                      ELSE 'Satisfacción baja (' || satisfaccion_promedio || ')' END END), '') AS motivos_riesgo,
       inconsistencia, fecha_corte
FROM puntos;

-- 5. Indicadores principales (una sola fila: tarjetas del panel) ---------------
CREATE VIEW actho.v_tasa_renovacion AS
-- Aproximación: Zoho sobrescribe la fecha de expiración al renovar, así que no hay historial.
--   Renovados    = vigentes afiliados hace más de un año (cumplieron al menos un ciclo).
--   No renovados = cancelados o expirados cuya expiración cayó en los últimos 12 meses.
SELECT p.fecha_corte,
       count(*) FILTER (WHERE e.es_vigente = 1 AND e.fecha_afiliacion <= p.fecha_corte - 365)   AS renovados,
       count(*) FILTER (WHERE e.estado_membresia IN ('Cancelado', 'Expirado', 'Inactivo')
                          AND e.fecha_expiracion >  p.fecha_corte - 365
                          AND e.fecha_expiracion <= p.fecha_corte)                              AS no_renovados,
       round(100.0 * count(*) FILTER (WHERE e.es_vigente = 1 AND e.fecha_afiliacion <= p.fecha_corte - 365)
             / nullif(count(*) FILTER (WHERE e.es_vigente = 1 AND e.fecha_afiliacion <= p.fecha_corte - 365)
                    + count(*) FILTER (WHERE e.estado_membresia IN ('Cancelado', 'Expirado', 'Inactivo')
                                         AND e.fecha_expiracion >  p.fecha_corte - 365
                                         AND e.fecha_expiracion <= p.fecha_corte), 0), 1)   AS tasa_renovacion_aprox,
       'Aproximada: el CRM no guarda el historial de renovaciones'::text                         AS nota
FROM actho.dim_empresa e
CROSS JOIN actho.v_parametros p
WHERE e.en_crm = 1
GROUP BY p.fecha_corte;

CREATE VIEW actho.v_kpi_principal AS
WITH e AS (SELECT * FROM actho.v_empresa_360),
     r AS (SELECT r.* FROM actho.fact_encuesta_evento r CROSS JOIN actho.v_parametros p
           WHERE r.fecha_respuesta::date >  p.fecha_corte - p.ventana_satisfaccion_dias
             AND r.fecha_respuesta::date <= p.fecha_corte),
     a AS (SELECT d.* FROM actho.v_asistencia_detalle d CROSS JOIN actho.v_parametros p
           WHERE d.fecha_evento > p.fecha_corte - 365 AND d.fecha_evento <= p.fecha_corte)
SELECT
    (SELECT fecha_corte FROM actho.v_parametros)                                     AS fecha_corte,
    (SELECT count(*) FROM e WHERE es_activo = 1)                                     AS afiliados_activos,
    (SELECT count(*) FROM e WHERE es_vigente = 1)                                    AS afiliados_vigentes,
    (SELECT count(*) FROM e WHERE es_nuevo_afiliado)                                 AS nuevos_afiliados,
    (SELECT count(*) FROM e WHERE es_vigente = 1 AND dias_a_vencer BETWEEN 0 AND 30) AS vencen_30_dias,
    (SELECT count(*) FROM e WHERE es_vigente = 1 AND dias_a_vencer BETWEEN 0 AND 60) AS vencen_60_dias,
    (SELECT count(*) FROM e WHERE es_vigente = 1 AND dias_a_vencer BETWEEN 0 AND 90) AS vencen_90_dias,
    (SELECT count(*) FROM e WHERE rango_vencimiento = 'Vencida')                     AS vencidas_sin_renovar,
    (SELECT tasa_renovacion_aprox FROM actho.v_tasa_renovacion)                      AS tasa_renovacion_aprox,
    (SELECT round(100.0 * count(*) FILTER (WHERE participa_en_ventana) / nullif(count(*), 0), 1)
       FROM e WHERE es_vigente = 1)                                                  AS pct_afiliados_participan,
    (SELECT count(*) FROM e WHERE es_vigente = 1 AND NOT participa_en_ventana)       AS afiliados_sin_participar,
    (SELECT count(*) FROM e WHERE semaforo = 'Rojo')                                 AS riesgo_rojo,
    (SELECT count(*) FROM e WHERE semaforo = 'Amarillo')                             AS riesgo_amarillo,
    (SELECT count(*) FROM e WHERE semaforo = 'Verde')                                AS riesgo_verde,
    (SELECT count(*) FROM a)                                                         AS inscripciones_12m,
    (SELECT count(DISTINCT persona_id) FROM a)                                       AS personas_12m,
    (SELECT count(DISTINCT empresa_id) FROM a WHERE condicion_empresa = 'No afiliada') AS empresas_no_afiliadas_12m,
    (SELECT count(DISTINCT persona_id) FROM a WHERE condicion_empresa = 'No afiliada') AS personas_no_afiliadas_12m,
    (SELECT round(avg(coalesce(satisfaccion_general, satisfaccion_prom)), 2) FROM r) AS satisfaccion_promedio,
    (SELECT round(100.0 * (count(*) FILTER (WHERE nps_categoria = 'Promotor')
                         - count(*) FILTER (WHERE nps_categoria = 'Detractor'))
                  / nullif(count(nps_puntaje), 0), 1) FROM r)                        AS nps_eventos,
    (SELECT count(nps_puntaje) FROM r)                                               AS respuestas_nps,
    NULL::numeric                                                                    AS nps_actho_90_dias;  -- se llena cuando haya encuesta de 90 días

-- 6. Vistas de gráficos ---------------------------------------------------------
CREATE VIEW actho.v_movimiento_mensual AS
-- Altas por fecha de afiliación y vencimientos por fecha de expiración (datos del CRM).
WITH meses AS (
    SELECT date_trunc('month', m)::date AS mes
    FROM actho.v_parametros p,
         generate_series(date_trunc('month', p.fecha_corte) - interval '23 months',
                         date_trunc('month', p.fecha_corte) + interval '12 months', interval '1 month') m
)
SELECT to_char(m.mes, 'YYYY-MM') AS anio_mes, m.mes,
       count(*) FILTER (WHERE date_trunc('month', e.fecha_afiliacion) = m.mes)               AS altas,
       count(*) FILTER (WHERE date_trunc('month', e.fecha_expiracion) = m.mes)               AS vencimientos,
       count(*) FILTER (WHERE date_trunc('month', e.fecha_expiracion) = m.mes AND e.es_vigente = 1) AS vencimientos_vigentes,
       count(*) FILTER (WHERE date_trunc('month', e.fecha_expiracion) = m.mes
                          AND e.estado_membresia IN ('Cancelado', 'Expirado', 'Inactivo'))   AS retiros
FROM meses m
LEFT JOIN actho.dim_empresa e ON e.en_crm = 1
GROUP BY m.mes ORDER BY m.mes;

CREATE VIEW actho.v_afiliados_distribucion AS
SELECT nivel_2027, tipo_membresia, sector, tamano_empresa, ciudad, region, ejecutiva,
       count(*) FILTER (WHERE es_activo = 1)  AS activos,
       count(*) FILTER (WHERE es_vigente = 1) AS vigentes,
       count(*) FILTER (WHERE es_vigente = 1 AND participa_en_ventana) AS vigentes_que_participan
FROM actho.v_empresa_360
WHERE es_vigente = 1
GROUP BY nivel_2027, tipo_membresia, sector, tamano_empresa, ciudad, region, ejecutiva;

CREATE VIEW actho.v_vencimientos_proximos AS
SELECT empresa_id, ejecutiva, nivel_2027, tipo_membresia, sector, ciudad, estado_membresia,
       fecha_expiracion, dias_a_vencer, rango_vencimiento,
       inscripciones_12m, ultima_asistencia, satisfaccion_promedio, nps,
       puntaje_riesgo, semaforo, motivos_riesgo
FROM actho.v_empresa_360
WHERE es_vigente = 1 AND (dias_a_vencer <= 90 OR rango_vencimiento = 'Vencida')
ORDER BY puntaje_riesgo DESC, dias_a_vencer;

CREATE VIEW actho.v_cartera_ejecutiva AS
SELECT ejecutiva_id, ejecutiva,
       count(*)                                                        AS afiliados_vigentes,
       count(*) FILTER (WHERE dias_a_vencer BETWEEN 0 AND 30)          AS vencen_30_dias,
       count(*) FILTER (WHERE dias_a_vencer BETWEEN 0 AND 90)          AS vencen_90_dias,
       count(*) FILTER (WHERE rango_vencimiento = 'Vencida')           AS vencidas,
       count(*) FILTER (WHERE NOT participa_en_ventana)                AS sin_participar,
       round(100.0 * count(*) FILTER (WHERE participa_en_ventana) / nullif(count(*), 0), 1) AS pct_participan,
       round(avg(satisfaccion_promedio), 2)                            AS satisfaccion_promedio,
       count(*) FILTER (WHERE detractor_reciente)                      AS detractores_recientes,
       count(*) FILTER (WHERE semaforo = 'Rojo')                       AS riesgo_rojo,
       count(*) FILTER (WHERE semaforo = 'Amarillo')                   AS riesgo_amarillo,
       count(*) FILTER (WHERE semaforo = 'Verde')                      AS riesgo_verde
FROM actho.v_empresa_360
WHERE es_vigente = 1
GROUP BY ejecutiva_id, ejecutiva
ORDER BY riesgo_rojo DESC, afiliados_vigentes DESC;

CREATE VIEW actho.v_participacion_mensual AS
SELECT anio_mes, linea_2027, modalidad, condicion_empresa,
       count(*)                   AS inscripciones,
       count(DISTINCT persona_id) AS personas,
       count(DISTINCT empresa_id) AS empresas,
       count(DISTINCT evento_id)  AS eventos
FROM actho.v_asistencia_detalle
GROUP BY anio_mes, linea_2027, modalidad, condicion_empresa
ORDER BY anio_mes;

CREATE VIEW actho.v_participacion_nivel_cargo AS
SELECT nivel_cargo, linea_2027, condicion_empresa,
       count(*) AS inscripciones, count(DISTINCT persona_id) AS personas, count(DISTINCT empresa_id) AS empresas
FROM actho.v_asistencia_detalle
GROUP BY nivel_cargo, linea_2027, condicion_empresa;

CREATE VIEW actho.v_evento_resumen AS
SELECT ev.evento_id, ev.nombre AS evento, ev.fecha, to_char(ev.fecha, 'YYYY-MM') AS anio_mes,
       ev.linea_2027, ev.experiencia, ev.modalidad,
       coalesce(a.inscripciones, 0)          AS inscripciones,
       coalesce(a.empresas, 0)               AS empresas,
       coalesce(a.empresas_afiliadas, 0)     AS empresas_afiliadas,
       coalesce(a.empresas, 0) - coalesce(a.empresas_afiliadas, 0) AS empresas_no_afiliadas,
       round(100.0 * a.inscripciones_afiliadas / nullif(a.inscripciones, 0), 1) AS pct_inscripciones_afiliadas,
       coalesce(r.respuestas, 0)             AS respuestas_encuesta,
       r.satisfaccion_promedio, r.nps, r.respuestas_nps
FROM actho.dim_evento ev
LEFT JOIN (SELECT evento_id, count(*) AS inscripciones, count(DISTINCT empresa_id) AS empresas,
                  count(DISTINCT empresa_id) FILTER (WHERE empresa_afiliada_vigente = 1) AS empresas_afiliadas,
                  count(*) FILTER (WHERE empresa_afiliada_vigente = 1) AS inscripciones_afiliadas
           FROM actho.fact_asistencia GROUP BY evento_id) a USING (evento_id)
LEFT JOIN (SELECT evento_id, count(*) AS respuestas,
                  round(avg(coalesce(satisfaccion_general, satisfaccion_prom)), 2) AS satisfaccion_promedio,
                  count(nps_puntaje) AS respuestas_nps,
                  round(100.0 * (count(*) FILTER (WHERE nps_categoria = 'Promotor')
                               - count(*) FILTER (WHERE nps_categoria = 'Detractor'))
                        / nullif(count(nps_puntaje), 0), 1) AS nps
           FROM actho.fact_encuesta_evento WHERE evento_id IS NOT NULL GROUP BY evento_id) r USING (evento_id)
ORDER BY ev.fecha;

CREATE VIEW actho.v_satisfaccion_mensual AS
SELECT anio_mes, origen_encuesta, modalidad,
       count(*)                                                           AS respuestas,
       round(avg(coalesce(satisfaccion_general, satisfaccion_prom)), 2)   AS satisfaccion_promedio,
       round(avg(calif_expositor), 2)  AS calif_expositor,
       round(avg(calif_contenido), 2)  AS calif_contenido,
       round(avg(calif_espacio), 2)    AS calif_espacio,
       count(nps_puntaje)              AS respuestas_nps,
       round(100.0 * (count(*) FILTER (WHERE nps_categoria = 'Promotor')
                    - count(*) FILTER (WHERE nps_categoria = 'Detractor'))
             / nullif(count(nps_puntaje), 0), 1) AS nps
FROM actho.v_encuesta_detalle
GROUP BY anio_mes, origen_encuesta, modalidad
ORDER BY anio_mes;

CREATE VIEW actho.v_temas_solicitados AS
SELECT tema, count(*) AS menciones, count(DISTINCT encuesta_id) AS respuestas
FROM actho.fact_encuesta_temas
GROUP BY tema ORDER BY menciones DESC;

CREATE VIEW actho.v_relacion_participacion_renovacion AS
-- Vista integrada: ¿los que participan más renuevan más y están más satisfechos?
SELECT CASE WHEN inscripciones_12m = 0 THEN '0 asistencias'
            WHEN inscripciones_12m <= 2 THEN '1-2 asistencias'
            WHEN inscripciones_12m <= 5 THEN '3-5 asistencias'
            ELSE '6 o más' END                                   AS nivel_participacion_12m,
       count(*)                                                  AS empresas_crm,
       count(*) FILTER (WHERE es_vigente = 1)                    AS vigentes,
       round(100.0 * count(*) FILTER (WHERE es_vigente = 1) / nullif(count(*), 0), 1) AS pct_vigentes,
       round(avg(satisfaccion_promedio), 2)                      AS satisfaccion_promedio
FROM actho.v_empresa_360
WHERE en_crm = 1 AND estado_membresia <> 'Sin estado'
GROUP BY 1 ORDER BY min(inscripciones_12m);

-- 7. Asistentes no afiliados (potenciales afiliados) ----------------------------
CREATE VIEW actho.v_no_afiliados_potenciales AS
SELECT empresa_id, origen, estado_membresia, inscripciones_total, inscripciones_12m,
       eventos_distintos, personas_distintas, lineas_distintas, ultima_asistencia,
       satisfaccion_promedio, tiene_promotor
FROM actho.v_empresa_360
WHERE es_vigente = 0 AND inscripciones_total > 0
ORDER BY inscripciones_12m DESC, personas_distintas DESC;

-- 8. Segmentos para comunicaciones (exportables; solo personas que autorizaron datos)
CREATE VIEW actho.v_segmentos_comunicacion AS
WITH personas AS (
    SELECT p.persona_id, p.nivel_cargo, p.autoriza_datos, e.*
    FROM actho.dim_persona p
    JOIN actho.v_empresa_360 e USING (empresa_id)
), resp AS (
    SELECT persona_id,
           bool_or(nps_categoria = 'Detractor' OR coalesce(satisfaccion_general, satisfaccion_prom) <= 3) AS detractor,
           bool_or(nps_categoria = 'Promotor')                                                          AS promotor
    FROM actho.fact_encuesta_evento WHERE persona_id IS NOT NULL GROUP BY persona_id
)
SELECT 'Afiliados que no participan' AS segmento, persona_id, empresa_id, ejecutiva, nivel_2027, nivel_cargo, autoriza_datos
  FROM personas WHERE es_vigente = 1 AND NOT participa_en_ventana
UNION ALL
SELECT 'Vencimientos próximos', persona_id, empresa_id, ejecutiva, nivel_2027, nivel_cargo, autoriza_datos
  FROM personas WHERE es_vigente = 1 AND (dias_a_vencer <= 90 OR rango_vencimiento = 'Vencida')
UNION ALL
SELECT 'Detractores recientes', p.persona_id, p.empresa_id, p.ejecutiva, p.nivel_2027, p.nivel_cargo, p.autoriza_datos
  FROM personas p JOIN resp r USING (persona_id) WHERE r.detractor
UNION ALL
SELECT 'Promotores', p.persona_id, p.empresa_id, p.ejecutiva, p.nivel_2027, p.nivel_cargo, p.autoriza_datos
  FROM personas p JOIN resp r USING (persona_id) WHERE r.promotor
UNION ALL
SELECT 'Asistentes no afiliados', persona_id, empresa_id, ejecutiva, nivel_2027, nivel_cargo, autoriza_datos
  FROM personas WHERE es_vigente = 0 AND inscripciones_total > 0
UNION ALL
SELECT 'Afiliados de un solo contacto', persona_id, empresa_id, ejecutiva, nivel_2027, nivel_cargo, autoriza_datos
  FROM personas WHERE es_vigente = 1 AND personas_distintas = 1
UNION ALL
SELECT 'Nuevos afiliados', persona_id, empresa_id, ejecutiva, nivel_2027, nivel_cargo, autoriza_datos
  FROM personas WHERE es_nuevo_afiliado;

CREATE VIEW actho.v_segmentos_resumen AS
SELECT segmento, count(*) AS personas, count(DISTINCT empresa_id) AS empresas,
       count(*) FILTER (WHERE autoriza_datos = 'Sí') AS personas_contactables
FROM actho.v_segmentos_comunicacion GROUP BY segmento ORDER BY segmento;

-- 9. Calidad de datos (para la página de diagnóstico) ---------------------------
CREATE VIEW actho.v_calidad_resumen AS
SELECT tabla, accion, count(*) AS hallazgos, sum(filas_afectadas) AS filas_afectadas
FROM actho.reporte_calidad GROUP BY tabla, accion ORDER BY tabla, accion;
