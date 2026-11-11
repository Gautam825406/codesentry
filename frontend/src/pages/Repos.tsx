import { useEffect, useState } from "react";
import { get, post, patch } from "../api/client";
import { Btn, Card, EmptyState, Field, Skeleton, inputCls, SeverityBadge } from "../components/ui";

export function Repos({ notify, go }: { notify: (m: string) => void; go: (page: string, arg?: any) => void }) {
  const [repos, setRepos] = useState<any[] | null>(null);
  const [fullName, setFullName] = useState("");
  const [err, setErr] = useState("");
  const load = () => get("/api/repos").then(setRepos).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  const connect = async () => {
    try { await post("/api/repos", { full_name: fullName }); setFullName(""); notify("Repository connected."); load(); }
    catch (e: any) { notify(e.message); }
  };
  if (!repos) return <Skeleton className="h-64" />;
  if (err) return <EmptyState title="Could not load repositories" body={err} />;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Repositories</h1>
      <Card>
        <div className="flex gap-3">
          <input className={inputCls} value={fullName} onChange={e => setFullName(e.target.value)} placeholder="owner/repo — e.g. demo/shop-api" />
          <Btn onClick={connect} disabled={!fullName.trim()}>Connect</Btn>
        </div>
        <p className="mt-2 text-xs text-slate-500">Connecting records the repository and its settings. Indexing clones/fetches contents via the GitHub App when configured; the demo repo ships its files locally.</p>
      </Card>
      {repos.length === 0 ? <EmptyState title="No repositories yet" body="Connect one above, or run the demo review from the Overview page." /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {repos.map((r: any) => (
            <Card key={r.id}>
              <div className="flex items-start justify-between">
                <div><div className="font-mono font-semibold text-white">{r.full_name}</div>
                  <div className="mt-1 text-xs text-slate-400">Index: {r.index_status} · Languages: {r.languages?.join(", ") || "—"}</div></div>
                {r.is_demo && <span className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-2 py-0.5 text-xs text-cyan-300">demo</span>}
              </div>
              <div className="mt-4 flex gap-2">
                <Btn variant="outline" onClick={() => go("repo", r.id)}>Open</Btn>
                <Btn variant="ghost" onClick={() => go("prs", r.id)}>Pull requests</Btn>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export function RepoDetail({ repoId, notify, go }: { repoId: number; notify: (m: string) => void; go: (page: string, arg?: any) => void }) {
  const [repo, setRepo] = useState<any>(null);
  const [settings, setSettings] = useState<any>(null);
  const [prs, setPrs] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [confirmPurge, setConfirmPurge] = useState(false);
  const load = () => {
    get(`/api/repos/${repoId}`).then(setRepo).catch((e) => setErr(e.message));
    get(`/api/repos/${repoId}/settings`).then(setSettings).catch(() => {});
    get(`/api/repos/${repoId}/prs`).then(setPrs).catch(() => {});
  };
  useEffect(() => { load(); }, [repoId]);
  if (err) return <EmptyState title="Repository not found or not authorised" body={err} />;
  if (!repo) return <Skeleton className="h-64" />;
  const save = async () => {
    try { await patch(`/api/repos/${repoId}/settings`, settings); notify("Settings saved."); }
    catch (e: any) { notify(e.message); }
  };
  const reindex = async () => {
    try { const r = await post(`/api/repos/${repoId}/reindex`, {}); notify(`Re-indexed: ${r.symbols} symbols (${r.parser}).`); load(); }
    catch (e: any) { notify(e.message); }
  };
  const purge = async () => {
    try { const r = await post(`/api/repos/${repoId}/purge?confirm=true`); notify(`Purged: ${r.symbols_deleted} symbols deleted, verified: ${r.verified}.`); setConfirmPurge(false); load(); }
    catch (e: any) { notify(e.message); }
  };
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-mono text-2xl font-bold text-white">{repo.full_name}</h1>
        <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">index: {repo.index_status} · {repo.symbols ?? 0} symbols</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <Btn onClick={reindex}>Full re-index</Btn>
        <Btn variant="outline" onClick={() => go("quality", repoId)}>Quality analytics</Btn>
        {!confirmPurge
          ? <Btn variant="danger" onClick={() => setConfirmPurge(true)}>Purge index…</Btn>
          : <span className="flex gap-2"><Btn variant="danger" onClick={purge}>Confirm purge</Btn><Btn variant="ghost" onClick={() => setConfirmPurge(false)}>Cancel</Btn></span>}
      </div>
      {settings && (
        <Card>
          <div className="mb-4 font-semibold text-white">Repository settings</div>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Confidence threshold (0–1)">
              <input type="number" step="0.05" min="0" max="1" className={inputCls} value={settings.confidence_threshold}
                onChange={e => setSettings({ ...settings, confidence_threshold: parseFloat(e.target.value) })} />
            </Field>
            <Field label="Model provider">
              <select className={inputCls} value={settings.model_provider} onChange={e => setSettings({ ...settings, model_provider: e.target.value })}>
                <option value="deterministic">deterministic (rule engine, no key)</option>
                <option value="groq">Groq (hosted)</option>
                <option value="ollama">Ollama (local)</option>
              </select>
            </Field>
            <Field label="Token budget per symbol">
              <input type="number" className={inputCls} value={settings.token_budget_per_symbol}
                onChange={e => setSettings({ ...settings, token_budget_per_symbol: parseInt(e.target.value) })} />
            </Field>
            <Field label="Daily cost limit (USD)">
              <input type="number" step="0.5" className={inputCls} value={settings.daily_cost_limit_usd}
                onChange={e => setSettings({ ...settings, daily_cost_limit_usd: parseFloat(e.target.value) })} />
            </Field>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={settings.gate_enabled} onChange={e => setSettings({ ...settings, gate_enabled: e.target.checked })} /> CI merge gate enabled
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={settings.training_opt_in} onChange={e => setSettings({ ...settings, training_opt_in: e.target.checked })} /> Training opt-in (OFF by default — feedback is only used for fine-tuning with explicit consent)
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={settings.index_paused} onChange={e => setSettings({ ...settings, index_paused: e.target.checked })} /> Pause indexing
            </label>
          </div>
          <div className="mt-4"><Btn onClick={save}>Save settings</Btn></div>
        </Card>
      )}
      <Card>
        <div className="mb-3 font-semibold text-white">Pull requests</div>
        {prs.length === 0 ? <p className="text-sm text-slate-400">No pull requests reviewed yet for this repository.</p> : (
          <div className="space-y-2">{prs.map((p: any) => (
            <button key={p.id} onClick={() => go("review", { repoId, number: p.number })} className="flex w-full items-center justify-between rounded-lg border border-slate-800 px-4 py-3 text-left hover:bg-slate-800/50">
              <span><span className="font-semibold text-white">#{p.number} {p.title}</span>
                <span className="ml-2 text-xs text-slate-400">{p.size_band} · {p.author}</span></span>
              <span className="flex items-center gap-2"><SeverityBadge severity={p.run?.gate_result === "fail" ? "high" : "low"} />
                <span className="text-xs text-slate-400">{p.run?.status || "not reviewed"} · gate {p.run?.gate_result || "—"}</span></span>
            </button>
          ))}</div>
        )}
      </Card>
    </div>
  );
}
