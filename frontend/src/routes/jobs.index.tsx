import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/status-badge";
import { jobSourceFilterOptions } from "@/lib/job-alerts";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronLeft, ChevronRight, Search, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { PageHeader } from "@/components/app-shell";
import { EmptyState, ErrorState, LoadingState, NotStated } from "@/components/states";
import { Field, selectClass, selectInline } from "@/components/field";
import { AddJobDialog } from "@/components/jobs/add-job-dialog";
import { ApplyYourselfTag, Deadline, JobStatusBadge, PublishedDate } from "@/components/jobs/job-bits";
import { MatchBadge } from "@/components/jobs/match";
import { api } from "@/api";
import { EMPLOYMENT_TYPE, JOB_STATUS, JOB_STATUSES, WORK_MODE } from "@/lib/labels";
import { languageLabel } from "@/lib/job-presentation";
import { FINLAND_FILTER_STORAGE_KEY, finlandQuery, parseFinlandFilter, type FinlandFilter } from "@/lib/job-feeds";
import type { EmploymentType, JobListParams, JobSort, JobStatus, WorkMode } from "@/api/types";

const PAGE_SIZE = 25;
const SORTS: Record<JobSort, string> = { newest: "Newest in DuuniScript", published: "Published", deadline: "Deadline", company: "Company", title: "Title", match: "Best match" };
const MATCH_FILTERS = [40, 60, 80];

export interface JobsSearch {
  finland?: FinlandFilter;
  q?: string; company?: string; location?: string; source?: string; status?: JobStatus[];
  employment_type?: EmploymentType; work_mode?: WorkMode; language?: string; min_match?: number;
  published_from?: string; published_to?: string; deadline_from?: string; deadline_to?: string;
  hidden?: boolean; include_hidden?: boolean; include_archived?: boolean; sort?: JobSort; offset?: number;
}

const str = (v: unknown) => (typeof v === "string" && v !== "" ? v : undefined);
const bool = (v: unknown) => (v === true || v === "true" ? true : undefined);
const oneOf = <T extends string>(v: unknown, list: readonly T[]) => (list.includes(v as T) ? (v as T) : undefined);

