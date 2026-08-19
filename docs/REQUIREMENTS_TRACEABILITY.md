# Matriz de trazabilidad — Matrix RH

> Creado por Aldo Garcia.
> `requisito -> componente -> prueba -> evidencia`

Estado: ✅ comprobado offline · ⚠️ cumplido con matiz documentado ·
🟠 pendiente de gate live en destino · 🔵 preparado, no conectado

Las cifras cerradas de cobertura y pass rate pertenecen al reporte generado por
la validación. Para la versión 1.1.0 no deben copiarse resultados de una versión
anterior: la fuente de verdad es `reports/final-validation.json` producido en el
equipo donde se instala el paquete.

---

## 1. Reglas innegociables (sección 1)

| # | Requisito | Componente | Prueba | Estado |
|---|---|---|---|---|
| 1 | El proyecto se llama Matrix RH | `Settings.app_name`, `README.md` | `test_health_no_depende_de_dependencias` | ✅ |
| 2 | Backend en Python 3.12 | `pyproject.toml` `requires-python` | `scripts.preflight::check_python` | ✅ |
| 3 | Tres modelos Ollama exactos | `Settings.ollama_*_model` | `test_modelos_por_defecto_son_los_declarados` | ✅ |
| 4 | No sustituir por modelos cloud | `FORBIDDEN_MODEL_PATTERN` | `test_los_modelos_configurados_no_son_cloud` | ✅ |
| 5 | URL de Ollama configurable, local por defecto | `Settings.ollama_base_url` | `test_url_de_ollama_es_local_por_defecto` | ✅ |
| 6 | Validar los tres modelos y el endpoint de embeddings al arrancar | `scripts.preflight::check_ollama` | contrato offline; preflight live pendiente | 🟠 |
| 7 | Dimensión 768 comprobada en runtime; fallo diagnóstico | `OllamaClient.embed`, `probe_embedding_dimension` | regresión offline; probe live pendiente | 🟠 |
| 8 | Ollama no expuesto a Internet | `docker-compose.yml`, `docs/SECURITY.md` §12 | revisión | ✅ |
| 9 | Mínimo privilegio, deny-by-default, defensa en profundidad | `PolicyEngine`, roles sin permisos de secretos | `TestMatrizDeAutorizacion` | ✅ |
| 10 | El LLM nunca recibe lo que el usuario no puede ver | Filtro ACL en la consulta a Qdrant | golden set `denied` 14/14 | ✅ |
| 11 | Autorizar **antes** de RAG, SQL y prompt | `Orchestrator.handle_chat` | `smoke_authorization` | ✅ |
| 12 | Prohibido almacenar secretos en código, frontend, Git, imágenes o logs | `secrets_scan`, `redaction` | `scripts.secrets_scan` → PASS | ✅ |
| 13 | Secretos por entorno; sólo `.env.example` | `Settings` con `SecretStr`, `.gitignore` | escaneo | ✅ |
| 14 | Código limpio, sin archivos `*_fix`/`*_new` | árbol del repositorio | inspección | ✅ |
| 15 | Refactorizar la causa raíz y ejecutar regresión | `reports/agent_reviews/architecture.md` §3 | suites completas | ✅ |
| 16 | Encabezado "Creado por Aldo Garcia." en todo archivo propio | todos los archivos | `verify_headers` (sección 5) | ✅ |
| 17 | Docstrings y comentarios que expliquen la intención | todos los módulos | revisión | ✅ |
| 18 | `README.md` por carpeta propia versionada | árbol de fuentes, configuración, corpus, pruebas e infraestructura | inspección | ✅ |
| 19 | Excluir carpetas generadas o de terceros | `.gitignore` | inspección | ✅ |
| 20 | ≥98 % de pruebas y 100 % de gates críticos | suites | `reports/final-validation.json` de la 1.1.0 | ⚠️ se decide al ejecutar el gate |
| 21 | El 98 % no compensa un fallo de seguridad | gates independientes en `run_quality_gate` | — | ✅ |
| 22 | Cero Critical y High | `bandit`, `pip-audit`, revisión | `reports/agent_reviews/cybersecurity.md` | ✅ |
| 23 | Cero secretos reales | `scripts.secrets_scan` | PASS | ✅ |
| 24 | E2E críticos al 100 % | `frontend/tests/e2e/` | specs revisados; navegador live pendiente | 🟠 |
| 25 | Reconocer información insuficiente; prohibido inventar | `KnowledgeAgent`, `INSUFFICIENT_ANSWER` | golden set `unsupported` 3/3 | ✅ |
| 26 | Trazabilidad de todo hecho a una fuente | `verify_grounding`, `StructuredEvidence` | `test_source_id_inventado_se_rechaza` | ✅ |
| 27 | Los documentos son datos, no instrucciones | `SYSTEM_POLICY` regla 5, `prompt_guard` | E2E 14 | ✅ |
| 28 | Sin información real sensible en pruebas | corpus y fixtures sintéticos | inspección | ✅ |
| 29 | Ejecutable desde cero siguiendo el README | `INSTALAR_MATRIX_RH.bat` | gate requerido en Windows limpio | 🟠 |
| 30 | Sin TODOs críticos, mocks activos ni rutas sin implementar | árbol | inspección | ✅ |
| 31 | Testeable sin Entra ID mediante proveedor local con el mismo modelo | `LocalTestIdentityProvider` + `PolicyEngine` | `smoke_authorization` | ✅ |
| 32 | El modo local no puede habilitarse en producción | `Settings._validate_environment_safety` | `TestSeguridadDeEntorno` (4 casos) | ✅ |
| 33 | Dos usuarios sintéticos con los accesos indicados | `seeds/identity_seed.py` | `TestSeedDeIdentidad` | ✅ |
| 34 | Hash Argon2id, nunca texto plano; advertencia documentada | `local_credentials` | `test_la_contrasena_no_se_guarda_en_texto_plano` | ✅ |
| 35 | El administrador no obtiene secretos ni SQL arbitrario | catálogo de permisos sin esos verbos | `test_matrix_accede_al_diagnostico_sin_secretos` | ✅ |
| 36 | `MatrixR1` con la misma interfaz y sin acceso a otras categorías | `ChatPage` único; backend deniega | golden set + E2E 02 | ✅ |
| 37 | No inventar conexiones externas; dejar adapter, config, health, pruebas y guía | `entra_provider`, `adapters` | `EXTERNAL_DEPENDENCIES_STATUS.md` | 🔵 |
| 38 | Una dependencia no disponible no bloquea la entrega si se marca | estados de integración | `/admin/diagnostics` | 🔵 |
| 39 | Cuatro `.bat` mínimos en la raíz, sin lógica duplicada | 6 `.bat` + `windows/*.ps1` | `check_windows_scripts` | ✅ |
| 40 | Arranque por doble clic con preflight y diagnóstico legible | `Start-MatrixRH.ps1` | implementación revisada; arranque live pendiente | 🟠 |
| 41 | Instalador con detección, idempotencia, preflight y errores accionables | `Install-MatrixRH.ps1` | implementación revisada; instalación live pendiente | 🟠 |
| 42 | Estado no validado documentado en tres sitios | README §12, `EXTERNAL_DEPENDENCIES_STATUS.md`, README de integración | inspección | ✅ |

