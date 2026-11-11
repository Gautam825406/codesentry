import { useEffect, useState } from "react";
import { get, post, setToken } from "../api/client";
import { Btn, Card, EmptyState, Field, Skeleton, Stat, inputCls, SeverityBadge } from "../components/ui";

export function Login({ onDone, notify }: { onDone: () => void; notify: (m: string) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await post("/api/auth/login", { email, password });
      setToken(r.token);
      onDone();
    } catch (err: any) { notify(err.message); } finally { setBusy(false); }
  };
  const demo = async () => {
    setBusy(true);
    try {
      const r = await post("/api/demo/seed");
      setToken(r.token);
      notify(`Demo seeded: PR #42 reviewed, gate ${r.gate_result} — ${r.findings.length} findings.`);
      onDone();
    } catch (err: any) { notify(err.message); } finally { setBusy(false); }
  };
  return (
    <div className="mx-auto max-w-md pt-16">
      <h1 className="text-3xl font-bold text-white">Sign in to <span className="grad-text">CodeSentry</span></h1>
      <p className="mt-2 text-sm text-slate-400">Agentic secure code review. No demo data is faked — every number on the dashboard comes from real reviews.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <Field label="Email"><input className={inputCls} value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.dev" /></Field>
        <Field label="Password"><input type="password" className={inputCls} value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" /></Field>
        <Btn type="submit" disabled={busy}>Sign in</Btn>
      </form>
      <div className="mt-6 rounded-2xl border border-slate-800 bg-[#0b1226] p-5">
        <div className="font-semibold text-white">Try the live demo — no GitHub needed</div>
        <p className="mt-1 text-sm text-slate-400">Seeds the sample shop API, indexes it, and runs a real review of PR #42: a SQL injection visible only through the call graph.</p>
        <div className="mt-3"><Btn onClick={demo} disabled={busy} variant="outline">Run demo review</Btn></div>
      </div>
    </div>
  );
}

export function Overview({ notify, go }: { notify: (m: string) => void; go: (page: string, arg?: any) => void }) {
  const [data, setData] = useState<any>(null);
  const [repos, setRepos] = useState<any[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    Promise.all([get("/metrics"), get("/api/repos")])
      .then(([m, r]) => { setData(m); setRepos(r); })
      .catch((e) => setErr(e.message));
  }, []);
  if (err) return <EmptyState title="Could not load the overview" body={err} />;
  if (!data) return <div className="grid gap-4 md:grid-cols-4"><Skeleton /><Skeleton /><Skeleton /><Skeleton /></div>;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Overview</h1>
        <p className="text-sm text-slate-400">Review activity and risk across your repositories — computed from persisted reviews, never hardcoded.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-4">
        <Stat label="Repositories" value={data.repos} />
        <Stat label="Reviews run" value={data.reviews} />
        <Stat label="Findings posted" value={data.findings_posted} sub={`of ${data.findings} total (incl. suppressed)`} />
        <Stat label="Feedback events" value={data.feedback_events} />
      </div>
      {repos.length === 0 ? (
        <EmptyState title="No repositories connected yet" body="Connect a repository, or run the demo review to see CodeSentry work end to end on the sample shop API."
          action={<Btn onClick={async () => { try { await post("/api/demo/seed"); notify("Demo seeded — reloading."); location.reload(); } catch (e: any) { notify(e.message); } }}>Run demo review</Btn>} />
      ) : (
        <Card>
          <div className="mb-3 font-semibold text-white">Repositories</div>
          <div className="space-y-2">
            {repos.map((r: any) => (
              <button key={r.id} onClick={() => go("repo", r.id)} className="flex w-full items-center justify-between rounded-lg border border-slate-800 px-4 py-3 text-left hover:bg-slate-800/50">
                <span><span className="font-mono text-sm text-white">{r.full_name}</span>
                  <span className="ml-3 text-xs text-slate-400">{r.languages?.join(", ") || "—"}</span></span>
                <span className="rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-300">{r.index_status}</span>
              </button>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
