# Prolowin Product Structure Reference Samples

These samples are used during G0 to derive the canonical assimilation rules before importing the complete Prolowin product base.

- `X-1148` — Enterprise double; complete-structure reference and recursive-BOM pattern.
- `X-1149` — Enterprise single; validates variant/configuration differences and scaling behavior.

## Current cross-sample findings

- Product structures are recursive.
- Complete reports flatten materials, subassemblies and operation stages.
- The same article code may repeat across operations; rows must not be naively summed.
- The root article itself can appear as a FIN row.
- Units of measure are heterogeneous and require controlled validation.
- Some consumption scales with seat count; some remains fixed; some is configuration-specific.
- Therefore BOMs must be tied to an exact product revision/configuration, not inferred from family-level multipliers.
