-- Esquema generado por src/cargar_postgres.py a partir de salida/

DROP SCHEMA IF EXISTS actho CASCADE;
CREATE SCHEMA actho;

CREATE TABLE actho.dim_ejecutiva (
    "ejecutiva_id" integer NOT NULL,
    "nombre" text,
    PRIMARY KEY (ejecutiva_id)
);

COMMENT ON COLUMN actho.dim_ejecutiva."ejecutiva_id" IS 'Identificador de la ejecutiva de cuenta (KAM) propietaria.';
COMMENT ON COLUMN actho.dim_ejecutiva."nombre" IS 'Nombre.';

CREATE TABLE actho.dim_fecha (
    "fecha" date NOT NULL,
    "anio" integer,
    "trimestre" integer,
    "mes" integer,
    "nombre_mes" text,
    "anio_mes" text,
    "semana_iso" integer,
    PRIMARY KEY (fecha)
);

COMMENT ON COLUMN actho.dim_fecha."fecha" IS 'Fecha.';
COMMENT ON COLUMN actho.dim_fecha."anio" IS 'Año.';
COMMENT ON COLUMN actho.dim_fecha."trimestre" IS 'Trimestre.';
COMMENT ON COLUMN actho.dim_fecha."mes" IS 'Mes (número).';
COMMENT ON COLUMN actho.dim_fecha."nombre_mes" IS 'Nombre del mes.';
COMMENT ON COLUMN actho.dim_fecha."anio_mes" IS 'Año y mes (AAAA-MM).';
COMMENT ON COLUMN actho.dim_fecha."semana_iso" IS 'Semana ISO.';

CREATE TABLE actho.dim_empresa (
    "empresa_id" text NOT NULL,
    "tipo_empresa" text,
    "pais" text,
    "region" text,
    "tipo_compania" text,
    "fecha_afiliacion" date,
    "independiente" text,
    "rango_empleados" text,
    "sector" text,
    "departamento" text,
    "ciudad" text,
    "subsector" text,
    "tipo_membresia" text,
    "categoria_membresia" text,
    "tipo_consultora" text,
    "pct_mujeres" numeric(10,2),
    "fecha_expiracion" date,
    "estado_membresia" text,
    "com_hr_estrategico" integer,
    "com_mas_que_un_salario" integer,
    "com_talento_que_elige" integer,
    "com_gente_que_crece" integer,
    "com_talento_aumentado" integer,
    "com_mujeres_hr" integer,
    "com_influenciador" integer,
    "tamano_empresa" text,
    "miembro_desde" date,
    "vinculado_comunidades" integer,
    "cantidad_miembros" integer,
    "nivel_2027" text,
    "es_activo" integer,
    "es_vigente" integer,
    "inconsistencia" text,
    "dias_a_vencer" integer,
    "rango_vencimiento" text,
    "n_comunidades" integer,
    "cantidad_miembros_atipico" integer,
    "es_persona_natural" integer,
    "n_registros_crm" integer,
    "en_crm" integer,
    "origen" text,
    "ejecutiva_id" integer,
    PRIMARY KEY (empresa_id),
    FOREIGN KEY (ejecutiva_id) REFERENCES actho.dim_ejecutiva(ejecutiva_id)
);

