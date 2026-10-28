# Prolowin Complete Structure Reference — X-2209

Status: G0 reference sample  
Date captured: 2026-10-28  
Source: Prolowin report "Estructura del Artículo - Completa - Todos los Artículos" supplied by FAIC

## Parent article

- Article: `X-2209`
- Configuration shown: `MR2-R14-3APB-1030-PP+APNA+RHL(...)`
- Product family: Moonraker Semicama
- Report quantity: `1.00 UNID.`
- Report scope: complete structure / all articles
- Report length observed: 6 pages

This is the third complete reference product used to validate the future Prolowin assimilation model.

## 1. Cross-family validation

Unlike X-1148/X-1149, X-2209 belongs to a different product family. It confirms that the structural rules already identified are not limited to Enterprise.

The report again contains:
- raw / purchased materials;
- manufactured parts;
- manufactured subassemblies;
- repeated article codes across operation stages;
- heterogeneous units of measure;
- final manufactured states;
- higher-level module codes.

## 2. Examples of direct material / component requirements

Visible examples include:

| Code | Description | Qty | UoM |
|---|---|---:|---|
| 0128 | RESORTE APOYAPIERNA SEMICAMA DORADO | 4.0000 | UNID. |
| 0156 | CEMENTO DE CONTACTO | 0.2223 | LITROS |
| 0199 | TUBO PVC CRISTAL 4*6 MM | 0.2760 | MTS |
| 0215 | PERFIL PLASTICO 120 MM | 4.0000 | UNID. |
| 0311 | TUBO EST RECT 30*20*1.8 MM | 1.3978 | BARRA |
| 0317 | TREFILADO 6.35*3000 | 0.1818 | BARRAS |
| 0398 | NO TEJIDO BLANCO 80 GRS | 0.2800 | MTS |
| 10532 | UNI SEGUN ESPECIFICACIONES (1.80 MTS) | 0.5000 | MTS |
| 11005 | TUERCA HEXAGONAL AUTOFRENANTE 7/16 SAE | 6.0000 | UNID. |
| 11006 | ARANDELA PLANA 7/16 HO | 2.0000 | UNID. |
| 14099 | REMACHE APOYABRAZOS MIDI BUS F10 | 6.0000 | UNID. |
| 14180 | TIRE DE CINTA PTO DIAMANTE DE 300 MM | 14.0000 | UNID. |
| 1423 | NYLON 6 SF NC010 | 0.0710 | KGS. |
| 1426 | POLIPROPILENO-PX 2630 | 0.3654 | KGS. |
| 14639 | CHAPA EN HOJA 1245*3000*2 LC DECAPADO | 0.9256 | KGS. |
| 14641 | CHAPA EN HOJA 1500*3000*3.2 LC | 3.6789 | KGS. |
| 14642 | CHAPA EN HOJA 1500*3000*4.75 LC | 0.6635 | KGS. |
| 14643 | CHAPA EN HOJA 1500*3000*6.35 LC | 8.6748 | KGS. |
| 15024 | PLASTICO CLAVA TAPIZADO SEMICAMA | 2.0000 | UNID. |
| 16565 | REVISTERO MOONRAKER | 2.0000 | UNID. |
| 16614M | APOYABRAZO MOONRAKER F10 | 3.0000 | UNID. |
| 16829 | TAPA APOYABRAZO SEMICAMA F10 | 3.0000 | UNID. |
| 17127 | BOLSA APOYAPIERNAS PREENFUNDADO SEMICAMA | 2.0000 | UNID. |
| 17273 | FLEJE 2.5*307 MM LC-DECAPADO | 1.3940 | KGS. |
| 17285M | CUBRE CENTRAL PARTE TRASERA | 1.0000 | UNID. |
| 17342 | TACO RESPALDO PISTON ALEMAN | 2.0000 | UNID. |
| 17423L | PALANCA SISTEMA RECLINACION MOONRAKER | 2.0000 | UNID. |
| 18484 | ESPUMA RESPALDO MOONRAKER R14 | 2.0000 | UNID. |
| 18500 | ESPUMA ALMOHADON MOONRAKER S.CAMA | 2.0000 | UNID. |
| 18501 | POLIETER TAPA TRASERA RESPALDO MOONRAKER | 2.0000 | UNID. |
| 18552 | TORNILLO P-MADERA 6*3/4 NEGRO | 8.0000 | UNID. |
| 18555 | LAMINA 80*100 - 30 MIC LISAS | 2.0000 | UNID. |
| 3160 | TUERCA AUTOBLOQUEANTE 5/16 GALVANIZADA | 8.0000 | UNID. |
| 3163 | BOLSA APOYAPIERNAS SEMICAMA | 2.0000 | UNID. |
| 3320 | POLIETILENO DE ALTA | 0.0044 | KGS. |
| 3946 | RESORTE ZIG-ZAG RESP SEMICAMA | 10.0000 | UNID. |
| 3947 | PORTA ZIG-ZAG | 20.0000 | UNID. |
| 3955 | PUNTERA PISTON 784575 | 2.0000 | UNID. |
| 3961 | PERNO PORTAPISTON SEMICAMA | 2.0000 | UNID. |
| 4177 | GAS DE SOLDAR | 0.2674 | MTS 3 |
| 4194 | ALAMBRE MIG MAG 0.9 MM | 0.3769 | KGS. |
| 4338 | TORNILLO 8X3/4 P. MECHA PHILIP TANQ. C/ARAND GALV. | 29.0000 | UNID. |
| 8026 | TUERCA AUTOBLOQUEANTE M8*1.25 MM | 4.0000 | UNID. |
| 8135 | PANA DINICAR P/COSTOS | 2.5000 | MTS |
| 9379 | ESM. POLIESTER MICRO TXT GRIS | 0.1832 | KGS. |
| 9808 | BOLSA RESPALDO SEMICAMA | 2.0000 | UNID. |

