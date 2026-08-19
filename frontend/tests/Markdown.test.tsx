/* Creado por Aldo Garcia. */
/**
 * Pruebas del renderizador Markdown.
 *
 * El caso critico es el de XSS: el renderizador construye elementos de React, de
 * modo que cualquier HTML incrustado en una respuesta del modelo o en un
 * documento corporativo debe aparecer como TEXTO, nunca como marcado activo.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "../src/security/Markdown";

describe("Markdown", () => {
  it("renderiza parrafos, negrita y listas", () => {
    render(<Markdown text={"Politica **vigente**\n\n- uno\n- dos"} />);
    expect(screen.getByText("vigente").tagName).toBe("STRONG");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("no ejecuta ni inyecta HTML incrustado", () => {
    const malicious = '<img src=x onerror="window.__pwned=true"> <script>window.__pwned=true</script>';
    const { container } = render(<Markdown text={malicious} />);

    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined();
    // El marcado se muestra como texto literal.
    expect(container.textContent).toContain("<img src=x");
  });

  it("marca como cita solo los source_id conocidos", () => {
    render(
      <Markdown
        text="Son 20 dias [[prestaciones/politica-vacaciones.md#2]] y no [[nomina/secreto.md#9]]."
        knownSources={new Set(["prestaciones/politica-vacaciones.md#2"])}
      />,
    );
    const citations = screen.getAllByTestId("citation");
    expect(citations).toHaveLength(1);
    expect(citations[0]).toHaveAttribute("title", "prestaciones/politica-vacaciones.md#2");
    // La cita desconocida queda como texto plano, sin apariencia de fuente.
    expect(screen.getByText(/nomina\/secreto\.md#9/)).toBeInTheDocument();
  });

  it("renderiza tablas dentro de un contenedor con scroll propio", () => {
    const { container } = render(
      <Markdown text={"| Antiguedad | Dias |\n| --- | --- |\n| 1 anio | 12 |"} />,
    );
    expect(container.querySelector(".table-scroll")).not.toBeNull();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader")).toHaveLength(2);
  });
});
