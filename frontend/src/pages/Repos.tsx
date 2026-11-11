import { useEffect, useMemo, useState } from "react";
import { get, post, patch } from "../api/client";
import {
  Badge, Btn, Card, ConfirmDialog, DataTable, EmptyState, Field, PageHeader,
  SearchInput, Skeleton, Stat, Switch, inputCls, selectCls, type DataTableColumn,
} from "../components/ui";

export function Repos({ notify, go }: { notify: (m: string) => void; go: (page: string, arg?: any) => void }) {
  const [repos, setRepos] = useState<any[] | null>(null);
  const [fullName, setFullName] = useState("");
  const [query, setQuery] = useState("");
  const [err, setErr] = useState("");
  const [sortKey, setSortKey] = useState("full_name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const load = () => get("/api/repos").then(setRepos).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  const connect = async () => {
    try { await post("/api/repos", { full_name: fullName }); setFullName(""); notify("Repository connected."); load(); }
    catch (e: any) { notify(e.message); }
  };
  const onSort = (key: string) => {
    if (key === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  };
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = (repos ?? []).filter((r: any) =>
      !q || [r.full_name, (r.languages ?? []).join(" "), r.index_status].join(" ").toLowerCase().includes(q));
    const dir = sortDir === "asc" ? 1 : -1;
    filtered.sort((a, b) => {
      if (sortKey === "symbols") return ((a.symbols ?? 0) - (b.symbols ?? 0)) * dir;
      if (sortKey === "index_status") return String(a.index_status ?? "").localeCompare(String(b.index_status ?? "")) * dir;
      return String(a.full_name ?? "").localeCompare(String(b.full_name ?? "")) * dir;
    });
    return filtered;
  }, [repos, query, sortKey, sortDir]);

  if (!repos) {
    return (
      <div className="space-y-6">
        <PageHeader title="Repositories" subtitle="Connected repositories and their index status." />
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (err) return <EmptyState title="Could not load repositories" body={err} />;

  const columns: DataTableColumn[] = [
    { key: "full_name", label: "Repository", sortable: true },
    { key: "languages", label: "Languages" },
    { key: "index_status", label: "Index status", sortable: true },
    { key: "symbols", label: "Symbols", sortable: true },
    { key: "actions", label: "Actions" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Repositories" subtitle="Connected repositories and their index status." />
      <Card>
        <form
          onSubmit={(e) => { e.preventDefault(); if (fullName.trim()) connect(); }}
          className="flex flex-col gap-3 sm:flex-row"
        >
          <label className="sr-only" htmlFor="connect-repo">Repository full name (owner/repo)</label>
          <input id="connect-repo" className={inputCls} value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="owner/repo — e.g. demo/shop-api" />
          <Btn type="submit" disabled={!fullName.trim()} className="shrink-0">Connect</Btn>
        </form>
        <p className="mt-2 text-xs text-slate-500">Connecting records the repository and its settings. Indexing clones/fetches contents via the GitHub App when configured; the demo repo ships its files locally.</p>
      </Card>
      <div className="max-w-md">
        <SearchInput value={query} onChange={setQuery} placeholder="Search repositories…" />
      </div>
      {repos.length === 0 ? (
        <EmptyState title="No repositories yet" body="Connect one above, or run the demo review from the Overview page." />
      ) : (
        <DataTable
          columns={columns} rows={rows} sortKey={sortKey} sortDir={sortDir} onSort={onSort}
          empty="No repositories match your search."
          renderCell={(row, col) => {
            if (col.key === "full_name") return (
              <button type="button" onClick={() => go("repo", row.id)} className="font-mono font-semibold text-white hover:text-violet-300">
                {row.full_name}{row.is_demo ? " " : ""}{row.is_demo && <Badge tone="cyan">demo</Badge>}
              </button>
            );
            if (col.key === "languages") return <span className="text-slate-400">{row.languages?.join(", ") || "—"}</span>;
            if (col.key === "index_status") return <Badge tone={row.index_status === "indexed" ? "emerald" : "slate"}>{row.index_status}</Badge>;
            if (col.key === "symbols") return <span>{row.symbols ?? 0}</span>;
            if (col.key === "actions") return (
              <span className="flex gap-2">
                <Btn variant="outline" onClick={() => go("repo", row.id)}>Open</Btn>
                <Btn variant="ghost" onClick={() => go("prs", row.id)}>Pull requests</Btn>
              </span>
            );
            return String(row[col.key] ?? "—");
          }}
        />
      )}
    </div>
  );
}

export function RepoDetail({ repoId, notify, go }: { repoId: number; notify: (m: string) => void; go: (page: string, arg?: any) => void }) {
  const [repo, setRepo] = useState<any>(null);
  const [settings, setSettings] = useState<any>(null);
  const [prs, setPrs] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [purgeOpen, setPurgeOpen] = useState(false);
  const [sortKey, setSortKey] = useState("number");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const load = () => {
    get(`/api/repos/${repoId}`).then(setRepo).catch((e) => setErr(e.message));
    get(`/api/repos/${repoId}/settings`).then(setSettings).catch(() => {});
    get(`/api/repos/${repoId}/prs`).then(setPrs).catch(() => {});
  };
  useEffect(() => { load(); }, [repoId]);
  if (err) return <EmptyState title="Repository not found or not authorised" body={err} />;
  if (!repo) {
    return (
      <div className="space-y-6">
        <PageHeader title="Repository" subtitle="Loading repository details…" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  const save = async () => {
    try { await patch(`/api/repos/${repoId}/settings`, settings); notify("Settings saved."); }
    catch (e: any) { notify(e.message); }
  };
  const reindex = async () => {
    try { const r = await post(`/api/repos/${repoId}/reindex`, {}); notify(`Re-indexed: ${r.symbols} symbols (${r.parser}).`); load(); }
    catch (e: any) { notify(e.message); }
  };
  const purge = async () => {
    try { const r = await post(`/api/repos/${repoId}/purge?confirm=true`); notify(`Purged: ${r.symbols_deleted} symbols deleted, verified: ${r.verified}.`); setPurgeOpen(false); load(); }
    catch (e: any) { notify(e.message); }
  };
  const onSort = (key: string) => {
    if (key === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  };
  const sortedPrs = useMemo(() => {
    const rows = [...prs];
    const dir = sortDir === "asc" ? 1 : -1;
    rows.sort((a, b) => {
      if (sortKey === "number") return (a.number - b.number) * dir;
      if (sortKey === "gate") return String(a.run?.gate_result ?? "").localeCompare(String(b.run?.gate_result ?? "")) * dir;
      if (sortKey === "status") return String(a.run?.status ?? "").localeCompare(String(b.run?.status ?? "")) * dir;
      return String(a.title ?? "").localeCompare(String(b.title ?? "")) * dir;
    });
    return rows;
  }, [prs, sortKey, sortDir]);

  const prColumns: DataTableColumn[] = [
    { key: "number", label: "PR", sortable: true },
    { key: "title", label: "Title", sortable: true },
    { key: "author", label: "Author" },
    { key: "size_band", label: "Size" },
    { key: "gate", label: "Gate result", sortable: true },
    { key: "status", label: "Status", sortable: true },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={repo.full_name}
        subtitle={`Index: ${repo.index_status} · ${repo.symbols ?? 0} symbols · ${repo.languages?.join(", ") || "—"}`}
        actions={
          <>
            <Btn variant="outline" onClick={() => go("repos")}>← All repositories</Btn>
            <Btn onClick={reindex}>Full re-index</Btn>
            <Btn variant="outline" onClick={() => go("quality", repoId)}>Quality analytics</Btn>
            <Btn variant="danger" onClick={() => setPurgeOpen(true)}>Purge index…</Btn>
          </>
        }
      />
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Symbols indexed" value={repo.symbols ?? 0} />
        <Stat label="Index status" value={repo.index_status} sub={repo.head_sha ? `head ${String(repo.head_sha).slice(0, 12)}` : undefined} />
        <Stat label="Languages" value={repo.languages?.length ?? 0} sub={repo.languages?.join(", ") || "—"} />
      </div>

      {settings && (
        <Card>
          <div className="mb-4 font-semibold text-white">Repository settings</div>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Confidence threshold (0–1)">
              <input type="number" step="0.05" min="0" max="1" className={inputCls} value={settings.confidence_threshold}
                onChange={(e) => setSettings({ ...settings, confidence_threshold: parseFloat(e.target.value) })} />
            </Field>
            <Field label="Model provider">
              <select className={selectCls} value={settings.model_provider} onChange={(e) => setSettings({ ...settings, model_provider: e.target.value })}>
                <option value="deterministic">deterministic (rule engine, no key)</option>
                <option value="groq">Groq (hosted)</option>
                <option value="ollama">Ollama (local)</option>
              </select>
            </Field>
            <Field label="Token budget per symbol">
              <input type="number" className={inputCls} value={settings.token_budget_per_symbol}
                onChange={(e) => setSettings({ ...settings, token_budget_per_symbol: parseInt(e.target.value) })} />
            </Field>
            <Field label="Daily cost limit (USD)">
              <input type="number" step="0.5" className={inputCls} value={settings.daily_cost_limit_usd}
                onChange={(e) => setSettings({ ...settings, daily_cost_limit_usd: parseFloat(e.target.value) })} />
            </Field>
            <div className="flex items-center gap-3">
              <Switch checked={!!settings.gate_enabled} onChange={(v) => setSettings({ ...settings, gate_enabled: v })} label="CI merge gate enabled" />
            </div>
            <div className="flex items-center gap-3">
              <Switch checked={!!settings.training_opt_in} onChange={(v) => setSettings({ ...settings, training_opt_in: v })} label="Training opt-in" />
            </div>
            <div className="flex items-center gap-3">
              <Switch checked={!!settings.index_paused} onChange={(v) => setSettings({ ...settings, index_paused: v })} label="Pause indexing" />
            </div>
          </div>
          <p className="mt-3 text-xs text-slate-500">Training opt-in is OFF by default — feedback is only used for fine-tuning with explicit consent.</p>
          <div className="mt-4"><Btn onClick={save}>Save settings</Btn></div>
        </Card>
      )}

      <section aria-labelledby="repo-prs">
        <h2 id="repo-prs" className="mb-3 text-lg font-bold text-white">Pull requests</h2>
        <DataTable
          columns={prColumns} rows={sortedPrs} sortKey={sortKey} sortDir={sortDir} onSort={onSort}
          empty="No pull requests reviewed yet for this repository."
          renderCell={(row, col) => {
            if (col.key === "number") return (
              <button type="button" onClick={() => go("review", { repoId, number: row.number })} className="font-semibold text-white hover:text-violet-300">
                #{row.number}
              </button>
            );
            if (col.key === "title") return (
              <button type="button" onClick={() => go("review", { repoId, number: row.number })} className="text-left text-white hover:text-violet-300">
                {row.title}
              </button>
            );
            if (col.key === "gate") return row.run?.gate_result
              ? <Badge tone={row.run.gate_result === "fail" ? "red" : "emerald"}>gate: {row.run.gate_result}</Badge>
              : <Badge tone="slate">—</Badge>;
            if (col.key === "status") return <span className="text-slate-300">{row.run?.status || "not reviewed"}</span>;
            return String(row[col.key] ?? "—");
          }}
        />
      </section>

      <ConfirmDialog
        open={purgeOpen}
        onCancel={() => setPurgeOpen(false)}
        onConfirm={purge}
        title="Purge index?"
        body={`This deletes all indexed symbols for ${repo.full_name} and resets its index status. Reviews and findings are not deleted. This cannot be undone.`}
        confirmLabel="Purge index"
        danger
      />
    </div>
  );
}