## 3. Repeated manufacturing-operation pattern

Examples again confirm that the same article can traverse several source operations:

```text
0045   020   PORTABUJE SOPORTA PESO - CORTAR Y PERFORAR   4
0045   030   PORTABUJE SOPORTA PESO - EMBUTIDO            4
0045   FIN   PORTABUJE SOPORTA PESO                       4

14375  020   CAÑO CENTRAL MIDIBUS F10 - CORTAR 500 MM     1
14375  FIN   CAÑO CENTRAL MIDIBUS F10                     1

17425  020   ARO APOYAPIERNAS SEMICAMA F10 - CORTE ...   2
17425  FIN   ARO APOYAPIERNAS SEMICAMA F10               2

18378  010   CAÑO RESPALDO MOONRAKER ... - CORTAR        2
18378  020   CAÑO RESPALDO MOONRAKER ... - DOBLADO       2
18378  FIN   CAÑO RESPALDO MOONRAKER ...                  2

3960   020   PORTAPISTON ESTRUCTURA - CORTAR DESARROLLO   2
3960   030   PORTAPISTON ESTRUCTURA - EMBUTIR             2
3960   FIN   PORTAPISTON ESTRUCTURA                       2
```

This reinforces the rule that operation rows are routing/state data, not separate additive material demand.

## 4. Strong new finding: one manufactured article spans multiple productive areas

The higher-level article `A-208` appears as:

```text
A-208 010 RESPALDO MOONRAKER ... - BALAN   2
A-208 020 RESPALDO MOONRAKER ... - CORTE   2
A-208 030 RESPALDO MOONRAKER ... - COSTU   2
A-208 040 RESPALDO MOONRAKER ... - PEGAD   2
A-208 050 RESPALDO MOONRAKER ... - ENFUN   2
A-208 FIN RESPALDO MOONRAKER ...           2
```

This is direct evidence that Prolowin uses operation sequences to represent a subassembly moving through multiple productive processes.

The abbreviations correspond operationally to FAIC's known production areas:
- BALAN -> Balancines
- CORTE -> Corte
- COSTU -> Costura
- PEGAD -> Pegado
- ENFUN -> Enfundado

Therefore the canonical model must support a true ordered route:

```text
ManufacturedArticle
    |
    +--> OperationSequence
            010 -> Process/Area
            020 -> Process/Area
            030 -> Process/Area
            040 -> Process/Area
            050 -> Process/Area
            FIN -> completion state
```

The same article identity persists across the route.

## 5. High-level modules confirmed for X-2209

Visible final-level module rows include:
- `A-208` RESPALDO MOONRAKER S.CAMA ... × 2
- `B-202` ALMOHADON-MOONRAKER (R14) × 2
- `C-225` CHASIS-MOONRAKER S.CAMA ... × 1
- `D-238` SUB CJ PATA 225 ... R14 × 1

These align with the earlier costing screen for X-2209 and confirm the same multi-level product-structure pattern across a different family.

## 6. Architectural consequence: BOM and BOP are distinct but linked

A product/subassembly requires two orthogonal models:

### BOM / ABM
What is needed:

```text
ParentArticle
    -> child components/materials
    -> quantity
    -> UoM
```

### BOP / Routing
How it is produced:

```text
ManufacturedArticle
    -> ordered operations
    -> process/area
    -> resource/work center
    -> nominal rate/calendar/capability
```

The source may expose both in the same reports/screens, but MOP must normalize them separately.

## 7. Route import rule

For each manufactured article:
1. preserve source operation code;
2. preserve source operation description;
3. derive sequence order from source code only when validated;
4. map source operation to canonical process/area through an explicit mapping table;
5. attach resource/work-center data from the manufacturing-process screen where available;
6. mark `FIN` as completion/final state, not automatically as a physical operation;
7. preserve effective/source dates.

The system must not infer area solely from article code prefixes.

## 8. Cross-sample conclusion after three products

X-1148, X-1149 and X-2209 jointly confirm:

- recursive product structures are a general pattern;
- complete reports are flattened projections;
- operation rows must be separated from material requirements;
- exact product/configuration BOMs are required;
- source UoMs must be preserved;
- manufactured articles may have multi-operation routes;
- routes can span several productive areas;
- high-level modules recur conceptually across families but use different codes and structures;
- the canonical model should support both BOM explosion and BOP/routing reconstruction.
