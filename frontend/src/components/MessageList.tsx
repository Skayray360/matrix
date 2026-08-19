/* Creado por Aldo Garcia. */
/** Lista de mensajes de la conversacion con sus fuentes citadas. */

import { useEffect, useRef } from "react";

import { Icon, BrandMark } from "./Icon";
import { Markdown } from "../security/Markdown";
import type { SourceRef } from "../services/api";

export type DisplayMessage = {
  id: string;
  role: string;
  content: string;
  sources: SourceRef[];
};

type Props = {
  messages: DisplayMessage[];
  pending: boolean;
  displayName: string;
};

export function MessageList({ messages, pending, displayName }: Props): JSX.Element {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // Se desplaza al ultimo mensaje al llegar una respuesta.
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, pending]);

  if (messages.length === 0 && !pending) {
    return (
      <div className="messages" id="conversacion">
        <div className="welcome-state">
          <span className="welcome-mark" aria-hidden="true">
            <BrandMark size={30} />
          </span>
          <span className="eyebrow">AGENTE ESPECIALIZADO DE CONOCIMIENTO</span>
          <h2>Hola, {displayName}</h2>
          <p>
            Consulte politicas y procesos de Recursos Humanos. Matrix RH limita
            cada respuesta documental a las fuentes que su perfil puede leer.
          </p>
          <p>
            Tambien puede adjuntar un archivo y pedir un resumen privado dentro de
            esta conversacion.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="messages" id="conversacion" aria-live="polite" aria-busy={pending}>
      <div className="thread">
        {messages.map((message) => {
          const known = new Set(message.sources.map((source) => source.source_id));
          // La cita en el texto pasa a ser el numero de la fuente en este
          // mensaje. Antes se imprimia el `source_id` completo entre corchetes
          // en mitad de la frase.
          const numbers = new Map(
            message.sources.map((source, index) => [source.source_id, index + 1] as const),
          );

          if (message.role === "user") {
            return (
              <article key={message.id} className="message user" data-testid="message-user">
                <div className="bubble">
                  <div className="message-role">Usted</div>
                  <Markdown text={message.content} knownSources={known} sourceNumbers={numbers} />
                </div>
              </article>
            );
          }

          return (
            <article key={message.id} className="message assistant" data-testid="message-assistant">
              <span className="message-mark" aria-hidden="true">
                <BrandMark size={17} />
              </span>
              <div className="message-body">
                <div className="message-head">
                  <span className="message-role">Matrix RH</span>
                  {message.sources.length > 0 ? (
                    <span className="grounded-badge">
                      <Icon name="check" size={11} />
                      {message.sources.length === 1
                        ? "Respaldado en 1 fuente"
                        : `Respaldado en ${message.sources.length} fuentes`}
                    </span>
                  ) : null}
                </div>

                <Markdown text={message.content} knownSources={known} sourceNumbers={numbers} />

                {message.sources.length > 0 ? (
                  <div className="sources" data-testid="sources">
                    <h4>Fuentes</h4>
                    <ul>
                      {message.sources.map((source, index) => (
                        <li key={source.source_id}>
                          <span className="source-chip" title={source.source_id}>
                            <span className="n" aria-hidden="true">
                              {index + 1}
                            </span>
                            <span className="name">{source.label}</span>
                            <span className="category">{source.category}</span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            </article>
          );
        })}

        {pending ? (
          <article className="message assistant" data-testid="message-pending">
            <span className="message-mark" aria-hidden="true">
              <BrandMark size={17} />
            </span>
            <div className="message-body">
              <div className="message-head">
                <span className="message-role">Matrix RH</span>
              </div>
              <div className="typing-indicator" role="status">
                <span aria-hidden="true" />
                <span aria-hidden="true" />
                <span aria-hidden="true" />
                <p>Consultando fuentes autorizadas</p>
              </div>
            </div>
          </article>
        ) : null}

        <div ref={endRef} />
      </div>
    </div>
  );
}
