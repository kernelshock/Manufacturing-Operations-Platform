# ADR-0012 — Normalize Prolowin Complete Reports by FIN Projection

Status: Accepted  
Date: 2026-10-28

## Context
Five authoritative Prolowin PDF reports were reviewed for:
X-1148, X-1149, X-2209, X-6111 and X-7070.

For this exact report format, every unique article code has exactly one `FIN` row. Manufactured articles may additionally have 010/020/025/030/040/050 operation rows.

The finished/root product itself also appears as a FIN row.

## Decision
For the Prolowin report format:
`Estructura del Artículo — Completa - Todos los Artículos`

MOP will normalize as follows:

1. preserve every source row immutably;
2. treat non-FIN rows as source operation/routing evidence;
3. use the single FIN row as the article's quantity in the flattened complete projection;
4. exclude the root article FIN row from component-demand summation;
5. never infer recursive parent-child hierarchy from the flattened report alone;
6. use native direct structures/tables to build canonical recursive BOM;
7. use the complete FIN projection as a reconciliation oracle.

## Validation guard
The FIN rule is accepted for the validated report format, not blindly for every possible Prolowin export.

If an imported batch for this format contains:
- zero FIN rows for an article code;
- multiple FIN rows for one article code;
- an unidentified root;
the batch/row must be flagged for review instead of silently accepted.

## Consequences
This prevents double-counting intermediate manufacturing stages while retaining their routing information and gives the migration process a deterministic reconciliation target.
