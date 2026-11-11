import { useEffect, useMemo, useState } from "react";
import { get, post } from "../api/client";
import type { Finding } from "../api/client";
import {
  Alert, Badge, Btn, Card, CopyButton, DataTable, EmptyState, PageHeader,
  Pagination, SearchInput, SeverityBadge, Skeleton, Stat, inputCls, selectCls,
  type DataTableColumn,
} from "../components/ui";

const VERDICTS = ["accept", "fixed", "reject_wrong", "reject_not_worth_fixing", "ignore"] as const;
const PAGE_SIZE = 10;
const SEV_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export function FindingCard({ f, notify, onDone }: { f: Finding; notify: (m: string) => void; onDone?: () => void }) {
  const [reason, setReason] = useState("");
  const [open, setOpen] = useState(false);
  const feedback = async (verdict: string) => {
    try {
      const r = await post(`/api/findings/${f.id}/feedback`, { verdict, reason });
      notify(`Feedback recorded: ${verdict} (finding now ${r.state}).`);
      onDone?.();
    } catch (e: any) { notify(e.message); }
  };
  const location = `${f.file_path}:${f.start_line}${f.end_line !== f.start_line ? `-${f.end_line}` : ""}`;
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={f.severity} />
            <Badge tone="slate">{f.source}</Badge>
            <Badge tone="slate">{f.category}</Badge>
            {f.cwe_id && <Badge tone="violet">{f.cwe_id}{f.cwe_title ? ` — ${f.cwe_title}` : ""}</Badge>}
            {f.owasp_ref && <Badge tone="cyan">{f.owasp_ref}</Badge>}
          </div>
          <div className="mt-2 font-semibold text-white">{f.title}</div>
          <div className="mt-1 text-sm text-slate-400">{f.description}</div>
          <div className="mt-2 flex flex-wrap items-center gap-2 font-mono text-xs text-slate-400">
            <span>{location} · PR #{f.pr_number} · confidence {f.confidence.toFixed(2)} · {f.model_version}</span>
            <CopyButton text={location} label="Copy location" />
          </div>
        </div>
        <Badge tone={f.state === "dismissed" ? "slate" : f.state === "suppressed" ? "amber" : "emerald"}>
          {f.state}{f.suppressed_reason ? ` — ${f.suppressed_reason}` : ""}
        </Badge>
      </div>
      <pre className="mt-3 overflow-x-auto rounded-lg bg-[#070b16] p-3 text-xs text-slate-200 scrollbar-thin">{f.evidence}</pre>
      {f.patch && (
        <div className="mt-3">
          <div className="text-xs font-semibold text-slate-300">Suggested patch {f.patch_valid ? "(validated — parses)" : "(not validated)"}</div>
          <pre className="mt-1 overflow-x-auto rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3 text-xs text-emerald-200 scrollbar-thin">{f.patch}</pre>
        </div>
      )}
      {f.state === "posted" && (
        <div className="mt-4">
          <button type="button" className="text-xs text-slate-400 underline hover:text-white" onClick={() => setOpen(!open)}>
            {open ? "Hide feedback" : "Give feedback…"}
          </button>
          {open && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <label className="sr-only" htmlFor={`reason-${f.id}`}>Reason (optional)</label>
              <input id={`reason-${f.id}`} className={inputCls} style={{ maxWidth: 260 }} placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
              {VERDICTS.map((v) => <Btn key={v} variant="ghost" onClick={() => feedback(v)}>{v.replace(/_/g, " ")}</Btn>)}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export function Findings({ notify, initialQuery }: { notify: (m: string) => void; initialQuery?: string }) {
  const [items, setItems] = useState<Finding[] | null>(null);
  const [repos, setRepos] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [query, setQuery] = useState(initialQuery ?? "");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [f, setF] = useState({ severity: "", cwe: "", category: "", repo_id: "", pr_number: "", agent: "", state: "" });
  useEffect(() => { if (initialQuery !== undefined) setQuery(initialQuery); }, [initialQuery]);
  useEffect(() => { setPage(1); }, [query, f, sort]);
  const load = () => {
    const q = new URLSearchParams(Object.entries(f).filter(([, v]) => v));
    get(`/api/findings?${q}`).then(setItems).catch((e) => setErr(e.message));
  };
  useEffect(() => { get("/api/repos").then(setRepos).catch(() => {}); }, []);
  useEffect(() => { load(); }, [f]);

  const visible = useMemo(() => {
    const filtered = (items ?? []).filter((x) => {
      if (!query.trim()) return true;
      const hay = [x.title, x.description, x.file_path, x.category, x.cwe_id ?? "", x.source].join(" ").toLowerCase();
      return hay.includes(query.trim().toLowerCase());
    });
    const sorted = [...filtered];
    if (sort === "severity") sorted.sort((a, b) => (SEV_RANK[a.severity] ?? 9) - (SEV_RANK[b.severity] ?? 9) || b.id - a.id);
    else if (sort === "confidence") sorted.sort((a, b) => b.confidence - a.confidence);
    else sorted.sort((a, b) => b.id - a.id);
    return sorted;
  }, [items, query, sort]);

  if (err) return <EmptyState title="Could not load findings" body={err} />;
  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const pageItems = visible.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  return (
    <div className="space-y-4">
      <PageHeader title="Findings" subtitle="Evidence-cited findings from review runs. Give feedback to drive precision and fine-tuning." />
      <Card>
        <SearchInput value={query} onChange={setQuery} placeholder="Search findings by title, file, CWE, category…" />
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <label className="sr-only" htmlFor="f-severity">Severity filter</label>
          <select id="f-severity" className={selectCls} value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })}>
            <option value="">Severity: all</option>{["critical", "high", "medium", "low"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <label className="sr-only" htmlFor="f-repo">Repository filter</label>
          <select id="f-repo" className={selectCls} value={f.repo_id} onChange={(e) => setF({ ...f, repo_id: e.target.value })}>
            <option value="">Repository: all</option>{repos.map((r: any) => <option key={r.id} value={r.id}>{r.full_name}</option>)}
          </select>
          <label className="sr-only" htmlFor="f-agent">Agent filter</label>
          <select id="f-agent" className={selectCls} value={f.agent} onChange={(e) => setF({ ...f, agent: e.target.value })}>
            <option value="">Agent: all</option>{["security", "logic", "style", "secret-scanner", "dependency-scanner"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <label className="sr-only" htmlFor="f-state">State filter</label>
          <select id="f-state" className={selectCls} value={f.state} onChange={(e) => setF({ ...f, state: e.target.value })}>
            <option value="">State: all</option>{["posted", "suppressed", "fixed", "dismissed"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <input className={inputCls} placeholder="CWE e.g. CWE-89" aria-label="CWE filter" value={f.cwe} onChange={(e) => setF({ ...f, cwe: e.target.value })} />
          <input className={inputCls} placeholder="Category e.g. sql_injection" aria-label="Category filter" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} />
          <input className={inputCls} placeholder="PR number" aria-label="PR number filter" value={f.pr_number} onChange={(e) => setF({ ...f, pr_number: e.target.value })} />
          <label className="sr-only" htmlFor="f-sort">Sort findings</label>
          <select id="f-sort" className={selectCls} value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="newest">Sort: Newest</option>
            <option value="severity">Sort: Severity</option>
            <option value="confidence">Sort: Confidence</option>
          </select>
        </div>
      </Card>
      {!items ? <Skeleton className="h-48" /> : visible.length === 0 ? (
        <EmptyState title="No findings match" body="Try widening the filters — or run the demo review to generate real findings on the sample repository." />
      ) : (
        <>
          <p className="text-sm text-slate-400" aria-live="polite">
            {visible.length} finding{visible.length === 1 ? "" : "s"} — showing {(safePage - 1) * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE, visible.length)}
          </p>
          <div className="space-y-4">{pageItems.map((x) => <FindingCard key={x.id} f={x} notify={notify} onDone={load} />)}</div>
          <Pagination page={safePage} pageCount={pageCount} onChange={setPage} />
        </>
      )}
    </div>
  );
}

export function PRs({ repoId, notify, go }: { repoId?: number; notify: (m: string) => void; go: (page: string, arg?: any) => void }) {
  const [repos, setRepos] = useState<any[]>([]);
  const [rows, setRows] = useState<any[] | null>(null);
  const [sortKey, setSortKey] = useState("repo");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  useEffect(() => {
    get("/api/repos").then(async (rs) => {
      setRepos(rs);
      const list = repoId ? rs.filter((r: any) => r.id === repoId) : rs;
      const all: any[] = [];
      for (const r of list) {
        const prs = await get(`/api/repos/${r.id}/prs`).catch(() => []);
        prs.forEach((p: any) => all.push({ ...p, repo: r }));
      }
      setRows(all);
    }).catch(() => setRows([]));
  }, [repoId]);
  void notify; void repos;
  const onSort = (key: string) => {
    if (key === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  };
  const sorted = useMemo(() => {
    const list = [...(rows ?? [])];
    const dir = sortDir === "asc" ? 1 : -1;
    list.sort((a, b) => {
      if (sortKey === "number") return (a.number - b.number) * dir || String(a.repo.full_name).localeCompare(String(b.repo.full_name)) * dir;
      if (sortKey === "gate") return String(a.run?.gate_result ?? "").localeCompare(String(b.run?.gate_result ?? "")) * dir;
      if (sortKey === "status") return String(a.run?.status ?? "").localeCompare(String(b.run?.status ?? "")) * dir;
      if (sortKey === "latency") return ((a.run?.latency_ms ?? -1) - (b.run?.latency_ms ?? -1)) * dir;
      return String(a.repo.full_name).localeCompare(String(b.repo.full_name)) * dir || (a.number - b.number) * dir;
    });
    return list;
  }, [rows, sortKey, sortDir]);

  if (!rows) {
    return (
      <div className="space-y-4">
        <PageHeader title="Pull requests" subtitle="Reviewed pull requests across your repositories." />
        <Skeleton className="h-48" />
      </div>
    );
  }
  const columns: DataTableColumn[] = [
    { key: "repo", label: "Repository", sortable: true },
    { key: "number", label: "PR", sortable: true },
    { key: "title", label: "Title" },
    { key: "size_band", label: "Size" },
    { key: "status", label: "Status", sortable: true },
    { key: "gate", label: "Gate", sortable: true },
    { key: "latency", label: "Latency", sortable: true },
  ];
  return (
    <div className="space-y-4">
      <PageHeader title="Pull requests" subtitle="Reviewed pull requests across your repositories." />
      {rows.length === 0 ? (
        <EmptyState title="No pull requests reviewed yet" body="Open a PR on a connected repository, or run the demo review — PR #42 on demo/shop-api is the seeded example." />
      ) : (
        <DataTable
          columns={columns} rows={sorted} sortKey={sortKey} sortDir={sortDir} onSort={onSort}
          empty="No pull requests yet."
          renderCell={(row, col) => {
            if (col.key === "repo") return <span className="font-mono text-xs text-slate-400">{row.repo.full_name}</span>;
            if (col.key === "number") return (
              <button type="button" onClick={() => go("review", { repoId: row.repo.id, number: row.number })} className="font-semibold text-white hover:text-violet-300">
                #{row.number}
              </button>
            );
            if (col.key === "title") return (
              <button type="button" onClick={() => go("review", { repoId: row.repo.id, number: row.number })} className="text-left text-white hover:text-violet-300">
                {row.title}
              </button>
            );
            if (col.key === "status") return <span className="text-slate-300">{row.run ? row.run.status : "not reviewed"}</span>;
            if (col.key === "gate") return row.run?.gate_result
              ? <Badge tone={row.run.gate_result === "fail" ? "red" : "emerald"}>gate: {row.run.gate_result}</Badge>
              : <Badge tone="slate">—</Badge>;
            if (col.key === "latency") return <span>{row.run ? `${row.run.latency_ms} ms` : "—"}</span>;
            return String(row[col.key] ?? "—");
          }}
        />
      )}
    </div>
  );
}

export function ReviewDetail({ repoId, number, notify }: { repoId: number; number: number; notify: (m: string) => void }) {
  const [pr, setPr] = useState<any>(null);
  const [err, setErr] = useState("");
  const load = () => get(`/api/repos/${repoId}/prs/${number}`).then(setPr).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [repoId, number]);
  if (err) return <EmptyState title="Review not found" body={err} />;
  if (!pr) {
    return (
      <div className="space-y-6">
        <PageHeader title={`PR #${number}`} subtitle="Loading review…" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  const run = pr.runs?.[0];
  const posted = run?.findings?.filter((f: any) => f.state === "posted") || [];
  const suppressed = run?.findings?.filter((f: any) => f.state === "suppressed") || [];
  return (
    <div className="space-y-6">
      <PageHeader
        title={`PR #${pr.number} — ${pr.title}`}
        subtitle={`${pr.repo_full_name} · by ${pr.author} · base ${pr.base_sha} · head ${pr.head_sha} · ${pr.size_band} · ${pr.state}`}
      />
      {!run ? (
        <EmptyState title="No review run yet" body="This PR has not been reviewed. Trigger a review from the repository page or via the API." />
      ) : (
        <>
          <Alert tone={run.gate_result === "fail" ? "error" : "success"}>
            Gate {run.gate_result === "fail" ? "failed" : "passed"} — review {run.status}.
            {run.gate_result === "fail"
              ? " High-severity findings block the CI check until fixed or dismissed by an authorised reviewer."
              : " No blocking findings were posted."}
          </Alert>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Status / gate" value={`${run.status} · ${run.gate_result}`} />
            <Stat label="Coverage" value={`${run.coverage?.pct ?? 0}%`} sub={`${run.coverage?.files_reviewed ?? 0}/${run.coverage?.files_total ?? 0} files reviewed`} />
            <Stat label="Latency / tokens / cost" value={`${run.latency_ms} ms`} sub={`${run.tokens_used} tokens · $${run.cost_usd}`} />
            <Stat label="Model" value={run.model_version} sub={run.prompt_version} />
          </div>
          <Card>
            <div className="mb-2 font-semibold text-white">Summary</div>
            <p className="text-sm text-slate-300">{run.summary || "No summary recorded for this run."}</p>
            {run.adapter_version && <p className="mt-2 text-xs text-slate-500">Adapter: {run.adapter_version}</p>}
          </Card>
          {(run.coverage?.files_skipped?.length ?? 0) > 0 && (
            <Alert tone="warning">
              Skipped files (disclosed, never silent): {run.coverage.files_skipped.map((s: any) => `${s.path} (${s.reason})`).join(", ")}
            </Alert>
          )}
          <h2 className="text-lg font-bold text-white">Findings posted ({posted.length})</h2>
          {posted.length === 0 ? <EmptyState title="No findings posted" body="Either the PR is clean, or every candidate finding was suppressed — see below for why." /> : posted.map((f: any) => <FindingCard key={f.id} f={f} notify={notify} onDone={load} />)}
          {suppressed.length > 0 && (
            <>
              <h2 className="text-lg font-bold text-white">Suppressed findings ({suppressed.length}) — and why</h2>
              {suppressed.map((f: any) => <FindingCard key={f.id} f={f} notify={notify} />)}
            </>
          )}
        </>
      )}
    </div>
  );
}
