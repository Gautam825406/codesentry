import { useEffect, useState } from "react";
import { token, setToken, get } from "./api/client";
import { Login, Overview } from "./pages/Overview";
import { Repos, RepoDetail } from "./pages/Repos";
import { Findings, PRs, ReviewDetail } from "./pages/Findings";
import { SecurityCenter, Quality, Agents, FineTuning, AuditLogs, SettingsPage, Documentation } from "./pages/Misc";

const NAV = [
  ["overview", "Overview"], ["repos", "Repositories"], ["prs", "Pull Requests"],
  ["findings", "Findings"], ["security", "Security Center"], ["quality", "Quality Analytics"],
  ["agents", "AI Agents"], ["finetuning", "Fine-Tuning"], ["audit", "Audit Logs"],
  ["settings", "Settings"], ["docs", "Documentation"],
] as const;

export default function App() {
  const [authed, setAuthed] = useState(!!token());
  const [page, setPage] = useState<string>("overview");
  const [arg, setArg] = useState<any>(undefined);
  const [toast, setToast] = useState("");
  const [me, setMe] = useState<any>(null);
  const notify = (m: string) => { setToast(m); setTimeout(() => setToast(""), 5000); };
  const go = (p: string, a?: any) => { setPage(p); setArg(a); window.scrollTo(0, 0); };
  useEffect(() => {
    if (authed) get("/api/auth/me").then(setMe).catch(() => { setToken(null); setAuthed(false); });
  }, [authed]);
  if (!authed) {
    return (
      <div className="min-h-screen bg-[#070b16]">
        <header className="sticky top-0 z-10 border-b border-slate-800 bg-[#070b16]/90 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
            <span className="text-xl font-bold text-white">🛡️ Code<span className="grad-text">Sentry</span></span>
            <span className="text-xs text-slate-400">Agentic secure code review</span>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 pb-16"><Login onDone={() => setAuthed(true)} notify={notify} /></main>
        {toast && <div className="fixed bottom-4 right-4 max-w-sm rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-white shadow-xl">{toast}</div>}
      </div>
    );
  }
  return (
    <div className="min-h-screen bg-[#070b16]">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-[#070b16]/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-6 py-3">
          <button onClick={() => go("overview")} className="text-xl font-bold text-white">🛡️ Code<span className="grad-text">Sentry</span></button>
          <nav className="flex flex-wrap gap-1">
            {NAV.map(([k, label]) => (
              <button key={k} onClick={() => go(k)}
                className={`rounded-lg px-3 py-1.5 text-sm ${page === k ? "bg-violet-600/20 text-violet-200" : "text-slate-400 hover:bg-slate-800 hover:text-white"}`}>{label}</button>
            ))}
          </nav>
          <span className="flex items-center gap-3 text-xs text-slate-400">
            <span>{me?.email}</span>
            <button className="rounded-lg border border-slate-700 px-2 py-1 hover:bg-slate-800" onClick={() => { setToken(null); setAuthed(false); }}>Sign out</button>
          </span>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        {page === "overview" && <Overview notify={notify} go={go} />}
        {page === "repos" && <Repos notify={notify} go={go} />}
        {page === "repo" && <RepoDetail repoId={arg} notify={notify} go={go} />}
        {page === "prs" && <PRs repoId={arg} notify={notify} go={go} />}
        {page === "review" && <ReviewDetail repoId={arg.repoId} number={arg.number} notify={notify} />}
        {page === "findings" && <Findings notify={notify} />}
        {page === "security" && <SecurityCenter notify={notify} />}
        {page === "quality" && <Quality repoId={arg} notify={notify} />}
        {page === "agents" && <Agents notify={notify} />}
        {page === "finetuning" && <FineTuning notify={notify} />}
        {page === "audit" && <AuditLogs />}
        {page === "settings" && <SettingsPage notify={notify} go={go} />}
        {page === "docs" && <Documentation />}
      </main>
      <footer className="border-t border-slate-800">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-6 py-6 text-xs text-slate-500">
          <span>CodeSentry — AST-aware review, cited findings, CI gating, learning from feedback.</span>
          <span>No auto-merge. No complete-security-coverage claim. Metrics come from persisted data only.</span>
        </div>
      </footer>
      {toast && <div className="fixed bottom-4 right-4 max-w-sm rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-white shadow-xl">{toast}</div>}
    </div>
  );
}
