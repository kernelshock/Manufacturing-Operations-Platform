import { useMemo, useState } from "react";

import type { CurrentUser } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { visibleModules, type ModuleId } from "../lib/permissions";
import { AuditPanel } from "./AuditPanel";
import {
  ContextSelector,
  type PlantContext
} from "./ContextSelector";
import { useSystemStatus } from "./useSystemStatus";

const futureModules = [
  "APS",
  "MES",
  "Kanban",
  "Mantenimiento",
  "Compras"
];

export function AppShell({ user }: { user: CurrentUser }) {
  const { logout } = useAuth();
  const system = useSystemStatus();
  const modules = useMemo(
    () => visibleModules(user.permissions),
    [user.permissions]
  );
  const [active, setActive] = useState<ModuleId>("home");
  const [context, setContext] = useState<PlantContext>({
    organization: null,
    plant: null
  });

  const activeModule =
    modules.find((module) => module.id === active) ?? modules[0];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <div className="sidebar-brand">
            <div className="brand-mark compact">MOP</div>
            <div>
              <strong>Operations</strong>
              <span>Platform Core</span>
            </div>
          </div>

          <nav aria-label="Módulos principales">
            {modules.map((module) => (
              <button
                className={module.id === activeModule.id ? "nav-item active" : "nav-item"}
                key={module.id}
                onClick={() => setActive(module.id)}
                type="button"
              >
                <span>{module.label}</span>
                <small>{module.description}</small>
              </button>
            ))}
          </nav>

          <div className="future-nav">
            <p>Próximos módulos</p>
            {futureModules.map((module) => (
              <span key={module}>{module}<small>G2+</small></span>
            ))}
          </div>
        </div>

        <div className="sidebar-footer">
          <span>{user.display_name}</span>
          <small>@{user.username}</small>
          <button type="button" onClick={() => void logout()}>
            Cerrar sesión
          </button>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Manufacturing Operations Platform</p>
            <h1>{activeModule.label}</h1>
          </div>
          <div className="topbar-actions">
            <ContextSelector
              user={user}
              value={context}
              onChange={setContext}
            />
            <span
              className={
                system.ready?.status === "ready"
                  ? "status-pill success"
                  : "status-pill warning"
              }
            >
              {system.ready?.status === "ready"
                ? "Sistema listo"
                : system.reachable
                  ? "Base no disponible"
                  : "Backend no disponible"}
            </span>
          </div>
        </header>

        <main className="main-content">
          {activeModule.id === "home" ? (
            <Dashboard
              context={context}
              permissions={user.permissions}
              system={system}
            />
          ) : null}
          {activeModule.id === "structure" ? (
            <StructurePanel context={context} />
          ) : null}
          {activeModule.id === "audit" ? <AuditPanel /> : null}
          {activeModule.id === "admin" ? (
            <AdminPanel permissions={user.permissions} />
          ) : null}
        </main>
      </div>
    </div>
  );
}

function Dashboard({
  context,
  permissions,
  system
}: {
  context: PlantContext;
  permissions: string[];
  system: ReturnType<typeof useSystemStatus>;
}) {
  return (
    <>
      <section className="hero-panel">
        <div>
          <p className="eyebrow">G1 · Platform Core</p>
          <h2>Base operativa disponible para los módulos industriales.</h2>
          <p>
            El shell consume exclusivamente la API versionada y refleja sesión,
            permisos, salud del servicio y contexto de planta.
          </p>
        </div>
        <div className="hero-version">
          <span>Versión backend</span>
          <strong>{system.meta?.version ?? "—"}</strong>
          <small>{system.meta?.environment ?? "sin conexión"}</small>
        </div>
      </section>

      <section className="metric-grid">
        <article className="metric-card">
          <span>Aplicación</span>
          <strong>{system.reachable ? "Online" : "Sin conexión"}</strong>
          <small>FastAPI / REST</small>
        </article>
        <article className="metric-card">
          <span>Base de datos</span>
          <strong>
            {system.ready?.checks.database === "ok" ? "Disponible" : "No lista"}
          </strong>
          <small>Readiness real</small>
        </article>
        <article className="metric-card">
          <span>Contexto</span>
          <strong>{context.plant?.code ?? context.organization?.code ?? "RBAC"}</strong>
          <small>{context.plant?.name ?? context.organization?.name ?? "Ámbito de acceso"}</small>
        </article>
        <article className="metric-card">
          <span>Capacidades</span>
          <strong>{permissions.length}</strong>
          <small>Permisos efectivos</small>
        </article>
      </section>

      <section className="content-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Arquitectura activa</p>
            <h2>Servicios del Platform Core</h2>
          </div>
        </div>
        <div className="service-grid">
          {[
            ["Identidad", "Sesión server-side y Argon2", "Activo"],
            ["RBAC", "Permisos con alcance organizacional", "Activo"],
            ["Auditoría", "Registro inmutable PostgreSQL", "Activo"],
            ["Core", "Organización → Planta → Área → Centro → Recurso", "Activo"]
          ].map(([title, description, state]) => (
            <article className="service-card" key={title}>
              <span className="status-dot" />
              <div>
                <strong>{title}</strong>
                <p>{description}</p>
              </div>
              <small>{state}</small>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

function StructurePanel({ context }: { context: PlantContext }) {
  return (
    <section className="content-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Core organizacional</p>
          <h2>Contexto de operación</h2>
        </div>
      </div>
      <div className="hierarchy">
        {["Organization", "Plant", "Area", "WorkCenter", "Resource"].map(
          (level, index) => (
            <div className="hierarchy-node" key={level}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{level}</strong>
            </div>
          )
        )}
      </div>
      <p className="muted">
        Selección actual:{" "}
        {context.plant?.name ??
          context.organization?.name ??
          "sin contexto global seleccionado"}.
      </p>
    </section>
  );
}

function AdminPanel({ permissions }: { permissions: string[] }) {
  return (
    <section className="content-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Gobernanza</p>
          <h2>Administración de acceso</h2>
        </div>
      </div>
      <div className="permission-list">
        {permissions
          .filter((permission) => permission.startsWith("admin."))
          .map((permission) => (
            <code key={permission}>{permission}</code>
          ))}
      </div>
      <p className="muted">
        G1.6 expone el shell y la visibilidad por permisos. Los formularios
        administrativos completos se incorporarán como superficies de módulo.
      </p>
    </section>
  );
}
