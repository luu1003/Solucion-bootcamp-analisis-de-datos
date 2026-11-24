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

-- 3b. Uso de beneficios (asistencia + comunidades + encuesta 90 días + plantilla) ---
-- Las vinculaciones vigentes a comunidades (es_fechado = 0) cuentan como uso en 12 meses, no en la ventana.
CREATE VIEW actho.v_uso_beneficio_detalle AS
SELECT u.uso_id, u.empresa_id, u.persona_id, u.servicio_id, s.servicio, s.linea_servicio,
       u.fecha, to_char(u.fecha, 'YYYY-MM') AS anio_mes, u.cantidad, u.fuente, u.detalle, u.es_fechado,
       e.nivel_2027, e.tipo_membresia, e.sector, e.ciudad, j.nombre AS ejecutiva,
       CASE WHEN e.es_vigente = 1 THEN 'Afiliada' ELSE 'No afiliada' END AS condicion_empresa
FROM actho.fact_uso_beneficio u
JOIN actho.dim_servicio s USING (servicio_id)
JOIN actho.dim_empresa e USING (empresa_id)
LEFT JOIN actho.dim_ejecutiva j ON j.ejecutiva_id = e.ejecutiva_id;

CREATE VIEW actho.v_empresa_beneficios AS
WITH u AS (
    SELECT u.*, s.linea_servicio,
           (u.es_fechado = 0 OR (u.fecha > p.fecha_corte - 365 AND u.fecha <= p.fecha_corte))        AS en_12m,
           (u.es_fechado = 1 AND u.fecha > p.fecha_corte - p.ventana_participacion_dias
                             AND u.fecha <= p.fecha_corte)                                           AS en_ventana,
           (u.es_fechado = 1 AND u.fecha <= p.fecha_corte)                                           AS hasta_corte
    FROM actho.fact_uso_beneficio u
    JOIN actho.dim_servicio s USING (servicio_id)
    CROSS JOIN actho.v_parametros p
)
SELECT empresa_id,
       count(*) FILTER (WHERE en_ventana)                              AS usos_ventana,
       count(*) FILTER (WHERE en_12m)                                  AS usos_12m,
       count(DISTINCT servicio_id) FILTER (WHERE en_12m)               AS servicios_12m,
       count(DISTINCT linea_servicio) FILTER (WHERE en_12m)            AS lineas_servicio_12m,
       string_agg(DISTINCT fuente, ' · ') FILTER (WHERE en_12m)        AS fuentes_uso_12m,
       max(fecha) FILTER (WHERE hasta_corte)                           AS ultimo_uso
FROM u GROUP BY empresa_id;

-- Aprovechamiento del nivel: servicios incluidos en el nivel 2027 que ya se pueden medir (hay fuente o datos)
-- y cuántos de ellos usó la empresa en 12 meses.
CREATE VIEW actho.v_empresa_aprovechamiento AS
WITH medibles AS (
    SELECT s.* FROM actho.dim_servicio s
    WHERE s.fuente_dato IN ('Asistencia', 'CRM y asistencia')
       OR s.servicio_id IN (SELECT DISTINCT servicio_id FROM actho.fact_uso_beneficio)
), usados AS (
    SELECT DISTINCT u.empresa_id, u.servicio_id
    FROM actho.fact_uso_beneficio u CROSS JOIN actho.v_parametros p
    WHERE u.es_fechado = 0 OR (u.fecha > p.fecha_corte - 365 AND u.fecha <= p.fecha_corte)
)
SELECT e.empresa_id,
       count(*)                                    AS servicios_incluidos_medibles,
       count(x.servicio_id)                        AS servicios_incluidos_usados
FROM actho.dim_empresa e
JOIN medibles s ON CASE e.nivel_2027 WHEN 'Conectar' THEN s.incluido_conectar
                                     WHEN 'Crecer'   THEN s.incluido_crecer
                                     WHEN 'Liderar'  THEN s.incluido_liderar ELSE 0 END = 1
