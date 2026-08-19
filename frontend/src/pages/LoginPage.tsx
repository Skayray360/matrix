/* Creado por Aldo Garcia. */
/**
 * Pantalla de acceso.
 *
 * El formulario local solo tiene sentido con `AUTH_PROVIDER=local_test`. Cuando
 * el backend corre con Entra ID, el boton corporativo redirige a
 * `/api/v1/auth/login` y el flujo OIDC ocurre entero en el servidor: el
 * navegador nunca ve un token.
 *
 * Por eso el acceso corporativo es ahora la accion principal de la pantalla y
 * el formulario local queda debajo, como la ayuda de pruebas que es. Antes
 * estaba al reves: el enlace a Entra ID vivia en letra chica al pie.
 *
 * El mensaje de error es siempre el que devuelve el backend, que no distingue
 * entre usuario inexistente y contrasena incorrecta.
 */

import { useState, type FormEvent } from "react";

import { Icon, BrandMark } from "../components/Icon";
import { api, ApiError } from "../services/api";

type Props = {
  onAuthenticated: () => void | Promise<void>;
};

export function LoginPage({ onAuthenticated }: Props): JSX.Element {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.localLogin(username, password);
      await onAuthenticated();
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : "No fue posible contactar al servidor de Matrix RH.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-shell">
      <aside className="login-aside">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <BrandMark size={24} />
          </span>
          <div className="brand-text">
            <strong>Matrix RH</strong>
            <span>Asistente interno de Recursos Humanos</span>
          </div>
        </div>

        <div>
          <h2>Respuestas de RH con la fuente siempre a la vista.</h2>
          <ul className="login-points">
            <li>
              <span className="marker" aria-hidden="true">
                <Icon name="shield" size={17} />
              </span>
              <div>
                <strong>Procesamiento 100% local</strong>
                <span>Ningun documento sale de la red interna.</span>
              </div>
            </li>
            <li>
              <span className="marker" aria-hidden="true">
                <Icon name="chat" size={17} />
              </span>
              <div>
                <strong>Cada respuesta citada</strong>
                <span>Vera el documento y la seccion que la sustentan.</span>
              </div>
            </li>
            <li>
              <span className="marker" aria-hidden="true">
                <Icon name="panel" size={17} />
              </span>
              <div>
                <strong>Solo lo que su perfil puede leer</strong>
                <span>El permiso lo decide el servidor, no la pantalla.</span>
              </div>
            </li>
          </ul>
        </div>

        <div className="login-foot">Matrix RH 1.1.0 · entorno local</div>
      </aside>

      <div className="login-main">
        <div className="login-card">
          <h1>Iniciar sesion</h1>
          <p className="subtitle">Use su cuenta corporativa para entrar.</p>

          <a className="entra-button" href="/api/v1/auth/login" rel="noreferrer">
            <Icon name="microsoft" size={18} />
            Continuar con Microsoft Entra ID
          </a>

          <div className="login-separator">
            <span>o acceso local de pruebas</span>
          </div>

          {error ? (
            <div className="banner" role="alert" data-testid="login-error">
              <Icon name="alert" size={17} />
              <p>{error}</p>
            </div>
          ) : null}

          <form onSubmit={handleSubmit} noValidate>
            <div className="field">
              <label htmlFor="username">Usuario</label>
              <input
                id="username"
                name="username"
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
                maxLength={128}
              />
            </div>

            <div className="field">
              <div className="field-head">
                <label htmlFor="password">Contrasena</label>
                <button
                  className="field-toggle"
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                >
                  {showPassword ? "Ocultar" : "Mostrar"}
                </button>
              </div>
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                maxLength={256}
              />
            </div>

            <button className="secondary-button" type="submit" disabled={busy}>
              {busy ? "Verificando..." : "Entrar"}
            </button>
          </form>

          <p className="hint">
            El acceso local solo funciona cuando el servidor corre con{" "}
            <code>AUTH_PROVIDER=local_test</code>. En produccion use el acceso
            corporativo.
          </p>
        </div>
      </div>
    </main>
  );
}
