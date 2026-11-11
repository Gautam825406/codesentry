import { useEffect, useState } from "react";
import { get, post } from "../api/client";
import { Btn, Card, EmptyState, Skeleton, Stat, inputCls } from "../components/ui";
import { FindingCard } from "./Findings";
import { RepoDetail } from "./Repos";

export function SecurityCenter({ notify }: { notify: (m: string) => void }) {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { get("/api/security").then(setData).catch((e) => setErr(e.message)); }, []);
  if (err) return <EmptyState title="Could not load the Security Center" body={err} />;
  if (!data) return <Skeleton className="h-48" />;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Security Center</h1>
      <div className="grid gap-4 md:grid-cols-3">
        <Stat label="Critical CWE findings" value={data.critical} />
        <Stat label="High CWE findings" value={data.high} />
        <Stat label="CWE categories seen" value={Object.keys(data.by_cwe || {}).length} sub={Object.entries(data.by_cwe || {}).map(([k, v]) => `${k}: ${v}`).join(" · ") || "none yet"} />
      </div>
      <p className="text-sm text-slate-400">Only findings with a valid CWE identifier appear here. A security finding without a valid CWE is never posted as one — that is a filter rule, not a display choice. Absence of findings is not proof of safety.</p>
      {data.findings.length === 0 ? <EmptyState title="No security findings posted" body="Run the demo review to see a CWE-89 SQL injection finding here." /> :
        data.findings.map((f: any) => <FindingCard key={f.id} f={f} notify={notify} />)}
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
  if (repos.length === 0) return <EmptyState title="No repositories yet" body="Connect a repository or run the demo review first." />;
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Quality Analytics</h1>
        <select className={inputCls} style={{ maxWidth: 320 }} value={sel} onChange={e => setSel(parseInt(e.target.value))}>
          {repos.map((r: any) => <option key={r.id} value={r.id}>{r.full_name}</option>)}
        </select>
      </div>
      {err && <EmptyState title="Could not load quality data" body={err} />}
      {!q ? <Skeleton className="h-48" /> : (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <Stat label="PRs reviewed" value={q.prs_reviewed} />
            <Stat label="Findings posted" value={q.posted} sub={`${q.suppressed} suppressed`} />
            <Stat label="Precision" value={q.precision === null ? "—" : q.precision.toFixed(2)} sub={q.precision === null ? "no feedback yet — not fabricated" : `${q.feedback_total} feedback events`} />
            <Stat label="False-positive rate" value={q.false_positive_rate === null ? "—" : q.false_positive_rate.toFixed(2)} sub={`p50 latency ${q.review_latency_ms_p50 ?? "—"} ms`} />
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <Card><div className="mb-2 font-semibold text-white">By severity</div>{Object.entries(q.by_severity || {}).map(([k, v]: any) => <div key={k} className="flex justify-between text-sm py-1"><span className="text-slate-400">{k}</span><span className="text-white">{v}</span></div>) || <p className="text-sm text-slate-400">None yet.</p>}</Card>
            <Card><div className="mb-2 font-semibold text-white">By CWE</div>{Object.entries(q.by_cwe || {}).map(([k, v]: any) => <div key={k} className="flex justify-between text-sm py-1"><span className="text-slate-400">{k}</span><span className="text-white">{v}</span></div>) || <p className="text-sm text-slate-400">None yet.</p>}</Card>
            <Card><div className="mb-2 font-semibold text-white">By agent</div>{Object.entries(q.by_agent || {}).map(([k, v]: any) => <div key={k} className="flex justify-between text-sm py-1"><span className="text-slate-400">{k}</span><span className="text-white">{v}</span></div>) || <p className="text-sm text-slate-400">None yet.</p>}</Card>
          </div>
          <Card>
            <div className="mb-2 font-semibold text-white">Feedback verdicts</div>
            {Object.keys(q.verdicts || {}).length === 0 ? <p className="text-sm text-slate-400">No feedback yet. Mark findings right or wrong from the Findings page — that is what drives precision and the fine-tuning dataset.</p> :
              Object.entries(q.verdicts).map(([k, v]: any) => <div key={k} className="flex justify-between text-sm py-1"><span className="text-slate-400">{k.replace(/_/g, " ")}</span><span className="text-white">{v}</span></div>)}
            <div className="mt-2 text-xs text-slate-500">Cost per PR: ${q.cost_per_pr_usd} · p95 latency: {q.review_latency_ms_p95 ?? "—"} ms</div>
          </Card>
        </>
      )}
    </div>
  );
}

