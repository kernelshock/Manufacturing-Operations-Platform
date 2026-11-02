import type {
  AuditEntry,
  CurrentUser,
  GanttProjection,
  LoginPayload,
  OperationalPlanProjection,
  Organization,
  Plant,
  ProductionPlan,
  ProductConfiguration,
  ReadyStatus,
  ServiceMeta,
  Supplier,
  TaquillaAssimilationBatch,
  TaquillaAssimilationResult,
  WhatIfApplyResult,
  WhatIfComparison,
  WhatIfEvaluationResult,
  WhatIfException,
  WhatIfScenario,
  UnitOfMeasure
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include"
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        message = payload.detail;
      }
    } catch {
      // Keep the status-based message when the response has no JSON body.
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  me: () => apiFetch<CurrentUser>("/api/v1/auth/me"),
  login: (payload: LoginPayload) =>
    apiFetch<CurrentUser>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  logout: () =>
    apiFetch<void>("/api/v1/auth/logout", {
      method: "POST"
    }),
  meta: () => apiFetch<ServiceMeta>("/api/v1/meta"),
  ready: () => apiFetch<ReadyStatus>("/health/ready"),
  organizations: () =>
    apiFetch<Organization[]>("/api/v1/core/organizations"),
  plants: (organizationId: string) =>
    apiFetch<Plant[]>(
      `/api/v1/core/plants?organization_id=${encodeURIComponent(organizationId)}`
    ),
  audit: (limit = 20) =>
    apiFetch<AuditEntry[]>(`/api/v1/audit/events?limit=${limit}`),
  uoms: () => apiFetch<UnitOfMeasure[]>("/api/v1/master-data/uoms"),
  productConfigurations: () =>
    apiFetch<ProductConfiguration[]>(
      "/api/v1/master-data/product-configurations?active=true"
    ),
  suppliers: () =>
    apiFetch<Supplier[]>("/api/v1/master-data/suppliers?active=true"),
  productionPlans: () =>
    apiFetch<ProductionPlan[]>("/api/v1/demand/plans"),
  operationalProjection: (planId: string) =>
    apiFetch<OperationalPlanProjection>(
      `/api/v1/demand/plans/${encodeURIComponent(planId)}/projection`
    ),
  assimilationBatches: () =>
    apiFetch<TaquillaAssimilationBatch[]>(
      "/api/v1/demand/assimilation/batches"
    ),
  importTaquilla: (payload: unknown) =>
    apiFetch<TaquillaAssimilationResult>(
      "/api/v1/demand/assimilation/taquillas/import",
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  ganttProjection: (planId?: string) =>
    apiFetch<GanttProjection>(
      planId
        ? `/api/v1/aps/gantt?plan_id=${encodeURIComponent(planId)}`
        : "/api/v1/aps/gantt"
    ),
  whatIfScenarios: () =>
    apiFetch<WhatIfScenario[]>("/api/v1/aps/what-if"),
  createWhatIf: (payload: {
    scenario_code: string;
    name: string;
    description?: string;
    baseline_publication_id: string;
  }) =>
    apiFetch<WhatIfScenario>("/api/v1/aps/what-if", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  addWhatIfException: (
    whatIfId: string,
    payload: {
      exception_type: "RESOURCE_BLACKOUT" | "RESOURCE_CAPACITY_FACTOR";
      resource_id: string;
      start_at: string;
      end_at: string;
      capacity_factor?: string;
      reason: string;
    }
  ) =>
    apiFetch<WhatIfException>(
      `/api/v1/aps/what-if/${encodeURIComponent(whatIfId)}/exceptions`,
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  evaluateWhatIf: (whatIfId: string) =>
    apiFetch<WhatIfEvaluationResult>(
      `/api/v1/aps/what-if/${encodeURIComponent(whatIfId)}/evaluate`,
      { method: "POST" }
    ),
  compareWhatIf: (whatIfId: string) =>
    apiFetch<WhatIfComparison>(
      `/api/v1/aps/what-if/${encodeURIComponent(whatIfId)}/compare`
    ),
  applyWhatIf: (whatIfId: string) =>
    apiFetch<WhatIfApplyResult>(
      `/api/v1/aps/what-if/${encodeURIComponent(whatIfId)}/apply`,
      { method: "POST" }
    ),
  discardWhatIf: (whatIfId: string) =>
    apiFetch<WhatIfScenario>(
      `/api/v1/aps/what-if/${encodeURIComponent(whatIfId)}/discard`,
      { method: "POST" }
    )
};
