import { useState, type FormEvent } from "react";

import { ApiError } from "../api/client";
import { useAuth } from "./AuthContext";

export function LoginScreen() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login({ username, password });
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "No fue posible iniciar sesión."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-layout">
      <section className="login-brand">
        <div className="brand-mark">MOP</div>
        <p className="eyebrow">Manufacturing Operations Platform</p>
        <h1>Operación industrial gobernada desde una sola plataforma.</h1>
        <p className="muted">
          Acceso controlado por identidad individual, permisos y alcance
          organizacional.
        </p>
      </section>

      <section className="login-card" aria-labelledby="login-title">
        <p className="eyebrow">Acceso seguro</p>
        <h2 id="login-title">Ingresar a MOP</h2>
        <form onSubmit={submit}>
          <label>
            Usuario
            <input
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
          </label>
          <label>
            Contraseña
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? "Validando…" : "Ingresar"}
          </button>
        </form>
      </section>
    </main>
  );
}
