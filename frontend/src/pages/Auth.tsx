import { useState, type FormEvent } from "react";
import { get, post, setToken } from "../api/client";
import { Alert, Badge, Btn, Card, Field, Spinner, inputCls } from "../components/ui";
import { PublicShell } from "../components/layout";
import type { ToastKind } from "../components/layout";

export type AuthProps = {
  onDone: () => void;
  notify: (message: string, kind?: ToastKind) => void;
  go: (view: string, anchor?: string) => void;
};

const DEMO_EMAIL = "demo@codesentry.dev";
const DEMO_PASSWORD = "demo1234";

const isValidEmail = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());

function friendlyAuthError(err: any): string {
  const msg = String(err?.message ?? err ?? "Something went wrong.");
  if (msg.startsWith("401")) return "Invalid credentials — check your email and password and try again.";
  if (msg.startsWith("400")) return msg.replace(/^400:\s*/, "");
  return msg;
}

function PasswordField({
  id, label, value, onChange, autoComplete, placeholder,
}: {
  id: string; label: string; value: string; onChange: (v: string) => void;
  autoComplete: string; placeholder?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <Field label={label}>
      <div className="relative">
        <input
          id={id}
          type={show ? "text" : "password"}
          className={`${inputCls} pr-16`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          placeholder={placeholder ?? "••••••••"}
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          aria-label={show ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          aria-pressed={show}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md px-2 py-1 text-xs font-medium text-slate-400 hover:bg-slate-800 hover:text-white focus:outline-none focus:ring-2 focus:ring-violet-500/50"
        >
          {show ? "Hide" : "Show"}
        </button>
      </div>
    </Field>
  );
}

function DemoCard({
  busy, onRun, error,
}: {
  busy: boolean; onRun: () => void; error: string;
}) {
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold text-white">Try the live demo — no GitHub needed</div>
        <Badge tone="emerald">Live demo</Badge>
      </div>
      <p className="mt-1 text-sm text-slate-400">
        Seeds the sample shop API, indexes it, and runs a real review of PR #42: a SQL injection
        visible only through the call graph.
      </p>
      {error && <div className="mt-3"><Alert tone="error">{error}</Alert></div>}
      <div className="mt-3">
        <Btn onClick={onRun} disabled={busy} variant="outline">
          {busy ? <><Spinner /> <span className="ml-2">Seeding demo…</span></> : "Run demo review"}
        </Btn>
      </div>
    </Card>
  );
}

export function Login({ onDone, notify, go }: AuthProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [ghError, setGhError] = useState("");
  const [busy, setBusy] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);
  const [ghBusy, setGhBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!isValidEmail(email)) { setError("Enter a valid email address."); return; }
    if (!password) { setError("Enter your password."); return; }
    setError("");
    setBusy(true);
    try {
      const r = await post("/api/auth/login", { email: email.trim(), password });
      setToken(r.token, remember);
      onDone();
    } catch (err: any) {
      setError(friendlyAuthError(err));
    } finally {
      setBusy(false);
    }
  };

  const githubSignIn = async () => {
    setGhError("");
    setGhBusy(true);
    try {
      const r = await get("/api/auth/github/login");
      window.location.href = r.authorize_url;
    } catch (err: any) {
      const msg = String(err?.message ?? "");
      if (msg.startsWith("501")) {
        setGhError("GitHub sign-in isn't configured on this deployment.");
      } else {
        setGhError(msg || "GitHub sign-in failed.");
      }
    } finally {
      setGhBusy(false);
    }
  };

  const demo = async () => {
    setError("");
    setDemoBusy(true);
    try {
      const r = await post("/api/demo/seed");
      setToken(r.token, remember);
      notify(`Demo seeded: PR #42 reviewed, gate ${r.gate_result} — ${r.findings.length} findings.`, "success");
      onDone();
    } catch (err: any) {
      setError(err?.message ?? "Demo seed failed.");
    } finally {
      setDemoBusy(false);
    }
  };

  return (
    <PublicShell onNavigate={(v, anchor) => go(v, anchor)}>
      <div className="mx-auto max-w-md pt-8 sm:pt-14">
        <h1 className="text-3xl font-bold text-white">
          Sign in to <span className="grad-text">CodeSentry</span>
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Agentic secure code review. No demo data is faked — every number on the dashboard comes
          from real reviews.
        </p>

        <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
          {error && <Alert tone="error">{error}</Alert>}
          <Field label="Email">
            <input
              id="login-email"
              type="email"
              className={inputCls}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="you@company.dev"
            />
          </Field>
          <PasswordField
            id="login-password"
            label="Password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
          />
          <div className="flex items-center justify-between gap-3">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="h-4 w-4 rounded border-slate-600 bg-[#070b16] accent-violet-600"
              />
              Remember me
            </label>
          </div>
          <Btn type="submit" disabled={busy || demoBusy} className="w-full justify-center">
            {busy ? <><Spinner /> <span className="ml-2">Signing in…</span></> : "Sign in"}
          </Btn>
        </form>

        <div className="mt-4 space-y-3">
          <button
            type="button"
            onClick={() => { setEmail(DEMO_EMAIL); setPassword(DEMO_PASSWORD); }}
            className="w-full rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:border-slate-600 hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500/50"
          >
            Use demo account — fills {DEMO_EMAIL} / demo1234
          </button>
          <Btn variant="outline" onClick={githubSignIn} disabled={ghBusy} className="w-full justify-center">
            {ghBusy ? <><Spinner /> <span className="ml-2">Redirecting to GitHub…</span></> : "Continue with GitHub"}
          </Btn>
          {ghError && <Alert tone="warning">{ghError}</Alert>}
        </div>

        <p className="mt-4 text-center text-sm text-slate-400">
          No account?{" "}
          <button
            type="button"
            onClick={() => go("register")}
            className="font-medium text-violet-300 hover:text-violet-200 focus:outline-none focus:ring-2 focus:ring-violet-500/50 rounded"
          >
            Create one
          </button>
        </p>

        <div className="mt-6">
          <DemoCard busy={demoBusy} onRun={demo} error="" />
        </div>

        <p className="mt-6 text-center text-xs text-slate-500">
          There is no password reset by email — if you forget your password, ask a workspace admin
          to reset it. GitHub sign-in works only when the deployment has GitHub OAuth configured.
        </p>
      </div>
    </PublicShell>
  );
}

