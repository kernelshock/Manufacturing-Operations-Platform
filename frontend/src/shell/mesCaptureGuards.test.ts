import { describe, expect, it } from "vitest";
import { canCaptureOperation } from "./mesCaptureGuards";

describe("G5.8 cross-dispatch execution protection", () => {
  const opA = { dispatch_id: "dispatch-A" };
  it("allows a released dispatch and editor to capture its own operation", () => {
    expect(canCaptureOperation(opA, "dispatch-A", true, "RELEASED")).toBe(true);
  });
  it("rejects stale selection from the previously selected dispatch", () => {
    expect(canCaptureOperation(opA, "dispatch-B", true, "RELEASED")).toBe(false);
  });
  it("rejects viewers, missing operations and unreleased dispatches", () => {
    expect(canCaptureOperation(opA, "dispatch-A", false, "RELEASED")).toBe(false);
    expect(canCaptureOperation(null, "dispatch-A", true, "RELEASED")).toBe(false);
    expect(canCaptureOperation(opA, "dispatch-A", true, "DRAFT")).toBe(false);
    expect(canCaptureOperation(opA, "dispatch-A", true, "CANCELLED")).toBe(false);
  });
});