COMMENT ON COLUMN actho.dim_empresa."empresa_id" IS 'Código anonimizado de la empresa (EMP-####). Llave común entre CRM, asistencia y encuestas.';
COMMENT ON COLUMN actho.dim_empresa."tipo_empresa" IS 'Tipo de empresa (nacional, multinacional, pública…).';
COMMENT ON COLUMN actho.dim_empresa."pais" IS 'País unificado.';
COMMENT ON COLUMN actho.dim_empresa."region" IS 'Región (derivada del departamento cuando faltaba).';
COMMENT ON COLUMN actho.dim_empresa."tipo_compania" IS 'Tipo de compañía en el CRM (Asociado, Cliente, Aliado, Otro).';
COMMENT ON COLUMN actho.dim_empresa."fecha_afiliacion" IS 'Fecha de afiliación (vacía si venía vacía o era imposible).';
COMMENT ON COLUMN actho.dim_empresa."independiente" IS 'Si es consultor independiente (Sí/No/Sin dato).';
COMMENT ON COLUMN actho.dim_empresa."rango_empleados" IS 'Rango de empleados normalizado.';
COMMENT ON COLUMN actho.dim_empresa."sector" IS 'Sector económico unificado.';
COMMENT ON COLUMN actho.dim_empresa."departamento" IS 'Departamento unificado.';
COMMENT ON COLUMN actho.dim_empresa."ciudad" IS 'Ciudad unificada.';
COMMENT ON COLUMN actho.dim_empresa."subsector" IS 'Subsector económico unificado.';
COMMENT ON COLUMN actho.dim_empresa."tipo_membresia" IS 'Quién se afilia: Empresa, Consultoras, Universidades o Persona natural.';
COMMENT ON COLUMN actho.dim_empresa."categoria_membresia" IS 'Categoría en Zoho: Estándar, Premium, Elite o Personal.';
COMMENT ON COLUMN actho.dim_empresa."tipo_consultora" IS 'Tipo de consultora (solo membresías de consultoras).';
COMMENT ON COLUMN actho.dim_empresa."pct_mujeres" IS 'Porcentaje de mujeres en la compañía (0-100).';
COMMENT ON COLUMN actho.dim_empresa."fecha_expiracion" IS 'Fecha de expiración de la afiliación.';
COMMENT ON COLUMN actho.dim_empresa."estado_membresia" IS 'Estado de la membresía (Activo, Periodo de gracia, Pronto a expirar, Expirado, Inactivo, Cancelado).';
COMMENT ON COLUMN actho.dim_empresa."com_hr_estrategico" IS 'Pertenece a la comunidad ''HR Estratégico'' (0 = no).';
COMMENT ON COLUMN actho.dim_empresa."com_mas_que_un_salario" IS 'Pertenece a la comunidad ''Más que un Salario'' (0 = no).';
COMMENT ON COLUMN actho.dim_empresa."com_talento_que_elige" IS 'Pertenece a la comunidad ''Talento que Elige'' (0 = no).';
COMMENT ON COLUMN actho.dim_empresa."com_gente_que_crece" IS 'Pertenece a la comunidad ''Gente que Crece'' (0 = no).';
COMMENT ON COLUMN actho.dim_empresa."com_talento_aumentado" IS 'Pertenece a la comunidad ''Talento Aumentado'' (0 = no).';
COMMENT ON COLUMN actho.dim_empresa."com_mujeres_hr" IS 'Pertenece a la comunidad ''Mujeres HR'' (0 = no).';
COMMENT ON COLUMN actho.dim_empresa."com_influenciador" IS 'Marcado como influenciador en el CRM (0 = no).';
COMMENT ON COLUMN actho.dim_empresa."tamano_empresa" IS 'Micro, Pequeña, Mediana o Grande.';
COMMENT ON COLUMN actho.dim_empresa."miembro_desde" IS 'Fecha ''Miembro desde'' del CRM.';
COMMENT ON COLUMN actho.dim_empresa."vinculado_comunidades" IS '1 si está vinculado a alguna comunidad.';
COMMENT ON COLUMN actho.dim_empresa."cantidad_miembros" IS 'Cantidad de miembros registrados de la empresa.';
COMMENT ON COLUMN actho.dim_empresa."nivel_2027" IS 'Nivel de la oferta 2027 equivalente: Conectar (Estándar), Crecer (Premium), Liderar (Elite).';
COMMENT ON COLUMN actho.dim_empresa."es_activo" IS '1 si el estado de la membresía es ''Activo'' (definición del indicador ''Afiliados activos'').';
COMMENT ON COLUMN actho.dim_empresa."es_vigente" IS '1 si es Activo, Periodo de gracia o Pronto a expirar.';
COMMENT ON COLUMN actho.dim_empresa."inconsistencia" IS 'Alertas de coherencia detectadas en el registro (no se corrigen, se marcan).';
COMMENT ON COLUMN actho.dim_empresa."dias_a_vencer" IS 'Días entre la fecha de corte y la expiración (solo membresías vigentes).';
COMMENT ON COLUMN actho.dim_empresa."rango_vencimiento" IS 'Vencida, 0-30, 31-60, 61-90 o Más de 90 días.';
COMMENT ON COLUMN actho.dim_empresa."n_comunidades" IS 'Número de comunidades temáticas a las que pertenece.';
COMMENT ON COLUMN actho.dim_empresa."cantidad_miembros_atipico" IS '1 si el valor es extremo según el rango intercuartílico.';
COMMENT ON COLUMN actho.dim_empresa."es_persona_natural" IS '1 si la membresía es de persona natural.';
COMMENT ON COLUMN actho.dim_empresa."n_registros_crm" IS 'Número de registros de la empresa en el CRM.';
COMMENT ON COLUMN actho.dim_empresa."en_crm" IS '1 si la empresa tiene registro en el CRM.';
COMMENT ON COLUMN actho.dim_empresa."origen" IS 'De dónde viene la empresa (CRM, Asistencia, Encuesta, Base de afiliados).';
COMMENT ON COLUMN actho.dim_empresa."ejecutiva_id" IS 'Identificador de la ejecutiva de cuenta (KAM) propietaria.';

