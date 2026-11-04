/** Exact-decimal presentation and safe CSV escaping without binary float conversion. */
export function exactDecimalText(value: string | null): string {
  return value === null ? "Desconocido" :
    value.replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
}

export function nonzeroDecimal(value: string | null): boolean {
  return value !== null && !/^[-+]?0+(?:\.0+)?$/.test(value);
}

export function csvField(value: unknown): string {
  let cell = String(value ?? "Desconocido").replace(/[\r\n]+/g, " ");
  if (/^[=+@-]/.test(cell)) cell = "'" + cell;
  return '"' + cell.replace(/"/g, '""') + '"';
}
