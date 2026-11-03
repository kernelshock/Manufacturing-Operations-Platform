import { describe, expect, it } from "vitest";
import type { OperationalPlanProjection } from "../api/types";
import { mesDisplayLabels } from "./mesDisplayLabels";

describe("G5.8 canonical MES labels", () => {
  it("preserves empty labels when demand context is not authorized or available", () => {
    expect(mesDisplayLabels(null).size).toBe(0);
  });

  it("uses the exact G3 taquilla/product IDs and descriptions without fabricating values", () => {
    const projection = {
      taquillas: [
        {
          id: "taquilla-01",
          taquilla_code: "26-157",
          products: [
            { id: "product-01", article_code: "MR-001", article_description: "Moonraker" },
            { id: "product-02", article_code: "AP-001", article_description: "Apollo" },
          ],
        },
      ],
    } as unknown as OperationalPlanProjection;
    const labels = mesDisplayLabels(projection);
    expect(labels.get("taquilla:taquilla-01")).toBe("26-157");
    expect(labels.get("product:product-01")).toBe("MR-001 · Moonraker");
    expect(labels.get("product:product-02")).toBe("AP-001 · Apollo");
    expect(labels.has("product:unknown")).toBe(false);
  });
});
