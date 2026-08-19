/* Creado por Aldo Garcia. */
/**
 * Cliente HTTP del frontend.
 *
 * Decisiones de seguridad:
 *  - `credentials: "same-origin"`: la sesion viaja en una cookie HttpOnly que el
 *    JavaScript no puede leer. No se guarda NINGUN token en localStorage ni en
 *    sessionStorage.
 *  - el token CSRF se mantiene solo en memoria del modulo y se envia en la
 *    cabecera `X-CSRF-Token` de toda peticion mutante.
 *  - los errores del backend llegan tipados (`code`, `message`, `request_id`); el
 *    frontend nunca muestra stack traces.
 */

const API_BASE = "/api/v1";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId: string | null;

  constructor(code: string, message: string, status: number, requestId: string | null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

/** Token CSRF vigente. Solo en memoria: se pierde al recargar y se vuelve a pedir. */
let csrfToken = "";

export function setCsrfToken(token: string): void {
  csrfToken = token;
}

export function getCsrfToken(): string {
  return csrfToken;
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  formData?: FormData;
  signal?: AbortSignal;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;

  if (options.formData) {
    body = options.formData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  if (method !== "GET" && method !== "HEAD" && csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body,
    credentials: "same-origin",
    signal: options.signal,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const requestId = response.headers.get("X-Request-ID");
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const detail = (payload ?? {}) as { code?: string; message?: string };
    throw new ApiError(
      detail.code ?? "internal_error",
      detail.message ?? "No fue posible completar la operacion.",
      response.status,
      requestId,
    );
  }

  return payload as T;
}

// --- Tipos de dominio -------------------------------------------------------

export type Me = {
  user_id: string;
  username: string;
  display_name: string;
  auth_source: string;
  roles: string[];
  permissions: string[];
  allowed_categories: string[];
  category_wildcard: boolean;
  csrf_token: string;
};

export type SourceRef = {
  source_id: string;
  category: string;
  filename: string;
  section: string;
  page_or_sheet: string;
  score: number;
  label: string;
  scope: string;
};

export type ChatReply = {
  conversation_id: string;
  message_id: string;
  answer: string;
  sources: SourceRef[];
  intent: string;
  grounded: boolean;
  latency_ms: number;
};

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: string;
  role: string;
  content: string;
  model: string | null;
  created_at: string;
  sources: { source_id: string }[];
};

export type DocumentStatus = {
  id: string;
  filename: string;
  status: string;
  chunk_count: number;
  scope: string;
  category: string | null;
  error_message: string | null;
};

export type ConversationDetail = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
  attachments: DocumentStatus[];
};

// --- Operaciones ------------------------------------------------------------

export const api = {
  async me(): Promise<Me> {
    const profile = await request<Me>("/me");
    setCsrfToken(profile.csrf_token);
    return profile;
  },

  async localLogin(username: string, password: string): Promise<Me> {
    const profile = await request<Me>("/auth/local/login", {
      method: "POST",
      body: { username, password },
    });
    setCsrfToken(profile.csrf_token);
    return profile;
  },

  async logout(): Promise<void> {
    await request("/auth/logout", { method: "POST" });
    setCsrfToken("");
  },

  listConversations(): Promise<ConversationSummary[]> {
    return request<ConversationSummary[]>("/conversations");
  },

  createConversation(title = ""): Promise<ConversationSummary> {
    return request<ConversationSummary>("/conversations", { method: "POST", body: { title } });
  },

  getConversation(id: string): Promise<ConversationDetail> {
    return request<ConversationDetail>(`/conversations/${encodeURIComponent(id)}`);
  },

  deleteConversation(id: string): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>(`/conversations/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  chat(message: string, conversationId: string | null): Promise<ChatReply> {
    return request<ChatReply>("/chat", {
      method: "POST",
      body: { message, conversation_id: conversationId },
    });
  },

  uploadAttachments(conversationId: string, files: File[]): Promise<{ documents: DocumentStatus[] }> {
    const form = new FormData();
    for (const file of files) {
      form.append("files", file);
    }
    return request<{ documents: DocumentStatus[] }>(
      `/conversations/${encodeURIComponent(conversationId)}/attachments`,
      { method: "POST", formData: form },
    );
  },

  documentStatus(documentId: string): Promise<DocumentStatus> {
    return request<DocumentStatus>(`/documents/${encodeURIComponent(documentId)}/status`);
  },
};
