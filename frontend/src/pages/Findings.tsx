import { useEffect, useState } from "react";
import { get, post } from "../api/client";
import type { Finding } from "../api/client";
import { Btn, Card, EmptyState, Skeleton, SeverityBadge, inputCls } from "../components/ui";

const VERDICTS = ["accept", "fixed", "reject_wrong", "reject_not_worth_fixing", "ignore"] as const;

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
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <SeverityBadge severity={f.severity} />
            <span className="rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-300">{f.source}</span>
            <span className="rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-300">{f.category}</span>
            {f.cwe_id && <span className="rounded-full border border-violet-500/40 bg-violet-500/10 px-2 py-0.5 text-xs text-violet-300">{f.cwe_id}{f.cwe_title ? ` — ${f.cwe_title}` : ""}</span>}
          </div>
          <div className="mt-2 font-semibold text-white">{f.title}</div>
          <div className="mt-1 text-sm text-slate-400">{f.description}</div>
          <div className="mt-2 font-mono text-xs text-slate-400">{f.file_path}:{f.start_line}{f.end_line !== f.start_line ? `-${f.end_line}` : ""} · PR #{f.pr_number} · confidence {f.confidence.toFixed(2)} · {f.model_version}</div>
        </div>
        <span className={`rounded-full border px-2 py-0.5 text-xs ${f.state === "dismissed" ? "border-slate-600 text-slate-400" : f.state === "suppressed" ? "border-amber-500/40 text-amber-300" : "border-emerald-500/40 text-emerald-300"}`}>{f.state}{f.suppressed_reason ? ` — ${f.suppressed_reason}` : ""}</span>
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
          <button className="text-xs text-slate-400 underline" onClick={() => setOpen(!open)}>{open ? "Hide feedback" : "Give feedback…"}</button>
          {open && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <input className={inputCls} style={{ maxWidth: 260 }} placeholder="Reason (optional)" value={reason} onChange={e => setReason(e.target.value)} />
              {VERDICTS.map(v => <Btn key={v} variant="ghost" onClick={() => feedback(v)}>{v.replace(/_/g, " ")}</Btn>)}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export function Findings({ notify }: { notify: (m: string) => void }) {
  const [items, setItems] = useState<Finding[] | null>(null);
  const [repos, setRepos] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [f, setF] = useState({ severity: "", cwe: "", category: "", repo_id: "", pr_number: "", agent: "", state: "" });
  const load = () => {
    const q = new URLSearchParams(Object.entries(f).filter(([, v]) => v));
    get(`/api/findings?${q}`).then(setItems).catch((e) => setErr(e.message));
  };
  useEffect(() => { get("/api/repos").then(setRepos).catch(() => {}); }, []);
  useEffect(() => { load(); }, [f]);
  if (err) return <EmptyState title="Could not load findings" body={err} />;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-white">Findings</h1>
      <Card>
        <div className="grid gap-3 md:grid-cols-4">
          <select className={inputCls} value={f.severity} onChange={e => setF({ ...f, severity: e.target.value })}>
            <option value="">Severity: all</option>{["critical", "high", "medium", "low"].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className={inputCls} value={f.repo_id} onChange={e => setF({ ...f, repo_id: e.target.value })}>
            <option value="">Repository: all</option>{repos.map((r: any) => <option key={r.id} value={r.id}>{r.full_name}</option>)}
          </select>
          <select className={inputCls} value={f.agent} onChange={e => setF({ ...f, agent: e.target.value })}>
            <option value="">Agent: all</option>{["security", "logic", "style", "secret-scanner", "dependency-scanner"].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className={inputCls} value={f.state} onChange={e => setF({ ...f, state: e.target.value })}>
            <option value="">State: all</option>{["posted", "suppressed", "fixed", "dismissed"].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <input className={inputCls} placeholder="CWE e.g. CWE-89" value={f.cwe} onChange={e => setF({ ...f, cwe: e.target.value })} />
          <input className={inputCls} placeholder="Category e.g. sql_injection" value={f.category} onChange={e => setF({ ...f, category: e.target.value })} />
          <input className={inputCls} placeholder="PR number" value={f.pr_number} onChange={e => setF({ ...f, pr_number: e.target.value })} />
        </div>
      </Card>
      {!items ? <Skeleton className="h-48" /> : items.length === 0 ? (
        <EmptyState title="No findings match" body="Try widening the filters — or run the demo review to generate real findings on the sample repository." />
      ) : items.map((x) => <FindingCard key={x.id} f={x} notify={notify} onDone={load} />)}
    </div>
  );
}

export function PRs({ repoId, notify, go }: { repoId?: number; notify: (m: string) => void; go: (page: string, arg?: any) => void }) {
  const [repos, setRepos] = useState<any[]>([]);
  const [rows, setRows] = useState<any[] | null>(null);
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
  if (!rows) return <Skeleton className="h-48" />;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-white">Pull requests</h1>
      {rows.length === 0 ? <EmptyState title="No pull requests reviewed yet" body="Open a PR on a connected repository, or run the demo review — PR #42 on demo/shop-api is the seeded example." /> : (
        <div className="space-y-2">{rows.map((p: any) => (
          <button key={`${p.repo.id}-${p.number}`} onClick={() => go("review", { repoId: p.repo.id, number: p.number })}
            className="flex w-full items-center justify-between rounded-2xl border border-slate-800 bg-[#0b1226] px-5 py-4 text-left hover:bg-slate-800/40">
            <span><span className="font-mono text-sm text-slate-400">{p.repo.full_name}</span>
              <span className="ml-2 font-semibold text-white">#{p.number} {p.title}</span>
              <span className="ml-2 text-xs text-slate-400">{p.size_band}</span></span>
            <span className="text-xs text-slate-300">{p.run ? `${p.run.status} · gate ${p.run.gate_result} · ${p.run.latency_ms}ms` : "not reviewed"}</span>
          </button>
        ))}</div>
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
  if (!pr) return <Skeleton className="h-64" />;
  const run = pr.runs?.[0];
  const posted = run?.findings?.filter((f: any) => f.state === "posted") || [];
  const suppressed = run?.findings?.filter((f: any) => f.state === "suppressed") || [];
  return (
    <div className="space-y-6">
      <div>
        <div className="font-mono text-sm text-slate-400">{pr.repo_full_name}</div>
        <h1 className="text-2xl font-bold text-white">PR #{pr.number} — {pr.title}</h1>
        <div className="mt-1 font-mono text-xs text-slate-400">base {pr.base_sha} · head {pr.head_sha} · {pr.size_band}</div>
      </div>
      {!run ? <EmptyState title="No review run yet" body="This PR has not been reviewed. Trigger a review from the repository page or via the API." /> : (
        <>
          <Card>
            <div className="grid gap-4 md:grid-cols-4 text-sm">
              <div><div className="text-slate-400">Status</div><div className="font-semibold text-white">{run.status} · gate <span className={run.gate_result === "fail" ? "text-red-400" : "text-emerald-400"}>{run.gate_result}</span></div></div>
              <div><div className="text-slate-400">Coverage</div><div className="font-semibold text-white">{run.coverage?.pct ?? 0}% — {run.coverage?.files_reviewed}/{run.coverage?.files_total} files</div></div>
              <div><div className="text-slate-400">Latency / tokens / cost</div><div className="font-semibold text-white">{run.latency_ms} ms · {run.tokens_used} tokens · ${run.cost_usd}</div></div>
              <div><div className="text-slate-400">Model</div><div className="font-semibold text-white">{run.model_version} · {run.prompt_version}</div></div>
            </div>
            <p className="mt-3 text-sm text-slate-300">{run.summary}</p>
            {(run.coverage?.files_skipped?.length ?? 0) > 0 && (
              <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-200">
                Skipped files (disclosed, never silent): {run.coverage.files_skipped.map((s: any) => `${s.path} (${s.reason})`).join(", ")}
              </div>
            )}
          </Card>
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
