# Manufacturing-Operations-Platform
Plataforma modular de Manufacturing Operations Management (MOM)

Sí. Este es el momento correcto para cambiar de enfoque. La v1.4 ya cumplió una función muy valiosa: nos permitió descubrir, mediante uso real, cómo funciona FAIC, qué datos existen, cuáles faltan, qué excepciones aparecen y dónde se conectan Producción, Materiales, Compras, Mantenimiento y Personas.

Mi recomendación es **congelar la v1.4 como prototipo funcional y referencia de requisitos** y comenzar una arquitectura nueva. No intentaría seguir agregando funciones al HTML actual hasta transformarlo accidentalmente en un ERP/MES monolítico difícil de mantener.

El nuevo proyecto debería concebirse como una **plataforma modular de Manufacturing Operations Management (MOM)**. Es precisamente la filosofía con la que Siemens separa MES, APS, Quality e Intelligence dentro de Opcenter, y encaja muy bien con ISA-95: el sistema que estamos diseñando corresponde fundamentalmente al nivel 3 —Manufacturing Operations Management— y debe poder intercambiar información con sistemas empresariales de nivel 4 y, en el futuro, con PLC, sensores y automatización de niveles 1–2. [isa.org](https://www.isa.org/standards-and-publications/isa-standards/isa-95-standard?utm_source=chatgpt.com)

## 1. Objetivo del nuevo sistema

La definición que propondría a Dirección sería:

> Construir una plataforma industrial modular y configurable que permita planificar, ejecutar, controlar y analizar las operaciones productivas, coordinando capacidad, materiales, personas, mantenimiento y abastecimiento sobre una única fuente de información operativa, sin alterar abruptamente la metodología actual de trabajo y permitiendo una migración gradual hacia una gestión digital integrada.

No lo llamaría ya “Dashboard de Producción”.

Internamente lo consideraría:

**FAIC Manufacturing Operations Platform — FMOP**

El nombre comercial puede decidirse posteriormente porque la arquitectura deberá permitir instalarlo en otras industrias.

El principio rector sería:

**una única plataforma, múltiples módulos, una única semántica de datos.**

---

# 2. Decisión de arquitectura

No recomiendo microservicios puros en esta etapa.

Recomiendo:

**Monolito modular + API-first + Event Driven Architecture + configuración versionada.**

Conceptualmente:

```text
                         ┌────────────────────────────┐
                         │      INTERFAZ WEB / PWA    │
                         │ dashboards · Gantt · nodos │
                         └──────────────┬─────────────┘
                                        │
                              API / WebSocket
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             │              OPERATIONS PLATFORM CORE               │
             │                                                     │
             │  Identity · Roles · Config · Audit · Events · Files │
             └───────────────┬─────────────────────────────────────┘
                             │
      ┌─────────────┬────────┼─────────┬──────────┬───────────┐
      │             │        │         │          │           │
      ▼             ▼        ▼         ▼          ▼           ▼
     APS            MES   MATERIALS  PURCHASES MAINTENANCE  WORKFORCE
 Planning        Execution  Kanban
      │             │        │         │          │           │
      └─────────────┴────────┴─────────┴──────────┴───────────┘
                             │
                      EVENT / DATA LAYER
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
              ANALYTICS            INTEGRATIONS
              KPI / RPD         ERP · files · PLC
```

Cada módulo tendrá su propio dominio lógico y API, aunque inicialmente se ejecuten dentro de la misma aplicación.

Eso nos permite, más adelante, separar físicamente:

`APS Service`

`Maintenance Service`

`Inventory Service`

etc., sin tener que rediseñar todo.

---

# 3. Qué conservar de la versión actual

Muchísimo.

No estamos tirando el trabajo realizado. Lo que cambia es su función.

La v1.4 se transforma en nuestra:

**Functional Reference Implementation.**

De ella tomaremos:

- modelo Plan → Taquilla → Producto;
- importador R-IC-08;
- segmentación por piso;
- segmentación por ancho;
- rutas productivas;
- editor visual tipo n8n;
- Gantt por proceso;
- calendario FAIC;
- setup;
- continuidad entre taquillas;
- avance real;
- materiales/ABM;
- PP/PR;
- compras/recepciones;
- mantenimiento;
- informes;
- What-if;
- indicadores.

Pero ya no continuaremos desarrollando esas capacidades dentro de un único HTML/IndexedDB.

---

# 4. Referencia funcional: SkyPlanner + Siemens + n8n

No intentaría copiar ninguno de los tres sistemas.

Tomaría un principio distinto de cada uno.

De **SkyPlanner** tomaría la experiencia de planificación: Gantt de capacidad finita, materiales, recursos, prioridades, bloqueos, replanning, What-if, shop-floor feedback, disponibilidad de personas, herramientas y materiales. SkyPlanner actualmente combina explícitamente capacidad, materiales, skills, setup, Gantt interactivo y realimentación desde planta. [SkyPlanner](https://skyplanner.ai/features/?utm_source=chatgpt.com)

De **Siemens Opcenter** tomaría la arquitectura MOM: planificación APS + ejecución MES + Intelligence + futuras integraciones de Quality/PLM. Siemens también separa BOM, routing, ejecución, capacidad, materiales e intelligence, que es exactamente hacia donde evolucionó espontáneamente nuestro prototipo. [Siemens](https://www.siemens.com/en-us/content/architecture-hub/op-center/?utm_source=chatgpt.com)

De **n8n** tomaría la UX del modelado visual: nodos, conexiones, entradas/salidas, ramificaciones, configuración contextual, trazabilidad de ejecuciones y extensibilidad. n8n está construido precisamente alrededor de workflows conectables y nodos configurables, además de poder autohospedarse. [n8n Docs](https://docs.n8n.io/?utm_source=chatgpt.com)

Pero hay una regla importante:

> El editor podrá parecerse conceptualmente a n8n. El núcleo transaccional de producción NO debe comportarse como un workflow no-code genérico.

Stock, producción, consumos, mantenimiento, compras y programación deben ejecutarse mediante reglas determinísticas, auditables y validadas.

---

# 5. Arquitectura funcional propuesta

Propongo 10 módulos.

| Módulo | Función principal |
|---|---|
| CORE | Usuarios, permisos, configuración, auditoría, eventos |
| MASTER DATA | Productos, materiales, recursos, proveedores, calendarios |
| DEMAND / ORDERS | Planes, taquillas, pedidos y prioridades |
| APS | Planificación y programación de capacidad finita |
| MES | Ejecución y seguimiento real de producción |
| MATERIALS | ABM/BOM, stock, consumos, Kanban, PP/PR |
| PURCHASING | Solicitudes, compras, proveedores, recepciones |
| MAINTENANCE | Activos, OT, fallas, impacto productivo |
| WORKFORCE | Personas, turnos, competencias, horas |
| INTELLIGENCE | KPI, metas, análisis y RPD |

Después aparecerían módulos opcionales:

`QUALITY`

`PLM`

`ENGINEERING`

`DESIGN & DEVELOPMENT`

`COSTING`

`CRM`

pero la arquitectura deberá preverlos desde el inicio.

Siemens, por ejemplo, utiliza MBOM y BOP como objetos centrales de planificación de fabricación dentro de Teamcenter; conviene que nuestro modelo de datos contemple desde ahora producto, revisión, BOM y proceso aunque todavía no construyamos PLM. [Siemens](https://www.siemens.com/en-us/solutions/manufacturing-process-planning/?utm_source=chatgpt.com)

---

# 6. CORE: la pieza más importante

El error habitual sería comenzar otra vez por el Gantt.

Esta vez empezaría por el núcleo.

CORE deberá administrar:

```text
Organización
    ↓
Planta
    ↓
Área
    ↓
Centro de trabajo
    ↓
Recurso
```

y transversalmente:

```text
Usuarios
Roles
Permisos
Calendarios
Unidades
Estados
Documentos
Configuraciones
Eventos
Auditoría
```

Esto permite que FAIC sea solamente una configuración.

Otra fábrica podría tener:

```text
Mecanizado
Tratamiento térmico
Pintura
Montaje
```

en lugar de:

```text
Balancines
Soldadura
Tapicería
Armado
```

sin modificar código.

---

# 7. Principio crítico: configuración, no forks

Para poder comercializarlo posteriormente, nunca deberíamos terminar con:

`FAIC_version.py`

`Cliente2_version.py`

`Cliente3_version.py`

Eso destruye la mantenibilidad.

Debe existir:

```text
PLATFORM
   +
INDUSTRY CONFIGURATION
```

Una instalación debería poder configurar:

- áreas;
- procesos;
- subprocesos;
- calendarios;
- turnos;
- productos;
- rutas;
- materiales;
- unidades;
- causas;
- estados;
- roles;
- KPI;
- fórmulas;
- dashboards;
- reglas;
- importadores;
- workflows;
- nomencladores.

---

# 8. Modelo maestro de información

Necesitamos abandonar la lógica de “campos sueltos”.

Los objetos fundamentales serán:

```text
PRODUCT
PRODUCT_VARIANT
PRODUCT_REVISION

MATERIAL
SUBASSEMBLY
ABM / BOM

ROUTING
PROCESS
OPERATION

RESOURCE
WORKCENTER
TOOL
ASSET

CUSTOMER_ORDER
PLAN
TAQUILLA

PRODUCTION_ORDER
OPERATION_EXECUTION

EMPLOYEE
SKILL
SHIFT

SUPPLIER
PURCHASE_ORDER
RECEIPT

INVENTORY
MATERIAL_MOVEMENT

MAINTENANCE_ORDER
DOWNTIME_EVENT

KPI
TARGET
ACTION
```

Esto será nuestro modelo canónico.

---

# 9. Fuente oficial de cada dato

Este punto es extremadamente importante.

No todo debe convertirse en “dato maestro del APS”.

Necesitamos definir **System of Record**.

Ejemplo:

| Información | Fuente oficial |
|---|---|
| Plan productivo | Operations Platform |
| Taquilla | PCP / Operations |
| ABM | Ingeniería/PCP |
| Stock operativo | Materials |
| Stock contable | ERP/Prolowin |
| Compra | Compras / ERP |
| Costo | Contabilidad |
| Ejecución productiva | MES |
| Mantenimiento | Maintenance |
| Personal | RRHH |
| Asignación turno/recurso | Workforce |

La plataforma debe **conciliar**, no apropiarse indiscriminadamente de todos los datos.

---

# 10. Flujo global de datos

El flujo completo que propondría es:

```text
PEDIDO / DEMANDA
        │
        ▼
PLAN
        │
        ▼
TAQUILLAS
        │
        ▼
PRODUCTOS / CONFIGURACIONES
        │
        ├─────────────► ABM / BOM
        │                    │
        │                    ▼
        │             DEMANDA MATERIAL
        │
        ▼
ROUTING / BOP
        │
        ▼
APS
capacidad + personas + materiales
        │
        ▼
PROGRAMA PUBLICADO
        │
        ▼
MES
ejecución real
        │
        ├────► tiempo real
        ├────► cantidades
        ├────► rechazos
        ├────► consumos
        │
        ▼
EVENTOS OPERATIVOS
        │
 ┌──────┼─────────┐
 ▼      ▼         ▼
STOCK  MAINT.   WORKFORCE
 │       │         │
 ▼       ▼         ▼
KANBAN CAPACIDAD HORAS
 │
 ▼
PP / PR
 │
 ▼
COMPRAS
 │
 ▼
RECEPCIONES
 │
 ▼
STOCK
```

Finalmente:

```text
TODOS LOS MÓDULOS
        ↓
INTELLIGENCE
        ↓
KPI
        ↓
METAS
        ↓
RPD
        ↓
DECISIONES
        ↓
ACCIONES
```

---

# 11. Arquitectura orientada a eventos

La comunicación entre módulos no debería depender de llamadas directas entre pantallas.

Ejemplo:

MES registra:

```text
OperationCompleted
```

El evento contiene:

```text
plan
taquilla
producto
operación
cantidad
hora
recurso
operador
```

Entonces otros módulos reaccionan.

Materials:

```text
OperationCompleted
→ MaterialConsumed
```

APS:

```text
OperationCompleted
→ recalcular programación
```

Intelligence:

```text
OperationCompleted
→ actualizar KPI
```

Maintenance podría producir:

```text
AssetDown
```

APS recibe:

```text
AssetDown
→ capacidad disponible = 0
→ recalcular riesgo
```

Esta arquitectura será fundamental para mantener los módulos desacoplados.

---

# 12. Eventos fundamentales

Algunos eventos que definiría desde el inicio:

```text
PlanCreated
PlanReleased
PlanPublished

TaquillaImported
ProductConfigured

ScheduleCalculated
SchedulePublished

OperationStarted
OperationCompleted
OperationDelayed

MaterialConsumed
StockAdjusted
StockBelowReorderPoint

ReplenishmentSuggested
PurchaseRequested
PurchaseIssued
MaterialReceived

AssetDown
AssetRestored

WorkerAssigned
ShiftChanged

KPIThresholdExceeded
ActionCreated
ActionClosed
```

Todos deben quedar auditados.

---

# 13. APS

El APS evolucionará hacia un motor verdadero de restricciones.

Debe considerar:

- capacidad finita;
- calendario;
- máquinas;
- personas;
- competencias;
- herramientas;
- dispositivos;
- materiales;
- setup;
- rutas;
- prioridades;
- mantenimiento;
- bloqueos;
- plazos.

Esto coincide con la función que Siemens define para APS: BOM, múltiples restricciones, materiales, capacidad, optimización y visualización interactiva. [Siemens](https://www.siemens.com/en-us/technology/advanced-planning-scheduling-aps/?utm_source=chatgpt.com)

El motor debería ser independiente de la UI.

Mi candidato técnico sería **OR-Tools CP-SAT**, inicialmente acompañado por heurísticas simples.

---

# 14. MES

El MES será el vínculo con planta.

Cada recurso/operario tendrá una interfaz extremadamente simple:

```text
QUÉ HACER AHORA

TQ 26-182
ENTERPRISE
SOLDADURA CHASIS
50 unidades

[ INICIAR ]
```

Luego:

```text
[ FINALIZAR ]

Cantidad OK
Cantidad rechazo
Problema
```

Nada más.

El resto debe venir precargado.

---

# 15. Materiales / ABM

Este módulo tendrá tres capas:

```text
ABM / BOM
   ↓
Demanda teórica
   ↓
Consumo real
```

Podremos comparar:

```text
TEÓRICO vs REAL
```

y detectar:

- sobreconsumo;
- merma;
- errores de ABM;
- rechazos;
- consumos anormales.

---

# 16. Kanban / MRP híbrido

No todo material debe manejarse igual.

Propondría:

```text
RUNNER
→ Kanban

REPEATER
→ Kanban / MRP

STRANGER
→ MRP / compra bajo necesidad
```

Y los puntos PP/PR podrán considerar:

```text
consumo histórico
+
demanda APS futura
+
lead time proveedor
+
stock seguridad
+
compras abiertas
```

---

# 17. Compras

Compras deberá recibir señales, no depender de recorrer tablas.

Ejemplo:

```text
MATERIAL 15137
Stock: 30
PP: 42
PR: 80

Proveedor: XXX
Lead time: 8 días

RIESGO:
Plan 26-215 afectado en 6 días
```

Entonces:

`GENERAR SOLICITUD`

no simplemente “material rojo”.

---

# 18. Mantenimiento

Mantenimiento debe estar conectado a capacidad.

No será solamente gestión de OT.

```text
Falla
 ↓
Activo
 ↓
Centro trabajo
 ↓
Capacidad perdida
 ↓
Planes afectados
 ↓
Pedidos afectados
```

Ejemplo:

> Robot 3 detenido → pérdida de 100 % de capacidad de Soldadura Respaldos → 3 planes afectados → primera fecha probable de atraso: X.

Eso transforma mantenimiento en información de decisión.

---

# 19. Workforce / Recursos Humanos operativos

No construiría un HRM.

Solo lo necesario para operaciones:

```text
Persona
Turno
Área
Competencias
Habilitaciones
Disponibilidad
Asignación
Horas
```

Entonces APS podrá saber:

```text
Robot disponible
pero
operador habilitado no disponible
```

por lo que la capacidad real será cero.

---

# 20. Costeo de mano de obra

Aunque no implementemos todavía PG-22 B/C, tendremos los datos para hacerlo.

Por producto:

```text
Producto
×
Proceso
×
Recurso
×
Horas
×
Cantidad
```

Entonces podrá conocerse:

`hh/unidad`

`hh/producto`

`hh/plan`

y comparar:

`ESTÁNDAR vs REAL`.

---

# 21. Intelligence

No quiero dashboards desconectados.

Cada KPI debe tener:

```text
KPI
Meta
Valor
Tendencia
Desviación
Causa
Responsable
Acción
Fecha
```

---

# 22. KPI operativos

Producción:

- cumplimiento del plan;
- OTD;
- throughput;
- lead time;
- WIP;
- productividad;
- adherencia al programa.

APS:

- carga/capacidad;
- estabilidad del programa;
- utilización;
- operaciones atrasadas;
- riesgo futuro.

Materiales:

- stockouts;
- cobertura;
- PP excedidos;
- rotación;
- consumo teórico vs real.

Compras:

- lead time real;
- OTIF proveedor;
- compras vencidas;
- recepción conforme.

Mantenimiento:

- downtime productivo;
- MTTR;
- MTBF;
- disponibilidad;
- impacto en planes.

Personas:

- hh/producto;
- productividad;
- cobertura de competencias;
- utilización.

---

# 23. RPD

El dashboard de Dirección no debería mostrar 100 indicadores.

Debería responder cinco preguntas:

```text
1. ¿Estamos cumpliendo?
2. ¿Qué está impidiendo cumplir?
3. ¿Qué riesgo tenemos hacia adelante?
4. ¿Qué tendencia está empeorando?
5. ¿Qué acción estamos tomando?
```

El reporte RPD podrá integrar:

```text
PRODUCCIÓN
MATERIALES
PROVEEDORES
MANTENIMIENTO
PERSONAS
CALIDAD
ACCIONES
```

---

# 24. Estrategia de adopción

Esta parte es crítica.

No pasaremos de:

`FAIC actual`

a:

`fábrica digital`

de un día para otro.

Usaremos cinco niveles.

| Nivel | Sistema |
|---|---|
| 0 | Observa |
| 1 | Replica |
| 2 | Recomienda |
| 3 | Controla |
| 4 | Automatiza |

Ejemplo materiales:

Primero:

`calcula PP`

Después:

`avisa`

Después:

`propone PR`

Después:

`genera solicitud`

Solo mucho más adelante:

`automatiza`.

Esto evita resistencia y errores de transición.

---

# 25. Estrategia de rollout

Cada módulo pasará por:

```text
DESARROLLO
 ↓
SIMULACIÓN
 ↓
SHADOW MODE
 ↓
PARALELO
 ↓
VALIDACIÓN
 ↓
PRODUCTIVO
```

Shadow mode significa que el nuevo sistema calcula, pero **no modifica nada**.

Eso será particularmente importante para:

- inventario;
- Kanban;
- compras;
- APS;
- mantenimiento.

---

# 26. Línea de evolución del proyecto

No voy a asignar todavía fechas artificiales. Propongo una línea por **gates demostrables ante Dirección**.

| Gate | Resultado demostrable |
|---|---|
| G0 | Arquitectura y modelo de datos aprobados |
| G1 | Plataforma Core funcionando |
| G2 | Maestros + importadores |
| G3 | Plan/Taquilla/Routing |
| G4 | APS capacidad finita |
| G5 | MES / ejecución real |
| G6 | Materiales + ABM |
| G7 | Kanban + Compras |
| G8 | Mantenimiento integrado |
| G9 | Workforce |
| G10 | Intelligence + RPD |
| G11 | Integraciones |
| G12 | Piloto industrial |
| G13 | Productivo FAIC |
| G14 | Paquete instalable multisector |

Cada Gate termina con:

**demo + evidencia + validación + decisión de continuar.**

Eso es lo que mostraría a Dirección.

---

# 27. Qué mostraría Dirección en cada avance

No mostraría código.

Mostraría:

```text
Alcance previsto
Alcance completado
Demo
Datos utilizados
Problema resuelto
Indicadores
Riesgos
Decisiones pendientes
Horas reales consumidas
```

---

# 28. Control de horas de desarrollo

Desde el primer Gate tendremos un Worklog.

Cada actividad debe registrar:

| Campo | Ejemplo |
|---|---|
| Fecha | 27/10/2026 |
| Gate | G2 |
| Módulo | Master Data |
| Tarea | Importador ABM |
| Tipo | Desarrollo |
| Horas reales | 3.5 |
| Resultado | Parser XLSX |
| Evidencia | commit / test |
| Reproceso | No |
| Motivo | — |

Las categorías serán:

```text
ANÁLISIS
ARQUITECTURA
UX
DESARROLLO
DATOS
TEST
DOCUMENTACIÓN
DESPLIEGUE
RETRABAJO
```

Dirección podrá ver:

```text
Horas acumuladas
Horas por módulo
Horas por Gate
Horas de retrabajo
% completado
Defectos abiertos
Defectos cerrados
```

No usaría las horas como principal métrica de éxito. Las acompañaría con **valor entregado y Gate alcanzado**.

---

# 29. Documentación técnica obligatoria

Desde G0 deberemos mantener:

```text
01 Architecture Decision Records
02 Data Dictionary
03 Domain Model
04 API Contracts
05 Event Catalog
06 Configuration Schema
07 Permissions Matrix
08 Test Cases
09 Deployment Guide
10 Release Notes
11 User Manuals
12 Migration Procedures
```

Así dejamos de tener conocimiento solamente “dentro del código”.

---

# 30. Infraestructura recomendada

Inicialmente:

```text
Servidor Linux intranet
        │
        ├── Web Frontend
        ├── API Backend
        ├── APS Worker
        ├── Background Workers
        │
        ├── PostgreSQL
        │
        └── Document Storage
```

Cliente:

```text
PC
Tablet
Terminal planta
TV dashboard
```

Posteriormente:

```text
PLC / máquina
   ↓
OPC UA / MQTT
   ↓
Edge Gateway
   ↓
Platform
```

Siemens utiliza precisamente una separación edge/MES de este tipo y contempla OPC UA para adquisición runtime. [Siemens](https://www.siemens.com/en-us/content/architecture-hub/op-center/?utm_source=chatgpt.com)

---

# 31. Seguridad

Desde el inicio:

- usuarios;
- roles;
- least privilege;
- audit log;
- TLS;
- backups;
- ambientes DEV/TEST/PROD;
- configuración versionada;
- trazabilidad de cambios;
- segmentación IT/OT.

ISA/IEC 62443 proporciona precisamente un marco de seguridad para sistemas industriales y recomienda abordar seguridad como combinación de personas, procesos y tecnología a lo largo del ciclo de vida. [isa.org](https://www.isa.org/standards-and-publications/isa-standards/isa-iec-62443-series-of-standards?utm_source=chatgpt.com)

---

# 32. Desarrollo / producción separados

Esto también debe cambiar.

Necesitamos:

```text
DEV
 ↓
TEST
 ↓
STAGING
 ↓
PRODUCTION
```

No editar directamente producción.

El propio enfoque documentado por n8n para entornos con source control advierte sobre el riesgo de mezclar desarrollo y producción y recomienda flujos de promoción controlados. [n8n Docs](https://docs.n8n.io/source-control-environments/create-environments/?utm_source=chatgpt.com)

---

# 33. Primera meta técnica

La primera versión de esta nueva arquitectura **no debería intentar fabricar todo otra vez**.

La llamaría:

### v2.0 — PLATFORM FOUNDATION

Y solo debería contener:

```text
CORE
Master Data
Plan
Taquilla
Producto
Routing
Resources
Calendars
Audit
Events
Configuration
```

Sin optimización avanzada.

Sin Kanban.

Sin mantenimiento.

Sin HR.

Primero construimos el esqueleto correcto.

---

# 34. Segunda meta

### v2.1 — APS

Recién allí:

```text
Finite capacity
Gantt
Routing visual
Priorities
What-if
Material constraints
Resource constraints
```

---

# 35. Tercera meta

### v2.2 — MES

```text
Start
Stop
Quantity
Scrap
Problem
Transfer
Operator
Resource
```

---

# 36. Después se conectan los demás módulos

```text
v2.3 Materials
v2.4 Purchasing
v2.5 Maintenance
v2.6 Workforce
v2.7 Intelligence
v2.8 Integration Hub
```

No significa que sean proyectos aislados.

Todos estarán previstos desde el modelo de datos inicial.

---

# 37. Un concepto fundamental: Integration Hub

Toda conexión externa debe pasar por adaptadores:

```text
                     OPERATIONS PLATFORM
                            │
                     INTEGRATION HUB
             ┌──────────────┼───────────────┐
             ▼              ▼               ▼
          PROLOWIN        FILES            API
             │              │               │
             ▼              ▼               ▼
           ERP        Excel / CSV      externos
```

Nunca deberíamos conectar directamente lógica productiva con una tabla específica de otro software.

---

# 38. Preparación para PLM futuro

Aunque PLM queda fuera del alcance actual, debemos reservar desde hoy conceptos como:

```text
Product Revision
Effectivity
MBOM
BOP
Change Order
Document Revision
```

De esa manera, dentro de unos años podríamos integrar Teamcenter, otro PLM o un módulo propio sin cambiar el corazón del MES.

---

# 39. Principio de diseño UX

La nueva plataforma tendrá tres patrones visuales principales:

**SkyPlanner**

para:

`planificación + capacidad + Gantt`.

**n8n**

para:

`routing + workflows + dependencias`.

**Siemens MOM**

para:

`estructura modular + ejecución + intelligence`.

No copiaríamos sus interfaces literalmente. Construiríamos un lenguaje visual coherente propio.

---

# 40. Lo más importante: no digitalizar malos hábitos

La plataforma no debe limitarse a informatizar todo exactamente como existe.

El principio que propongo será:

> primero reflejar la realidad; después medirla; después entenderla; después mejorarla; finalmente automatizarla.

Ese orden es fundamental.

---

## Mi recomendación final

Creo que debemos considerar terminado el ciclo:

**FAIC Dashboard Operaciones v0.x / v1.x**

como fase de **discovery y prototipado**.

La v1.4 nos permitió descubrir que el problema real no era construir un APS.

El problema real es construir un:

### Manufacturing Operations Management Platform

en el cual el APS es solamente uno de los motores.

La arquitectura correcta sería:

```text
                   OPERATIONS PLATFORM
                          CORE
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
      APS                 MES             MATERIALS
       │                   │                   │
       ├───────────┬───────┴──────┬────────────┤
       │           │              │            │
   WORKFORCE   MAINTENANCE    PURCHASING    QUALITY*
       │           │              │            │
       └───────────┴───────┬──────┴────────────┘
                           │
                      INTELLIGENCE
                           │
                          RPD
```

`* Quality` queda preparado pero fuera del alcance inicial.

Esto nos da una plataforma suficientemente simple para comenzar con FAIC y suficientemente sólida para que en el futuro pueda convertirse en un producto instalable en otras estructuras industriales.

---

### A partir de ahora, propongo avanzar exactamente como pediste: una decisión nueva por vez.

No voy a asumir cuestiones fundamentales de FAIC. Cuando necesite una definición, te la voy a preguntar antes de incorporarla al modelo.

Y la **primera pregunta** que necesitamos resolver para iniciar G0 es probablemente la más importante de toda la arquitectura:

**Hoy, ¿cuál es la fuente oficial para los datos de artículos/materiales, existencias, proveedores, órdenes de compra y recepciones: Prolowin, otro sistema, Excel, o una combinación de varios?**

Y especialmente necesito saber si **Prolowin permite acceder a esos datos mediante base de datos, exportación Excel/CSV o alguna API**, aunque hoy no la estén utilizando.

Esa respuesta determinará si nuestro módulo Materials/Purchasing será inicialmente **sistema maestro**, **sistema espejo** o **sistema de conciliación**.