CREATE TABLE actho.dim_persona (
    "persona_id" text NOT NULL,
    "empresa_id" text,
    "nivel_cargo" text,
    "autoriza_datos" text,
    "es_contacto_principal" integer,
    "inscripciones_2026" integer,
    PRIMARY KEY (persona_id),
    FOREIGN KEY (empresa_id) REFERENCES actho.dim_empresa(empresa_id)
);

COMMENT ON COLUMN actho.dim_persona."persona_id" IS 'Código anonimizado de la persona (P-#####).';
COMMENT ON COLUMN actho.dim_persona."empresa_id" IS 'Código anonimizado de la empresa (EMP-####). Llave común entre CRM, asistencia y encuestas.';
COMMENT ON COLUMN actho.dim_persona."nivel_cargo" IS 'Nivel de cargo agrupado.';
COMMENT ON COLUMN actho.dim_persona."autoriza_datos" IS 'Autorización de tratamiento de datos (Sí/No/Sin dato). Condición para usar la persona en campañas.';
COMMENT ON COLUMN actho.dim_persona."es_contacto_principal" IS '1 si es el afiliado principal de su empresa según la base de afiliados.';
COMMENT ON COLUMN actho.dim_persona."inscripciones_2026" IS 'Número de eventos 2026 en los que está inscrita la persona.';

CREATE TABLE actho.dim_evento (
    "evento_id" integer NOT NULL,
    "hoja_origen" text,
    "fecha" date,
    "nombre" text,
    "linea_2027" text,
    "experiencia" text,
    "modalidad" text,
    "fecha_fin" date,
    "anio" integer,
    "mes" integer,
    "inscritos" integer,
    "empresas_distintas" integer,
    PRIMARY KEY (evento_id)
);

