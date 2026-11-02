import { describe, expect, it } from "vitest";

import { visibleModules } from "./permissions";

describe("permission-driven navigation", () => {
  it("always exposes the home module", () => {
    expect(visibleModules([]).map((item) => item.id)).toEqual(["home"]);
  });

  it("exposes audit only with audit.read", () => {
    const modules = visibleModules(["audit.read"]).map((item) => item.id);

    expect(modules).toContain("audit");
    expect(modules).not.toContain("admin");
  });

  it("exposes organizational structure for any core read capability", () => {
    const modules = visibleModules(["core.plant.read"]).map((item) => item.id);

    expect(modules).toContain("structure");
  });

  it("exposes Master Data only with a Master Data capability", () => {
    expect(
      visibleModules(["masterdata.read"]).map((item) => item.id)
    ).toContain("master-data");
    expect(
      visibleModules(["masterdata.edit"]).map((item) => item.id)
    ).toContain("master-data");
  });

  it("exposes Demand only with demand capabilities", () => {
    expect(
      visibleModules(["demand.read"]).map((item) => item.id)
    ).toContain("demand");
    expect(
      visibleModules(["demand.edit"]).map((item) => item.id)
    ).toContain("demand");
    expect(visibleModules([]).map((item) => item.id)).not.toContain("demand");
  });

  it("exposes administration with either administrative capability", () => {
    expect(
      visibleModules(["admin.users"]).map((item) => item.id)
    ).toContain("admin");
    expect(
      visibleModules(["admin.roles"]).map((item) => item.id)
    ).toContain("admin");
  });
});
