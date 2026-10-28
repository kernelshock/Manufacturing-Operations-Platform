# Prolowin Complete Structure Reference — X-1148

Status: G0 reference sample  
Date captured: 2026-10-28  
Source: Prolowin report "Estructura del Artículo - Completa - Todos los Artículos" supplied by FAIC

## Parent article

- Article: `X-1148`
- Configuration: `ENT2-R14-4APB-I310+PA+APNA+RHL(PF/PF/CN/...)`
- Report quantity: `1.00 UNID.`
- Report scope: complete structure / all articles
- Report length observed: 7 pages

This report is treated as the first complete product-structure reference for the future Prolowin assimilation model.

## Critical finding: rows mix article identity and operation stage

The report columns are:

- `Código`
- `Op.`
- `Descripción`
- `Cantidad`

The same article code may appear multiple times with different operation codes and then again with `FIN`.

Examples visible in the report:

```text
0336   020   PLANCHUELA 109 ... CORTAR 109 MM      4.0000 UNID.
0336   FIN   PLANCHUELA 109 ...                     4.0000 UNID.

15176L 020   CHAPA PATA ... EMBUTIR M/IZQUIERDA     1.0000 UNID.
15176L 030   CHAPA PATA ... PRIMER EMBUTIDO          1.0000 UNID.
15176L 040   CHAPA PATA ... SEGUNDO EMBUTIDO         1.0000 UNID.
15176L 050   CHAPA PATA ... TERCER EMBUTIDO          1.0000 UNID.
15176L FIN   CHAPA PATA INCLINADA 195 MM             1.0000 UNID.

18416  020   CAÑO RESPALDO ... CORTAR 194            2.0000 UNID.
18416  030   CAÑO RESPALDO ... 1° CURVA              2.0000 UNID.
18416  FIN   CAÑO RESPALDO ...                       2.0000 UNID.

3960   020   PORTAPISTON ... CORTAR DESARROLLO       2.0000 UNID.
3960   030   PORTAPISTON ... EMBUTIR                  2.0000 UNID.
3960   FIN   PORTAPISTON ESTRUCTURA                   2.0000 UNID.

5251   030   CAÑO CURVADO 870 ... CURVAR              2.0000 UNID.
5251   FIN   CAÑO CURVADO 870 ...                     2.0000 UNID.

5876   020   SOPORTE APOYAPIERNAS ... CORTE 405 MM    2.0000 UNID.
5876   FIN   SOPORTE APOYAPIERNAS EJECUTIVO-1        2.0000 UNID.

SR-118 010   RESP ENTI ...                            2.0000 UNID.
SR-118 FIN   RESP ENTI ...                            2.0000 UNID.
```

## Import rule derived from this pattern

Rows with the same article code but different `Op.` values are **not independent material requirements by default**.

They may represent successive manufacturing states/operations of the same physical item.

Therefore a naive import that sums every row would overstate demand.

The importer must separate:

```text
ARTICLE IDENTITY
    code = 15176L
    final required quantity = 1

from

OPERATION TRACE
    020 -> ...
    030 -> ...
    040 -> ...
    050 -> ...
    FIN -> finished state
```

The same rule applies to other repeated codes.

## Preliminary row semantics

Suggested canonical interpretation:

```text
SourceStructureRow
- parent_article_code
- article_code
- source_operation_code
- source_description
- reported_quantity
- reported_uom
- report_level/path if available
- source_report_timestamp
```

Then normalize into separate entities:

```text
Article
Operation
ArticleOperation
ComponentRelation
MaterialRequirement
```

A transformation rule must determine whether a row is:
- a component requirement;
- an intermediate operation state;
- a final manufactured component;
- a raw/purchased material;
- or an unknown case requiring review.

## Visible examples of leaf/raw/consumable-type requirements

The report includes many codes that appear to be direct material requirements, for example:

