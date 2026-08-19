/* Creado por Aldo Garcia. */
/** Utilidades compartidas por los E2E de Matrix RH. */

import { expect, type Page } from "@playwright/test";

/**
 * Credenciales sinteticas de prueba declaradas en la especificacion.
 * NO son secretos productivos: las cuentas se deshabilitan antes de produccion.
 */
export const TEST_PASSWORD = "Matrix RH";
export const ADMIN_USER = "Matrix";
export const RESTRICTED_USER = "MatrixR1";

export async function login(page: Page, username: string, password = TEST_PASSWORD): Promise<void> {
  await page.goto("/");
  await page.getByLabel("Usuario").fill(username);
  await page.getByLabel("Contrasena").fill(password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByTestId("identity-user")).toBeVisible({ timeout: 30_000 });
}

export async function ask(page: Page, question: string): Promise<string> {
  await page.getByTestId("composer-input").fill(question);
  await page.getByTestId("send-button").click();
  // Se espera a que aparezca una respuesta del asistente y desaparezca el
  // indicador de espera.
  await expect(page.getByTestId("message-pending")).toBeHidden({ timeout: 240_000 });
  const answers = page.getByTestId("message-assistant");
  await expect(answers.last()).toBeVisible();
  return (await answers.last().innerText()).trim();
}

export async function logout(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Salir" }).click();
  await expect(page.getByRole("button", { name: "Entrar" })).toBeVisible();
}

/** Terminos que jamas deben aparecer en una respuesta a un usuario restringido. */
export const RESTRICTED_TERMS = [
  "politica-de-nomina",
  "proceso-de-reclutamiento",
  "reglamento-interior",
  "seguridad-higiene-y-ambiente",
];

export function assertNoRestrictedLeak(answer: string): void {
  const lowered = answer.toLowerCase();
  for (const term of RESTRICTED_TERMS) {
    expect(lowered, `la respuesta filtro la fuente restringida ${term}`).not.toContain(term);
  }
}
