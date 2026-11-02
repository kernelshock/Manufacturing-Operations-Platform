export type GanttScale = "hour" | "shift" | "day";

export function pixelsPerHour(scale: GanttScale): number {
  if (scale === "hour") return 56;
  if (scale === "shift") return 24;
  return 8;
}

export function timelineHours(startIso: string, endIso: string): number {
  return Math.max(
    1,
    (new Date(endIso).getTime() - new Date(startIso).getTime()) / 3_600_000
  );
}

export function offsetHours(startIso: string, targetIso: string): number {
  return Math.max(
    0,
    (new Date(targetIso).getTime() - new Date(startIso).getTime()) / 3_600_000
  );
}

export function widthHours(startIso: string, endIso: string): number {
  return Math.max(
    0,
    (new Date(endIso).getTime() - new Date(startIso).getTime()) / 3_600_000
  );
}

export function timelineWidthPx(
  startIso: string,
  endIso: string,
  scale: GanttScale
): number {
  return Math.max(900, timelineHours(startIso, endIso) * pixelsPerHour(scale));
}
