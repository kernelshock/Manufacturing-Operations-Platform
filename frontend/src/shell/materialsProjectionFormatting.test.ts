import { describe, expect, it } from "vitest";
import { csvField, exactDecimalText, nonzeroDecimal } from "./materialsProjectionFormatting";

describe("G6.7 exact quantities and safe export", () => {
  it("never rounds or coerces large decimal quantities to binary float", () => {
    expect(exactDecimalText("1234567890123456.12345678")).toBe("1234567890123456.12345678");
    expect(exactDecimalText("4.25000000")).toBe("4.25");
    expect(exactDecimalText("0.00000000")).toBe("0");
    expect(exactDecimalText(null)).toBe("Desconocido");
  });
  it("preserves the difference between unknown and known zero stock", () => {
    expect(nonzeroDecimal(null)).toBe(false);
    expect(nonzeroDecimal("0.00000000")).toBe(false);
    expect(nonzeroDecimal("000.00")).toBe(false);
    expect(nonzeroDecimal("0.00000001")).toBe(true);
    expect(nonzeroDecimal("17.00000000")).toBe(true);
  });
  it("escapes CSV delimiters and neutralizes spreadsheet formulas", () => {
    expect(csvField("normal, text")).toBe('"normal, text"');
    expect(csvField('a"b')).toBe('"a""b"');
    expect(csvField("=HYPERLINK('x')")).toBe('"\'=HYPERLINK(\'x\')"');
    expect(csvField("@SUM(1)")).toBe('"\'@SUM(1)"');
    expect(csvField(null)).toBe('"Desconocido"');
  });
});
