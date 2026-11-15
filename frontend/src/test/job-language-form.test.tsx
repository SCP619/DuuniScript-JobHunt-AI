import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useState } from "react";
import { emptyJobForm, formToCreate, formToUpdate, JobFields } from "@/components/jobs/job-fields";

function Form({ language = "" }: { language?: string }) {
  const [values, setValues] = useState({ ...emptyJobForm(), language });
  return <JobFields idPrefix="test" mode="edit" values={values} errors={{}} onChange={(key, value) => setValues((prev) => ({ ...prev, [key]: value }))} />;
}

describe("posting language form values", () => {
  it("sends null for Not set", () => {
    expect(formToCreate(emptyJobForm()).language).toBeNull();
    expect(formToUpdate({ ...emptyJobForm(), language: "fi" }, emptyJobForm()).language).toBeNull();
  });
  it("preselects Other for an existing outside code and preserves it", () => {
    render(<Form language="de" />);
    expect((screen.getByLabelText("Posting language") as HTMLSelectElement).value).toBe("other");
    expect((screen.getByLabelText("Language code") as HTMLInputElement).value).toBe("de");
    expect(formToUpdate({ ...emptyJobForm(), language: "de" }, { ...emptyJobForm(), language: "de" })).toEqual({});
  });
  it("allows entering an Other code and returning to a named language", () => {
    render(<Form />);
    fireEvent.change(screen.getByLabelText("Posting language"), { target: { value: "other" } });
    fireEvent.change(screen.getByLabelText("Language code"), { target: { value: "de" } });
    expect(formToCreate({ ...emptyJobForm(), language: "de" }).language).toBe("de");
    fireEvent.change(screen.getByLabelText("Posting language"), { target: { value: "fi" } });
    expect(screen.queryByLabelText("Language code")).toBeNull();
    expect((screen.getByLabelText("Posting language") as HTMLSelectElement).value).toBe("fi");
  });
});