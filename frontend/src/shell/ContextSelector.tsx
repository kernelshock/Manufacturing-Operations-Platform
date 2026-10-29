import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { CurrentUser, Organization, Plant } from "../api/types";
import { hasPermission } from "../lib/permissions";

export type PlantContext = {
  organization: Organization | null;
  plant: Plant | null;
};

export function ContextSelector({
  user,
  value,
  onChange
}: {
  user: CurrentUser;
  value: PlantContext;
  onChange: (next: PlantContext) => void;
}) {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [plants, setPlants] = useState<Plant[]>([]);
  const [loading, setLoading] = useState(false);

  const canReadOrganizations = hasPermission(
    user.permissions,
    "core.organization.read"
  );
  const canReadPlants = hasPermission(user.permissions, "core.plant.read");

  useEffect(() => {
    if (!canReadOrganizations) return;
    setLoading(true);
    api
      .organizations()
      .then(setOrganizations)
      .finally(() => setLoading(false));
  }, [canReadOrganizations]);

  useEffect(() => {
    if (!value.organization || !canReadPlants) {
      setPlants([]);
      return;
    }
    api.plants(value.organization.id).then(setPlants);
  }, [value.organization, canReadPlants]);

  if (!canReadOrganizations) {
    return (
      <div className="context-chip" title="Ámbito determinado por RBAC">
        Ámbito asignado
      </div>
    );
  }

  return (
    <div className="context-selector" aria-label="Contexto operativo">
      <select
        aria-label="Organización"
        disabled={loading}
        value={value.organization?.id ?? ""}
        onChange={(event) => {
          const organization =
            organizations.find((item) => item.id === event.target.value) ??
            null;
          onChange({ organization, plant: null });
        }}
      >
        <option value="">Organización</option>
        {organizations.map((organization) => (
          <option key={organization.id} value={organization.id}>
            {organization.code} · {organization.name}
          </option>
        ))}
      </select>

      <select
        aria-label="Planta"
        disabled={!value.organization || !canReadPlants}
        value={value.plant?.id ?? ""}
        onChange={(event) => {
          const plant =
            plants.find((item) => item.id === event.target.value) ?? null;
          onChange({ ...value, plant });
        }}
      >
        <option value="">Planta</option>
        {plants.map((plant) => (
          <option key={plant.id} value={plant.id}>
            {plant.code} · {plant.name}
          </option>
        ))}
      </select>
    </div>
  );
}
