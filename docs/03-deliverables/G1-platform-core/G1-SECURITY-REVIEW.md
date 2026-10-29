# G1 Security Review

Date: 2026-10-29  
Scope: G1 Platform Core  
Disposition: **PASS FOR G1 VALIDATION**

## Identity and authentication
- individual local accounts; no target-state shared operator identity;
- Argon2 memory-hard password hashing;
- minimum password length enforced by the user schema;
- opaque high-entropy session tokens;
- only session-token digests stored in PostgreSQL;
- HttpOnly + SameSite=Strict session cookie;
- Secure cookie forced for shadow/parallel/production environments;
- persistent account lockout after repeated failures;
- generic login failure response;
- dummy Argon2 verification for unknown usernames;
- logout revokes server-side session.

## Authorization
- server-side capability authorization;
- role-permission model;
- global / organization / plant / area assignment scopes;
- hierarchy-aware scope evaluation;
- UI permission visibility is not treated as an authorization control;
- integration tests verify scope escape is denied.

## Audit
- authentication and privileged/core mutations recorded;
- audit records contain no password or raw session token;
- PostgreSQL trigger rejects UPDATE and DELETE on audit history;
- read access requires `audit.read`.

## Network/runtime
- DEV/TEST exposes only nginx/frontend on loopback;
- API and PostgreSQL remain internal to Docker networks;
- migration completion gates API startup;
- readiness includes database connectivity;
- login endpoint rate limited at nginx;
- response security headers enabled;
- sensitive APIs marked no-store.

## Supply chain
- GitHub Actions pinned to immutable SHAs;
- container bases pinned to immutable digests;
- Python and npm dependency locks committed and enforced;
- Python vulnerability audit clean at canonical gate;
- npm vulnerability audit clean at canonical gate;
- tracked-file secret scan active.

## Residual/deferred risks
### Accepted for G1
- DEV/TEST runtime uses HTTP on loopback. Production HTTPS is an ADR-0015 requirement.
- G1 does not claim production backup readiness. ADR-0017 requires automated separated backups and a successful restore test before Parallel/Production.
- local identity is intentional; OIDC remains a future federation path.
- no durable background worker is deployed because its contract does not yet exist.

### Not accepted
- committed production credentials;
- public PostgreSQL/API exposure in the baseline Compose topology;
- bypass of server-side RBAC;
- mutable audit history;
- floating workflow Actions or base container tags in the hardened baseline.

## Conclusion
The G1 Platform Core security baseline is sufficient for continuation to later development gates. This is not a production-security certification and does not waive the explicit ADR-0015/0017 controls required before production.
