/* Creado por Aldo Garcia. */
/** Trazabilidad segura de la ultima respuesta: solo metadatos ya autorizados. */

import { Icon } from "./Icon";
import type { SourceRef } from "../services/api";

export type ExecutionTrace = {
  conversationId: string;
  intent: string;
  grounded: boolean;
  latencyMs: number;
  sources: SourceRef[];
};

type Props = {
  trace: ExecutionTrace | null;
  onClose?: () => void;
};

/** `score` llega entre 0 y 1. Se acota antes de pintarlo. */
function scorePercent(score: number): number {
  if (!Number.isFinite(score)) return 0;
  return Math.round(Math.min(1, Math.max(0, score)) * 100);
}

export function TracePanel({ trace, onClose }: Props): JSX.Element {
  const hasDocumentSources = (trace?.sources.length ?? 0) > 0;
  const resultLabel = !trace
    ? "Sin ejecutar"
    : hasDocumentSources
      ? "Con fuentes"
      : "Sin fuentes documentales";
  const resultNote = !trace
    ? "Aun no se ha pedido ninguna respuesta"
    : hasDocumentSources
      ? "Cada afirmacion cita un documento autorizado"
      : "La respuesta no se apoyo en ningun documento";

  return (
    <aside className="inspector" aria-label="Trazabilidad de la ultima respuesta">
      <div className="inspector-heading">
        <div>
          <span className="eyebrow">TRAZABILIDAD</span>
          <h3>Ultima respuesta</h3>
        </div>
        {onClose ? (
          <button
            type="button"
            className="icon-button ghost"
            onClick={onClose}
            aria-label="Cerrar trazabilidad"
          >
            <Icon name="close" size={16} />
          </button>
        ) : null}
      </div>

      <div className={`result-verdict ${hasDocumentSources ? "ok" : "neutral"}`}>
        <Icon name={hasDocumentSources ? "check" : "alert"} size={18} />
        <div>
          <span className="result-badge">{resultLabel}</span>
          <small>{resultNote}</small>
        </div>
      </div>

      <dl className="execution-grid">
        <div>
          <dt>Conversacion</dt>
          <dd title={trace?.conversationId}>{trace ? trace.conversationId.slice(0, 8) : "—"}</dd>
        </div>
        <div>
          <dt>Intencion</dt>
          <dd>{trace?.intent || "—"}</dd>
        </div>
        <div>
          <dt>Latencia</dt>
          <dd>{trace ? `${trace.latencyMs} ms` : "—"}</dd>
        </div>
        <div>
          <dt>Evidencias</dt>
          <dd>{trace?.sources.length ?? 0}</dd>
        </div>
      </dl>

      <section className="evidence-section" aria-labelledby="evidence-title">
        <div className="section-title">
          <h4 id="evidence-title">Fuentes verificadas</h4>
          <span className="counter">{trace?.sources.length ?? 0}</span>
        </div>
        {trace && trace.sources.length > 0 ? (
          <ul className="evidence-list">
            {trace.sources.map((source, index) => (
              <li key={source.source_id}>
                <span className="n" aria-hidden="true">
                  {index + 1}
                </span>
                <div className="evidence-body">
                  <strong>{source.label}</strong>
                  <span className="category">{source.category}</span>
                  {source.section ? <small>{source.section}</small> : null}
                  {/* El backend ya enviaba `score` en cada fuente; la interfaz
                      nunca lo mostraba. Es lo que separa una cita solida de una
                      coincidencia debil. */}
                  <div className="evidence-score">
                    <span className="track" aria-hidden="true">
                      <span className="fill" style={{ width: `${scorePercent(source.score)}%` }} />
                    </span>
                    <span className="value">
                      relevancia {scorePercent(source.score)}%
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="inspector-empty">
            Las fuentes autorizadas de la ultima respuesta apareceran aqui.
          </p>
        )}
      </section>

      <p className="trace-note">
        La interfaz solo muestra evidencia que el backend autorizo antes de consultar el indice.
      </p>
    </aside>
  );
}