COMMENT ON COLUMN actho.dim_evento."evento_id" IS 'N° de evento según la hoja de homologación 2026.';
COMMENT ON COLUMN actho.dim_evento."hoja_origen" IS 'Nombre de la hoja del libro de asistencia.';
COMMENT ON COLUMN actho.dim_evento."fecha" IS 'Fecha.';
COMMENT ON COLUMN actho.dim_evento."nombre" IS 'Nombre.';
COMMENT ON COLUMN actho.dim_evento."linea_2027" IS 'Línea de la oferta 2027 validada por ACTHO (Anticipar, Saber, Pares, Proyectar, Foro, Evento grande).';
COMMENT ON COLUMN actho.dim_evento."experiencia" IS 'Experiencia o detalle dentro de la línea.';
COMMENT ON COLUMN actho.dim_evento."modalidad" IS 'Presencial, Virtual o Híbrido.';
COMMENT ON COLUMN actho.dim_evento."fecha_fin" IS 'Fecha de fin del evento (eventos de varios días).';
COMMENT ON COLUMN actho.dim_evento."anio" IS 'Año.';
COMMENT ON COLUMN actho.dim_evento."mes" IS 'Mes (número).';
COMMENT ON COLUMN actho.dim_evento."inscritos" IS 'Personas inscritas al evento (sin duplicados).';
COMMENT ON COLUMN actho.dim_evento."empresas_distintas" IS 'Empresas distintas con al menos una inscripción al evento.';

CREATE TABLE actho.fact_membresia (
    "registro_id" text NOT NULL,
    "empresa_id" text,
    "ejecutiva_id" integer,
    "tipo_membresia" text,
    "categoria_membresia" text,
    "nivel_2027" text,
    "estado_membresia" text,
    "es_activo" integer,
    "es_vigente" integer,
    "fecha_afiliacion" date,
    "miembro_desde" date,
    "fecha_expiracion" date,
    "dias_a_vencer" integer,
    "rango_vencimiento" text,
    "inconsistencia" text,
    "es_registro_principal" integer,
    PRIMARY KEY (registro_id),
    FOREIGN KEY (empresa_id) REFERENCES actho.dim_empresa(empresa_id),
    FOREIGN KEY (ejecutiva_id) REFERENCES actho.dim_ejecutiva(ejecutiva_id)
);

COMMENT ON COLUMN actho.fact_membresia."registro_id" IS 'ID del registro en Zoho CRM (R-####). Una empresa puede tener varios.';
COMMENT ON COLUMN actho.fact_membresia."empresa_id" IS 'Código anonimizado de la empresa (EMP-####). Llave común entre CRM, asistencia y encuestas.';
COMMENT ON COLUMN actho.fact_membresia."ejecutiva_id" IS 'Identificador de la ejecutiva de cuenta (KAM) propietaria.';
COMMENT ON COLUMN actho.fact_membresia."tipo_membresia" IS 'Quién se afilia: Empresa, Consultoras, Universidades o Persona natural.';
COMMENT ON COLUMN actho.fact_membresia."categoria_membresia" IS 'Categoría en Zoho: Estándar, Premium, Elite o Personal.';
COMMENT ON COLUMN actho.fact_membresia."nivel_2027" IS 'Nivel de la oferta 2027 equivalente: Conectar (Estándar), Crecer (Premium), Liderar (Elite).';
COMMENT ON COLUMN actho.fact_membresia."estado_membresia" IS 'Estado de la membresía (Activo, Periodo de gracia, Pronto a expirar, Expirado, Inactivo, Cancelado).';
COMMENT ON COLUMN actho.fact_membresia."es_activo" IS '1 si el estado de la membresía es ''Activo'' (definición del indicador ''Afiliados activos'').';
COMMENT ON COLUMN actho.fact_membresia."es_vigente" IS '1 si es Activo, Periodo de gracia o Pronto a expirar.';
COMMENT ON COLUMN actho.fact_membresia."fecha_afiliacion" IS 'Fecha de afiliación (vacía si venía vacía o era imposible).';
COMMENT ON COLUMN actho.fact_membresia."miembro_desde" IS 'Fecha ''Miembro desde'' del CRM.';
COMMENT ON COLUMN actho.fact_membresia."fecha_expiracion" IS 'Fecha de expiración de la afiliación.';
COMMENT ON COLUMN actho.fact_membresia."dias_a_vencer" IS 'Días entre la fecha de corte y la expiración (solo membresías vigentes).';
COMMENT ON COLUMN actho.fact_membresia."rango_vencimiento" IS 'Vencida, 0-30, 31-60, 61-90 o Más de 90 días.';
COMMENT ON COLUMN actho.fact_membresia."inconsistencia" IS 'Alertas de coherencia detectadas en el registro (no se corrigen, se marcan).';
COMMENT ON COLUMN actho.fact_membresia."es_registro_principal" IS '1 si es el registro que representa a la empresa en dim_empresa.';

