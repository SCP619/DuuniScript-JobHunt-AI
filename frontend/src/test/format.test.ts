import { describe, expect, it } from "vitest";
import { formatDateOnly, formatDateTime, isPastDate } from "@/lib/format";
import { fieldErrors, ApiError } from "@/api/errors";
import { buildQuery } from "@/api/http";

describe("date display rules", () => {
  it("formats YYYY-MM-DD as d.M.yyyy", () => {
    expect(formatDateOnly("2026-03-05")).toBe("5.3.2026");
  });
  it("returns null for a missing date (shown as 'Not stated', never guessed)", () => {
    expect(formatDateOnly(null)).toBeNull();
  });
  it("shows exact deadline times in Helsinki time", () => {
    expect(formatDateTime("2026-11-30T14:00:00Z")).toBe("30.11.2026 at 16.00");
  });
  it("detects passed deadlines against Helsinki today", () => {
    expect(isPastDate("2026-01-01", new Date("2026-01-02T12:00:00Z"))).toBe(true);
    expect(isPastDate("2026-01-02", new Date("2026-01-02T12:00:00Z"))).toBe(false);
  });
});

describe("API helpers", () => {
  it("repeats status params", () => {
    expect(buildQuery({ status: ["new", "saved"], q: "" })).toBe("?status=new&status=saved");
  });
  it("maps validation_error loc to field names", () => {
    const e = new ApiError(422, "validation_error", "x", { fields: [{ loc: ["body", "title"], msg: "Required", type: "missing" }] });
    expect(fieldErrors(e)).toEqual({ title: "Required" });
  });
});
