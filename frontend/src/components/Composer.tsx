/* Creado por Aldo Garcia. */
/**
 * Composer: texto + adjuntos.
 *
 * Distingue visualmente el adjunto privado de conversacion del conocimiento
 * corporativo permanente: el texto bajo el campo lo dice explicitamente,
 * porque confundir ambos es la forma mas facil de publicar por accidente un
 * documento personal en la base corporativa.
 *
 * La zona de arrastre ya no ocupa sitio de forma permanente: el archivo se
 * adjunta con el clip, y el area de soltar solo se dibuja mientras se arrastra
 * algo encima.
 */

import { useEffect, useRef, useState, type DragEvent, type KeyboardEvent } from "react";

import { Icon, type IconName } from "./Icon";
import type { DocumentStatus } from "../services/api";

type Props = {
  disabled: boolean;
  attachments: DocumentStatus[];
  onSend: (message: string) => void;
  onUpload: (files: File[]) => void;
};

const ACCEPTED = ".docx,.md,.pdf,.txt,.xlsx,.csv";

/** El estado se lee por icono ademas de por color: el color solo no basta. */
function statusIcon(status: string): IconName {
  if (status === "indexed") return "check";
  if (status === "failed") return "alert";
  return "spinner";
}

export function Composer({ disabled, attachments, onSend, onUpload }: Props): JSX.Element {
  const [text, setText] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const textarea = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const control = textarea.current;
    if (!control) return;
    control.style.height = "auto";
    control.style.height = `${Math.min(control.scrollHeight, 180)}px`;
  }, [text]);

  function submit(): void {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    // Enter envia; Shift+Enter inserta salto de linea.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    setDragging(false);
    const files = Array.from(event.dataTransfer.files ?? []);
    if (files.length > 0) onUpload(files);
  }

  return (
    <div
      className="composer"
      id="composer-area"
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(event) => {
        // Solo se apaga al salir del contenedor, no al pasar entre sus hijos.
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setDragging(false);
        }
      }}
      onDrop={handleDrop}
    >
      {dragging ? (
        <div className="drop-overlay" aria-hidden="true">
          <Icon name="paperclip" size={22} />
          Suelte el archivo para analizarlo aqui
          <small>{ACCEPTED}</small>
        </div>
      ) : null}

      <div className="composer-stack">
        {attachments.length > 0 ? (
          <div className="attachments" data-testid="attachments">
            {attachments.map((attachment) => (
              <span
                key={attachment.id}
                className="attachment"
                data-status={attachment.status}
                title={attachment.error_message ?? attachment.status}
              >
                <Icon name={statusIcon(attachment.status)} size={13} />
                <span className="filename">{attachment.filename}</span>
                <span className="status">
                  {attachment.status}
                  {attachment.status === "indexed" ? ` · ${attachment.chunk_count} fragmentos` : ""}
                </span>
              </span>
            ))}
          </div>
        ) : null}

        <div className="composer-inner">
          <label className="visually-hidden" htmlFor="composer-input">
            Mensaje para Matrix RH
          </label>
          <textarea
            ref={textarea}
            id="composer-input"
            data-testid="composer-input"
            placeholder="Pregunte sobre Recursos Humanos o solicite el resumen de un adjunto..."
            value={text}
            maxLength={8000}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={handleKeyDown}
            aria-label="Mensaje para Matrix RH"
          />

          <div className="composer-actions">
            <button
              type="button"
              className="icon-button"
              onClick={() => fileInput.current?.click()}
              disabled={disabled}
              aria-label="Adjuntar archivo a esta conversacion"
              title="Adjuntar archivo a esta conversacion"
            >
              <Icon name="paperclip" size={17} />
            </button>
            <input
              ref={fileInput}
              type="file"
              accept={ACCEPTED}
              multiple
              hidden
              aria-label="Adjuntar archivos a la conversacion"
              onChange={(event) => {
                const files = Array.from(event.target.files ?? []);
                if (files.length > 0) onUpload(files);
                event.target.value = "";
              }}
            />

            <span className="composer-hint">Enter envia · Shift+Enter salto de linea</span>
            <span className="character-count">{text.length} / 8000</span>
            <button
              className="send-button"
              type="button"
              onClick={submit}
              disabled={disabled || text.trim().length === 0}
              data-testid="send-button"
            >
              Enviar
              <Icon name="send" size={15} />
            </button>
          </div>
        </div>

        <p className="composer-note">
          Arrastre un archivo ({ACCEPTED}) o use el clip para analizarlo{" "}
          <strong>solo en esta conversacion</strong>.
        </p>
      </div>
    </div>
  );
}