export function Agents({ notify }: { notify: (m: string) => void }) {
  const [data, setData] = useState<any>(null);
  useEffect(() => { get("/api/agents").then(setData).catch(() => {}); }, []);
  if (!data) return <Skeleton className="h-48" />;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">AI Agents</h1>
      <p className="text-sm text-slate-400">LangGraph graph: {data.graph}. Parser: <code>{data.parser}</code> · Embeddings: <code>{data.embeddings}</code> · LLM provider: <code>{data.llm_provider}</code>.</p>
      <div className="grid gap-4 md:grid-cols-3">
        {data.agents.map((a: any) => (
          <Card key={a.name}>
            <div className="flex items-center justify-between"><span className="font-semibold capitalize text-white">{a.name} agent</span>
              <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300">{a.status}</span></div>
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
  const load = () => { get("/api/training/datasets").then(setDatasets).catch(() => {}); get("/api/training/adapters").then(setAdapters).catch(() => {}); };
  useEffect(() => { load(); }, []);
  const build = async () => { try { const r = await post("/api/training/datasets/build"); notify(r.built ? `Dataset ${r.version}: ${r.train} train / ${r.val} val / ${r.heldout} held-out.` : r.reason); load(); } catch (e: any) { notify(e.message); } };
  const train = async (id: number) => { try { const r = await post(`/api/training/datasets/${id}/train`); notify(`Adapter ${r.version}: ${r.status}. ${r.metrics?.error || ""}`); load(); } catch (e: any) { notify(e.message); } };
  const act = async (id: number, action: "promote" | "rollback") => { try { await post(`/api/training/adapters/${id}/${action}`); notify(`Adapter ${action}d.`); load(); } catch (e: any) { notify(e.message); } };
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Fine-Tuning (LoRA)</h1>
      <p className="text-sm text-slate-400">Datasets are built only from authorised-reviewer correctness verdicts on repositories with training opt-in. Promotion is blocked unless the held-out evaluation gate passes. No training run is claimed unless a real job completed — this environment has no GPU, so training stays honestly <code>not_started</code> until run on a GPU host.</p>
      <Btn onClick={build}>Build dataset from feedback</Btn>
      <Card><div className="mb-2 font-semibold text-white">Dataset versions</div>
        {datasets.length === 0 ? <p className="text-sm text-slate-400">No datasets yet. Give feedback on findings first, with training opt-in enabled on the repository.</p> :
          datasets.map((d: any) => (
            <div key={d.id} className="flex items-center justify-between border-t border-slate-800 py-3 text-sm">
              <span><span className="font-mono text-white">{d.version}</span> <span className="text-slate-400">· train {d.train} · val {d.val} · held-out {d.heldout}</span></span>
              <Btn variant="outline" onClick={() => train(d.id)}>Start LoRA training</Btn>
            </div>
          ))}
      </Card>
      <Card><div className="mb-2 font-semibold text-white">LoRA adapters</div>
        {adapters.length === 0 ? <p className="text-sm text-slate-400">No adapters yet.</p> :
          adapters.map((a: any) => (
            <div key={a.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 py-3 text-sm">
              <span><span className="font-mono text-white">{a.version}</span> <span className="text-slate-400">· {a.base_model} · {a.status}{a.promoted ? " · promoted" : ""}</span></span>
              <span className="flex gap-2"><Btn variant="outline" onClick={() => act(a.id, "promote")}>Promote</Btn><Btn variant="ghost" onClick={() => act(a.id, "rollback")}>Rollback</Btn></span>
            </div>
          ))}
      </Card>
    </div>
  );
}

export function AuditLogs() {
  const [events, setEvents] = useState<any[] | null>(null);
  useEffect(() => { get("/api/audit").then(setEvents).catch(() => setEvents([])); }, []);
  if (!events) return <Skeleton className="h-48" />;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-white">Audit Logs</h1>
      {events.length === 0 ? <EmptyState title="No audit events yet" body="Installs, settings changes, dismissals, purges and adapter promotions are recorded here." /> : (
        <Card><div className="space-y-2">{events.map((e: any) => (
          <div key={e.id} className="flex justify-between gap-4 border-b border-slate-800/60 py-2 text-sm">
            <span><span className="font-semibold text-white">{e.action}</span> <span className="text-slate-400">by {e.actor}</span></span>
            <span className="font-mono text-xs text-slate-500">{e.created_at}</span>
          </div>
        ))}</div></Card>
      )}
    </div>
  );
}

export function SettingsPage({ notify, go }: { notify: (m: string) => void; go: (page: string, arg?: any) => void }) {
  const [repos, setRepos] = useState<any[]>([]);
  const [sel, setSel] = useState<number | undefined>(undefined);
  useEffect(() => { get("/api/repos").then((rs) => { setRepos(rs); if (rs[0]) setSel(rs[0].id); }).catch(() => {}); }, []);
  if (repos.length === 0) return <EmptyState title="No repositories yet" body="Connect a repository or run the demo review first." />;
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <select className={inputCls} style={{ maxWidth: 320 }} value={sel} onChange={e => setSel(parseInt(e.target.value))}>
          {repos.map((r: any) => <option key={r.id} value={r.id}>{r.full_name}</option>)}
        </select>
      </div>
      {sel && <RepoDetail repoId={sel} notify={notify} go={go} />}
    </div>
  );
}

export function Documentation() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Documentation</h1>
      <Card><div className="font-semibold text-white">What CodeSentry does</div>
        <p className="mt-2 text-sm text-slate-400">CodeSentry indexes repositories by structure (tree-sitter symbols + call graph), reviews PR diffs with three LangGraph agents, and posts only evidence-cited, confidence-filtered findings with CWE mapping and validated patches. High-severity findings block the CI check until fixed or dismissed by an authorised reviewer.</p></Card>
      <Card><div className="font-semibold text-white">Demo in 60 seconds</div>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-400">
          <li>Sign in, or click “Run demo review” on the login page.</li>
          <li>Open Repositories → demo/shop-api → PR #42.</li>
          <li>Read the CWE-89 SQL injection: the sink is in <code>app/db.py</code>, the tainted input in <code>app/orders.py</code> — the finding exists only because the call graph was retrieved.</li>
          <li>Apply the suggested patch mentally (it parameterises the query), mark the finding fixed, and watch the Quality page update.</li>
        </ol></Card>
      <Card><div className="font-semibold text-white">API (selected)</div>
        <pre className="mt-2 overflow-x-auto rounded-lg bg-[#070b16] p-3 text-xs text-slate-300 scrollbar-thin">{`POST /webhooks/github            GitHub events (HMAC verified, deduped)
GET  /api/repos                   List visible repositories
GET  /api/repos/{id}/settings     PATCH to update (admin only)
POST /api/repos/{id}/reindex      Full re-index (admin)
GET  /api/repos/{id}/prs          GET /api/repos/{id}/prs/{number}
POST /api/findings/{id}/feedback  accept | fixed | reject_wrong | reject_not_worth_fixing | ignore
GET  /api/repos/{id}/quality      Metrics from persisted data only
POST /api/repos/{id}/purge?confirm=true
GET  /health  ·  GET /metrics`}</pre></Card>
      <Card><div className="font-semibold text-white">What it will not do</div>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-400">
          <li>No auto-merge, no auto-apply of patches. Humans decide.</li>
          <li>No claim of complete security coverage — absence of findings is not proof of safety.</li>
          <li>Taint analysis in v1 is heuristic hints, not a verified data-flow proof.</li>
          <li>Python and JavaScript/TypeScript only in v1.</li>
          <li>No training on private code without explicit opt-in (default off).</li>
        </ul></Card>
    </div>
  );
}