LEFT JOIN usados x ON x.empresa_id = e.empresa_id AND x.servicio_id = s.servicio_id
WHERE e.es_vigente = 1
GROUP BY e.empresa_id;

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
           coalesce(s.tiene_promotor, false)                            AS tiene_promotor,
           coalesce(b.usos_ventana, 0) > 0                              AS usa_beneficio_ventana,
           coalesce(b.usos_12m, 0) > 0                                  AS usa_beneficio_12m,
           coalesce(b.usos_12m, 0)                                      AS usos_beneficio_12m,
           coalesce(b.servicios_12m, 0)                                 AS servicios_12m,
           b.fuentes_uso_12m, b.ultimo_uso,
           ap.servicios_incluidos_medibles, ap.servicios_incluidos_usados
    FROM actho.dim_empresa e
    CROSS JOIN actho.v_parametros p
    LEFT JOIN actho.dim_ejecutiva j ON j.ejecutiva_id = e.ejecutiva_id
    LEFT JOIN actho.v_empresa_actividad a ON a.empresa_id = e.empresa_id
    LEFT JOIN actho.v_empresa_satisfaccion s ON s.empresa_id = e.empresa_id
    LEFT JOIN actho.v_empresa_beneficios b ON b.empresa_id = e.empresa_id
    LEFT JOIN actho.v_empresa_aprovechamiento ap ON ap.empresa_id = e.empresa_id
), puntos AS (
    SELECT b.*,
           CASE WHEN b.es_vigente = 0 THEN 0
                WHEN b.dias_vence < 0 OR b.estado_membresia = 'Periodo de gracia' THEN b.pts_vencida
                WHEN b.dias_vence <= 30 THEN b.pts_vence_30
                WHEN b.dias_vence <= 60 THEN b.pts_vence_60
                WHEN b.dias_vence <= 90 THEN b.pts_vence_90
                ELSE 0 END                                                AS pts_vencimiento,
           -- Participación = uso de cualquier beneficio (no solo asistencia a eventos).
           CASE WHEN b.es_vigente = 0 OR b.usa_beneficio_ventana THEN 0
                ELSE b.pts_sin_participacion
                     + CASE WHEN NOT b.usa_beneficio_12m THEN b.pts_sin_participacion_12m ELSE 0 END
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
       usa_beneficio_ventana                                              AS participa_en_ventana,
       usa_beneficio_12m, usos_beneficio_12m, servicios_12m, fuentes_uso_12m, ultimo_uso,
       servicios_incluidos_medibles, servicios_incluidos_usados,
       round(100.0 * servicios_incluidos_usados / nullif(servicios_incluidos_medibles, 0), 0) AS pct_aprovechamiento,
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
                 CASE WHEN NOT usa_beneficio_12m THEN 'Sin uso de beneficios en 12 meses'
                      ELSE 'Sin uso de beneficios en ' || ventana_participacion_dias || ' días' END END,
            CASE WHEN pts_satisfaccion > 0 THEN
                 CASE WHEN detractor_reciente THEN 'Detractor reciente'
                      ELSE 'Satisfacción baja (' || satisfaccion_promedio || ')' END END), '') AS motivos_riesgo,
       inconsistencia, estado_crm,
       -- Renovación aproximada por empresa (misma regla que v_tasa_renovacion; permite filtrarla)
       CASE WHEN en_crm = 1 AND es_vigente = 1 AND fecha_afiliacion <= fecha_corte - 365 THEN 'Renovó'
            WHEN en_crm = 1 AND estado_membresia IN ('Cancelado', 'Expirado', 'Inactivo')
                 AND fecha_expiracion > fecha_corte - 365 AND fecha_expiracion <= fecha_corte THEN 'No renovó'
       END                                                                AS renovacion_aprox,
       fecha_corte
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

-- 5b. Encuesta de relación a 90 días: NPS de ACTHO e intención de renovar -------
CREATE VIEW actho.v_encuesta_relacion_detalle AS
SELECT r.*, r.fecha_respuesta::date AS fecha, to_char(r.fecha_respuesta, 'YYYY-MM') AS anio_mes,
       e.nivel_2027, e.tipo_membresia, e.sector, e.ciudad AS ciudad_empresa, j.nombre AS ejecutiva, e.es_vigente
FROM actho.fact_encuesta_relacion r
LEFT JOIN actho.dim_empresa e USING (empresa_id)
LEFT JOIN actho.dim_ejecutiva j ON j.ejecutiva_id = e.ejecutiva_id
WHERE r.es_prueba = 0;

CREATE VIEW actho.v_nps_actho AS
SELECT count(*)                                                        AS respuestas,
       count(nps_actho)                                                AS respuestas_nps,
       count(*) FILTER (WHERE nps_categoria = 'Promotor')              AS promotores,
       count(*) FILTER (WHERE nps_categoria = 'Pasivo')                AS pasivos,
       count(*) FILTER (WHERE nps_categoria = 'Detractor')             AS detractores,
       round(100.0 * (count(*) FILTER (WHERE nps_categoria = 'Promotor')
                    - count(*) FILTER (WHERE nps_categoria = 'Detractor'))
             / nullif(count(nps_actho), 0), 1)                         AS nps_actho,
       round(avg(intencion_renovar), 2)                                AS intencion_renovar_prom,
       round(100.0 * count(*) FILTER (WHERE intencion_renovar >= 4) / nullif(count(intencion_renovar), 0), 1)
                                                                       AS pct_intencion_alta,
       round(avg(cumplimiento_expectativas), 2)                        AS cumplimiento_prom,
       round(avg(calif_bienvenida), 2)                                 AS bienvenida_prom,
       round(avg(calif_ejecutiva), 2)                                  AS ejecutiva_prom,
       count(*) FILTER (WHERE quiere_contacto = 'Sí')                  AS piden_contacto,
       max(fecha_respuesta)::date                                      AS ultima_respuesta
