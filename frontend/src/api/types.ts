export type CurrentUser = {
  id: string;
  username: string;
  display_name: string;
  enabled: boolean;
  permissions: string[];
};

export type LoginPayload = {
  username: string;
  password: string;
};

export type ServiceMeta = {
  name: string;
  version: string;
  environment: string;
  api_prefix: string;
};

export type ReadyStatus = {
  status: "ready" | "not_ready";
  service: string;
  checks: Record<string, string>;
};

export type Organization = {
  id: string;
  code: string;
  name: string;
  active: boolean;
};

export type Plant = {
  id: string;
  organization_id: string;
  code: string;
  name: string;
  active: boolean;
};

export type AuditEntry = {
  id: string;
  occurred_at: string;
  actor_username: string | null;
  action: string;
  object_type: string;
  object_id: string | null;
  outcome: string;
  request_id: string | null;
};
