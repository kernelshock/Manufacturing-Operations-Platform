import type { OperationalPlanProjection } from "../api/types";

/** UI-only labels built from G3's canonical projection; never copy into MES records. */
export function mesDisplayLabels(projection: OperationalPlanProjection | null): Map<string, string> {
  const result = new Map<string, string>();
  for (const taquilla of projection?.taquillas ?? []) {
    result.set(`taquilla:${taquilla.id}`, taquilla.taquilla_code);
    for (const product of taquilla.products) {
      result.set(`product:${product.id}`, `${product.article_code} · ${product.article_description}`);
    }
  }
  return result;
}
