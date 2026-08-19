<!-- Creado por Aldo Garcia. -->

# Validación del release 1.1.0

Fecha: 2026-08-12.

Revisión r1: corrige la detección de la salida oficial de `uv 0.11.33`, que
puede incluir hash y fecha de compilación antes de
`x86_64-pc-windows-msvc`.

Este informe corresponde al contenido exacto preparado para
`MatrixRH-1.1.0.zip`. No contiene rutas, credenciales ni datos del equipo de
validación.

## Resultado reproducible sin servicios externos

| Gate | Resultado |
|---|---|
| Backend | 495 PASS, 154 SKIP por dependencias live, 0 FAIL |
| Cobertura offline | 72 % total; rutas live/API sin servicios bajan el agregado |
| Frontend | TypeScript PASS, Vitest 14/14, Vite build PASS |
| Playwright | 28 flujos descubiertos; ejecución live pendiente |
| Ruff | PASS |
| mypy | PASS en 82 archivos fuente |
| Lock Python | `uv lock --check --offline` PASS, 95 paquetes resueltos |
| Cadena npm | PASS, 151 manifiestos instalados revisados |
| Secretos | PASS, 0 secretos reales |
| Encabezados | PASS, 257 archivos revisados en el paquete extraído |

## Flujos corregidos

- El resumen de adjuntos recupera todos los fragmentos privados autorizados por
  usuario y conversación, sin depender del umbral semántico de una consulta
  genérica como “resume este archivo”.
- Los archivos extensos usan resumen jerárquico: Gemma procesa lotes y Qwen
  integra el resultado cuando el contexto lo requiere.
- La identidad se responde de forma determinista: `Soy Matrix RH.`
- Las consultas de RH son documentales y fallan cerrado si no existe evidencia
  autorizada; las consultas generales siguen una ruta separada sin citas falsas.
- El layout oficial admite `general/**` y
  `especializadas/<categoria>/**`, conservando compatibilidad con el layout
  anterior.
- Los perfiles HCM se sincronizan de forma revocable y los permisos de
  categorías y conectores se materializan en la base de datos.

## Validación pendiente del equipo destino

El ZIP no declara como aprobadas las dependencias que no estaban disponibles en
este entorno de construcción: Windows/PowerShell, WAMP MySQL, Ollama con los tres
modelos, Qdrant y los flujos E2E de navegador con la pila completa. El operador
debe ejecutar `INSTALAR_MATRIX_RH.bat` y después
`DIAGNOSTICO_MATRIX_RH.bat`; esos scripts conservan el código de salida y no
convierten un bloqueo externo en PASS.
