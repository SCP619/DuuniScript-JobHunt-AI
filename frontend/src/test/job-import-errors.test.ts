import { describe, expect, it } from "vitest";
import { ApiError, errorMessage } from "@/api/errors";
import { importAction } from "@/components/jobs/add-job-dialog";

describe("job import recovery actions", () => {
  it.each(["http_status", "dns_failed", "timeout", "robots_disallowed", "other", undefined])("offers later/manual for any 502 reason: %s", (reason) => {
    const error = new ApiError(502, "fetch_failed", "The site could not be opened.", { reason });
    expect(importAction(error)).toBe("later");
    expect(errorMessage(error)).toBe(error.message);
  });
  it("offers manual entry when structured data is absent", () => {
    expect(importAction(new ApiError(422, "no_structured_job_data", "No job details were found."))).toBe("manual");
  });
  it("offers manual entry when robots disallows access", () => {
    expect(importAction(new ApiError(422, "fetch_failed", "Automated access is not allowed.", { reason: "robots_disallowed" }))).toBe("manual");
  });
  it("offers retry for a 504 timeout", () => {
    expect(importAction(new ApiError(504, "fetch_failed", "The site took too long.", { reason: "timeout" }))).toBe("retry");
  });
  it.each(["url_import_disabled", "source_disabled"])("disables imports for %s", (code) => {
    expect(importAction(new ApiError(403, code, "Importing is disabled."))).toBe("disable");
  });
  it("offers the existing job for duplicates", () => {
    expect(importAction(new ApiError(409, "duplicate_job", "Already saved.", { job_id: "sample-job" }))).toBe("duplicate");
  });
  it.each(["blocked_address", "not_html"])("does not offer manual recovery for %s", (reason) => {
    expect(importAction(new ApiError(422, "fetch_failed", "This link cannot be imported.", { reason }))).toBe("none");
  });
});