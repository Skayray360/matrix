<!-- Creado por Aldo Garcia. -->

# app/agents/

Agentes runtime.

| Archivo | Contenido |
|---|---|
| `orchestrator.py` | Autoriza, elige herramientas y modelo, audita |
| `knowledge_agent.py` | Sintetiza sobre evidencia autorizada y verifica grounding |
| `prompts.py` | System policy y bloques separados del prompt |
| `query_planner.py` | Lenguaje natural → plan JSON validado |

## Asimetría deliberada

El Agente de Conocimiento **no recibe** el motor de políticas ni el vector store:
sólo objetos `Evidence` ya autorizados. Es una restricción de diseño, no una
convención. Aunque una inyección de prompt lo convenciera, no hay nada que pueda
ejecutar.

## Orden del orquestador

`autenticar → intención → autorizar la fuente aplicable → herramientas →
recuperar sólo lo permitido → validar suficiencia → elegir modelo → sintetizar →
verificar citas → auditar → responder`

`identity` responde sin modelo. `general` y `conversational` pueden usar un modelo
sin tocar RAG. En intenciones documentales, un conjunto autorizado vacío o una
recuperación sin evidencia nunca habilitan conocimiento general como reemplazo.

## Contratos visibles

- La identidad del asistente es siempre **Matrix RH**, independientemente del
  modelo elegido por el router; la respuesta de identidad es exacta y no llama a
  Ollama.
- Una pregunta documental, incluido el resumen de un adjunto, sólo puede usar
  evidencia recuperada y autorizada.
- La capacidad del modelo se usa para comprender, resumir, comparar y redactar;
  nunca para ampliar el alcance documental ni completar huecos sin fuente.
- El resumen interno de una conversación larga conserva continuidad de diálogo;
  no se usa como evidencia documental.
- La ruta `general` puede explicar, idear o redactar sin fuentes internas, pero no
  presenta conocimiento del modelo como política de la empresa.