CREATE TABLE actho.fact_asistencia (
    "asistencia_id" integer NOT NULL,
    "empresa_id" text,
    "persona_id" text,
    "nivel_cargo" text,
    "costo" text,
    "autoriza_datos" text,
    "codigo_afiliado" numeric(10,2),
    "evento_id" integer,
    "afiliado_segun_hoja" text,
    "empresa_en_crm" integer,
    "empresa_afiliada_vigente" integer,
    PRIMARY KEY (asistencia_id),
    FOREIGN KEY (empresa_id) REFERENCES actho.dim_empresa(empresa_id),
    FOREIGN KEY (persona_id) REFERENCES actho.dim_persona(persona_id),
    FOREIGN KEY (evento_id) REFERENCES actho.dim_evento(evento_id)
);

COMMENT ON COLUMN actho.fact_asistencia."asistencia_id" IS 'Consecutivo de la inscripción (una fila por persona y evento).';
COMMENT ON COLUMN actho.fact_asistencia."empresa_id" IS 'Código anonimizado de la empresa (EMP-####). Llave común entre CRM, asistencia y encuestas.';
COMMENT ON COLUMN actho.fact_asistencia."persona_id" IS 'Código anonimizado de la persona (P-#####).';
COMMENT ON COLUMN actho.fact_asistencia."nivel_cargo" IS 'Nivel de cargo agrupado.';
COMMENT ON COLUMN actho.fact_asistencia."costo" IS 'Con costo / Sin costo.';
COMMENT ON COLUMN actho.fact_asistencia."autoriza_datos" IS 'Autorización de tratamiento de datos (Sí/No/Sin dato). Condición para usar la persona en campañas.';
COMMENT ON COLUMN actho.fact_asistencia."codigo_afiliado" IS 'Código 1/2 de la primera columna de cada hoja (encabezado ''AFILIADO'' en algunas). Los datos sugieren 1 = afiliado, 2 = no afiliado; confirmar con ACTHO.';
COMMENT ON COLUMN actho.fact_asistencia."evento_id" IS 'N° de evento según la hoja de homologación 2026.';
COMMENT ON COLUMN actho.fact_asistencia."afiliado_segun_hoja" IS 'Afiliado / No afiliado / Sin dato, interpretando el código de la hoja (hipótesis por confirmar).';
COMMENT ON COLUMN actho.fact_asistencia."empresa_en_crm" IS '1 si la empresa tiene registro en el CRM.';
COMMENT ON COLUMN actho.fact_asistencia."empresa_afiliada_vigente" IS '1 si la empresa tiene hoy una membresía vigente en el CRM.';

CREATE TABLE actho.fact_encuesta_evento (
    "encuesta_id" integer NOT NULL,
    "respuesta_id" text,
    "origen_encuesta" text,
    "modalidad" text,
    "fecha_respuesta" timestamp,
    "persona_id" text,
    "empresa_id" text,
    "ciudad" text,
    "calif_espacio" numeric(10,2),
    "calif_convocatoria" numeric(10,2),
    "calif_expositor" numeric(10,2),
    "calif_contenido" numeric(10,2),
    "temas_solicitados" text,
    "empresa_en_crm_origen" text,
    "metodo_asignacion_empresa" text,
    "satisfaccion_prom" numeric(10,2),
    "evento_id" integer,
    "evento_inferencia" text,
    "nivel_cargo" text,
    "afiliado_declarado" text,
    "satisfaccion_general" numeric(10,2),
    "lo_que_gusto" text,
    "a_mejorar" text,
    "nps_puntaje" integer,
    "nps_categoria" text,
    "calif_recepcion" numeric(10,2),
    "calif_manejo_tiempo" numeric(10,2),
    "calif_alimentacion" numeric(10,2),
    "acepta_tratamiento_datos" text,
    "acepta_novedades" text,
    "acepta_compartir_datos" text,
    "acepta_uso_imagen" text,
    "tipo_cruce" text,
    "anio" integer,
    "empresa_en_crm" integer,
    PRIMARY KEY (encuesta_id),
    UNIQUE (respuesta_id),
    FOREIGN KEY (empresa_id) REFERENCES actho.dim_empresa(empresa_id),
    FOREIGN KEY (persona_id) REFERENCES actho.dim_persona(persona_id),
    FOREIGN KEY (evento_id) REFERENCES actho.dim_evento(evento_id)
);

