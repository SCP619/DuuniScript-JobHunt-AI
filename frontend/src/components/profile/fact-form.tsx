import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, describedBy, selectClass } from "@/components/field";
import { errorMessage, fieldErrors, isApiError } from "@/api";
import { FACT_CATEGORIES, FACT_CATEGORY } from "@/lib/labels";
import type { FactCategory, FactRead } from "@/api/types";

export interface FactFormValues { category: FactCategory; subject: string; value_text: string; valid_from: string; valid_until: string; }

export const factToForm = (f?: FactRead, category: FactCategory = "skill"): FactFormValues => ({
  category: f?.category ?? category, subject: f?.subject ?? "", value_text: f?.value_text ?? "",
  valid_from: f?.valid_from ?? "", valid_until: f?.valid_until ?? "",
});

/** Shared create/edit form. onSubmit receives values; thrown API errors are mapped to fields. */
export function FactForm({
  initial, submitLabel, onSubmit, onCancel, idPrefix, beforeSubmit,
}: {
  initial: FactFormValues; submitLabel: string; idPrefix: string; onCancel?: () => void;
  onSubmit: (v: FactFormValues) => Promise<unknown>;
  /** Optional gate (e.g. confirmation). Return false to stop. */
  beforeSubmit?: (v: FactFormValues) => Promise<boolean>;
}) {
  const [v, setV] = useState(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const id = (k: string) => `${idPrefix}-${k}`;
  const set = (k: keyof FactFormValues, val: string) => setV((s) => ({ ...s, [k]: val }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (beforeSubmit && !(await beforeSubmit(v))) return;
    setPending(true); setErrors({}); setFormError(null);
    try {
      await onSubmit(v);
    } catch (err) {
      if (isApiError(err) && err.code === "invalid_date_range") {
        setErrors({ valid_from: err.message, valid_until: err.message });
      } else {
        const fe = fieldErrors(err);
        setErrors(fe);
        if (!Object.keys(fe).length) setFormError(errorMessage(err));
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <Field id={id("category")} label="Category" error={errors.category}>
        <select id={id("category")} className={selectClass} value={v.category} onChange={(e) => set("category", e.target.value)}>
          {FACT_CATEGORIES.map((c) => <option key={c} value={c}>{FACT_CATEGORY[c]}</option>)}
        </select>
      </Field>
      <Field id={id("subject")} label="Subject" required error={errors.subject} hint="A short name, such as a degree, role or skill.">
        <Input id={id("subject")} value={v.subject} onChange={(e) => set("subject", e.target.value)} {...describedBy(id("subject"), errors.subject, true)} />
      </Field>
      <Field id={id("value_text")} label="Details" required error={errors.value_text}>
        <Textarea id={id("value_text")} rows={4} value={v.value_text} onChange={(e) => set("value_text", e.target.value)} {...describedBy(id("value_text"), errors.value_text)} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id={id("valid_from")} label="Valid from" error={errors.valid_from}>
          <Input id={id("valid_from")} type="date" value={v.valid_from} onChange={(e) => set("valid_from", e.target.value)} {...describedBy(id("valid_from"), errors.valid_from)} />
        </Field>
        <Field id={id("valid_until")} label="Valid until" error={errors.valid_until}>
          <Input id={id("valid_until")} type="date" value={v.valid_until} onChange={(e) => set("valid_until", e.target.value)} {...describedBy(id("valid_until"), errors.valid_until)} />
        </Field>
      </div>
      {formError && <p role="alert" className="text-sm text-destructive">{formError}</p>}
      <div className="flex justify-end gap-2">
        {onCancel && <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>}
        <Button type="submit" disabled={pending}>{pending && <Loader2 aria-hidden className="size-4 animate-spin" />}{submitLabel}</Button>
      </div>
    </form>
  );
}
