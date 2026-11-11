import { useEffect, useMemo, useState } from "react";
import { get, post } from "../api/client";
import {
  Badge, BarChart, Btn, Card, DataTable, DonutChart, EmptyState, PageHeader,
  Skeleton, Stat, type DataTableColumn,
} from "../components/ui";

const SEV_ORDER = ["critical", "high", "medium", "low"];
const SEV_COLORS: Record<string, string> = {
  critical: "#ef4444", high: "#f97316", medium: "#f59e0b", low: "#64748b",
};

function gateBadge(gate?: string | null) {
  if (!gate) return <Badge tone="slate">not reviewed</Badge>;
  return gate === "fail" ? <Badge tone="red">gate: fail</Badge> : <Badge tone="emerald">gate: {gate}</Badge>;
}

export function Overview({ notify, go }: { notify: (m: string) => void; go: (page: string, arg?: any) => void }) {
  const [data, setData] = useState<any>(null);
  const [repos, setRepos] = useState<any[]>([]);
  const [findings, setFindings] = useState<any[]>([]);
  const [prs, setPrs] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [seeding, setSeeding] = useState(false);
  const [sortKey, setSortKey] = useState("full_name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  useEffect(() => {
    Promise.all([get("/metrics"), get("/api/repos"), get("/api/findings")])
      .then(async ([m, r, f]) => {
        setData(m); setRepos(r); setFindings(f);
        const all: any[] = [];
        for (const repo of r) {
          const list = await get(`/api/repos/${repo.id}/prs`).catch(() => []);
          list.forEach((p: any) => all.push({ ...p, repo }));
        }
        all.sort((a, b) => (b.id ?? 0) - (a.id ?? 0));
        setPrs(all);
      })
      .catch((e) => setErr(e.message));
  }, []);

  const onSort = (key: string) => {
    if (key === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  };

  const sortedRepos = useMemo(() => {
    const rows = [...repos];
    const dir = sortDir === "asc" ? 1 : -1;
    rows.sort((a, b) => {
      if (sortKey === "symbols") return ((a.symbols ?? 0) - (b.symbols ?? 0)) * dir;
      if (sortKey === "index_status") return String(a.index_status ?? "").localeCompare(String(b.index_status ?? "")) * dir;
      return String(a.full_name ?? "").localeCompare(String(b.full_name ?? "")) * dir;
    });
    return rows;
  }, [repos, sortKey, sortDir]);

  const sevData = useMemo(
    () => SEV_ORDER.filter((s) => findings.some((f: any) => f.severity === s))
      .map((s) => ({ label: s, value: findings.filter((f: any) => f.severity === s).length, color: SEV_COLORS[s] })),
    [findings],
  );
  const agentData = useMemo(() => {
    const counts: Record<string, number> = {};
    findings.forEach((f: any) => { counts[f.source] = (counts[f.source] ?? 0) + 1; });
    return Object.entries(counts).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
  }, [findings]);

  if (err) return <EmptyState title="Could not load the overview" body={err} />;
  if (!data) {
    return (
      <div className="space-y-6">
        <PageHeader title="Overview" subtitle="Review activity and risk across your repositories — computed from persisted reviews, never hardcoded." />
        <div className="grid gap-4 md:grid-cols-4"><Skeleton /><Skeleton /><Skeleton /><Skeleton /></div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  const demoSeed = async () => {
    setSeeding(true);
    try { await post("/api/demo/seed"); notify("Demo seeded — reloading."); location.reload(); }
    catch (e: any) { notify(e.message); } finally { setSeeding(false); }
  };

  const repoColumns: DataTableColumn[] = [
    { key: "full_name", label: "Repository", sortable: true },
    { key: "index_status", label: "Index status", sortable: true },
    { key: "symbols", label: "Symbols", sortable: true },
    { key: "languages", label: "Languages" },
    { key: "actions", label: "Actions" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        subtitle="Review activity and risk across your repositories — computed from persisted reviews, never hardcoded."
        actions={<Btn variant="outline" onClick={() => go("repos")}>Manage repositories</Btn>}
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Repositories" value={data.repos} />
        <Stat label="Reviews run" value={data.reviews} />
        <Stat label="Findings posted" value={data.findings_posted} sub={`of ${data.findings} total (incl. suppressed)`} />
        <Stat label="Feedback events" value={data.feedback_events} />
      </div>

      {repos.length === 0 ? (
        <EmptyState
          title="No repositories connected yet"
          body="Connect a repository, or run the demo review to see CodeSentry work end to end on the sample shop API."
          action={<Btn onClick={demoSeed} disabled={seeding}>{seeding ? "Seeding demo…" : "Run demo review"}</Btn>}
        />
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <div className="mb-3 font-semibold text-white">Findings by severity</div>
              <DonutChart data={sevData} />
            </Card>
            <Card>
              <div className="mb-3 font-semibold text-white">Findings by agent</div>
              {agentData.length === 0
                ? <p className="text-sm text-slate-400">No findings yet.</p>
                : <BarChart data={agentData} />}
            </Card>
          </div>

          <section aria-labelledby="recent-prs">
            <div className="mb-3 flex items-center justify-between">
              <h2 id="recent-prs" className="text-lg font-bold text-white">Recent pull requests</h2>
              <Btn variant="ghost" onClick={() => go("prs")}>View all</Btn>
            </div>
            {prs.length === 0 ? (
              <EmptyState title="No pull requests reviewed yet" body="Open a PR on a connected repository, or run the demo review — PR #42 on demo/shop-api is the seeded example." />
            ) : (
              <div className="space-y-2">
                {prs.slice(0, 5).map((p: any) => (
                  <button key={`${p.repo.id}-${p.number}`} onClick={() => go("review", { repoId: p.repo.id, number: p.number })}
                    className="flex w-full flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-800 bg-[#0b1226] px-4 py-3 text-left hover:bg-slate-800/50">
                    <span className="min-w-0">
                      <span className="font-mono text-xs text-slate-400">{p.repo.full_name}</span>
                      <span className="ml-2 font-semibold text-white">#{p.number} {p.title}</span>
                      <span className="ml-2 text-xs text-slate-400">{p.size_band} · {p.author}</span>
                    </span>
                    <span className="flex items-center gap-2">{gateBadge(p.run?.gate_result)}
                      <span className="text-xs text-slate-400">{p.run ? `${p.run.status} · ${p.run.latency_ms} ms` : "not reviewed"}</span></span>
                  </button>
                ))}
              </div>
            )}
          </section>

          <section aria-labelledby="repo-table">
            <h2 id="repo-table" className="mb-3 text-lg font-bold text-white">Repositories</h2>
            <DataTable
              columns={repoColumns} rows={sortedRepos} sortKey={sortKey} sortDir={sortDir} onSort={onSort}
              empty="No repositories yet."
              renderCell={(row, col) => {
                if (col.key === "full_name") return (
                  <button type="button" onClick={() => go("repo", row.id)} className="font-mono font-semibold text-white hover:text-violet-300">
                    {row.full_name}{row.is_demo ? " " : ""}{row.is_demo && <Badge tone="cyan">demo</Badge>}
                  </button>
                );
                if (col.key === "index_status") return <Badge tone={row.index_status === "indexed" ? "emerald" : "slate"}>{row.index_status}</Badge>;
                if (col.key === "symbols") return <span>{row.symbols ?? 0}</span>;
                if (col.key === "languages") return <span className="text-slate-400">{row.languages?.join(", ") || "—"}</span>;
                if (col.key === "actions") return (
                  <span className="flex gap-2">
                    <Btn variant="outline" onClick={() => go("repo", row.id)}>Open</Btn>
                    <Btn variant="ghost" onClick={() => go("prs", row.id)}>Pull requests</Btn>
                  </span>
                );
                return String(row[col.key] ?? "—");
              }}
            />
          </section>
        </>
      )}
    </div>
  );
}
