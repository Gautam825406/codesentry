import { useEffect } from "react";
import { Badge, Btn, Card, SeverityBadge, Stat } from "../components/ui";
import { HONEST_LINE, PublicShell } from "../components/layout";

const FEATURES: { title: string; body: string }[] = [
  {
    title: "AST indexing & call graph",
    body: "Every repository is indexed by structure — tree-sitter symbols plus a call graph — so review retrieves the code that actually matters, not just the diff.",
  },
  {
    title: "3-agent review",
    body: "Three LangGraph agents review each pull request: planning what to retrieve, reviewing with evidence, and validating the suggested patch.",
  },
  {
    title: "Cited findings, CWE & OWASP",
    body: "Findings cite the exact file, lines, and evidence. Severities map to CWE and OWASP references, so a finding is checkable, not a black-box verdict.",
  },
  {
    title: "Validated patches",
    body: "Every suggested patch is validated before it is shown. If a patch does not apply cleanly, it is not presented as a fix.",
  },
  {
    title: "CI merge gate",
    body: "High-severity findings block the CI check until they are fixed or dismissed by an authorised reviewer. Humans decide — nothing auto-merges.",
  },
  {
    title: "Feedback → fine-tuning",
    body: "Reviewer feedback (accept, fixed, wrong, not worth fixing) is recorded and feeds fine-tuning data, so the reviewer gets sharper over time.",
  },
];

const STEPS: { n: string; title: string; body: string }[] = [
  {
    n: "1",
    title: "Index the repository",
    body: "Connect a repo and CodeSentry parses it into symbols and a call graph — functions, callers, and the paths between them.",
  },
  {
    n: "2",
    title: "Open a pull request",
    body: "A GitHub webhook delivers the PR diff. The planner agent retrieves the relevant symbols and call-graph context around the change.",
  },
  {
    n: "3",
    title: "Agents review with evidence",
    body: "Three agents review the change, keep only confidence-filtered findings, and attach the evidence, CWE mapping, and a validated patch to each one.",
  },
  {
    n: "4",
    title: "Gate the merge",
    body: "The CI check passes or fails on the findings. High-severity findings block the merge until fixed or dismissed by an authorised reviewer.",
  },
];

const FAQS: { q: string; a: string }[] = [
  {
    q: "Is absence of findings proof of safety?",
    a: "No. CodeSentry finds what its agents can evidence from the indexed code and the diff. A clean review means no findings were found — it is not a guarantee that the code is secure.",
  },
  {
    q: "Does it auto-merge or auto-apply patches?",
    a: "No. Patches are suggestions, validated for applicability, and a human applies them. High-severity findings block the CI gate, but merging is always a human decision.",
  },
  {
    q: "Which languages are supported?",
    a: "Python and JavaScript/TypeScript in v1. Other languages are not indexed or reviewed yet.",
  },
  {
    q: "Do I need to connect GitHub to try it?",
    a: "No. Run the live demo from the sign-in page — it seeds a sample shop API and reviews PR #42 with no GitHub connection. Connecting a real repository uses the GitHub App.",
  },
  {
    q: "Is my code used for training?",
    a: "No training on private code without explicit opt-in, which is off by default. Reviewer feedback you explicitly record can feed fine-tuning data.",
  },
  {
    q: "How do I know a finding is real?",
    a: "Every finding carries its evidence: file, lines, the retrieved call-graph context, a confidence score, and a CWE/OWASP reference. If the evidence does not support it, mark it wrong — that feedback improves future reviews.",
  },
];

