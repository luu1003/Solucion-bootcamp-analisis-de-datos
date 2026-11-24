-- ════════════════════════════════════════════════════════════════════════════
-- Esquemas de control e historial · Reto ACTHO
-- A diferencia de 'actho' (que se recrea en cada carga), estos esquemas
-- PERSISTEN entre cargas: guardan la trazabilidad de la ingesta y la historia.
-- Se crean desde src/ingesta_control.py (Airflow) y son idempotentes.
-- ════════════════════════════════════════════════════════════════════════════
CREATE SCHEMA IF NOT EXISTS ingesta;
CREATE SCHEMA IF NOT EXISTS historial;

-- Una fila por ejecución del DAG de ingesta.
CREATE TABLE IF NOT EXISTS ingesta.ejecucion (
    id                bigserial PRIMARY KEY,
    dag_run_id        text,
    inicio            timestamptz NOT NULL DEFAULT now(),
    fin               timestamptz,
    estado            text NOT NULL DEFAULT 'en_curso'
                      CHECK (estado IN ('en_curso', 'procesado', 'sin_cambios', 'con_errores')),
    fecha_corte       date,
    fuentes_cambiadas text[],
    detalle           jsonb
);
CREATE INDEX IF NOT EXISTS ix_ejecucion_run ON ingesta.ejecucion (dag_run_id);

-- Una fila por archivo fuente procesado (capa bronce: qué archivo exacto entró).
CREATE TABLE IF NOT EXISTS ingesta.lote_carga (
    id            bigserial PRIMARY KEY,
    ejecucion_id  bigint REFERENCES ingesta.ejecucion(id),
    fuente        text NOT NULL CHECK (fuente IN ('zoho_crm', 'asistencia_excel', 'encuesta_presencial',
                                                  'encuesta_virtual', 'encuesta_post_evento', 'base_afiliados',
                                                  'encuesta_90d', 'uso_beneficios')),
    archivo       text NOT NULL,
    hash_sha256   char(64) NOT NULL,
    bytes         bigint,
    estado        text NOT NULL DEFAULT 'procesado' CHECK (estado IN ('procesado', 'con_errores')),
    cargado_en    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (fuente, hash_sha256)          -- el mismo archivo no se registra dos veces
);
-- Bases creadas antes de agregar la plantilla de uso de beneficios: se actualiza la lista de fuentes válidas.
ALTER TABLE ingesta.lote_carga DROP CONSTRAINT IF EXISTS lote_carga_fuente_check;
ALTER TABLE ingesta.lote_carga ADD CONSTRAINT lote_carga_fuente_check
    CHECK (fuente IN ('zoho_crm', 'asistencia_excel', 'encuesta_presencial', 'encuesta_virtual',
                      'encuesta_post_evento', 'base_afiliados', 'encuesta_90d', 'uso_beneficios'));

-- Semáforo por empresa en cada fecha de corte (permite ver cómo evoluciona el riesgo).
CREATE TABLE IF NOT EXISTS historial.evaluacion_riesgo (
    fecha_corte        date NOT NULL,
    empresa_id         text NOT NULL,
    ejecutiva          text,
    nivel_2027         text,
    estado_membresia   text,
    dias_a_vencer      integer,
    pts_vencimiento    smallint,
    pts_participacion  smallint,
    pts_satisfaccion   smallint,
    puntaje            smallint NOT NULL,
    semaforo           text NOT NULL,
    motivos            text,
    version_reglas     char(8) NOT NULL,   -- huella de los parámetros usados
    calculado_en       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (fecha_corte, empresa_id)
);
CREATE INDEX IF NOT EXISTS ix_eval_semaforo ON historial.evaluacion_riesgo (fecha_corte, semaforo);

-- Foto mensual de las membresías: resuelve que Zoho no guarde historial de renovaciones.
CREATE TABLE IF NOT EXISTS historial.snapshot_membresia (
    periodo              date NOT NULL,      -- primer día del mes
    empresa_id           text NOT NULL,
    ejecutiva            text,
    estado_membresia     text,
    tipo_membresia       text,
    categoria_membresia  text,
    nivel_2027           text,
    fecha_afiliacion     date,
    fecha_expiracion     date,
    es_vigente           smallint,
    tomado_en            timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (periodo, empresa_id)
);

-- Movimientos entre fotos consecutivas: altas, retiros y renovaciones medidas (no aproximadas).
CREATE OR REPLACE VIEW historial.v_movimientos_mensuales AS
WITH periodos AS (
    SELECT periodo, lag(periodo) OVER (ORDER BY periodo) AS periodo_anterior
    FROM (SELECT DISTINCT periodo FROM historial.snapshot_membresia) d
), pares AS (
    SELECT a.periodo, a.empresa_id, a.es_vigente AS vigente_ahora, b.es_vigente AS vigente_antes,
           a.fecha_expiracion AS exp_ahora, b.fecha_expiracion AS exp_antes
    FROM historial.snapshot_membresia a
    JOIN periodos p USING (periodo)
    LEFT JOIN historial.snapshot_membresia b
           ON b.periodo = p.periodo_anterior AND b.empresa_id = a.empresa_id
    WHERE p.periodo_anterior IS NOT NULL
)
SELECT periodo,
       count(*) FILTER (WHERE vigente_ahora = 1 AND coalesce(vigente_antes, 0) = 0)        AS altas_o_reactivaciones,
       count(*) FILTER (WHERE vigente_ahora = 0 AND vigente_antes = 1)                      AS retiros,
       count(*) FILTER (WHERE vigente_ahora = 1 AND vigente_antes = 1 AND exp_ahora > exp_antes) AS renovaciones,
       count(*) FILTER (WHERE vigente_antes = 1)                                            AS vigentes_mes_anterior
FROM pares
GROUP BY periodo
ORDER BY periodo;

-- Renovación medida por empresa: membresías vigentes que vencían antes del mes siguiente y qué pasó en la foto
-- de ese mes. 'Pendiente' = sigue vigente sin nueva fecha (p. ej. en periodo de gracia).
CREATE OR REPLACE VIEW historial.v_renovacion_medida AS
WITH periodos AS (
    SELECT periodo, lag(periodo) OVER (ORDER BY periodo) AS periodo_anterior
    FROM (SELECT DISTINCT periodo FROM historial.snapshot_membresia) d
)
SELECT p.periodo, b.empresa_id, b.nivel_2027, b.ejecutiva,
       b.fecha_expiracion AS expiracion_anterior, a.fecha_expiracion AS expiracion_nueva,
       CASE WHEN a.es_vigente = 1 AND a.fecha_expiracion > b.fecha_expiracion THEN 'Renovó'
            WHEN coalesce(a.es_vigente, 0) = 0 THEN 'No renovó'
            ELSE 'Pendiente' END AS resultado
FROM historial.snapshot_membresia b
JOIN periodos p ON b.periodo = p.periodo_anterior
LEFT JOIN historial.snapshot_membresia a ON a.periodo = p.periodo AND a.empresa_id = b.empresa_id
WHERE b.es_vigente = 1 AND b.fecha_expiracion < p.periodo;
