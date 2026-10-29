import { useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../api/client";
import type {
  ProductConfiguration,
  Supplier,
  UnitOfMeasure
} from "../api/types";

export function MasterDataPanel() {
  const [configurations, setConfigurations] = useState<ProductConfiguration[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [uoms, setUoms] = useState<UnitOfMeasure[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    Promise.all([api.productConfigurations(), api.suppliers(), api.uoms()])
      .then(([configurationData, supplierData, uomData]) => {
        if (!active) return;
        setConfigurations(configurationData);
        setSuppliers(supplierData);
        setUoms(uomData);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(
          reason instanceof ApiError
            ? reason.message
            : "No fue posible cargar los datos maestros."
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const uomById = useMemo(
    () => new Map(uoms.map((uom) => [uom.id, uom.code])),
    [uoms]
  );

  return (
    <>
      <section className="content-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">G2 · Master Data</p>
            <h2>Configuraciones de producto</h2>
          </div>
          <span className="status-pill neutral">
            {configurations.length} activas
          </span>
        </div>

        {loading ? <p className="muted">Cargando datos maestros…</p> : null}
        {error ? <p className="inline-error">{error}</p> : null}

        {!loading && !error && configurations.length === 0 ? (
          <p className="muted">
            Todavía no hay configuraciones de producto activas. Cada configuración
            se vincula a un Article terminado exacto.
          </p>
        ) : null}

        {configurations.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Familia</th>
                  <th>Modelo</th>
                  <th>Clase</th>
                  <th>Ancho</th>
                  <th>Configuración</th>
                </tr>
              </thead>
              <tbody>
                {configurations.map((configuration) => (
                  <tr key={configuration.id}>
                    <td>
                      <strong>{configuration.family_code}</strong>
                      <br />
                      <small>{configuration.family_name}</small>
                    </td>
                    <td>
                      <strong>{configuration.model_code}</strong>
                      <br />
                      <small>{configuration.model_name}</small>
                    </td>
                    <td>{configuration.product_class}</td>
                    <td>
                      {configuration.width
                        ? `${configuration.width} ${uomById.get(
                            configuration.width_uom_id ?? ""
                          ) ?? ""}`.trim()
                        : "—"}
                    </td>
                    <td>{configuration.configuration_string}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <section className="content-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Abastecimiento</p>
            <h2>Proveedores</h2>
          </div>
          <span className="status-pill neutral">{suppliers.length} activos</span>
        </div>

        {!loading && !error && suppliers.length === 0 ? (
          <p className="muted">
            Todavía no hay proveedores activos en el maestro canónico.
          </p>
        ) : null}

        {suppliers.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Razón social</th>
                  <th>Nombre comercial</th>
                  <th>Rubro</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map((supplier) => (
                  <tr key={supplier.id}>
                    <td><strong>{supplier.code}</strong></td>
                    <td>{supplier.legal_name}</td>
                    <td>{supplier.trade_name ?? "—"}</td>
                    <td>{supplier.supply_category}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </>
  );
}
