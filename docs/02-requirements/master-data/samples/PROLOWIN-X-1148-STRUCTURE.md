# Prolowin Product Structure Sample — X-1148 Enterprise

Status: G0 source-structure analysis  
Date: 2026-10-28  
Source: Prolowin manufacturing-process screens supplied by FAIC

## 1. Finished article

Article:
- Code: `X-1148`
- Description/configuration: `ENT2-R14-4APB-I310+PA+APNA+RHL(PF/PF/CN/PL.PL/PF)`

Production operation shown:
- Code: `FIN`
- Description: `COSTEAR COMPONENTES`

Top-level required articles:

| Child code | Role / description | Qty | Unit |
|---|---|---:|---|
| A-115 | RESP ENTERPRISE EJECUTIVO R14 (RELAX) | 2.000000 | UNID. |
| B-104 | ALMOHADON ENTERPRISE (R14) TIPO ORION (NUEVO) | 2.000000 | UNID. |
| C-109 | CHASIS-ENTERPRISE (2) R14-4APB-I310-SALDIVA | 1.000000 | UNID. |
| D-113 | SUB CJ PATA 195+AGARRE ENTERP R14 (DOB) SALDIVA | 1.000000 | UNID. |
| E-110 | CAJON TRASERO ORION DOBLE C/AP H=425 | 1.000000 | UNID. |
| F-107 | ESPUMA DE FORMA (RELAX HIBRIDO LISO) ENTERPRISE | 2.000000 | UNID. |
| G-158 | RHL (PEA/PEA/CNA/PLI/PLI/PEA) C.APNAS (PEA/CNA) | 2.000000 | UNID. |

This confirms that `X-1148` is an assembled/configured parent article whose BOM children are themselves manufacturing or material entities.

## 2. Child article A-115

Article:
- Code: `A-115`
- Description: `RESP ENTERPRISE EJECUTIVO R14 (RELAX)`

Production operation:
- Code: `FIN`
- Description: `ARMAR COMPONENTES`

Executor/resource:
- Code: `0050`
- Name: `CALESITA DE ARMADO`
- Principal: `SI`
- Rate shown: `50.00 Unid./Hora`

Required articles visible in the supplied screen:

| Child code | Description | Qty | Unit |
|---|---|---:|---|
| SR-118 | RESP ENTI C.PARR S.REV I R14 | RE | REC. EJECUT | 1.000000 | UNID. |
| 4177 | GAS DE SOLDAR (835 M3/1500) | 0.067000 | MTS 3 |
| 4194 | ALAMBRE MIG MAG 0.9 MM | 0.094000 | KGS. |
| 9379 | ESM. POLIESTER MICRO TXT GRIS (COD 226135/1) | 0.036000 | KGS. |
| 2395 | RESORTE ZIG-ZAG RESP EJECUTIVO (RESORTES) | 5.000000 | UNID. |
| 3947 | PORTA ZIG-ZAG (PLASTICO) | 1.000000 | UNID. |
| 16547 | PERNO SOPORTAPESO 58.5MM CROM.BLANCO | 2.000000 | UNID. |
| 11533 | TUERCA HEXAGONAL AUTOFRENANTE M 10*1 | 2.000000 | UNID. |
| 3233 | ESPUMA RESPALDO ENTERPRISE (INYEC.FRIO) | 1.000000 | UNID. |
| 3540 | NO TEJIDO MOLDE 201 RESP (325*600) | 1.000000 | UNID. |

Interpretation:
- `SR-118` is another structured child/subassembly candidate.
- Numeric codes such as 4177/4194/etc. appear as purchased or consumable leaf materials in this level, but leaf status must be validated recursively during import.
- Quantities include both discrete units and continuous/consumable units.

## 3. Child article B-104

Article:
- Code: `B-104`
- Description: `ALMOHADON ENTERPRISE (R14) TIPO ORION (NUEVO)`

Production operation:
- Code: `FIN`
- Description: `SOLDAR COMPONENTES`

Executor/resource:
- Code: `0160`
- Name: `ROBOT SOLD.N°3`
- Principal: `SI`
- Rate shown: `10.00 Unid./Hora`

Required articles visible in the supplied screen:

