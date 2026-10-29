import { useAuth } from "./auth/AuthContext";
import { LoginScreen } from "./auth/LoginScreen";
import { AppShell } from "./shell/AppShell";

export function App() {
  const { state, refresh } = useAuth();

  if (state.status === "loading") {
    return (
      <main className="center-state">
        <div className="brand-mark">MOP</div>
        <h1>Inicializando plataforma…</h1>
      </main>
    );
  }

  if (state.status === "error") {
    return (
      <main className="center-state">
        <div className="brand-mark">MOP</div>
        <h1>No se pudo validar la sesión.</h1>
        <p>{state.error}</p>
        <button className="primary-button" onClick={() => void refresh()}>
          Reintentar
        </button>
      </main>
    );
  }

  if (state.status === "anonymous") {
    return <LoginScreen />;
  }

  return <AppShell user={state.user} />;
}
