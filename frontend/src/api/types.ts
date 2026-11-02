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


export type ProductionPlan = {
  id: string;
  plan_number: string;
  description: string | null;
  status: "DRAFT" | "OPEN" | "COMPLETED" | "CANCELLED";
  historical_completion_classification: "ON_TIME" | "DELAYED" | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type OperationalRoutingProjection = {
  routing_revision_id: string | null;
  binding_mode: "RESOLVED" | "OVERRIDE" | null;
  revision_no: number | null;
  status: string | null;
  effective_at: string | null;
  override_reason: string | null;
};

export type OperationalProductProjection = {
  id: string;
  sequence_no: number;
  article_id: string;
  article_code: string;
  article_description: string;
  requested_quantity: string;
  deck_position: "SINGLE" | "UPPER" | "LOWER";
  source_document_key: string | null;
  source_line_key: string | null;
  routing: OperationalRoutingProjection;
};

export type OperationalTaquillaProjection = {
  id: string;
  taquilla_code: string;
  sequence_no: number;
  status: "DRAFT" | "READY" | "COMPLETED" | "CANCELLED";
  vehicle_topology: "SIMPLE" | "DOUBLE_DECK";
  historical_completion_classification: "ON_TIME" | "DELAYED" | null;
  cancellation_reason: string | null;
  products: OperationalProductProjection[];
  product_count: number;
  total_requested_quantity: string;
  routing_bound_count: number;
  routing_missing_count: number;
};

export type OperationalPlanProjection = {
  id: string;
  plan_number: string;
  description: string | null;
  status: "DRAFT" | "OPEN" | "COMPLETED" | "CANCELLED";
  historical_completion_classification: "ON_TIME" | "DELAYED" | null;
  cancellation_reason: string | null;
  taquillas: OperationalTaquillaProjection[];
  taquilla_count: number;
  product_line_count: number;
  routing_missing_count: number;
  blocked_taquilla_count: number;
};

export type TaquillaAssimilationBatch = {
  id: string;
  plan_id: string;
  target_taquilla_id: string | null;
  source_system: string;
  parser_version: string;
  mapping_version: string;
  payload_fingerprint: string;
  taquilla_code: string;
  sequence_no: number;
  vehicle_topology: "SIMPLE" | "DOUBLE_DECK";
  status: "RECEIVED" | "VALIDATED" | "REVIEW_REQUIRED" | "REJECTED" | "APPLIED";
  accepted_lines: number;
  rejected_lines: number;
  imported_by: string | null;
  imported_at: string;
};


export type TaquillaAssimilationIssue = {
  id: string;
  batch_id: string;
  rule_code: string;
  severity: "WARNING" | "ERROR" | "BLOCKER";
  message: string;
  source_document_key: string | null;
  source_line_key: string | null;
  created_at: string;
};

export type TaquillaAssimilationResult = {
  batch: TaquillaAssimilationBatch;
  issues: TaquillaAssimilationIssue[];
  target_taquilla_id: string | null;
  idempotent_replay: boolean;
};


export type GanttSegment = {
  segment_no: number;
  start_at: string;
  end_at: string;
  effective_rate_per_hour: string;
  produced_quantity: string;
};

export type GanttOperation = {
  publication_id: string;
  publication_version: number;
  publication_status: string;
  run_id: string;
  scenario_id: string;
  plan_id: string;
  plan_number: string;
  taquilla_id: string;
  taquilla_code: string;
  taquilla_sequence_no: number;
  product_line_id: string;
  product_sequence_no: number;
  article_id: string;
  article_code: string;
  article_description: string;
  deck_position: string;
  routing_revision_id: string;
  routing_operation_id: string;
  routing_sequence_no: number;
  operation_code: string;
  operation_description: string | null;
  resource_id: string;
  resource_code: string;
  resource_name: string;
  work_center_id: string;
  work_center_code: string;
  work_center_name: string;
  area_id: string;
  area_code: string;
  area_name: string;
  sequence_no: number;
  planned_start: string;
  planned_finish: string;
  processing_seconds: string;
  requested_quantity: string;
  segments: GanttSegment[];
};

export type GanttPublication = {
  publication_id: string;
  scenario_id: string;
  run_id: string;
  plan_id: string;
  plan_number: string;
  version_no: number;
  status: string;
  published_at: string;
  schedule_fingerprint: string;
  operation_count: number;
};

export type GanttProjection = {
  scope: "MASTER" | "PLAN";
  plan_id: string | null;
  plan_number: string | null;
  window_start: string | null;
  window_end: string | null;
  publications: GanttPublication[];
  operations: GanttOperation[];
  operation_count: number;
  taquilla_count: number;
  resource_count: number;
  constraints_evaluated: string[];
  constraints_not_evaluated: string[];
};
