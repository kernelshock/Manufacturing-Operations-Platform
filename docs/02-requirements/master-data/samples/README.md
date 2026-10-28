> **Authority note — 2026-10-28:** the five complete PDFs (X-1148, X-1149, X-2209, X-6111, X-7070) are now the authoritative G0 reference corpus. Earlier screenshot-derived observations are superseded where they differ.

# Prolowin Product Structure Reference Samples

These samples are used during G0 to derive the canonical assimilation rules before importing the complete Prolowin product base.

- `X-1148` — Enterprise double; complete-structure reference and recursive-BOM pattern.
- `X-1149` — Enterprise single; validates variant/configuration differences and scaling behavior.
- `X-2209` — Moonraker Semicama; validates cross-family recursion and multi-area operation routing.

## Current cross-sample findings

- Product structures are recursive.
- Complete reports flatten materials, subassemblies and operation stages.
- The same article code may repeat across operations; rows must not be naively summed.
- The root article itself can appear as a FIN row.
- Units of measure are heterogeneous and require controlled validation.
- Some consumption scales with seat count; some remains fixed; some is configuration-specific.
- Therefore BOMs must be tied to an exact product revision/configuration, not inferred from family-level multipliers.

- X-2209 confirms that one manufactured article can traverse multiple productive areas before FIN.
- BOM/ABM (what is required) and BOP/Routing (how it is produced) must be normalized separately.

- `X-6111` — Apollo; links material 14027 Kanban demand to the complete product structure.
- `X-7070` — Discovery; validates cross-family reuse and shared subassemblies.
- Across all five authoritative PDFs, each unique article code has exactly one FIN row; non-FIN rows represent operation states. See ADR-0012.
