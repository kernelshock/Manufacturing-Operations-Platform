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

export type UnitOfMeasure = {
  id: string;
  code: string;
  dimension: "COUNT" | "LENGTH" | "MASS" | "VOLUME" | "OTHER";
  canonical: boolean;
  active: boolean;
};

export type ProductConfiguration = {
  id: string;
  article_id: string;
  family_code: string;
  family_name: string;
  model_code: string;
  model_name: string;
  product_class: string;
  width: string | null;
  width_uom_id: string | null;
  configuration_string: string;
  active: boolean;
  created_at: string;
  updated_at: string;
};


export type Supplier = {
  id: string;
  code: string;
  legal_name: string;
  trade_name: string | null;
  supply_category: "UNKNOWN" | "PRODUCT" | "PROCESS" | "SERVICE" | "MIXED";
  active: boolean;
  created_at: string;
  updated_at: string;
};