export function Register({ onDone, notify, go }: AuthProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [terms, setTerms] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setError("Enter your full name."); return; }
    if (!isValidEmail(email)) { setError("Enter a valid email address."); return; }
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    if (password !== confirm) { setError("Passwords do not match."); return; }
    if (!terms) { setError("Please accept the terms in the Documentation to create an account."); return; }
    setError("");
    setBusy(true);
    try {
      const r = await post("/api/auth/register", { email: email.trim(), password, name: name.trim() });
      setToken(r.token);
      notify("Account created — welcome to CodeSentry.", "success");
      onDone();
    } catch (err: any) {
      setError(friendlyAuthError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <PublicShell onNavigate={(v, anchor) => go(v, anchor)}>
      <div className="mx-auto max-w-md pt-8 sm:pt-14">
        <h1 className="text-3xl font-bold text-white">
          Create your <span className="grad-text">CodeSentry</span> account
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Review pull requests with cited evidence and a CI gate. No role selection — new accounts
          start as regular users; an admin can promote you later.
        </p>

        <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
          {error && <Alert tone="error">{error}</Alert>}
          <Field label="Full name">
            <input
              id="register-name"
              type="text"
              className={inputCls}
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="name"
              placeholder="Ada Lovelace"
            />
          </Field>
          <Field label="Email">
            <input
              id="register-email"
              type="email"
              className={inputCls}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="you@company.dev"
            />
          </Field>
          <PasswordField
            id="register-password"
            label="Password (at least 8 characters)"
            value={password}
            onChange={setPassword}
            autoComplete="new-password"
          />
          <PasswordField
            id="register-confirm"
            label="Confirm password"
            value={confirm}
            onChange={setConfirm}
            autoComplete="new-password"
          />
          <label className="flex cursor-pointer items-start gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={terms}
              onChange={(e) => setTerms(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 rounded border-slate-600 bg-[#070b16] accent-violet-600"
            />
            <span>
              I agree to use CodeSentry responsibly — findings are advisory, not proof of safety —
              as described in the{" "}
              <button
                type="button"
                onClick={() => go("docs")}
                className="font-medium text-violet-300 hover:text-violet-200 focus:outline-none focus:ring-2 focus:ring-violet-500/50 rounded"
              >
                Documentation
              </button>
              .
            </span>
          </label>
          <Btn type="submit" disabled={busy} className="w-full justify-center">
            {busy ? <><Spinner /> <span className="ml-2">Creating account…</span></> : "Create account"}
          </Btn>
        </form>

        <p className="mt-4 text-center text-sm text-slate-400">
          Already have an account?{" "}
          <button
            type="button"
            onClick={() => go("login")}
            className="font-medium text-violet-300 hover:text-violet-200 focus:outline-none focus:ring-2 focus:ring-violet-500/50 rounded"
          >
            Sign in
          </button>
        </p>
      </div>
    </PublicShell>
  );
}
