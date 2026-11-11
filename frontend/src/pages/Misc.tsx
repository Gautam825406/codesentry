import { useEffect, useMemo, useState } from "react";
import { get, post } from "../api/client";
import {
  Alert, Avatar, Badge, BarChart, Btn, Card, ConfirmDialog, CopyButton, DataTable,
  DonutChart, EmptyState, PageHeader, Pagination, SearchInput, Skeleton, Stat, Tabs,
  selectCls, type DataTableColumn,
} from "../components/ui";
import { FindingCard } from "./Findings";
import { RepoDetail } from "./Repos";

const objEntries = (o: any) => Object.entries(o ?? {}).map(([label, value]) => ({ label, value: Number(value) }));

export function SecurityCenter({ notify }: { notify: (m: string) => void }) {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { get("/api/security").then(setData).catch((e) => setErr(e.message)); }, []);
  if (err) return <EmptyState title="Could not load the Security Center" body={err} />;
  if (!data) {
    return (
      <div className="space-y-6">
        <PageHeader title="Security Center" subtitle="CWE-mapped security findings, from persisted reviews only." />
        <Skeleton className="h-48" />
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <PageHeader title="Security Center" subtitle="CWE-mapped security findings, from persisted reviews only." />
      <div className="grid gap-4 md:grid-cols-3">
        <Stat label="Critical CWE findings" value={data.critical} />
        <Stat label="High CWE findings" value={data.high} />
        <Stat label="CWE categories seen" value={Object.keys(data.by_cwe || {}).length} sub={Object.entries(data.by_cwe || {}).map(([k, v]) => `${k}: ${v}`).join(" · ") || "none yet"} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <div className="mb-3 font-semibold text-white">Findings by CWE</div>
          {objEntries(data.by_cwe).length === 0 ? <p className="text-sm text-slate-400">No CWE findings yet.</p> : <BarChart data={objEntries(data.by_cwe)} />}
        </Card>
        <Card>
          <div className="mb-2 font-semibold text-white">How this is counted</div>
          <p className="text-sm text-slate-400">Only findings with a valid CWE identifier appear here. A security finding without a valid CWE is never posted as one — that is a filter rule, not a display choice. Absence of findings is not proof of safety.</p>
        </Card>
      </div>
      {data.findings.length === 0 ? <EmptyState title="No security findings posted" body="Run the demo review to see a CWE-89 SQL injection finding here." /> :
        <div className="space-y-4">{data.findings.map((f: any) => <FindingCard key={f.id} f={f} notify={notify} />)}</div>}
    </div>
  );
}

