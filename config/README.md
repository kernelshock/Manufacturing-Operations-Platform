# Configuration

Versioned configuration schemas and tenant/plant configurations live here.

Planned structure:
- `schemas/`: validated configuration schemas.
- `tenants/faic/`: FAIC-specific configuration without forking platform code.

Rule: industrial customization must prefer configuration over client-specific code forks.

Runtime compatibility for each development/release baseline is pinned in `release-manifest.toml`. Secrets and environment-specific credentials are never stored here.
