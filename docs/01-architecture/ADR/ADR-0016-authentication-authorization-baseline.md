# ADR-0016 — Authentication and Authorization Baseline

Status: Accepted  
Date: 2026-10-28

## Decision
G1 will implement application-local identity with role-based access control (RBAC), while keeping authentication behind an interface that supports later OIDC federation.

Initial capabilities:
- unique user account;
- password hash using a modern memory-hard password hashing algorithm;
- enabled/disabled status;
- roles;
- permissions;
- plant/area scope where applicable;
- auditable sign-in and privileged actions;
- secure server-side/session-cookie web authentication.

## Authorization
Permissions are capability-based, for example:
- plan.read
- plan.release
- masterdata.edit
- kanban.trigger
- purchase.approve
- maintenance.close
- admin.users

Roles are collections of permissions and can be configured per deployment.

## Future identity federation
The authentication boundary must support replacement/federation with OIDC-compatible enterprise identity without rewriting domain authorization.

Potential future sources include corporate directory/SSO, but none is assumed in G0.

## Security rules
- no shared operator accounts as the target state;
- no plaintext credentials;
- no credentials in repository/config files;
- privileged actions are audited;
- authorization is enforced server-side even when UI controls are hidden.

## Rationale
FAIC identity infrastructure is not yet inventoried. Local RBAC allows G1 to proceed while preserving a clean upgrade path to enterprise SSO.