export function Quality({ repoId, notify }: { repoId?: number; notify: (m: string) => void }) {
  const [repos, setRepos] = useState<any[]>([]);
  const [sel, setSel] = useState<number | undefined>(repoId);
  const [q, setQ] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { get("/api/repos").then((rs) => { setRepos(rs); if (!sel && rs[0]) setSel(rs[0].id); }).catch(() => {}); }, []);
  useEffect(() => { if (sel) get(`/api/repos/${sel}/quality`).then(setQ).catch((e) => setErr(e.message)); }, [sel]);
  void notify;
  // Hooks must stay above the early return (React error #310 otherwise).
  const verdictData = useMemo(() => {
    const entries = objEntries(q?.verdicts);
    return entries.map((d) => ({ ...d, color: d.label === "reject_wrong" ? "#ef4444" : d.label === "accept" || d.label === "fixed" ? "#10b981" : "#64748b" }));
  }, [q]);
  if (repos.length === 0) return <EmptyState title="No repositories yet" body="Connect a repository or run the demo review first." />;
  return (
    <div className="space-y-6">
      <PageHeader
        title="Quality Analytics"
        subtitle="Precision, latency and cost — computed from persisted findings, feedback and runs. Nothing is fabricated."
        actions={
          <label className="flex items-center gap-2 text-sm text-slate-300">
            Repository
            <select className={selectCls} style={{ width: 280 }} value={sel} onChange={(e) => { setSel(parseInt(e.target.value)); setQ(null); }}>
              {repos.map((r: any) => <option key={r.id} value={r.id}>{r.full_name}</option>)}
            </select>
          </label>
        }
      />
      {err && <EmptyState title="Could not load quality data" body={err} />}
      {!q ? <Skeleton className="h-48" /> : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="PRs reviewed" value={q.prs_reviewed} />
            <Stat label="Findings posted" value={q.posted} sub={`${q.suppressed} suppressed · ${q.total_findings} total`} />
            <Stat label="Precision" value={q.precision === null ? "—" : q.precision.toFixed(2)} sub={q.precision === null ? "no feedback yet — not fabricated" : `${q.feedback_total} feedback events`} />
            <Stat label="False-positive rate" value={q.false_positive_rate === null ? "—" : q.false_positive_rate.toFixed(2)} sub={`p50 latency ${q.review_latency_ms_p50 ?? "—"} ms`} />
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <Card><div className="mb-3 font-semibold text-white">By severity</div><BarChart data={objEntries(q.by_severity)} /></Card>
            <Card><div className="mb-3 font-semibold text-white">By CWE</div><BarChart data={objEntries(q.by_cwe)} /></Card>
            <Card><div className="mb-3 font-semibold text-white">By agent</div><BarChart data={objEntries(q.by_agent)} /></Card>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <div className="mb-3 font-semibold text-white">Feedback verdicts</div>
              {verdictData.length === 0
                ? <p className="text-sm text-slate-400">No feedback yet. Mark findings right or wrong from the Findings page — that is what drives precision and the fine-tuning dataset.</p>
                : <DonutChart data={verdictData} />}
            </Card>
            <Card>
              <div className="mb-3 font-semibold text-white">Cost &amp; latency</div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-slate-400">Cost per PR</span><span className="font-medium text-white">${q.cost_per_pr_usd}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Review latency p50</span><span className="font-medium text-white">{q.review_latency_ms_p50 ?? "—"} ms</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Review latency p95</span><span className="font-medium text-white">{q.review_latency_ms_p95 ?? "—"} ms</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Feedback events</span><span className="font-medium text-white">{q.feedback_total}</span></div>
              </div>
              <p className="mt-3 text-xs text-slate-500">Only p50/p95 latency is stored per repository, so no latency series is charted — a line would need per-run values the API does not return.</p>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

export function Agents({ notify }: { notify: (m: string) => void }) {
  const [data, setData] = useState<any>(null);
  void notify;
  useEffect(() => { get("/api/agents").then(setData).catch(() => {}); }, []);
  if (!data) {
    return (
      <div className="space-y-6">
        <PageHeader title="AI Agents" subtitle="The three review agents and the pipeline they run in." />
        <Skeleton className="h-48" />
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <PageHeader title="AI Agents" subtitle="The three review agents and the pipeline they run in." />
      <Card>
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
          <span className="text-slate-400">LangGraph graph: <span className="text-slate-200">{data.graph}</span></span>
          <span className="text-slate-400">Parser: <code className="text-slate-200">{data.parser}</code></span>
          <span className="text-slate-400">Embeddings: <code className="text-slate-200">{data.embeddings}</code></span>
          <span className="text-slate-400">LLM provider: <code className="text-slate-200">{data.llm_provider}</code></span>
        </div>
      </Card>
      <div className="grid gap-4 md:grid-cols-3">
        {data.agents.map((a: any) => (
          <Card key={a.name}>
            <div className="flex items-center justify-between">
              <span className="font-semibold capitalize text-white">{a.name} agent</span>
              <Badge tone="emerald">{a.status}</Badge>
            </div>
            <p className="mt-2 text-sm text-slate-400">{a.mandate}</p>
            <p className="mt-2 text-xs text-slate-500">Model: {a.model}</p>
          </Card>
        ))}
      </div>
      <Card>
        <div className="font-semibold text-white">How a review runs</div>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-400">
          <li>Changed symbols are retrieved graph-first: the symbol, its callers, its callees, its tests, then vector-similar code — inside a per-symbol token budget.</li>
          <li>Three agents review the same context pack with different mandates and return Pydantic-validated findings.</li>
          <li>The filter drops uncited, low-confidence, duplicate, previously-rejected and CWE-less security findings. Suppressed findings are logged with a reason.</li>
          <li>Patches are attached only when they parse and stay inside the finding's lines.</li>
        </ol>
      </Card>
    </div>
  );
}

export function FineTuning({ notify }: { notify: (m: string) => void }) {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [adapters, setAdapters] = useState<any[]>([]);
  const [confirm, setConfirm] = useState<{ id: number; action: "promote" | "rollback"; label: string } | null>(null);
  const load = () => { get("/api/training/datasets").then(setDatasets).catch(() => {}); get("/api/training/adapters").then(setAdapters).catch(() => {}); };
  useEffect(() => { load(); }, []);
  const build = async () => { try { const r = await post("/api/training/datasets/build"); notify(r.built ? `Dataset ${r.version}: ${r.train} train / ${r.val} val / ${r.heldout} held-out.` : r.reason); load(); } catch (e: any) { notify(e.message); } };
  const train = async (id: number) => { try { const r = await post(`/api/training/datasets/${id}/train`); notify(`Adapter ${r.version}: ${r.status}. ${r.metrics?.error || ""}`); load(); } catch (e: any) { notify(e.message); } };
  const act = async (id: number, action: "promote" | "rollback") => { try { await post(`/api/training/adapters/${id}/${action}`); notify(`Adapter ${action}d.`); load(); } catch (e: any) { notify(e.message); } };
  const datasetColumns: DataTableColumn[] = [
    { key: "version", label: "Version" }, { key: "train", label: "Train" },
    { key: "val", label: "Val" }, { key: "heldout", label: "Held-out" },
    { key: "source", label: "Source" }, { key: "actions", label: "Actions" },
  ];
  const adapterColumns: DataTableColumn[] = [
    { key: "version", label: "Version" }, { key: "base_model", label: "Base model" },
    { key: "status", label: "Status" }, { key: "promoted", label: "Promoted" },
    { key: "actions", label: "Actions" },
  ];
  return (
    <div className="space-y-6">
      <PageHeader
        title="Fine-Tuning (LoRA)"
        subtitle="Datasets built only from authorised-reviewer correctness verdicts on repositories with training opt-in."
        actions={<Btn onClick={build}>Build dataset from feedback</Btn>}
      />
      <Alert tone="info">
        Promotion is blocked unless the held-out evaluation gate passes. No training run is claimed unless a real job completed — this environment has no GPU, so training stays honestly <code>not_started</code> until run on a GPU host.
      </Alert>
      <section aria-labelledby="ft-datasets">
        <h2 id="ft-datasets" className="mb-3 text-lg font-bold text-white">Dataset versions</h2>
        <DataTable
          columns={datasetColumns} rows={datasets}
          empty="No datasets yet. Give feedback on findings first, with training opt-in enabled on the repository."
          renderCell={(row, col) => {
            if (col.key === "version") return <span className="font-mono font-medium text-white">{row.version}</span>;
            if (col.key === "actions") return <Btn variant="outline" onClick={() => train(row.id)}>Start LoRA training</Btn>;
            return String(row[col.key] ?? "—");
          }}
        />
      </section>
      <section aria-labelledby="ft-adapters">
        <h2 id="ft-adapters" className="mb-3 text-lg font-bold text-white">LoRA adapters</h2>
        <DataTable
          columns={adapterColumns} rows={adapters}
          empty="No adapters yet."
          renderCell={(row, col) => {
            if (col.key === "version") return <span className="font-mono font-medium text-white">{row.version}</span>;
            if (col.key === "promoted") return row.promoted ? <Badge tone="emerald">promoted</Badge> : <Badge tone="slate">not promoted</Badge>;
            if (col.key === "status") return <Badge tone={row.status === "ready" ? "emerald" : "slate"}>{row.status}</Badge>;
            if (col.key === "actions") return (
              <span className="flex gap-2">
                <Btn variant="outline" onClick={() => setConfirm({ id: row.id, action: "promote", label: row.version })}>Promote</Btn>
                <Btn variant="ghost" onClick={() => setConfirm({ id: row.id, action: "rollback", label: row.version })}>Rollback</Btn>
              </span>
            );
            return String(row[col.key] ?? "—");
          }}
        />
      </section>
      <ConfirmDialog
        open={!!confirm}
        onCancel={() => setConfirm(null)}
        onConfirm={() => { if (confirm) { act(confirm.id, confirm.action); setConfirm(null); } }}
        title={confirm?.action === "promote" ? "Promote adapter?" : "Roll back adapter?"}
        body={confirm?.action === "promote"
          ? `Promote adapter ${confirm?.label} to serve live reviews? Promotion is blocked unless the held-out evaluation gate passes.`
          : `Roll back adapter ${confirm?.label}? It will no longer serve live reviews.`}
        confirmLabel={confirm?.action === "promote" ? "Promote" : "Roll back"}
        danger={confirm?.action === "rollback"}
      />
    </div>
  );
}

export function AuditLogs() {
  const [events, setEvents] = useState<any[] | null>(null);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 15;
  useEffect(() => { get("/api/audit").then(setEvents).catch(() => setEvents([])); }, []);
  useEffect(() => { setPage(1); }, [query]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (events ?? []).filter((e: any) =>
      !q || [e.action, e.actor].join(" ").toLowerCase().includes(q));
  }, [events, query]);
  if (!events) {
    return (
      <div className="space-y-4">
        <PageHeader title="Audit Logs" subtitle="Installs, settings changes, dismissals, purges and adapter promotions." />
        <Skeleton className="h-48" />
      </div>
    );
  }
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const pageRows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const columns: DataTableColumn[] = [
    { key: "action", label: "Action" }, { key: "actor", label: "Actor" },
    { key: "repo_id", label: "Repository" }, { key: "created_at", label: "When" },
  ];
  return (
    <div className="space-y-4">
      <PageHeader title="Audit Logs" subtitle="Installs, settings changes, dismissals, purges and adapter promotions." />
      <div className="max-w-md"><SearchInput value={query} onChange={setQuery} placeholder="Filter by action or actor…" /></div>
      {events.length === 0 ? (
        <EmptyState title="No audit events yet" body="Installs, settings changes, dismissals, purges and adapter promotions are recorded here." />
      ) : (
        <>
          <p className="text-sm text-slate-400" aria-live="polite">{filtered.length} event{filtered.length === 1 ? "" : "s"}</p>
          <DataTable
            columns={columns} rows={pageRows}
            empty="No audit events match your filter."
            renderCell={(row, col) => {
              if (col.key === "action") return <span className="font-semibold text-white">{row.action}</span>;
              if (col.key === "repo_id") return <span>{row.repo_id ?? "—"}</span>;
              if (col.key === "created_at") return <span className="font-mono text-xs text-slate-500">{row.created_at ?? "—"}</span>;
              return String(row[col.key] ?? "—");
            }}
          />
          <Pagination page={safePage} pageCount={pageCount} onChange={setPage} />
        </>
      )}
    </div>
  );
}

export function SettingsPage({ notify, go }: { notify: (m: string) => void; go: (page: string, arg?: any) => void }) {
  const [repos, setRepos] = useState<any[]>([]);
  const [sel, setSel] = useState<number | undefined>(undefined);
  const [me, setMe] = useState<any>(null);
  useEffect(() => { get("/api/repos").then((rs) => { setRepos(rs); if (rs[0]) setSel(rs[0].id); }).catch(() => {}); }, []);
  useEffect(() => { get("/api/auth/me").then(setMe).catch(() => {}); }, []);
  if (repos.length === 0) return <EmptyState title="No repositories yet" body="Connect a repository or run the demo review first." />;
  return (
    <div className="space-y-6">
      <PageHeader title="Settings" subtitle="Your profile and per-repository settings." />
      {me && (
        <Card>
          <div className="flex items-center gap-4">
            <Avatar name={me.name || me.email || "?"} className="h-12 w-12 text-base" />
            <div>
              <div className="font-semibold text-white">{me.name || "—"}</div>
              <div className="text-sm text-slate-400">{me.email}</div>
              <div className="mt-1 flex flex-wrap gap-2">
                <Badge tone="violet">{me.role}</Badge>
                {me.github_login && <Badge tone="slate">GitHub: {me.github_login}</Badge>}
              </div>
            </div>
          </div>
        </Card>
      )}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-white">Repository settings</h2>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          Repository
          <select className={selectCls} style={{ width: 280 }} value={sel} onChange={(e) => setSel(parseInt(e.target.value))}>
            {repos.map((r: any) => <option key={r.id} value={r.id}>{r.full_name}</option>)}
          </select>
        </label>
      </div>
      {sel && <RepoDetail repoId={sel} notify={notify} go={go} />}
    </div>
  );
}

const API_SNIPPET = `curl -H "Authorization: Bearer $CS_TOKEN" \\
  https://codesentry-backend-hl76.onrender.com/api/repos`;

export function Documentation() {
  const [tab, setTab] = useState("overview");
  return (
    <div className="space-y-6">
      <PageHeader title="Documentation" subtitle="What CodeSentry does, how to run the demo, and the API surface." />
      <Tabs
        tabs={[
          { id: "overview", label: "Overview" },
          { id: "demo", label: "Demo walkthrough" },
          { id: "api", label: "API" },
          { id: "limits", label: "Limits" },
        ]}
        active={tab}
        onChange={setTab}
      />
      {tab === "overview" && (
        <Card><div className="font-semibold text-white">What CodeSentry does</div>
          <p className="mt-2 text-sm text-slate-400">CodeSentry indexes repositories by structure (tree-sitter symbols + call graph), reviews PR diffs with three LangGraph agents, and posts only evidence-cited, confidence-filtered findings with CWE mapping and validated patches. High-severity findings block the CI check until fixed or dismissed by an authorised reviewer.</p></Card>
      )}
      {tab === "demo" && (
        <Card><div className="font-semibold text-white">Demo in 60 seconds</div>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-400">
            <li>Sign in, or click “Run demo review” on the login page.</li>
            <li>Open Repositories → demo/shop-api → PR #42.</li>
            <li>Read the CWE-89 SQL injection: the sink is in <code>app/db.py</code>, the tainted input in <code>app/orders.py</code> — the finding exists only because the call graph was retrieved.</li>
            <li>Apply the suggested patch mentally (it parameterises the query), mark the finding fixed, and watch the Quality page update.</li>
          </ol></Card>
      )}
      {tab === "api" && (
        <Card><div className="font-semibold text-white">API (selected)</div>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-[#070b16] p-3 text-xs text-slate-300 scrollbar-thin">{`POST /webhooks/github            GitHub events (HMAC verified, deduped)
GET  /api/repos                   List visible repositories
GET  /api/repos/{id}/settings     PATCH to update (admin only)
POST /api/repos/{id}/reindex      Full re-index (admin)
GET  /api/repos/{id}/prs          GET /api/repos/{id}/prs/{number}
POST /api/findings/{id}/feedback  accept | fixed | reject_wrong | reject_not_worth_fixing | ignore
GET  /api/repos/{id}/quality      Metrics from persisted data only
POST /api/repos/{id}/purge?confirm=true
GET  /health  ·  GET /metrics`}</pre>
          <div className="mt-4">
            <div className="mb-2 text-xs font-semibold text-slate-300">Example: list repositories</div>
            <div className="flex items-start justify-between gap-3">
              <pre className="flex-1 overflow-x-auto rounded-lg bg-[#070b16] p-3 text-xs text-slate-300 scrollbar-thin">{API_SNIPPET}</pre>
              <CopyButton text={API_SNIPPET} label="Copy" />
            </div>
          </div>
        </Card>
      )}
      {tab === "limits" && (
        <Card><div className="font-semibold text-white">What it will not do</div>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-400">
            <li>No auto-merge, no auto-apply of patches. Humans decide.</li>
            <li>No claim of complete security coverage — absence of findings is not proof of safety.</li>
            <li>Taint analysis in v1 is heuristic hints, not a verified data-flow proof.</li>
            <li>Python and JavaScript/TypeScript only in v1.</li>
            <li>No training on private code without explicit opt-in (default off).</li>
          </ul></Card>
      )}
    </div>
  );
}