export const Route = createFileRoute("/jobs/")({
  validateSearch: (s: Record<string, unknown>): JobsSearch => {
    const rawStatus = Array.isArray(s.status) ? s.status : s.status != null ? [s.status] : [];
    const status = rawStatus.filter((x): x is JobStatus => JOB_STATUSES.includes(x as JobStatus));
    const offset = Number(s.offset);
    return {
      finland: parseFinlandFilter(s.finland),
      q: str(s.q), company: str(s.company), location: str(s.location), source: str(s.source),
      status: status.length ? status : undefined,
      employment_type: oneOf(s.employment_type, Object.keys(EMPLOYMENT_TYPE) as EmploymentType[]),
      work_mode: oneOf(s.work_mode, Object.keys(WORK_MODE) as WorkMode[]),
      language: str(s.language),
      min_match: MATCH_FILTERS.includes(Number(s.min_match)) ? Number(s.min_match) : undefined,
      published_from: str(s.published_from), published_to: str(s.published_to),
      deadline_from: str(s.deadline_from), deadline_to: str(s.deadline_to),
      hidden: bool(s.hidden), include_hidden: bool(s.include_hidden), include_archived: bool(s.include_archived),
      sort: oneOf(s.sort, Object.keys(SORTS) as JobSort[]),
      offset: Number.isFinite(offset) && offset > 0 ? offset : undefined,
    };
  },
  head: () => ({
    meta: [
      { title: "Jobs — DuuniScript" },
      { name: "description", content: "Browse, filter and track the job postings you have collected." },
      { property: "og:title", content: "Jobs — DuuniScript" },
      { property: "og:description", content: "Browse, filter and track the job postings you have collected." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: JobsPage,
});

function JobsPage() {
  const rawSearch = Route.useSearch();
  const search = { ...rawSearch, language: ["en", "fi", "sv", "unknown"].includes(rawSearch.language ?? "") ? rawSearch.language : undefined };
  const navigate = useNavigate({ from: "/jobs/" });
  const set = (patch: Partial<JobsSearch>) =>
    navigate({ search: (prev) => ({ ...prev, offset: undefined, ...patch }), replace: true });

  const [rememberedFinland, setRememberedFinland] = useState<FinlandFilter>("yes_unknown");
  const [preferenceReady, setPreferenceReady] = useState(false);
  useEffect(() => {
    try { setRememberedFinland(parseFinlandFilter(localStorage.getItem(FINLAND_FILTER_STORAGE_KEY)) ?? "yes_unknown"); } catch { /* storage may be blocked */ }
    setPreferenceReady(true);
  }, []);
  const finland = search.finland ?? rememberedFinland;
  useEffect(() => {
    if (!preferenceReady || !search.finland) return;
    setRememberedFinland(search.finland);
    try { localStorage.setItem(FINLAND_FILTER_STORAGE_KEY, search.finland); } catch { /* storage may be blocked */ }
  }, [preferenceReady, search.finland]);
  const { finland: _finland, ...apiSearch } = search;
  const params: JobListParams = { ...apiSearch, available_from_finland: finlandQuery(finland), sort: search.sort ?? "newest", limit: PAGE_SIZE, offset: search.offset ?? 0 };
  const jobsQ = useQuery({ queryKey: ["jobs", params], queryFn: () => api.listJobs(params), enabled: preferenceReady, placeholderData: keepPreviousData });
  const sourcesQ = useQuery({ queryKey: ["sources"], queryFn: api.listSources });
  const sourceName = (k: string) => sourcesQ.data?.find((s) => s.key === k)?.name ?? k;

  const [q, setQ] = useState(search.q ?? "");
  const [applyYourselfOnly, setApplyYourselfOnly] = useState(false);
  useEffect(() => setQ(search.q ?? ""), [search.q]);

  const advancedCount = [search.company, search.location, search.employment_type, search.work_mode, search.language, search.published_from, search.published_to, search.deadline_from, search.deadline_to].filter(Boolean).length;
  const anyFilter = advancedCount > 0 || !!(search.q || search.source || search.status || search.min_match || search.hidden || search.include_hidden || search.include_archived);

  const data = jobsQ.data;
  const visibleJobs = data?.items.filter((j) => !applyYourselfOnly || j.apply_manually) ?? [];
  const offset = search.offset ?? 0;

  return (
    <>
      <PageHeader
        title={search.hidden ? "Hidden jobs" : "Jobs"}
        description="Postings you have added or that your sources have found. Nothing is applied for without you."
        actions={<AddJobDialog />}
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Label htmlFor="job-finland">Can I work from Finland?</Label>
        <select id="job-finland" className={selectInline} value={finland} onChange={(e) => {
          const choice = parseFinlandFilter(e.target.value);
          if (choice) set({ finland: choice });
        }}>
          <option value="yes">Yes</option>
          <option value="yes_unknown">Yes or not stated</option>
          <option value="all">All</option>
        </select>
      </div>
      <section aria-label="Filters" className="mb-4 space-y-3 rounded-lg border bg-card p-3">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
          <form className="relative flex-1" role="search" onSubmit={(e) => { e.preventDefault(); set({ q: q.trim() || undefined }); }}>
            <Label htmlFor="job-search" className="sr-only">Search jobs</Label>
            <Search aria-hidden className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input id="job-search" type="search" placeholder="Search title, company or description" className="pl-8" value={q}
              onChange={(e) => setQ(e.target.value)} onBlur={() => (q.trim() || undefined) !== search.q && set({ q: q.trim() || undefined })} />
          </form>
          <div className="flex flex-wrap items-center gap-2">
            <StatusFilter value={search.status ?? []} onChange={(s) => set({ status: s.length ? s : undefined })} />
            <Label htmlFor="job-match" className="sr-only">Minimum match</Label>
            <select id="job-match" className={selectInline} value={search.min_match ?? ""} onChange={(e) => set({ min_match: e.target.value ? Number(e.target.value) : undefined })}>
              <option value="">Match: Any</option>
              {MATCH_FILTERS.map((n) => <option key={n} value={n}>Match: {n}+</option>)}
            </select>
            <Label htmlFor="job-source" className="sr-only">Source</Label>
            <select id="job-source" className={selectInline} value={search.source ?? ""} onChange={(e) => set({ source: e.target.value || undefined })}>
              <option value="">All sources</option>
              {jobSourceFilterOptions(sourcesQ.data ?? []).map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
            </select>
            <Label htmlFor="job-sort" className="sr-only">Sort by</Label>
            <select id="job-sort" className={selectInline} value={search.sort ?? "newest"} onChange={(e) => set({ sort: e.target.value === "newest" ? undefined : (e.target.value as JobSort) })}>
              {Object.entries(SORTS).map(([k, l]) => <option key={k} value={k}>Sort: {l}</option>)}
            </select>
          </div>
        </div>

        <Collapsible defaultOpen={advancedCount > 0}>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm" className="-ml-2">
                <SlidersHorizontal aria-hidden className="size-4" />More filters{advancedCount ? ` (${advancedCount})` : ""}
                <ChevronDown aria-hidden className="size-4" />
              </Button>
            </CollapsibleTrigger>
            <div className="flex items-center gap-2">
              <Switch id="apply-yourself-only" checked={applyYourselfOnly} onCheckedChange={setApplyYourselfOnly} />
              <Label htmlFor="apply-yourself-only" className="text-sm font-normal">Apply yourself</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch id="show-archived" checked={!!search.include_archived} onCheckedChange={(c) => set({ include_archived: c || undefined })} />
              <Label htmlFor="show-archived" className="text-sm font-normal">Show archived</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch id="show-hidden" checked={!!search.include_hidden} disabled={!!search.hidden} onCheckedChange={(c) => set({ include_hidden: c || undefined })} />
              <Label htmlFor="show-hidden" className="text-sm font-normal">Show hidden</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch id="only-hidden" checked={!!search.hidden} onCheckedChange={(c) => set({ hidden: c || undefined, include_hidden: undefined })} />
              <Label htmlFor="only-hidden" className="text-sm font-normal">Hidden jobs only</Label>
            </div>
            {anyFilter && (
              <Button variant="link" size="sm" className="ml-auto" onClick={() => navigate({ search: { sort: search.sort, finland: search.finland }, replace: true })}>Clear filters</Button>
            )}
          </div>
          <CollapsibleContent>
            <AdvancedFilters search={search} set={set} />
          </CollapsibleContent>
        </Collapsible>
      </section>
      {applyYourselfOnly && <p className="mb-3 text-sm text-muted-foreground">Showing Apply yourself jobs on this page.</p>}

      {jobsQ.isSuccess && data && data.items.length > 0 && data.items.every((j) => j.match_score === null) && (
        <p className="mb-4 text-sm text-muted-foreground">Verify your profile facts to see how well each job matches. <Link to="/profile" className="text-primary underline">Open your profile</Link></p>
      )}

      {!preferenceReady || jobsQ.isLoading ? (
        <LoadingState label="Loading jobs…" />
      ) : jobsQ.isError ? (
        <ErrorState error={jobsQ.error} onRetry={() => jobsQ.refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title={anyFilter ? "No jobs match these filters" : "No jobs yet"}>
          {anyFilter ? "Try removing a filter." : "Add a job from a link or enter one manually to get started."}
        </EmptyState>
      ) : (
        <>
          <p className="sr-only" aria-live="polite">{data.total} jobs found</p>
          {/* Wide screens: table */}
          <div className="hidden overflow-x-auto rounded-lg border bg-card md:block">
            <table className="w-full text-sm">
              <caption className="sr-only">Jobs</caption>
              <thead className="border-b bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-2.5 font-medium">Title</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Company</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Location</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Published</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Deadline</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Source</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {visibleJobs.map((j) => (
                  <tr key={j.id} className={j.archived ? "text-muted-foreground hover:bg-muted/30" : "hover:bg-muted/30"}>
                    <td className="px-4 py-3">
                      <Link to="/jobs/$id" params={{ id: j.id }} className="font-medium hover:underline">{j.title}</Link>
                      <MatchBadge score={j.match_score} hasBlockers={j.match_has_blockers} className="ml-2" />
                      <div><ApplyYourselfTag value={j.apply_manually} />{j.archived && <StatusBadge tone="muted" label="Archived" className="ml-2" />}</div>
                      {j.language !== null && <span className="mt-1 block text-xs text-muted-foreground">{languageLabel(j.language)}</span>}
                      {j.available_from_finland === "yes" && <span className="mt-1 block text-xs">Works from Finland</span>}
                      {j.available_from_finland === "no" && <span className="mt-1 block text-xs text-muted-foreground">Not open to Finland</span>}
                      {j.hidden && <span className="ml-2 text-xs text-muted-foreground">(hidden)</span>}
                      {j.possible_duplicate_of && <StatusBadge tone="warning" label="Possible duplicate" className="mt-1" />}
                    </td>
                    <td className="px-4 py-3">{j.company}</td>
                    <td className="px-4 py-3">{j.location ?? <NotStated />}</td>
                    <td className="whitespace-nowrap px-4 py-3"><PublishedDate value={j.published_on} /></td>
                    <td className="whitespace-nowrap px-4 py-3"><Deadline on={j.deadline_on} /></td>
                    <td className="px-4 py-3 text-muted-foreground">{j.sources.map(sourceName).join(", ")}</td>
                    <td className="px-4 py-3"><JobStatusBadge status={j.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Narrow screens: list */}
          <ul className="space-y-2 md:hidden">
            {visibleJobs.map((j) => (
              <li key={j.id} className={j.archived ? "rounded-lg border bg-muted/30 p-4 text-muted-foreground" : "rounded-lg border bg-card p-4"}>
                <div className="flex items-start justify-between gap-3">
                  <Link to="/jobs/$id" params={{ id: j.id }} className="font-medium hover:underline">{j.title}</Link>
                  <JobStatusBadge status={j.status} />
                </div>
                <MatchBadge score={j.match_score} hasBlockers={j.match_has_blockers} className="mt-2" />
                <div><ApplyYourselfTag value={j.apply_manually} />{j.archived && <StatusBadge tone="muted" label="Archived" className="ml-2" />}</div>
                {j.available_from_finland === "yes" && <p className="mt-1 text-xs">Works from Finland</p>}
                {j.available_from_finland === "no" && <p className="mt-1 text-xs text-muted-foreground">Not open to Finland</p>}
                {j.possible_duplicate_of && <StatusBadge tone="warning" label="Possible duplicate" className="mt-1" />}
                {j.language !== null && <p className="mt-1 text-xs text-muted-foreground">{languageLabel(j.language)}</p>}
                <p className="text-sm text-muted-foreground">{j.company}{j.location ? ` · ${j.location}` : ""}{j.hidden ? " · hidden" : ""}</p>
                <dl className="mt-2 grid grid-cols-2 gap-1 text-xs">
                  <dt className="text-muted-foreground">Published</dt><dd><PublishedDate value={j.published_on} /></dd>
                  <dt className="text-muted-foreground">Deadline</dt><dd><Deadline on={j.deadline_on} /></dd>
                  <dt className="text-muted-foreground">Source</dt><dd>{j.sources.map(sourceName).join(", ")}</dd>
                </dl>
              </li>
            ))}
          </ul>
          {applyYourselfOnly && !visibleJobs.length && <EmptyState title="No Apply yourself jobs on this page" />}
          <nav aria-label="Pagination" className="mt-4 flex items-center justify-between text-sm">
            <p className="text-muted-foreground">
              {offset + 1}–{Math.min(offset + data.items.length, data.total)} of {data.total}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => navigate({ search: (p) => ({ ...p, offset: Math.max(0, offset - PAGE_SIZE) || undefined }) })}>
                <ChevronLeft aria-hidden className="size-4" />Previous
              </Button>
              <Button variant="outline" size="sm" disabled={offset + PAGE_SIZE >= data.total} onClick={() => navigate({ search: (p) => ({ ...p, offset: offset + PAGE_SIZE }) })}>
                Next<ChevronRight aria-hidden className="size-4" />
              </Button>
            </div>
          </nav>
        </>
      )}
    </>
  );
}

function StatusFilter({ value, onChange }: { value: JobStatus[]; onChange: (v: JobStatus[]) => void }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-9">
          Status{value.length ? `: ${value.length === 1 && value[0] ? JOB_STATUS[value[0]].label : `${value.length} selected`}` : ": All"}
          <ChevronDown aria-hidden className="size-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-2" align="start">
        <fieldset>
          <legend className="px-2 pb-1 text-xs font-medium text-muted-foreground">Filter by status</legend>
          {JOB_STATUSES.map((s) => (
            <label key={s} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted">
              <Checkbox checked={value.includes(s)} onCheckedChange={(c) => onChange(c ? [...value, s] : value.filter((x) => x !== s))} />
              {JOB_STATUS[s].label}
            </label>
          ))}
        </fieldset>
      </PopoverContent>
    </Popover>
  );
}

function AdvancedFilters({ search, set }: { search: JobsSearch; set: (p: Partial<JobsSearch>) => void }) {
  const [company, setCompany] = useState(search.company ?? "");
  const [location, setLocation] = useState(search.location ?? "");
  const date = (key: keyof JobsSearch, label: string) => (
    <Field id={`f-${key}`} label={label}>
      <Input id={`f-${key}`} type="date" value={(search[key] as string) ?? ""} onChange={(e) => set({ [key]: e.target.value || undefined })} />
    </Field>
  );
  return (
    <div className="grid gap-3 pt-3 sm:grid-cols-2 lg:grid-cols-4">
      <Field id="f-company" label="Company">
        <Input id="f-company" value={company} onChange={(e) => setCompany(e.target.value)} onBlur={() => set({ company: company.trim() || undefined })}
          onKeyDown={(e) => e.key === "Enter" && set({ company: company.trim() || undefined })} />
      </Field>
      <Field id="f-location" label="Location">
        <Input id="f-location" value={location} onChange={(e) => setLocation(e.target.value)} onBlur={() => set({ location: location.trim() || undefined })}
          onKeyDown={(e) => e.key === "Enter" && set({ location: location.trim() || undefined })} />
      </Field>
      <Field id="f-emp" label="Employment type">
        <select id="f-emp" className={selectClass} value={search.employment_type ?? ""} onChange={(e) => set({ employment_type: (e.target.value || undefined) as EmploymentType | undefined })}>
          <option value="">Any</option>
          {Object.entries(EMPLOYMENT_TYPE).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </Field>
      <Field id="f-mode" label="Work mode">
        <select id="f-mode" className={selectClass} value={search.work_mode ?? ""} onChange={(e) => set({ work_mode: (e.target.value || undefined) as WorkMode | undefined })}>
          <option value="">Any</option>
          {Object.entries(WORK_MODE).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </Field>
      <Field id="f-language" label="Posting language">
        <select id="f-language" className={selectClass} value={search.language ?? ""} onChange={(e) => set({ language: e.target.value || undefined })}>
          <option value="">Any</option>
          <option value="en">English</option>
          <option value="fi">Finnish</option>
          <option value="sv">Swedish</option>
          <option value="unknown">Not known</option>
        </select>
      </Field>
      {date("published_from", "Published from")}
      {date("published_to", "Published to")}
      {date("deadline_from", "Deadline from")}
      {date("deadline_to", "Deadline to")}
    </div>
  );
}