FROM actho.fact_encuesta_relacion WHERE es_prueba = 0;

-- A quién enviarle la encuesta: afiliados que cumplen ~90 días o a los que les faltan ~60 días para renovar,
-- sin respuesta en los últimos 6 meses.
CREATE VIEW actho.v_encuesta_90d_por_enviar AS
SELECT e.empresa_id, e.ejecutiva, e.nivel_2027, e.fecha_afiliacion, e.fecha_expiracion, e.dias_a_vencer,
       CASE WHEN e.fecha_afiliacion BETWEEN e.fecha_corte - 120 AND e.fecha_corte - 75 THEN 'Cumple 90 días de afiliación'
            ELSE 'Faltan unos 60 días para renovar' END AS motivo
FROM actho.v_empresa_360 e
WHERE e.es_vigente = 1
  AND (e.fecha_afiliacion BETWEEN e.fecha_corte - 120 AND e.fecha_corte - 75 OR e.dias_a_vencer BETWEEN 45 AND 75)
  AND NOT EXISTS (SELECT 1 FROM actho.fact_encuesta_relacion r
                  WHERE r.empresa_id = e.empresa_id AND r.es_prueba = 0
                    AND r.fecha_respuesta::date > e.fecha_corte - 180);

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
    (SELECT nps_actho FROM actho.v_nps_actho)                                        AS nps_actho_90_dias,
    (SELECT respuestas_nps FROM actho.v_nps_actho)                                   AS respuestas_nps_actho;

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
  FROM personas WHERE es_nuevo_afiliado
UNION ALL
SELECT 'Encuesta de 90 días por enviar', persona_id, empresa_id, ejecutiva, nivel_2027, nivel_cargo, autoriza_datos
  FROM personas WHERE empresa_id IN (SELECT empresa_id FROM actho.v_encuesta_90d_por_enviar);

CREATE VIEW actho.v_segmentos_resumen AS
SELECT segmento, count(*) AS personas, count(DISTINCT empresa_id) AS empresas,
       count(*) FILTER (WHERE autoriza_datos = 'Sí') AS personas_contactables
FROM actho.v_segmentos_comunicacion GROUP BY segmento ORDER BY segmento;

-- 9. Calidad de datos (para la página de diagnóstico) ---------------------------
CREATE VIEW actho.v_calidad_resumen AS
SELECT tabla, accion, count(*) AS hallazgos, sum(filas_afectadas) AS filas_afectadas
FROM actho.reporte_calidad GROUP BY tabla, accion ORDER BY tabla, accion;