---

## 1.1. Trazabilidad de la entrega 1.1.0

| Necesidad | Contrato implementado | Evidencia de regresión |
|---|---|---|
| Aprovechar ambos modelos locales | Gemma atiende la ruta rápida; Qwen se selecciona por profundidad, consulta larga, categorías múltiples, baja confianza, modo mixto o resumen extenso | `test_ai_runtime_contracts.py`, `test_model_policy.py` |
| Resumir archivos cargados sin falso vacío | Recuperación privada por propietario y conversación, resumen jerárquico y cierre extractivo citado si la regeneración no queda sustentada | `test_ai_runtime_contracts.py`, `test_rag_pipeline_isolated.py` |
| Reducir latencia | Selección temprana de modelo, conexión HTTP reutilizable, `keep_alive`, caché LRU de embeddings y mapas de resumen con paralelismo acotado | `test_ai_runtime_contracts.py` |
| Separar documentación general y especializada | Rutas oficiales `general/**` y `especializadas/<dominio>/**`, compatibilidad legacy sin mover el corpus y categorías nuevas cerradas por defecto | `test_knowledge_layout.py`, `test_access_profile_contract.py` |
| Renovar la presentación sin romper integraciones | La UI conserva sesión, CSRF, conversaciones, chat y carga privada; accesos rápidos sólo envían prompts | pruebas Vitest y E2E descritas en `docs/E2E.md` |
| Identidad constante y respuestas documentales sustentadas | La identidad devuelve exactamente `Soy Matrix RH.` sin LLM; las preguntas RH/documentales fallan cerradas sin citas autorizadas | `test_ai_runtime_contracts.py`, golden set |
| Aplicar la matriz de acceso | Perfil base obligatorio, roles HCM acumulativos, revocación en sincronización y carga/resumen administrativo limitados a la categoría efectiva | `test_access_profile_contract.py`, `test_entra_role_sync.py`, `test_admin_category_scope.py` |

---

## 2. Arquitectura runtime (sección 3)

| Componente | Módulo | Prueba |
|---|---|---|
| API Gateway | `app/api/` | `TestSalud`, `TestCabecerasYErrores` |
| Authorization Guard | `app/authorization/` | `TestFirmaDelContexto`, `TestMatrizDeAutorizacion` |
| Orquestador | `app/agents/orchestrator.py` | `test_ai_runtime_contracts.py`, `smoke_authorization`, golden set |
| Agente de Conocimiento | `app/agents/knowledge_agent.py` | `TestAgenteDeConocimiento` |
| RAG Tool | `app/rag/retriever.py` | `test_ai_runtime_contracts.py`, `TestFiltroAclDeQdrant`, golden set |
| Structured Data Tool | `app/structured_data/` | `test_structured_query.py` (30 casos) |
| Model Router | `app/llm/model_policy.py` | `test_ai_runtime_contracts.py`, `test_model_policy.py` |
| Memory Manager | `app/memory/service.py` | `TestOwnershipDeConversaciones` |
| Ingestion Service | `app/ingestion/` | `test_loaders.py`, reconciliación real |
| Scheduler | `app/jobs/scheduler.py` | lock de `reconcile_with_lock` |
| Audit & Observability | `app/audit/`, `app/common/logging.py` | `TestRedaccion` |

