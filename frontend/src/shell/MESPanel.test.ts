import { describe, expect, it } from "vitest";
import { navigationModules, visibleModules } from "../lib/permissions";

describe("G5.7 MES navigation authorization", () => {
  it("exposes MES to mes.read, hides it without MES grants", () => {
    expect(navigationModules.find(module => module.id === "mes")?.requiredAny).toEqual(["mes.read", "mes.edit"]);
    expect(visibleModules([]).some(module => module.id === "mes")).toBe(false);
    expect(visibleModules(["mes.read"]).some(module => module.id === "mes")).toBe(true);
    expect(visibleModules(["mes.edit"]).some(module => module.id === "mes")).toBe(true);
  });
});