-- 10. Definiciones de los indicadores (propuesta para acordar con ACTHO) -----------
-- 'estado' = 'Propuesta' hasta que ACTHO la valide; al acordarla, cambiar a 'Acordada' aquí.
CREATE TABLE actho.definicion_indicador (
    orden       int PRIMARY KEY,
    indicador   text NOT NULL,
    definicion  text NOT NULL,
    calculo     text,
    fuente      text,
    estado      text NOT NULL DEFAULT 'Propuesta'
);
INSERT INTO actho.definicion_indicador (orden, indicador, definicion, calculo, fuente, estado) VALUES
 (1, 'Afiliados activos', 'Empresas cuyo «Estado de la membresía» en Zoho es Activo.',
  'Una empresa cuenta una vez aunque tenga varios registros en el CRM.', 'Zoho CRM', 'Propuesta'),
 (2, 'Afiliados vigentes', 'Activos más los que están en periodo de gracia o pronto a expirar: todavía reciben beneficios.',
  'Estado de la membresía ∈ {Activo, Periodo de gracia, Pronto a expirar}.', 'Zoho CRM', 'Propuesta'),
 (3, 'Uso de beneficios', 'Porcentaje de afiliados vigentes que usaron al menos un beneficio en los últimos 90 días.',
  'Usos fechados (asistencia, encuesta de 90 días, plantilla mensual) en la ventana de participación. La vinculación a comunidades cuenta solo para 12 meses.',
  'Asistencia, Zoho (comunidades), encuesta de 90 días, plantilla mensual', 'Propuesta'),
 (4, 'Aprovechamiento del nivel', 'De los servicios incluidos en el nivel 2027 que hoy se pueden medir, cuántos usó la empresa en 12 meses.',
  'Servicios incluidos usados ÷ servicios incluidos medibles.', 'Catálogo de servicios 2027 + uso de beneficios', 'Propuesta'),
 (5, 'Vencen en 30, 60 y 90 días', 'Membresías vigentes cuya fecha de expiración cae en esa ventana desde la fecha de corte.',
  'Fecha de expiración − fecha de corte entre 0 y N días.', 'Zoho CRM', 'Propuesta'),
 (6, 'Tasa de renovación (aproximada)', 'Mientras Zoho no guarde historial: vigentes con más de un año de afiliación frente a los que se retiraron en los últimos 12 meses.',
  'Renovó ÷ (Renovó + No renovó). Se puede filtrar por nivel, sector, ciudad o ejecutiva.', 'Zoho CRM', 'Propuesta'),
 (7, 'Tasa de renovación (medida)', 'Membresías que vencían en un mes y aparecen renovadas en la foto del mes siguiente.',
  'Compara las fotos mensuales de historial.snapshot_membresia; reemplaza a la aproximada desde la segunda foto.', 'Airflow (fotos mensuales)', 'Propuesta'),
 (8, 'Retiros', 'Membresías canceladas, expiradas o inactivas cuya fecha de expiración cayó en el periodo.',
  'Estado ∈ {Cancelado, Expirado, Inactivo}.', 'Zoho CRM', 'Propuesta'),
 (9, 'Altas', 'Empresas cuya fecha de afiliación cae en el mes.', 'Fecha de afiliación del registro principal.', 'Zoho CRM', 'Propuesta'),
 (10, 'Satisfacción', 'Promedio de las calificaciones de 1 a 5 de las encuestas de eventos.',
  'Satisfacción general (post-evento) o promedio de aspectos (formularios presencial y virtual).', 'Encuestas de eventos', 'Propuesta'),
 (11, 'NPS de eventos', '% de promotores (9-10) menos % de detractores (0-6) en la encuesta post-evento.', 'Solo respuestas con puntaje 0-10.', 'Encuesta post-evento', 'Propuesta'),
 (12, 'NPS de ACTHO', 'Mismo cálculo con la encuesta de relación a 90 días: mide la relación con la asociación, no un evento.',
  'Excluye respuestas de prueba.', 'Encuesta de 90 días', 'Propuesta'),
 (13, 'Intención de renovar', 'Porcentaje que responde 4 o 5 a «¿Qué tan probable es que renueves?» en la encuesta de 90 días.', '', 'Encuesta de 90 días', 'Propuesta'),
 (14, 'Riesgo de no renovar (semáforo)', 'Suma de puntos por vencimiento cercano, falta de uso de beneficios y satisfacción baja. Alto desde 5 puntos, medio desde 3.',
  'Parámetros en actho.config_parametro; se puede simular en la página Pulso.', 'Todas', 'Propuesta'),
 (15, 'Asistentes no afiliados', 'Empresas y personas que participan en eventos sin membresía vigente.', '', 'Asistencia + Zoho', 'Propuesta');

-- Conciliación: por qué el tablero y los informes de Zoho muestran cifras distintas de «activos».
CREATE VIEW actho.v_conciliacion_activos AS
SELECT 1 AS orden, 'Registros con «Estado = Activo» en Zoho (lo que cuenta el informe de membresías)'::text AS concepto,
       count(*) AS cantidad FROM actho.fact_membresia WHERE estado_crm = 'Activo'
UNION ALL
SELECT 2, 'Empresas distintas entre esos registros (una empresa puede tener varios)', count(DISTINCT empresa_id)
FROM actho.fact_membresia WHERE estado_crm = 'Activo'
UNION ALL
SELECT 3, 'Empresas con «Estado de la membresía = Activo» (indicador Afiliados activos)', count(*)
FROM actho.dim_empresa WHERE es_activo = 1
UNION ALL
SELECT 4, 'Empresas vigentes: activas + periodo de gracia + pronto a expirar (indicador Afiliados vigentes)', count(*)
FROM actho.dim_empresa WHERE es_vigente = 1
ORDER BY 1;

CREATE VIEW actho.v_conciliacion_detalle AS
SELECT estado_membresia, count(*) AS registros_zoho_activo, count(DISTINCT empresa_id) AS empresas
FROM actho.fact_membresia WHERE estado_crm = 'Activo'
GROUP BY estado_membresia ORDER BY 2 DESC;
