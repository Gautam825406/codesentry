import { useState, type ReactNode } from "react";
import { Avatar, Btn, Dropdown, SearchInput } from "./ui";

export const HONEST_LINE = "No auto-merge. No complete-security-coverage claim. Metrics come from persisted data only.";

function Logo({ onClick }: { onClick?: () => void }) {
  const inner = (
    <>
      <span aria-hidden="true" className="text-lg leading-none">🛡️</span>
      <span className="text-lg font-bold text-white">Code<span className="grad-text">Sentry</span></span>
    </>
  );
  return onClick ? (
    <button type="button" onClick={onClick} className="flex items-center gap-2" aria-label="CodeSentry home">{inner}</button>
  ) : (
    <span className="flex items-center gap-2">{inner}</span>
  );
}

/* ------------------------------------------------------------------ */
/* Toasts (rendered by App.tsx)                                        */
/* ------------------------------------------------------------------ */

export type ToastKind = "success" | "error" | "info";
export type ToastItem = { id: number; message: string; kind: ToastKind };

const TOAST_STYLES: Record<ToastKind, string> = {
  success: "border-emerald-500/40 bg-slate-900",
  error: "border-red-500/40 bg-slate-900",
  info: "border-slate-700 bg-slate-900",
};

export function Toasts({ items }: { items: ToastItem[] }) {
  if (items.length === 0) return null;
  return (
    <div className="fixed bottom-4 right-4 z-[60] flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2" aria-live="polite">
      {items.map((t) => (
        <div key={t.id} role="status" className={`rounded-lg border px-4 py-3 text-sm text-white shadow-xl ${TOAST_STYLES[t.kind]}`}>
          {t.message}
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* PublicShell — logged-out pages                                      */
/* ------------------------------------------------------------------ */

export type PublicView = "landing" | "login" | "register" | "docs";
export type PublicAnchor = "features" | "how" | "faq";

export function PublicShell({ children, onNavigate }: { children: ReactNode; onNavigate: (view: PublicView, anchor?: PublicAnchor) => void }) {
  const anchorLink = (label: string, anchor: PublicAnchor) => (
    <button key={label} type="button" onClick={() => onNavigate("landing", anchor)} className="block py-1 text-sm text-slate-400 hover:text-white">{label}</button>
  );
  const docLink = (label: string) => (
    <button key={label} type="button" onClick={() => onNavigate("docs")} className="block py-1 text-sm text-slate-400 hover:text-white">{label}</button>
  );
  return (
    <div className="flex min-h-screen flex-col bg-[#070b16]">
      <header className="sticky top-0 z-40 border-b border-slate-800 bg-[#070b16]/95">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Logo onClick={() => onNavigate("landing")} />
          <nav aria-label="Product" className="hidden items-center gap-1 md:flex">
            {(["Features", "How it works", "FAQ"] as const).map((label) => (
              <button key={label} type="button"
                onClick={() => onNavigate("landing", label === "Features" ? "features" : label === "How it works" ? "how" : "faq")}
                className="rounded-lg px-3 py-1.5 text-sm text-slate-400 hover:bg-slate-800 hover:text-white">{label}</button>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Btn variant="ghost" onClick={() => onNavigate("login")}>Sign in</Btn>
            <Btn onClick={() => onNavigate("register")}>Get started</Btn>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">{children}</main>
      <footer className="border-t border-slate-800">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:grid-cols-4 sm:px-6">
          <div>
            <Logo />
            <p className="mt-3 text-sm text-slate-400">Agentic secure code review — AST-aware, cited findings, CI gating.</p>
          </div>
          <nav aria-label="Product">
            <div className="text-sm font-semibold text-white">Product</div>
            <div className="mt-2">
              {anchorLink("Features", "features")}
              {anchorLink("How it works", "how")}
              {anchorLink("FAQ", "faq")}
              {docLink("Documentation")}
            </div>
          </nav>
          <nav aria-label="Company">
            <div className="text-sm font-semibold text-white">Company</div>
            <div className="mt-2">{["About", "Security"].map(docLink)}</div>
          </nav>
          <nav aria-label="Resources">
            <div className="text-sm font-semibold text-white">Resources</div>
            <div className="mt-2">{["Documentation", "API reference"].map(docLink)}</div>
            <button type="button" onClick={() => onNavigate("login")} className="block py-1 text-sm text-slate-400 hover:text-white">Sign in</button>
          </nav>
        </div>
        <div className="border-t border-slate-800">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs text-slate-500 sm:px-6">
            <span>CodeSentry — AST-aware review, cited findings, CI gating, learning from feedback.</span>
            <span>{HONEST_LINE}</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* AppShell — authenticated desktop-website layout                     */
/* ------------------------------------------------------------------ */

const PAGE_TITLES: Record<string, string> = {
  overview: "Overview", repos: "Repositories", repo: "Repository", prs: "Pull Requests",
  review: "Review", findings: "Findings", security: "Security Center", quality: "Quality Analytics",
  agents: "AI Agents", finetuning: "Fine-Tuning", audit: "Audit Logs", settings: "Settings", docs: "Documentation",
};

function NavIcon({ name, className = "h-4 w-4 shrink-0" }: { name: string; className?: string }) {
  const paths: Record<string, ReactNode> = {
    overview: (<><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>),
    repos: (<><path d="M4 7a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7z" /><path d="M4 7h16" /></>),
    prs: (<><circle cx="6" cy="6" r="2.5" /><circle cx="6" cy="18" r="2.5" /><circle cx="18" cy="8" r="2.5" /><path d="M6 8.5v7" /><path d="M18 10.5c0 3-4.5 3-7 4.5" /></>),
    findings: (<><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z" /><path d="M12 8v4" /><path d="M12 15.5h.01" /></>),
    security: (<><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z" /><path d="M9 12l2 2 4-4" /></>),
    quality: (<><path d="M5 20v-8" /><path d="M11 20V5" /><path d="M17 20v-5" /><path d="M3 20h18" /></>),
    agents: (<><rect x="6" y="6" width="12" height="12" rx="2" /><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" /></>),
    finetuning: (<><path d="M4 8h9M19 8h1M4 16h3M13 16h7" /><circle cx="16" cy="8" r="2" /><circle cx="10" cy="16" r="2" /></>),
    audit: (<><path d="M8 6h13M8 12h13M8 18h13" /><path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01" /></>),
    settings: (<><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1" /></>),
    docs: (<><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5v14z" /><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5" /></>),
  };
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
      className={className} aria-hidden="true">{paths[name]}</svg>
  );
}

const NAV_SECTIONS: { label: string; items: { id: string; label: string }[] }[] = [
  { label: "Workspace", items: [
    { id: "overview", label: "Overview" }, { id: "repos", label: "Repositories" },
    { id: "prs", label: "Pull Requests" }, { id: "findings", label: "Findings" },
  ] },
  { label: "Insights", items: [
    { id: "security", label: "Security Center" }, { id: "quality", label: "Quality Analytics" },
    { id: "agents", label: "AI Agents" }, { id: "finetuning", label: "Fine-Tuning" },
  ] },
  { label: "Admin", items: [
    { id: "audit", label: "Audit Logs" }, { id: "settings", label: "Settings" },
  ] },
  { label: "Help", items: [{ id: "docs", label: "Documentation" }] },
];

function activeNavId(page: string): string {
  if (page === "repo") return "repos";
  if (page === "review") return "prs";
  return page;
}

export function AppShell({ me, page, go, onSignOut, children }: {
  me: any; page: string; go: (page: string, arg?: any) => void; onSignOut: () => void; children: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem("cs_sidebar_collapsed") === "1"; } catch { return false; }
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const [search, setSearch] = useState("");
  const activeId = activeNavId(page);
  const displayName = me?.name || me?.email?.split("@")[0] || "Account";
  const role = me?.role || "member";

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      const next = !c;
      try { localStorage.setItem("cs_sidebar_collapsed", next ? "1" : "0"); } catch { /* storage unavailable */ }
      return next;
    });
  };

  const submitSearch = () => {
    const q = search.trim();
    if (q) go("findings", { q });
  };

  const sidebarContent = (forDrawer: boolean) => (
    <>
      <div className={`flex items-center border-b border-slate-800 px-4 py-3 ${collapsed && !forDrawer ? "justify-center" : "justify-between"}`}>
        {collapsed && !forDrawer ? (
          <span className="text-lg leading-none" aria-hidden="true">🛡️</span>
        ) : (
          <Logo onClick={() => go("overview")} />
        )}
        {forDrawer && (
          <button type="button" onClick={() => setMobileOpen(false)} aria-label="Close navigation"
            className="rounded-lg px-2 py-1 text-lg leading-none text-slate-400 hover:bg-slate-800 hover:text-white">&times;</button>
        )}
      </div>
      <nav aria-label="Primary" className="scrollbar-thin flex-1 overflow-y-auto px-2 py-3">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="mb-4">
            {(!collapsed || forDrawer) && (
              <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">{section.label}</div>
            )}
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const active = activeId === item.id;
                return (
                  <li key={item.id}>
                    <button type="button" onClick={() => { go(item.id); setMobileOpen(false); }}
                      aria-current={active ? "page" : undefined}
                      aria-label={collapsed && !forDrawer ? item.label : undefined}
                      title={collapsed && !forDrawer ? item.label : undefined}
                      className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm ${
                        collapsed && !forDrawer ? "justify-center px-0" : ""
                      } ${active ? "bg-violet-600/15 font-medium text-violet-200" : "text-slate-400 hover:bg-slate-800/70 hover:text-white"}`}>
                      <NavIcon name={item.id} />
                      {(!collapsed || forDrawer) && <span className="truncate">{item.label}</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-t border-slate-800 p-2">
        <button type="button" onClick={toggleCollapsed} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={`hidden w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-400 hover:bg-slate-800/70 hover:text-white lg:flex ${collapsed ? "justify-center px-0" : ""}`}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            className={`h-4 w-4 shrink-0 transition-transform ${collapsed ? "rotate-180" : ""}`} aria-hidden="true">
            <path d="M15 18l-6-6 6-6" />
          </svg>
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-[#070b16] lg:flex">
      {/* Desktop sidebar */}
      <aside aria-label="Sidebar"
        className={`sticky top-0 hidden h-screen shrink-0 flex-col border-r border-slate-800 bg-[#0b1226] lg:flex ${collapsed ? "w-[68px]" : "w-64"}`}>
        {sidebarContent(false)}
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/70" onClick={() => setMobileOpen(false)} aria-hidden="true" />
          <aside aria-label="Sidebar" className="absolute left-0 top-0 flex h-full w-72 flex-col border-r border-slate-800 bg-[#0b1226]">
            {sidebarContent(true)}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-slate-800 bg-[#070b16]/95">
          <div className="flex items-center gap-3 px-4 py-3 sm:px-6">
            <button type="button" onClick={() => setMobileOpen(true)} aria-label="Open navigation"
              className="rounded-lg p-2 text-slate-300 hover:bg-slate-800 lg:hidden">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
                className="h-5 w-5" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg>
            </button>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-white">{PAGE_TITLES[page] ?? "CodeSentry"}</div>
              <div className="hidden truncate text-xs text-slate-500 sm:block">CodeSentry</div>
            </div>
            <div className="hidden w-64 md:block lg:w-80">
              <SearchInput value={search} onChange={setSearch} onSubmit={submitSearch} placeholder="Search findings…" />
            </div>
            <Dropdown
              trigger={
                <button type="button" aria-label="Account menu" className="flex items-center gap-2 rounded-lg px-2 py-1 hover:bg-slate-800">
                  <Avatar name={displayName} />
                  <span className="hidden text-left sm:block">
                    <span className="block max-w-[160px] truncate text-sm font-medium text-white">{displayName}</span>
                    <span className="block text-xs capitalize text-slate-500">{role}</span>
                  </span>
                </button>
              }>
              <div className="border-b border-slate-800 px-3 py-2">
                <div className="truncate text-sm font-medium text-white">{displayName}</div>
                <div className="truncate text-xs text-slate-400">{me?.email ?? ""}</div>
                <div className="mt-0.5 text-xs capitalize text-slate-500">{role}</div>
              </div>
              {[
                { label: "Settings", onClick: () => go("settings") },
                { label: "Documentation", onClick: () => go("docs") },
              ].map((item) => (
                <button key={item.label} type="button" role="menuitem" onClick={item.onClick}
                  className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-300 hover:bg-slate-800 hover:text-white">
                  {item.label}
                </button>
              ))}
              <button type="button" role="menuitem" onClick={onSignOut}
                className="block w-full rounded-lg px-3 py-2 text-left text-sm text-red-300 hover:bg-slate-800">
                Sign out
              </button>
            </Dropdown>
          </div>
          <div className="px-4 pb-3 md:hidden">
            <SearchInput value={search} onChange={setSearch} onSubmit={submitSearch} placeholder="Search findings…" />
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:py-8">{children}</main>

        <footer className="border-t border-slate-800">
          <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-5 text-xs text-slate-500 sm:px-6">
            <span>CodeSentry — AST-aware review, cited findings, CI gating, learning from feedback.</span>
            <span>{HONEST_LINE}</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
