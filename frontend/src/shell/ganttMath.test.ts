import { describe, expect, it } from "vitest";

import {
  offsetHours,
  pixelsPerHour,
  timelineHours,
  timelineWidthPx,
  widthHours
} from "./ganttMath";

describe("Gantt projection math", () => {
  const start = "2026-11-02T10:00:00Z";
  const end = "2026-11-02T16:00:00Z";

  it("derives coordinates only from backend timestamps", () => {
    expect(timelineHours(start, end)).toBe(6);
    expect(offsetHours(start, "2026-11-02T12:30:00Z")).toBe(2.5);
    expect(widthHours("2026-11-02T12:30:00Z", "2026-11-02T13:15:00Z")).toBe(0.75);
  });

  it("changes visual density without changing time semantics", () => {
    expect(pixelsPerHour("hour")).toBeGreaterThan(pixelsPerHour("shift"));
    expect(pixelsPerHour("shift")).toBeGreaterThan(pixelsPerHour("day"));
    expect(timelineWidthPx(start, end, "hour")).toBeGreaterThanOrEqual(900);
  });
});
