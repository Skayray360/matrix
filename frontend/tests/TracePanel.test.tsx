/* Creado por Aldo Garcia. */
/** La trazabilidad solo presenta metadatos autorizados recibidos del backend. */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TracePanel } from "../src/components/TracePanel";

describe("TracePanel", () => {
  it("muestra estado inicial sin inventar evidencia", () => {
    render(<TracePanel trace={null} />);
    expect(screen.getByText("Sin ejecutar")).toBeInTheDocument();
    expect(screen.getByText(/fuentes autorizadas/i)).toBeInTheDocument();
  });

  it("no etiqueta como documentada una respuesta sin fuentes", () => {
    render(
      <TracePanel
        trace={{
          conversationId: "conv-general",
          intent: "identity",
          grounded: true,
          latencyMs: 12,
          sources: [],
        }}
      />,
    );

    expect(screen.getByText("Sin fuentes documentales")).toBeInTheDocument();
    expect(screen.queryByText("Con fuentes")).not.toBeInTheDocument();
  });

  it("muestra la fuente y latencia de la ultima respuesta", () => {
    render(
      <TracePanel
        trace={{
          conversationId: "12345678-abcd-efgh-ijkl-123456789012",
          intent: "document_question",
          grounded: true,
          latencyMs: 640,
          sources: [
            {
              source_id: "general/manual.md#0",
              category: "general",
              filename: "manual.md",
              section: "Objetivo",
              page_or_sheet: "",
              score: 0.8,
              label: "Manual general",
              scope: "corporate",
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("Con fuentes")).toBeInTheDocument();
    expect(screen.getByText("640 ms")).toBeInTheDocument();
    expect(screen.getByText("Manual general")).toBeInTheDocument();
    expect(screen.getByText("general")).toBeInTheDocument();
  });
});
