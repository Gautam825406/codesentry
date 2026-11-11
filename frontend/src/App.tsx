import { useCallback, useEffect, useState } from "react";
import { token, setToken, clearToken, get } from "./api/client";
import { Overview } from "./pages/Overview";
import { Login, Register } from "./pages/Auth";
import { Landing } from "./pages/Landing";
import { Repos, RepoDetail } from "./pages/Repos";
import { Findings, PRs, ReviewDetail } from "./pages/Findings";
import { SecurityCenter, Quality, Agents, FineTuning, AuditLogs, SettingsPage, Documentation } from "./pages/Misc";
import { AppShell, PublicShell, Toasts, type PublicView, type ToastItem, type ToastKind } from "./components/layout";

type UnauthedView = "landing" | "login" | "register" | "docs";

export default function App() {
  const [authed, setAuthed] = useState(!!token());
  const [page, setPage] = useState<string>("overview");
  const [arg, setArg] = useState<any>(undefined);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [me, setMe] = useState<any>(null);
  const [publicView, setPublicView] = useState<UnauthedView>("landing");
  const [landingNav, setLandingNav] = useState<{ anchor?: string; nonce: number }>({ nonce: 0 });

  const notify = useCallback((m: string, kind: ToastKind = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, message: m, kind }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
  }, []);

  const go = (p: string, a?: any) => { setPage(p); setArg(a); window.scrollTo(0, 0); };
  const goPublic = (v: string, anchor?: string) => {
    setPublicView(v as UnauthedView);
    if (v === "landing") setLandingNav((n) => ({ anchor, nonce: n.nonce + 1 }));
    // When navigating to a landing anchor, the Landing effect scrolls after
    // render; otherwise scroll to top immediately.
    if (!anchor) window.scrollTo(0, 0);
  };
  const signOut = () => { clearToken(); setAuthed(false); setMe(null); setPage("overview"); setArg(undefined); setPublicView("landing"); };

  // Defensively consume a ?token= query param (e.g. from an OAuth callback
  // landing on the app root) and remove it from the URL afterwards.
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const qt = params.get("token");
      if (qt) {
        setToken(qt);
        setAuthed(true);
        const url = new URL(window.location.href);
        url.searchParams.delete("token");
        window.history.replaceState({}, "", url.pathname + url.search + url.hash);
      }
    } catch { /* ignore malformed URLs */ }
  }, []);

  useEffect(() => {
    if (authed) get("/api/auth/me").then(setMe).catch(() => { clearToken(); setAuthed(false); });
  }, [authed]);

  if (!authed) {
    return (
      <>
        {publicView === "landing" && <Landing go={goPublic} scrollTo={landingNav.anchor} scrollNonce={landingNav.nonce} />}
        {publicView === "login" && <Login onDone={() => setAuthed(true)} notify={notify} go={goPublic} />}
        {publicView === "register" && <Register onDone={() => setAuthed(true)} notify={notify} go={goPublic} />}
        {publicView === "docs" && (
          <PublicShell onNavigate={(v, anchor) => goPublic(v, anchor)}>
            <Documentation />
          </PublicShell>
        )}
        <Toasts items={toasts} />
      </>
    );
  }

  return (
    <>
      <AppShell me={me} page={page} go={go} onSignOut={signOut}>
        {page === "overview" && <Overview notify={notify} go={go} />}
        {page === "repos" && <Repos notify={notify} go={go} />}
        {page === "repo" && <RepoDetail repoId={arg} notify={notify} go={go} />}
        {page === "prs" && <PRs repoId={arg} notify={notify} go={go} />}
        {page === "review" && <ReviewDetail repoId={arg.repoId} number={arg.number} notify={notify} />}
        {page === "findings" && <Findings notify={notify} initialQuery={arg?.q} />}
        {page === "security" && <SecurityCenter notify={notify} />}
        {page === "quality" && <Quality repoId={arg} notify={notify} />}
        {page === "agents" && <Agents notify={notify} />}
        {page === "finetuning" && <FineTuning notify={notify} />}
        {page === "audit" && <AuditLogs />}
        {page === "settings" && <SettingsPage notify={notify} go={go} />}
        {page === "docs" && <Documentation />}
      </AppShell>
      <Toasts items={toasts} />
    </>
  );
}
