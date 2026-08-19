/* Creado por Aldo Garcia. */
/**
 * Pantalla principal de chat.
 *
 * Punto importante del diseno: `Matrix` y `MatrixR1` ven **exactamente la misma
 * interfaz**. No hay ninguna opcion oculta por rol. La diferencia de informacion
 * proviene unicamente del backend y sus politicas; ocultar un boton nunca es un
 * control de seguridad.
 */

import { useCallback, useEffect, useState } from "react";

import { Composer } from "../components/Composer";
import { Icon } from "../components/Icon";
import { MessageList, type DisplayMessage } from "../components/MessageList";
import { QuickActions } from "../components/QuickActions";
import { Sidebar } from "../components/Sidebar";
import { ThemeControl } from "../components/ThemeControl";
import { TracePanel, type ExecutionTrace } from "../components/TracePanel";
import {
  api,
  ApiError,
  type ConversationSummary,
  type DocumentStatus,
  type Me,
} from "../services/api";

type Props = {
  me: Me;
  onLogout: () => void | Promise<void>;
};

/** Iniciales para el avatar de identidad. Nunca mas de dos letras. */
function initials(displayName: string): string {
  const parts = displayName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toLocaleUpperCase("es");
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toLocaleUpperCase("es");
}

export function ChatPage({ me, onLogout }: Props): JSX.Element {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [attachments, setAttachments] = useState<DocumentStatus[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [trace, setTrace] = useState<ExecutionTrace | null>(null);

  const describeError = useCallback((caught: unknown): string => {
    if (caught instanceof ApiError) {
      return caught.requestId
        ? `${caught.message} (referencia: ${caught.requestId})`
        : caught.message;
    }
    return "No fue posible completar la operacion.";
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await api.listConversations());
    } catch (caught) {
      setError(describeError(caught));
    }
  }, [describeError]);

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  const openConversation = useCallback(
    async (id: string) => {
      setError(null);
      setSidebarOpen(false);
      try {
        const detail = await api.getConversation(id);
        setActiveId(detail.id);
        setAttachments(detail.attachments);
        // La traza corresponde exclusivamente a la ultima respuesta recibida
        // en la conversacion activa. No se reutiliza metadata de otra sesion.
        setTrace(null);
        setMessages(
          detail.messages.map((message) => ({
            id: message.id,
            role: message.role,
            content: message.content,
            // El detalle guarda los source_id citados; la etiqueta legible se
            // reconstruye a partir del propio identificador.
            sources: message.sources.map((source) => ({
              source_id: source.source_id,
              category: source.source_id.split("/")[0] ?? "",
              filename: source.source_id.split("/").slice(1).join("/"),
              section: "",
              page_or_sheet: "",
              score: 0,
              label: source.source_id,
              scope: "corporate",
            })),
          })),
        );
      } catch (caught) {
        setError(describeError(caught));
      }
    },
    [describeError],
  );

  const startConversation = useCallback(async () => {
    setError(null);
    setSidebarOpen(false);
    try {
      const created = await api.createConversation();
      setActiveId(created.id);
      setMessages([]);
      setAttachments([]);
      setTrace(null);
      await refreshConversations();
    } catch (caught) {
      setError(describeError(caught));
    }
  }, [describeError, refreshConversations]);

  const removeConversation = useCallback(
    async (id: string) => {
      try {
        await api.deleteConversation(id);
        if (id === activeId) {
          setActiveId(null);
          setMessages([]);
          setAttachments([]);
          setTrace(null);
        }
        await refreshConversations();
      } catch (caught) {
        setError(describeError(caught));
      }
    },
    [activeId, describeError, refreshConversations],
  );

  const sendMessage = useCallback(
    async (text: string) => {
      setError(null);
      setPending(true);
      const optimisticId = `local-${Date.now()}`;
      setMessages((current) => [
        ...current,
        { id: optimisticId, role: "user", content: text, sources: [] },
      ]);
      try {
        const reply = await api.chat(text, activeId);
        setActiveId(reply.conversation_id);
        setMessages((current) => [
          ...current,
          {
            id: reply.message_id,
            role: "assistant",
            content: reply.answer,
            sources: reply.sources,
          },
        ]);
        setTrace({
          conversationId: reply.conversation_id,
          intent: reply.intent,
          grounded: reply.grounded,
          latencyMs: reply.latency_ms,
          sources: reply.sources,
        });
        await refreshConversations();
      } catch (caught) {
        setError(describeError(caught));
        // Se retira el mensaje optimista: no se envio realmente.
        setMessages((current) => current.filter((message) => message.id !== optimisticId));
      } finally {
        setPending(false);
      }
    },
    [activeId, describeError, refreshConversations],
  );

  const uploadFiles = useCallback(
    async (files: File[]) => {
      setError(null);
      let conversationId = activeId;
      try {
        if (!conversationId) {
          const created = await api.createConversation();
          conversationId = created.id;
          setActiveId(created.id);
          setTrace(null);
          await refreshConversations();
        }
        const result = await api.uploadAttachments(conversationId, files);
        setAttachments((current) => [...current, ...result.documents]);
      } catch (caught) {
        setError(describeError(caught));
      }
    },
    [activeId, describeError, refreshConversations],
  );

  return (
    <div className="app-shell">
      <a className="skip-link" href="#conversacion">
        Ir a la conversacion
      </a>

      <Sidebar
        open={sidebarOpen}
        conversations={conversations}
        activeId={activeId}
        onSelect={openConversation}
        onCreate={startConversation}
        onDelete={removeConversation}
        onClose={() => setSidebarOpen(false)}
      />

      <header className="app-header">
        <div className="header-title-group">
          <button
            className="icon-button menu-toggle"
            type="button"
            onClick={() => setSidebarOpen((open) => !open)}
            aria-expanded={sidebarOpen}
            aria-controls="conversaciones"
            aria-label="Conversaciones"
            title="Conversaciones"
          >
            <Icon name="menu" />
          </button>
          <div>
            <h1 className="app-title">Recursos Humanos</h1>
            <span className="app-subtitle">Agente especializado de conocimiento</span>
          </div>
        </div>

        <div className="header-actions">
          <span className="local-badge">100% local</span>

          <ThemeControl />

          <button
            className="toggle-button"
            type="button"
            onClick={() => setInspectorOpen((open) => !open)}
            aria-expanded={inspectorOpen}
            aria-label="Mostrar u ocultar trazabilidad"
            title="Trazabilidad"
          >
            <Icon name="panel" size={17} />
            <span className="label">Trazabilidad</span>
          </button>

          <span className="header-divider" aria-hidden="true" />

          <div className="identity">
            <span className="avatar" aria-hidden="true">
              {initials(me.display_name)}
            </span>
            <span className="identity-text">
              <span className="identity-name" data-testid="identity-user">
                {me.display_name}
              </span>
              <span className="identity-meta">
                <span data-testid="identity-source">{me.auth_source}</span>
                <span className="sep" aria-hidden="true">
                  ·
                </span>
                <span data-testid="identity-scope">
                  {me.category_wildcard
                    ? "acceso de negocio ampliado"
                    : `${me.allowed_categories.length} categoria(s)`}
                </span>
              </span>
            </span>
          </div>

          <button className="secondary-button" type="button" onClick={() => void onLogout()}>
            Salir
          </button>
        </div>
      </header>

      {/* El aviso ocupa su propia fila de la rejilla. Antes flotaba sobre la
          conversacion y tapaba el primer mensaje. */}
      {error ? (
        <div className="banner" role="alert" data-testid="error-banner">
          <Icon name="alert" size={17} />
          <p>{error}</p>
          <button type="button" onClick={() => setError(null)} aria-label="Cerrar aviso">
            <Icon name="close" size={16} />
          </button>
        </div>
      ) : null}

      <QuickActions disabled={pending} onSelect={(prompt) => void sendMessage(prompt)} />

      <main className={`main${inspectorOpen ? " inspector-open" : ""}`}>
        <section className="chat-surface" aria-label="Conversacion con Matrix RH">
          <MessageList messages={messages} pending={pending} displayName={me.display_name} />

          <Composer
            disabled={pending}
            attachments={attachments}
            onSend={(text) => void sendMessage(text)}
            onUpload={(files) => void uploadFiles(files)}
          />
        </section>

        {inspectorOpen ? (
          <TracePanel trace={trace} onClose={() => setInspectorOpen(false)} />
        ) : null}
      </main>

      {sidebarOpen ? (
        <button
          className="scrim"
          type="button"
          aria-label="Cerrar conversaciones"
          onClick={() => setSidebarOpen(false)}
        />
      ) : null}
    </div>
  );
}
