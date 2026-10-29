export type ModuleId =
  | "home"
  | "structure"
  | "audit"
  | "admin";

export type NavigationModule = {
  id: ModuleId;
  label: string;
  description: string;
  requiredAny?: string[];
};

export const navigationModules: NavigationModule[] = [
  {
    id: "home",
    label: "Inicio",
    description: "Estado operativo y contexto"
  },
  {
    id: "structure",
    label: "Estructura",
    description: "Organización, plantas y recursos",
    requiredAny: [
      "core.organization.read",
      "core.plant.read",
      "core.area.read",
      "core.workcenter.read",
      "core.resource.read"
    ]
  },
  {
    id: "audit",
    label: "Auditoría",
    description: "Trazabilidad inmutable",
    requiredAny: ["audit.read"]
  },
  {
    id: "admin",
    label: "Administración",
    description: "Usuarios, roles y permisos",
    requiredAny: ["admin.users", "admin.roles"]
  }
];

export function hasPermission(
  permissions: string[],
  permission: string
): boolean {
  return permissions.includes(permission);
}

export function canSeeModule(
  permissions: string[],
  module: NavigationModule
): boolean {
  if (!module.requiredAny?.length) {
    return true;
  }
  return module.requiredAny.some((permission) =>
    hasPermission(permissions, permission)
  );
}

export function visibleModules(
  permissions: string[]
): NavigationModule[] {
  return navigationModules.filter((module) =>
    canSeeModule(permissions, module)
  );
}