export function Landing({ go, scrollTo, scrollNonce }: {
  go: (view: string, anchor?: string) => void;
  scrollTo?: string;
  scrollNonce?: number;
}) {
  // Scroll to a landing section (features / how / faq) when the navbar or
  // footer navigates here with an anchor; re-runs when the nonce changes so
  // clicking the same link twice still scrolls.
  useEffect(() => {
    if (!scrollTo) return;
    const el = document.getElementById(scrollTo);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [scrollTo, scrollNonce]);
  return (
    <PublicShell onNavigate={(v, anchor) => go(v, anchor)}>
      {/* Hero */}
      <section aria-labelledby="hero-heading" className="mx-auto max-w-4xl pt-10 text-center sm:pt-16">
        <Badge tone="violet" className="mb-4">Agentic secure code review</Badge>
        <h1 id="hero-heading" className="text-4xl font-bold leading-tight text-white sm:text-5xl">
          Code review that <span className="grad-text">cites its evidence</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-base text-slate-400 sm:text-lg">
          CodeSentry indexes your code as an AST and call graph, reviews pull requests with three
          agents, and posts only confidence-filtered findings — each with its evidence, CWE
          mapping, and a validated patch — behind a CI merge gate.
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <Btn onClick={() => go("login")}>Run the live demo</Btn>
          <Btn variant="outline" onClick={() => go("docs")}>See how it works</Btn>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          No GitHub needed for the demo — it seeds a sample shop API and reviews PR #42.
        </p>
      </section>

      {/* Product preview — real demo finding */}
      <section aria-labelledby="preview-heading" className="mx-auto mt-14 max-w-4xl">
        <h2 id="preview-heading" className="text-center text-xl font-bold text-white">
          What a review actually looks like
        </h2>
        <Card className="mt-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Badge tone="emerald">Live demo finding — PR #42</Badge>
            <Badge tone="red">Gate: fail</Badge>
          </div>
          <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge severity="high" />
                <span className="font-semibold text-white">SQL injection via string-formatted query</span>
              </div>
              <p className="mt-2 text-sm text-slate-400">
                User input from <code className="text-slate-200">app/orders.py:6</code> reaches a
                SQL query built by string formatting. The sink is only visible through the call
                graph — the diff alone does not show it.
              </p>
            </div>
          </div>
          <dl className="mt-4 grid gap-3 border-t border-slate-800 pt-4 text-sm sm:grid-cols-4">
            <div><dt className="text-xs uppercase tracking-wide text-slate-500">File</dt><dd className="mt-0.5 text-slate-200">app/orders.py:6</dd></div>
            <div><dt className="text-xs uppercase tracking-wide text-slate-500">CWE</dt><dd className="mt-0.5 text-slate-200">CWE-89 — SQL Injection</dd></div>
            <div><dt className="text-xs uppercase tracking-wide text-slate-500">Confidence</dt><dd className="mt-0.5 text-slate-200">0.94</dd></div>
            <div><dt className="text-xs uppercase tracking-wide text-slate-500">Patch</dt><dd className="mt-0.5 text-slate-200">Parameterised query (validated)</dd></div>
          </dl>
          <p className="mt-4 text-xs text-slate-500">
            This is the real finding from the live demo review of PR #42 — not a mock-up.
          </p>
        </Card>
      </section>

      {/* Features */}
      <section id="features" aria-labelledby="features-heading" className="mt-16">
        <h2 id="features-heading" className="text-center text-2xl font-bold text-white">Built for review you can check</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <Card key={f.title}>
              <div className="font-semibold text-white">{f.title}</div>
              <p className="mt-2 text-sm text-slate-400">{f.body}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" aria-labelledby="how-heading" className="mt-16">
        <h2 id="how-heading" className="text-center text-2xl font-bold text-white">How it works</h2>
        <ol className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s) => (
            <li key={s.n}>
              <Card className="h-full">
                <span aria-hidden="true" className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-violet-600 text-sm font-bold text-white">{s.n}</span>
                <div className="mt-3 font-semibold text-white">{s.title}</div>
                <p className="mt-1 text-sm text-slate-400">{s.body}</p>
              </Card>
            </li>
          ))}
        </ol>
      </section>

      {/* Stats / trust band — verified figures only */}
      <section aria-labelledby="stats-heading" className="mt-16">
        <h2 id="stats-heading" className="text-center text-2xl font-bold text-white">Measured, not claimed</h2>
        <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-slate-400">
          Every number below comes from a real, live index or evaluation run. {HONEST_LINE}
        </p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Symbols indexed" value="321" sub="codesentry repo (live)" />
          <Stat label="Symbols indexed" value="339" sub="querypilot repo (live)" />
          <Stat label="Eval precision / recall" value="1.00 / 1.00" sub="N=8 labelled PRs — small sample" />
          <Stat label="Findings on demo PR #42" value="2" sub="1 HIGH (CWE-89)" />
        </div>
      </section>

      {/* Testimonials — clearly placeholder */}
      <section aria-labelledby="testimonials-heading" className="mt-16">
        <h2 id="testimonials-heading" className="text-center text-2xl font-bold text-white">
          What reviewers say <span className="text-base font-medium text-slate-400">— placeholder</span>
        </h2>
        <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-slate-400">
          Placeholder section: no reviewer quotes have been collected yet. These quotes are
          stand-ins for layout only and are not from real people.
        </p>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <Card>
            <p className="text-sm text-slate-300">
              “Placeholder quote — the call-graph evidence is what made us trust the findings
              enough to block merges on them.”
            </p>
            <p className="mt-3 text-xs text-slate-500">— Placeholder reviewer, role TBD</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-300">
              “Placeholder quote — validated patches mean reviewers spend time judging the fix,
              not checking whether it applies.”
            </p>
            <p className="mt-3 text-xs text-slate-500">— Placeholder reviewer, role TBD</p>
          </Card>
        </div>
      </section>

      {/* Free & open source */}
      <section aria-labelledby="oss-heading" className="mt-16">
        <Card className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 id="oss-heading" className="text-lg font-bold text-white">Free &amp; open source</h2>
            <p className="mt-1 text-sm text-slate-400">
              CodeSentry is open source. Read the code, run it yourself, or contribute.
            </p>
          </div>
          <a
            href="https://github.com/Gautam825406/codesentry"
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50"
          >
            View on GitHub
          </a>
        </Card>
      </section>

      {/* FAQ */}
      <section id="faq" aria-labelledby="faq-heading" className="mx-auto mt-16 max-w-3xl">
        <h2 id="faq-heading" className="text-center text-2xl font-bold text-white">Frequently asked questions</h2>
        <div className="mt-6 space-y-3">
          {FAQS.map((f) => (
            <details key={f.q} className="rounded-xl border border-slate-800 bg-[#0b1226] px-5 py-4">
              <summary className="cursor-pointer text-sm font-semibold text-white focus:outline-none focus:ring-2 focus:ring-violet-500/50 rounded">
                {f.q}
              </summary>
              <p className="mt-2 text-sm text-slate-400">{f.a}</p>
            </details>
          ))}
        </div>
        <div className="mt-10 text-center">
          <Btn onClick={() => go("login")}>Run the live demo</Btn>
          <p className="mt-3 text-xs text-slate-500">{HONEST_LINE}</p>
        </div>
      </section>
    </PublicShell>
  );
}
