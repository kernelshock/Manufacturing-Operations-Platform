import type {
  AuditEntry,
  CurrentUser,
  LoginPayload,
  Organization,
  Plant,
  ProductConfiguration,
  ReadyStatus,
  ServiceMeta,
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
    )
};