---

## 3. Parámetros del RAG (sección 9)

| Parámetro | Valor | Prueba |
|---|---|---|
| `RAG_CHUNK_SIZE_TOKENS` | 900 | `test_valores_por_defecto_son_los_exigidos` |
| `RAG_CHUNK_OVERLAP_TOKENS` | 120 | ídem |
| `RAG_EMBEDDING_DIMENSION` | 768 | ídem + preflight |
| `RAG_TOP_K` | 6 | ídem |
| `RAG_FETCH_K` | 24 | ídem |
| `RAG_MIN_SIMILARITY` | 0.35 | ídem |
| `RAG_MMR_LAMBDA` | 0.65 | ídem |
| `RAG_REINDEX_INTERVAL_HOURS` | 24 | ídem |
| `OLLAMA_FAST_NUM_CTX` / `OLLAMA_FAST_MAX_TOKENS` | 8192 / 768 | `test_ai_runtime_contracts.py` |
| `OLLAMA_DEEP_NUM_CTX` / `OLLAMA_DEEP_MAX_TOKENS` | 32768 / 2048 | ídem |
| `OLLAMA_KEEP_ALIVE` | 15m | ídem + snapshot de diagnóstico |
| `OLLAMA_EMBEDDING_CACHE_SIZE` | 256 | ídem; caché por SHA, sin conservar texto |
| `RAG_SUMMARY_SCAN_MAX_CHUNKS` | 256 | ídem; truncamiento visible |
| `RAG_SUMMARY_MAX_CHUNKS` | 24 | ídem |
| `OLLAMA_SUMMARY_PARALLEL_BATCHES` | 2 | ídem |
| chunk > overlap | validado | `test_chunk_size_debe_superar_al_overlap` |
| fetch_k ≥ top_k | validado | `test_fetch_k_no_puede_ser_menor_que_top_k` |
| MMR ∈ [0,1] | validado | `test_mmr_lambda_fuera_de_rango_se_rechaza` |
| dimensión coincide | validado | `test_dimensiones_deben_coincidir` |

---

## 4. Matriz de autorización (sección 6.1)

| Recurso | `Matrix` | `MatrixR1` | Prueba |
|---|---|---|---|
| `prestaciones` RAG | ALLOW | ALLOW | golden set `prest-01..08` |
| `nomina` RAG | ALLOW | DENY | `nom-01..05` |
| `reclutamiento` RAG | ALLOW | DENY | `rec-01..05` |
| `relaciones_laborales` RAG | ALLOW | DENY | `rel-01..05` |
| `salud_ambiental` RAG | ALLOW | DENY | `sal-01..05` |
| Categorías nuevas | DENY hasta política/rol explícito | DENY | `test_access_profile_contract.py` |
| Fuentes estructuradas | ALLOW concedidas | DENY | `test_fuentes_estructuradas_denegadas_por_defecto` |
| Administración de conocimiento | ALLOW | DENY | `TestEscaladaDeRol` |
| Administración de usuarios/roles | ALLOW | DENY | ídem |
| Secretos/configuración | DENY | DENY | `test_ninguna_respuesta_expone_secretos` |

---

## 5. Verificación de encabezados de autoría

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.verify_headers
```

Comprueba que todo archivo propio versionado lleva la leyenda exacta según su
lenguaje, y excluye las carpetas generadas o de terceros.

---

## 6. Defectos y sus pruebas de regresión

| ID | Defecto | Prueba que lo cubre |
|---|---|---|
| DEF-001 | Path traversal con ruta absoluta POSIX | `test_rechaza_path_traversal[/etc/passwd]` |
| DEF-002 | Evento de auditoría no escribible | migración `0002` + `smoke_authorization` |
| DEF-003 | Validación de carga tras tocar infraestructura | `TestCargaDeArchivos` (4 casos) |
| DEF-004 | `ContextVar` con default mutable | revisión + `TestRedaccion` |
| DEF-005 | Interpolación de identificadores en SQL | `TestVerificacionPorAst` (11 casos) |
| DEF-006 | Router clasificaba mal preguntas documentales | `test_consulta_simple_usa_ruta_rapida` |
| DEF-007 | Documento corto en un solo chunk | `test_los_encabezados_abren_chunk_nuevo` |
| DEF-008 | Falta de prefijos de tarea de embeddings | pruebas de prefijos; golden set live requerido para 1.1.0 |
| DEF-009 | Sesión MySQL única durante horas | golden set en modo generación |
| DEF-010 | `trigger` palabra reservada | migración `0001` aplicada |
| DEF-011 | Anotación de retorno ambigua en la ruta SPA | colección de la suite de integración |