- `0156` CEMENTO DE CONTACTO — 1.3002 LITROS
- `0199` TUBO PVC CRISTAL 4*6 MM — 0.2760 MTS
- `0215` PERFIL PLASTICO 120 MM — 4.0000 UNID.
- `0223` BOLSA RESPALDO EJECUTIVO — 2.0000 UNID.
- `0249` BOLSA APOYAPIERNAS EJECUTIVO — 2.0000 UNID.
- `0311` TUBO EST RECT 30*20*1.8 MM — 2.2996 BARRA
- `0312` TUBO EST CUAD 20*20*1.8 MM — 0.2000 BARRA
- `0317` TREFILADO (1010) 6.35*3000MM — 0.0800 BARRAS
- `0380` TUERCA AUTOBLOQUEANTE 1/4 W — 8.0000 UNID.
- `0398` NO TEJIDO BLANCO 80 GRS — 0.5400 MTS
- `0568` TUBO EST RECT 50*30*1.6 MM — 0.0483 BARRA
- `14690` BUJE SOPORTAPESO (TIPO CLIP) — 8.0000 UNID.
- `15025` PLASTICO CLAVA TAPIZADO EJECUTIVO — 2.0000 UNID.
- `15276` TORNILLO HEX. M8*1.25*35 G8.8 GALVANIZADO — 4.0000 UNID.
- `15277` ARANDELA PLANA GALVANIZADA ESP 2 MM D INT 8.4 — 4.0000 UNID.
- `16077` FLEJE 3.2*84 MM LC DECAPADO — 0.1506 KGS.
- `17342` TACO RESPALDO PISTON ALEMAN — 2.0000 UNID.
- `17575` NO TEJIDO BLANCO RESPALDO — 2.0000 UNID.
- `17890` BUJE ROSCADO L=35MM CINTURON 3P. — 2.0000 UNID.
- `1791` GRAMPA 84/11 — 92.0000 UNID.
- `17985` TORNILLO HEXAGONAL 12*3/4 P. MECHA GALVANIZADO — 4.0000 UNID.
- `3123` ARANDELA SEGUER RS6 — 4.0000 UNID.
- `3160` TUERCA AUTOBLOQUEANTE 5/16 GALVANIZADA — 4.0000 UNID.
- `3233` ESPUMA RESPALDO ENTERPRISE — 2.0000 UNID.
- `3540` NO TEJIDO MOLDE 201 RESP — 2.0000 UNID.
- `3937` FLEJE 1.6*74 MM LAMINADO FRIO — 1.4556 KGS.
- `3947` PORTA ZIG-ZAG (PLASTICO) — 20.0000 UNID.
- `3955` PUNTERA PISTON 784575 (STABILUS) — 2.0000 UNID.
- `3961` PERNO PORTAPISTON SEMICAMA (TORNERIA) — 2.0000 UNID.
- `5411` RESORTE ZIG-ZAG BASE EJECUTIVO-1 — 6.0000 UNID.
- `5429` ELAST POLIESTER BENTLEY N°20 ANCHO 9 MM — 1.5181 MTS
- `5430` TORNILLO 8X5/8 P. MECHA PHILIP. S/ARAND GALV. — 2.0000 UNID.
- `5434` PALANQUITA PUNTERA PISTON 783234 — 2.0000 UNID.
- `5692C` TOPE PLASTICO PISTON ANGOSTO — 6.0000 UNID.
- `5692G` TOPE PLASTICO PISTON ANCHO — 4.0000 UNID.
- `5855` RESORTE CAJON EJECUTIVO DORADO — 4.0000 UNID.
- `5966M` TAPA BUMERANG ENTERPRISE DERECHO — 1.0000 UNID.
- `5967M` TAPA BUMERANG ENTERPRISE IZQUIERDO — 1.0000 UNID.

These examples also confirm heterogeneous units of measure:
- UNID.
- MTS
- LITROS
- KGS.
- BARRA / BARRAS

The import model must preserve the source UoM and normalize it through a controlled UoM master rather than assuming all quantities are discrete pieces.

## Visible manufactured/subassembly codes

The complete report also includes structured codes such as:

- `SA-100` APOYAPIERNAS ENTERPRISE 425 (ESTRUCTURA) — 2
- `SB-101` BASE ORION / ENTERPRISE STD — 2
- `SC-117` CHASIS(1) IZQUIERDA DE DOBLE ENTERPRISE (R14) — 1
- `SC-118` CHASIS(1) DERECHO DE DOBLE ENTERPRISE (R14) — 1
- `SC-119` CHASIS(2) ENTERPRISE R14 (ESTRUCTURA) — 1
- `SCAJ-103` CAJON TRASERO DOBLE ORION (ESTRUCTURA) — 1
- `SL-102(D)` COSTADO DER ENT R14 (...) — 2
- `SL-104(I)` COSTADO IZQ ENT R14 (...) — 1
- `SL-108(I)` COSTADO IZQ ENT R14 (...) — 1
- `SP-122(D)` PATA DER ... R14 — 1
- `SPAR-109` PARRILLA ENT DOBLE - C/CAJON - 2PP / CON CHAPA U — 1
- `SR-118` RESP ENTI ... — 2

These codes support the recursive manufactured-subassembly model established in the earlier X-1148 analysis.

## Important distinction for the full-structure report

The "Completa - Todos los Artículos" report appears to flatten:
1. material requirements;
2. intermediate manufactured components;
3. operation stages.

Therefore it is excellent as a **reconciliation/check report**, but should not automatically be treated as a directly importable flat BOM.

Preferred ingestion strategy:
- import the native parent-child structures recursively where possible;
- import this complete report as a validation/reconciliation projection;
- compare the recursively exploded canonical BOM against the Prolowin complete report.

## Validation objective

For any article X:

```text
Canonical recursive explosion(X)
        should reconcile with
Prolowin "Completa - Todos los Artículos" projection(X)
```

subject to defined rules for:
- repeated operation rows;
- intermediate manufactured items;
- UoM normalization;
- scrap/yield if later identified;
- substitutes;
- inactive/obsolete operations.
