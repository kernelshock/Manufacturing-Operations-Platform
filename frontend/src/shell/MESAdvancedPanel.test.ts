import { describe, expect, it } from "vitest";
import { successorCandidates } from "./MESAdvancedPanel";

const record = (id: string, dispatch_id: string, product_line_id: string, routing_sequence_no: number) => ({
  id, dispatch_id, product_line_id, routing_sequence_no,
  operation_code: "OP", operation_description: "Etapa", status: "PENDING",
  produced_quantity: null
});

describe("G5.8 MES WIP/rework target selection", () => {
  it("filters successors to the same dispatch and product line in routing order", () => {
    const source = record("a","dispatch-1","product-1",1);
    const second = record("b","dispatch-1","product-1",2);
    const third = record("c","dispatch-1","product-1",3);
    const crossProduct = record("x","dispatch-1","product-2",2);
    const crossDispatch = record("y","dispatch-2","product-1",2);
    const earlier = record("z","dispatch-1","product-1",0);
    expect(successorCandidates([third,crossProduct,second,crossDispatch,earlier,source],source).map(x=>x.id))
      .toEqual(["b","c"]);
    expect(successorCandidates([source],null)).toEqual([]);
  });
});