| Child code | Description | Qty | Unit |
|---|---|---:|---|
| SB-101 | BASE ORION /ENTERPRISE STD | 1.000000 | UNID. |
| 4177 | GAS DE SOLDAR (835 M3/1500) | 0.019000 | MTS 3 |
| 4194 | ALAMBRE MIG MAG 0.9 | 0.027000 | KGS. |
| 9379 | ESM. POLIESTER MICRO TXT GRIS (COD 226135/1) | 0.050000 | KGS. |
| 5411 | RESORTE ZIG-ZAG BASE EJECUTIVO-1 (RESORTES) | 3.000000 | UNID. |
| 3096 | MANGUERA DE BASE 23 MM | 6.000000 | UNID. |
| 2085 | ESPUMA ALMOHADON EJECUTIVO (INYEC.FRIO) | 1.000000 | UNID. |
| 0156 | CEMENTO DE CONTACTO* 200 LITROS | 0.075000 | LITROS |
| 2105 | GRAMPA DORADA RING 16G110 N26 | 9.000000 | UNID. |
| 12366 | BOLSA ALMOHADON EJECUTIVO | 1.000000 | UNID. |

Interpretation:
- `SB-101` is another lower-level structured child/subassembly candidate.
- The same consumables (for example 4177, 4194, 9379) can appear in more than one manufactured child with different usage quantities.

## 4. Confirmed structural pattern

The data structure is recursive:

```text
Finished Article X-1148
  |
  +-- A-115 x2
  |     |
  |     +-- SR-118 x1
  |     +-- 4177 gas x0.067
  |     +-- 4194 wire x0.094
  |     +-- ...
  |
  +-- B-104 x2
  |     |
  |     +-- SB-101 x1
  |     +-- 4177 gas x0.019
  |     +-- 4194 wire x0.027
  |     +-- ...
  |
  +-- C-109 x1
  +-- D-113 x1
  +-- E-110 x1
  +-- F-107 x2
  +-- G-158 x2
```

The model must therefore support arbitrary-depth BOM explosion rather than a fixed number of levels.

## 5. Routing / operation data embedded by article

Each manufactured article may also have:
- one or more production operations;
- executor/resource code;
- executor/resource name;
- principal flag;
- rate such as units/hour;
- operator/user;
- effective/update date.

This means the source is not only a BOM/ABM repository; it also contains elements of the **routing / Bill of Process (BOP)**.

Canonical separation should be:

```text
Article / ProductRevision
   |
   +-- BOM/ABM structure
   |      +-- ComponentRelation(parent, child, qty, UoM)
   |
   +-- Routing / Operations
          +-- Operation
          +-- Resource / WorkCenter
          +-- nominal rate
```

## 6. Import design implications

The future Prolowin importer must not assume code prefixes are sufficient to determine entity type.

For every code it should:
1. import the article master;
2. query/read its product structure;
3. detect whether it has children;
4. classify it provisionally as manufactured/subassembly vs leaf material;
5. preserve parent-child quantity and UoM;
6. recursively expand children until no further structure is found;
7. separately import operation/resource data;
8. detect cycles or invalid self-references;
9. version/effective-date the imported structure;
10. retain original Prolowin code as external business key.

## 7. Key finding for Materials

Material demand cannot be calculated only from the first level.

For example, one X-1148 contains two A-115 and two B-104. Therefore the total demand for welding gas 4177 attributable to those two visible branches alone is:

```text
A-115 contribution = 2 × 0.067 = 0.134 m3
B-104 contribution = 2 × 0.019 = 0.038 m3

Visible subtotal = 0.172 m3 per X-1148
```

Additional branches (C-109, D-113, E-110, F-107, G-158 and deeper children) may add further demand.

This demonstrates why MOP needs a recursive explosion engine with quantity multiplication across levels.


## 8. Costing pseudo-operations vs physical production operations

The parent article `X-1148` shows:
- operation `FIN / COSTEAR COMPONENTES`;
- executor `5555 / MAQUINA FICTICIA (COSTO)`.

This must not automatically become a schedulable production resource in APS.

By contrast:
- `A-115`: `ARMAR COMPONENTES` executed by `0050 / CALESITA DE ARMADO`;
- `B-104`: `SOLDAR COMPONENTES` executed by `0160 / ROBOT SOLD.N°3`;

represent physical production operations/resources.

Therefore imported source operations require classification, for example:

```text
operation_kind:
  PHYSICAL_PRODUCTION
  COSTING_ONLY
  ADMINISTRATIVE
  UNKNOWN
```

and resources require:

```text
resource_kind:
  PHYSICAL_MACHINE
  MANUAL_STATION
  LABOR_RESOURCE
  COSTING_PSEUDO_RESOURCE
  UNKNOWN
```

Only validated physical production operations/resources may contribute finite capacity to APS.