COMMENT ON COLUMN actho.fact_encuesta_evento."encuesta_id" IS 'Consecutivo de la respuesta.';
COMMENT ON COLUMN actho.fact_encuesta_evento."respuesta_id" IS 'ID de respuesta del formulario.';
COMMENT ON COLUMN actho.fact_encuesta_evento."origen_encuesta" IS 'Formulario de origen (presencial, virtual o post-evento 2026).';
COMMENT ON COLUMN actho.fact_encuesta_evento."modalidad" IS 'Presencial, Virtual o Híbrido.';
COMMENT ON COLUMN actho.fact_encuesta_evento."fecha_respuesta" IS 'Fecha y hora en que se completó la respuesta.';
COMMENT ON COLUMN actho.fact_encuesta_evento."persona_id" IS 'Código anonimizado de la persona (P-#####).';
COMMENT ON COLUMN actho.fact_encuesta_evento."empresa_id" IS 'Código anonimizado de la empresa (EMP-####). Llave común entre CRM, asistencia y encuestas.';
COMMENT ON COLUMN actho.fact_encuesta_evento."ciudad" IS 'Ciudad unificada.';
COMMENT ON COLUMN actho.fact_encuesta_evento."calif_espacio" IS 'Locación (presencial) o plataforma (virtual), 1-5.';
COMMENT ON COLUMN actho.fact_encuesta_evento."calif_convocatoria" IS 'Convocatoria y publicidad, 1-5.';
COMMENT ON COLUMN actho.fact_encuesta_evento."calif_expositor" IS 'Calidad de conferencistas / expositores, 1-5.';
COMMENT ON COLUMN actho.fact_encuesta_evento."calif_contenido" IS 'Relevancia y utilidad del contenido, 1-5.';
COMMENT ON COLUMN actho.fact_encuesta_evento."temas_solicitados" IS 'Temas pedidos en texto libre (encuestas 2025-2026).';
COMMENT ON COLUMN actho.fact_encuesta_evento."empresa_en_crm_origen" IS 'Indicador ''EMPRESA_EN_CRM'' agregado en el archivo original.';
COMMENT ON COLUMN actho.fact_encuesta_evento."metodo_asignacion_empresa" IS 'Cómo se asignó la empresa a la respuesta (correo exacto, nombre, dominio…).';
COMMENT ON COLUMN actho.fact_encuesta_evento."satisfaccion_prom" IS 'Promedio de las calificaciones 1-5 disponibles de la respuesta.';
COMMENT ON COLUMN actho.fact_encuesta_evento."evento_id" IS 'N° de evento según la hoja de homologación 2026.';
COMMENT ON COLUMN actho.fact_encuesta_evento."evento_inferencia" IS 'Resultado de inferir el evento por fecha (las encuestas no traen el evento).';
COMMENT ON COLUMN actho.fact_encuesta_evento."nivel_cargo" IS 'Nivel de cargo agrupado.';
COMMENT ON COLUMN actho.fact_encuesta_evento."afiliado_declarado" IS 'Si la persona dice ser afiliada.';
COMMENT ON COLUMN actho.fact_encuesta_evento."satisfaccion_general" IS 'Satisfacción general con el espacio, 1-5 (solo post-evento).';
COMMENT ON COLUMN actho.fact_encuesta_evento."lo_que_gusto" IS 'Lo que más gustó (texto libre).';
COMMENT ON COLUMN actho.fact_encuesta_evento."a_mejorar" IS 'Qué mejorar (texto libre).';
COMMENT ON COLUMN actho.fact_encuesta_evento."nps_puntaje" IS 'Probabilidad de recomendar, 0-10 (solo post-evento).';
COMMENT ON COLUMN actho.fact_encuesta_evento."nps_categoria" IS 'Promotor (9-10), Pasivo (7-8) o Detractor (0-6).';
COMMENT ON COLUMN actho.fact_encuesta_evento."calif_recepcion" IS 'Recepción y acompañamiento del equipo, 1-5 (solo post-evento).';
COMMENT ON COLUMN actho.fact_encuesta_evento."calif_manejo_tiempo" IS 'Manejo del tiempo, 1-5 (solo post-evento).';
COMMENT ON COLUMN actho.fact_encuesta_evento."calif_alimentacion" IS 'Alimentación, 1-5 (solo post-evento presencial).';
COMMENT ON COLUMN actho.fact_encuesta_evento."acepta_tratamiento_datos" IS 'Aceptó la política de tratamiento de datos.';
COMMENT ON COLUMN actho.fact_encuesta_evento."acepta_novedades" IS 'Quiere recibir novedades y ofertas.';
COMMENT ON COLUMN actho.fact_encuesta_evento."acepta_compartir_datos" IS 'Autoriza compartir datos con patrocinadores.';
COMMENT ON COLUMN actho.fact_encuesta_evento."acepta_uso_imagen" IS 'Autoriza el uso de su imagen.';
COMMENT ON COLUMN actho.fact_encuesta_evento."tipo_cruce" IS 'Confiabilidad del cruce con la empresa: Exacto, Aproximado, Sin coincidencia o Sin empresa.';
COMMENT ON COLUMN actho.fact_encuesta_evento."anio" IS 'Año.';
COMMENT ON COLUMN actho.fact_encuesta_evento."empresa_en_crm" IS '1 si la empresa tiene registro en el CRM.';

