/* Creado por Aldo Garcia. */
/**
 * E2E 11, 12, 15, 16, 19, 31: routing de modelos, resiliencia, categorias nuevas
 * y bloqueo del modo local en produccion.
 *
 * El routing se observa por la vista administrativa de diagnostico y por la
 * auditoria, no exponiendo el modelo al usuario final (seccion 14).
 */

import { expect, test } from "@playwright/test";

import { ADMIN_USER, ask, login } from "./helpers";

test.describe("Operacion y resiliencia", () => {
  test("E2E-11/12 la politica de dos modelos esta activa y usa los modelos exigidos", async ({
    page,
  }) => {
    await login(page, ADMIN_USER);
    const diagnostics = await (await page.request.get("/api/v1/admin/diagnostics")).json();

    expect(diagnostics.models.fast).toBe("gemma4:latest");
    expect(diagnostics.models.deep).toBe("qwen3.6:latest");
    expect(diagnostics.models.embedding).toBe("embeddinggemma:latest");
    expect(diagnostics.models.embedding_dimension).toBe(768);

    // Consulta simple: debe resolverse por la ruta rapida.
    await page.getByTestId("new-conversation").click();
    await ask(page, "Cuantos dias de vacaciones corresponden a 5 anios de antiguedad?");

    // Consulta comparativa multi-categoria: debe escalar a la ruta profunda.
    await page.getByTestId("new-conversation").click();
    await ask(
      page,
      "Compara en detalle las reglas de prestaciones frente a las de nomina y explica sus implicaciones para un empleado de confianza.",
    );

    const audit = await (
      await page.request.get("/api/v1/admin/audit/recent?limit=25")
    ).json();
    const models = (audit.events as { selected_model: string | null }[])
      .map((event) => event.selected_model)
      .filter(Boolean);
    expect(models).toContain("gemma4:latest");
    expect(models).toContain("qwen3.6:latest");
  });

  test("E2E-13 el diagnostico expone parametros del RAG y ningun secreto", async ({ page }) => {
    await login(page, ADMIN_USER);
    const response = await page.request.get("/api/v1/admin/diagnostics");
    expect(response.status()).toBe(200);
    const body = await response.json();

    expect(body.rag.RAG_TOP_K).toBe(6);
    expect(body.rag.RAG_FETCH_K).toBe(24);
    expect(body.rag.RAG_CHUNK_SIZE_TOKENS).toBe(900);
    expect(body.rag.RAG_CHUNK_OVERLAP_TOKENS).toBe(120);
    expect(body.rag.RAG_MIN_SIMILARITY).toBe(0.35);
    expect(body.rag.RAG_MMR_LAMBDA).toBe(0.65);

    const serialized = JSON.stringify(body).toLowerCase();
    for (const forbidden of ["password", "client_secret", "mysql+pymysql", "argon2", "api_key"]) {
      expect(serialized, `el diagnostico expuso ${forbidden}`).not.toContain(forbidden);
    }
  });

  test("E2E-19 una categoria nueva queda deny-by-default hasta tener politica", async ({ page }) => {
    await login(page, ADMIN_USER);
    const summary = await (await page.request.get("/api/v1/admin/knowledge/summary")).json();
    const known = summary.known_categories as string[];

    // Las cinco semillas son conocidas...
    for (const seed of [
      "prestaciones",
      "nomina",
      "reclutamiento",
      "relaciones_laborales",
      "salud_ambiental",
    ]) {
      expect(known).toContain(seed);
    }
    // ...y una categoria marcada como no elegible por wildcard sigue fuera del
    // alcance efectivo incluso del administrador de negocio.
    const me = await (await page.request.get("/api/v1/me")).json();
    expect(me.allowed_categories).not.toContain("investigaciones_internas");
  });

  test("E2E-15/16 los errores no filtran stack traces ni secretos", async ({ page }) => {
    await login(page, ADMIN_USER);

    // Recurso inexistente: respuesta tipada y sin detalles internos.
    const missing = await page.request.get("/api/v1/conversations/no-existe-este-id");
    expect(missing.status()).toBe(404);
    const body = await missing.text();
    expect(body).not.toContain("Traceback");
    expect(body).not.toContain("sqlalchemy");
    expect(body).not.toContain("mysql");
    expect(JSON.parse(body).code).toBe("not_found");
  });

  test("las cabeceras de seguridad estan presentes", async ({ page }) => {
    const response = await page.request.get("/api/v1/health");
    const headers = response.headers();
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["x-frame-options"]).toBe("DENY");
    expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
    expect(headers["content-security-policy"]).toContain("object-src 'none'");
    expect(headers["referrer-policy"]).toBe("no-referrer");
  });

  test("la interfaz es usable en viewport movil sin scroll horizontal", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 780 });
    await login(page, ADMIN_USER);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    );
    expect(overflow).toBe(false);
    await expect(page.getByRole("button", { name: "Conversaciones" })).toBeVisible();
  });
});
