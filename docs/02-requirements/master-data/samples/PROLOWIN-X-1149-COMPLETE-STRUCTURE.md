# Prolowin Complete Structure Reference — X-1149

Status: G0 reference sample  
Date captured: 2026-10-28  
Source: Prolowin report "Estructura del Artículo - Completa - Todos los Artículos" supplied by FAIC

## Parent article

- Article: `X-1149`
- Configuration: `ENT1-R14-2APB-655+PA+APNA+RHL(PF/PF/CN/PL.PL/PF)` (as shown across supplied Prolowin screens)
- Report quantity: `1.00 UNID.`
- Report scope: complete structure / all articles
- Report length observed: 7 pages
- Product family: Enterprise
- Configuration role: single-seat Enterprise reference

This is the second complete reference product used to validate the future Prolowin assimilation model.

## Relationship to X-1148

`X-1148` and `X-1149` belong to the same Enterprise family but represent different configurations.

The comparison is useful because it demonstrates that product structure cannot be derived from a simple multiplier alone.

Examples visible in both reports:

| Code | X-1148 | X-1149 | Observation |
|---|---:|---:|---|
| 0156 CEMENTO DE CONTACTO | 1.3002 L | 0.6501 L | exactly 1/2 in visible reports |
| 0199 TUBO PVC CRISTAL | 0.2760 m | 0.1380 m | exactly 1/2 |
| 0215 PERFIL PLASTICO 120 MM | 4 | 2 | exactly 1/2 |
| 0223 BOLSA RESPALDO EJECUTIVO | 2 | 1 | exactly 1/2 |
| 0249 BOLSA APOYAPIERNAS EJECUTIVO | 2 | 1 | exactly 1/2 |
| 0317 TREFILADO 6.35*3000 | 0.0800 | 0.0400 | exactly 1/2 |
| 0398 NO TEJIDO BLANCO 80 GRS | 0.5400 m | 0.2700 m | exactly 1/2 |
| 15176L CHAPA PATA INCLINADA | 1 | 1 | fixed at this level, not halved |
| 15276 TORNILLO HEX. M8*1.25*35 | 4 | 4 | fixed |
| 15277 ARANDELA PLANA | 4 | 4 | fixed |
| 16077 FLEJE 3.2*84 | 0.1506 kg | 0.0753 kg | exactly 1/2 |
| 1791 GRAMPA 84/11 | 92 | 46 | exactly 1/2 |
| 17985 TORNILLO HEXAGONAL 12*3/4 | 4 | 2 | exactly 1/2 |
| 3937 FLEJE 1.6*74 | 1.4556 kg | 0.7278 kg | exactly 1/2 |
| 3947 PORTA ZIG-ZAG | 20 | 10 | exactly 1/2 |
| 3960 PORTAPISTON ESTRUCTURA | 2 | 1 | exactly 1/2 |
| 3961 PERNO PORTAPISTON | 2 | 1 | exactly 1/2 |
| 5434 PALANQUITA PUNTERA PISTON | 2 | 1 | exactly 1/2 |
| 5692C TOPE PISTON ANGOSTO | 6 | 3 | exactly 1/2 |
| 5692G TOPE PISTON ANCHO | 4 | 2 | exactly 1/2 |
| 5855 RESORTE CAJON EJECUTIVO | 4 | 2 | exactly 1/2 |
| 5876 SOPORTE APOYAPIERNAS | 2 | 1 | exactly 1/2 |

Other items differ by configuration rather than by a pure 2:1 ratio. Therefore MOP must always use the effective BOM/ABM of the exact product/configuration code.

## Repeated operation-state pattern confirmed

The same source pattern observed in X-1148 is present again.

Examples:

```text
0336   020 ... CORTAR ...       2
0336   FIN ...                  2

15176L 020 ...                  1
15176L 030 ...                  1
15176L 040 ...                  1
15176L 050 ...                  1
15176L FIN ...                  1

17651  020 ... CORTAR 59MM      2
17651  FIN ...                  2

3960   020 ... CORTAR ...       1
3960   030 ... EMBUTIR          1
3960   FIN ...                  1

4064   020 ... PERFORAR ...     1
4064   030 ... EMBUTIR ...      1
4064   040 ... SACAR BOCADO     1
4064   050 ... EMBUTIDO         1
4064   FIN ...                  1

5876   020 ... CORTE 405 MM     1
5876   FIN ...                  1

SR-118 010 ...                  1
SR-118 FIN ...                  1
```

This confirms that `Op.` is part of the manufacturing-state/routing representation and cannot be summed as independent material consumption.

## Additional manufactured / structured items visible

Examples in the supplied X-1149 report include:
- `SL-103(I)` COSTADO IZQ ENT R14 (BUTACA STD)
- `SP-122(I)` PATA IZQ ... R14
- `SPAR-117` PARRILLA CHASIS ENTERP(1) R14 ...
- `SR-118` RESP ENTI ...
- `4064` LATERAL BASE SEMICAMA EJEC IZQ with multiple operations
- `4065` LATERAL BASE SEMICAMA DERECHO with manufacturing operations
- `18478L` CHAPA U DE PATA ... with cutting + FIN
- `18597L` CHAPA L DE PARRILLA ... with cutting + FIN

These reinforce the recursive manufactured-component model.

## Source-data quality observation

The report contains at least one suspicious unit/value combination visible in the supplied pages:

`17959 — FLEJE 3.2*52 MM LC-DECAPADO — 0.0922 UNID.`

A strip/fleje expressed as `UNID.` may be legitimate in Prolowin or may reflect a master-data inconsistency. It must be preserved exactly on ingestion and flagged for validation rather than silently converted.

This supports a general rule:

```text
source UoM -> preserve
canonical UoM mapping -> validate
conversion -> only after approved mapping
```

## Parent self-row

The final page explicitly contains:

`X-1149 | FIN | ENT1-R14-2APB-655+PA+APNA+RHL(...) | 1.0000 UNID.`

Therefore the complete report includes the root article itself in addition to descendants.

Import/reconciliation logic must exclude the root self-row from component-demand summation.

## Structural conclusion from X-1148 + X-1149

Two complete samples now confirm:

1. the full report is a flattened projection, not a pure flat BOM;
2. it contains the root article;
3. it contains manufactured subassemblies;
4. it contains raw/purchased materials;
5. it contains repeated rows for successive operations;
6. it contains heterogeneous UoM;
7. quantities depend on exact product configuration;
8. some quantities scale with seat count while others are configuration-fixed;
9. product-family similarity is not sufficient to infer consumption;
10. recursive source structure remains the authoritative way to derive the canonical BOM.

## Canonical assimilation rule

For every finished product code:

```text
Exact ProductRevision / Configuration
        |
        +--> recursive ComponentRelation tree
        |
        +--> ArticleOperation / Routing
        |
        +--> flattened canonical material explosion
        |
        +--> reconcile against Prolowin complete report
```

The complete report is used as a reconciliation oracle after operation rows and root/self rows are normalized appropriately.