CREATE TABLE actho.fact_encuesta_temas (
    "encuesta_id" integer,
    "respuesta_id" text,
    "tema" text,
    "detalle" text,
    FOREIGN KEY (encuesta_id) REFERENCES actho.fact_encuesta_evento(encuesta_id)
);

COMMENT ON COLUMN actho.fact_encuesta_temas."encuesta_id" IS 'Consecutivo de la respuesta.';
COMMENT ON COLUMN actho.fact_encuesta_temas."respuesta_id" IS 'ID de respuesta del formulario.';
COMMENT ON COLUMN actho.fact_encuesta_temas."tema" IS 'Tema solicitado para próximos espacios.';
COMMENT ON COLUMN actho.fact_encuesta_temas."detalle" IS 'Detalle cuando el tema es ''Otro''.';

CREATE TABLE actho.reporte_calidad (
    "tabla" text,
    "campo" text,
    "problema" text,
    "regla_aplicada" text,
    "filas_afectadas" integer,
    "accion" text
);


CREATE TABLE actho.diccionario_datos (
    "tabla" text,
    "campo" text,
    "tipo" text,
    "descripcion" text,
    "filas" integer,
    "nulos" integer,
    "pct_nulos" numeric(10,2),
    "valores_distintos" integer,
    "ejemplo" text
);


CREATE INDEX ON actho.fact_asistencia (empresa_id);
CREATE INDEX ON actho.fact_asistencia (evento_id);
CREATE INDEX ON actho.fact_asistencia (persona_id);
CREATE INDEX ON actho.fact_encuesta_evento (empresa_id);
CREATE INDEX ON actho.fact_encuesta_evento (evento_id);
CREATE INDEX ON actho.fact_membresia (empresa_id);
CREATE INDEX ON actho.dim_empresa (estado_membresia);
CREATE INDEX ON actho.dim_empresa (ejecutiva_id);
