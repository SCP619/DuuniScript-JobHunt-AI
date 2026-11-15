import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, describedBy, selectClass } from "@/components/field";
import { EMPLOYMENT_TYPE, WORK_MODE } from "@/lib/labels";
import { isoToLocalInputs, localDateTimeToIso } from "@/lib/format";
import type { EmploymentType, JobCreate, JobRead, JobUpdate, WorkMode } from "@/api/types";

export interface JobFormValues {
  title: string; company: string; url: string; application_url: string; location: string; description: string;
  employment_type: string; work_mode: string; salary_text: string; language: string;
  published_on: string; deadline_on: string; deadline_at_date: string; deadline_at_time: string;
}

export const emptyJobForm = (url = ""): JobFormValues => ({
  title: "", company: "", url, application_url: "", location: "", description: "", employment_type: "",
  work_mode: "", salary_text: "", language: "", published_on: "", deadline_on: "", deadline_at_date: "", deadline_at_time: "",
});

export function jobToForm(j: JobRead): JobFormValues {
  const at = isoToLocalInputs(j.deadline_at);
  return {
    title: j.title, company: j.company, url: j.canonical_url ?? "", application_url: j.application_url ?? "",
    location: j.location ?? "", description: j.description ?? "", employment_type: j.employment_type ?? "",
    work_mode: j.work_mode ?? "", salary_text: j.salary_text ?? "", language: j.language ?? "",
    published_on: j.published_on ?? "", deadline_on: j.deadline_on ?? "", deadline_at_date: at.date, deadline_at_time: at.time,
  };
}

const n = (v: string) => (v.trim() === "" ? null : v);

/** Returns a client-side message if the deadline time inputs are half-filled. */
export function deadlineAtProblem(v: JobFormValues) {
  if (!!v.deadline_at_date !== !!v.deadline_at_time) return "Enter both a date and a time, or leave both empty.";
  return null;
}
const deadlineAt = (v: JobFormValues) =>
  v.deadline_at_date && v.deadline_at_time ? localDateTimeToIso(v.deadline_at_date, v.deadline_at_time) : null;

export function formToCreate(v: JobFormValues): JobCreate {
  return {
    title: v.title, company: v.company, url: n(v.url), application_url: n(v.application_url), location: n(v.location),
    description: n(v.description), employment_type: (n(v.employment_type) as EmploymentType | null),
    work_mode: (n(v.work_mode) as WorkMode | null), salary_text: n(v.salary_text), language: n(v.language),
    published_on: n(v.published_on), deadline_on: n(v.deadline_on), deadline_at: deadlineAt(v),
  };
}

/** Only fields that changed. title/company are sent as strings (the API rejects null). */
export function formToUpdate(initial: JobFormValues, v: JobFormValues): JobUpdate {
  const out: JobUpdate = {};
  const keys = ["location", "description", "employment_type", "work_mode", "salary_text", "language", "application_url", "published_on", "deadline_on"] as const;
  if (v.title !== initial.title) out.title = v.title;
  if (v.company !== initial.company) out.company = v.company;
  for (const k of keys) if (v[k] !== initial[k]) (out as Record<string, unknown>)[k] = n(v[k]);
  if (v.deadline_at_date !== initial.deadline_at_date || v.deadline_at_time !== initial.deadline_at_time) out.deadline_at = deadlineAt(v);
  return out;
}

export function JobFields({
  values, onChange, errors, mode, idPrefix,
}: {
  values: JobFormValues; onChange: (k: keyof JobFormValues, v: string) => void;
  errors: Record<string, string>; mode: "create" | "edit"; idPrefix: string;
}) {
  const [otherSelected, setOtherSelected] = useState(false);
  const otherLanguage = otherSelected || (!!values.language && !["en", "fi", "sv"].includes(values.language));
  const id = (k: string) => `${idPrefix}-${k}`;
  const text = (k: keyof JobFormValues, label: string, opts: { required?: boolean; type?: string; hint?: string; errKey?: string; max?: number } = {}) => {
    const err = errors[opts.errKey ?? k];
    return (
      <Field id={id(k)} label={label} required={opts.required} error={err} hint={opts.hint}>
        <Input id={id(k)} type={opts.type ?? "text"} value={values[k]} maxLength={opts.max}
          onChange={(e) => onChange(k, e.target.value)} required={opts.required} {...describedBy(id(k), err, !!opts.hint)} />
      </Field>
    );
  };
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {text("title", "Job title", { required: true, max: 300 })}
      {text("company", "Company", { required: true, max: 300 })}
      {mode === "create" && (
        <div className="sm:col-span-2">{text("url", "Link to the posting", { type: "url", hint: "Saved as a link only; DuuniScript won't open it." })}</div>
      )}
      <div className="sm:col-span-2">{text("application_url", "Application link", { type: "url" })}</div>
      {text("location", "Location")}
      <div className="space-y-3">
        <Field id={id("language")} label="Posting language" error={errors.language}>
          <select id={id("language")} className={selectClass} value={otherLanguage ? "other" : values.language}
            {...describedBy(id("language"), errors.language)}
            onChange={(e) => { setOtherSelected(e.target.value === "other"); onChange("language", e.target.value === "other" ? "" : e.target.value); }}>
            <option value="">Not set</option>
            <option value="en">English</option>
            <option value="fi">Finnish</option>
            <option value="sv">Swedish</option>
            <option value="other">Other</option>
          </select>
        </Field>
        {otherLanguage && <Field id={id("language-code")} label="Language code">
          <Input id={id("language-code")} value={values.language} maxLength={35} placeholder="de" onChange={(e) => onChange("language", e.target.value)} />
        </Field>}
      </div>
      <Field id={id("employment_type")} label="Employment type" error={errors.employment_type}>
        <select id={id("employment_type")} className={selectClass} value={values.employment_type} onChange={(e) => onChange("employment_type", e.target.value)}>
          <option value="">Not stated</option>
          {Object.entries(EMPLOYMENT_TYPE).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </Field>
      <Field id={id("work_mode")} label="Work mode" error={errors.work_mode}>
        <select id={id("work_mode")} className={selectClass} value={values.work_mode} onChange={(e) => onChange("work_mode", e.target.value)}>
          <option value="">Not stated</option>
          {Object.entries(WORK_MODE).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </Field>
      <div className="sm:col-span-2">{text("salary_text", "Salary", { hint: "Copy it exactly as the posting states it." })}</div>
      {text("published_on", "Published", { type: "date", hint: "Leave empty if the posting doesn't say." })}
      {text("deadline_on", "Deadline (date)", { type: "date", hint: "Leave empty if the posting doesn't say." })}
      <fieldset className="sm:col-span-2">
        <legend className="mb-1.5 text-sm font-medium">Exact deadline time (only if the posting states one)</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id={id("deadline_at_date")} label="Date" error={errors.deadline_at}>
            <Input id={id("deadline_at_date")} type="date" value={values.deadline_at_date} onChange={(e) => onChange("deadline_at_date", e.target.value)} {...describedBy(id("deadline_at_date"), errors.deadline_at)} />
          </Field>
          <Field id={id("deadline_at_time")} label="Time (your local time)">
            <Input id={id("deadline_at_time")} type="time" value={values.deadline_at_time} onChange={(e) => onChange("deadline_at_time", e.target.value)} />
          </Field>
        </div>
      </fieldset>
      <Field id={id("description")} label="Description" error={errors.description} className="sm:col-span-2">
        <Textarea id={id("description")} rows={6} value={values.description} onChange={(e) => onChange("description", e.target.value)} {...describedBy(id("description"), errors.description)} />
      </Field>
    </div>
  );
}
