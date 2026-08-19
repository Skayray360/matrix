# Auditoría de entrega 1.1.0 — Matrix RH

> Creado por Aldo Garcia.
> Fecha de corte: 2026-08-12.

## Veredicto

**Estado: listo para validación integral en el equipo Windows destino.**

Las comprobaciones offline de la versión 1.1.0 están en `PASS`: regresiones de
backend, contrato de modelos y resumen, perfiles HCM, taxonomía documental,
alcance administrativo, componentes/build del frontend, encabezados y enlaces
de documentación.

Esta sesión no ejecutó WAMP/MySQL, Qdrant, los tres modelos Ollama ni un
navegador Windows. En consecuencia, **no se declara aprobación operativa final,
pass rate global, cobertura final ni latencias live**. Esas cifras sólo son
válidas cuando `windows\Validate-MatrixRH.ps1` termina con código 0 y genera
`reports/final-validation.json` en el equipo de instalación.

## Alcance comprobado offline

| Gate | Estado | Evidencia |
|---|---|---|
| Identidad literal | `PASS` | «¿Quién eres?» devuelve `Soy Matrix RH.` sin LLM/RAG |
| Separación general/documental | `PASS` | RH y referencias a documentos fallan cerradas sin citas; general sólo fuera de ese ámbito |
| Routing local | `PASS` | Gemma por defecto; Qwen por señales auditables de complejidad o resumen largo |
| Resumen de adjuntos | `PASS` | scroll privado por usuario/conversación, límite visible, map/reduce y fallback extractivo citado |
| Perfiles HCM | `PASS` | base obligatoria, roles acumulativos, revocación y segregación de Nómina |
| Gobierno documental | `PASS` | `general/**`, `especializadas/<dominio>/**`, compatibilidad legacy y categorías nuevas cerradas |
| Alcance administrativo | `PASS` | carga y resumen intersectan `knowledge.admin` con categorías efectivas |
| Fuentes estructuradas | `PASS` | concesiones materializadas desde catálogo, permiso funcional y rol; coordinadores sin consulta |
| Frontend | `PASS` offline | conserva API, sesión, CSRF, conversaciones, carga privada y chat |
| Documentación | `PASS` | comandos, enlaces, autoría y límites revisados contra el código |

## Alcance estructurado efectivo

Los perfiles corporativos no reciben conectores por wildcard. Se requieren a la
vez `structured.query` y una fila `StructuredSourcePermission`:

| Rol HCM | Fuentes concedidas |
|---|---|
| `hcm_adm_ia_matrix` | `rh_demo`, `postgres_analytics` |
| `hcm_adm_admpersonal` | `sap_hcm`, `oracle_hcm` |
| cualquier `hcm_coord_*` | ninguna; tampoco recibe `structured.query` |
| otros `hcm_adm_*` | ninguna hasta declaración explícita |

`matrix_admin_test` conserva las cuatro fuentes como fixture de desarrollo; no
es un perfil corporativo ni se permite en producción. Que una fuente esté
concedida no significa que esté conectada: además debe estar habilitada, tener
DSN read-only y superar su health check.

## Gates pendientes en el equipo destino

| Gate live | Criterio de aprobación |
|---|---|
| Instalador Windows | `INSTALAR_MATRIX_RH.bat` termina en código 0 desde una carpeta limpia |
| MySQL/MariaDB de WAMP | base propia, migraciones y seed completan sin afectar bases ajenas |
| Qdrant | colecciones, upsert, scroll privado, búsqueda ACL y reconciliación operan |
| Ollama | modelos exactos presentes; generación real y embedding de dimensión 768 |
| RAG live | golden set dentro del umbral y fuga ACL igual a cero |
| Frontend E2E visual | login, chat, carga, resumen, fuentes, denegaciones, CSRF y logout en navegador real |
| Arranque | `/health`, `/ready`, frontend same-origin y parada limpia |

## Procedimiento de aceptación

1. Extraiga el ZIP en una ruta nueva y estable.
2. Inicie WAMP/MySQL y Ollama; confirme los tres modelos con `ollama list`.
3. Ejecute `INSTALAR_MATRIX_RH.bat`.
4. Ejecute `INICIAR_MATRIX_RH.bat` y pruebe un resumen de archivo adjunto.
5. Ejecute `windows\Validate-MatrixRH.ps1` sin `-SkipE2E` ni `-QuickRag` para el cierre.
6. Acepte la entrega sólo si el BAT devuelve 0 y
   `reports/final-validation.json` no contiene gates críticos abiertos.

Si algo falla, ejecute `DIAGNOSTICO_MATRIX_RH.bat` y corrija el primer `FAIL`.
No copie secretos ni cree PID, tablas o ACL manualmente.

## Condiciones antes de producción

- conectar y validar un tenant Entra real;
- deshabilitar las cuentas y el proveedor `local_test`;
- usar secretos externos y cuentas de base con mínimo privilegio;
- validar por separado Nómina General y Nómina Confidencial;
- habilitar sólo conectores con DSN read-only y pruebas positivas/negativas;
- repetir el gate integral en la topología productiva.
