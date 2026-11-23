import { Component, useEffect, useRef, useState, type ReactNode } from "react";

/* ------------------------------------------------------------------ */
/* Panels                                                              */
/* ------------------------------------------------------------------ */

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-lg border border-[#e4e7ec] bg-white p-5 ${className}`}>{children}</div>;
}

export function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <Card>
      <div className="text-xs font-medium uppercase tracking-wide text-[#667085]">{label}</div>
      <div className="mt-1 text-2xl font-bold text-[#101828]">{value}</div>
      {sub && <div className="mt-1 text-xs text-[#667085]">{sub}</div>}
    </Card>
  );
}

const SEV: Record<string, string> = {
  critical: "bg-[#fef3f2] text-[#b42318] border-[#fecdca]",
  high: "bg-[#fffaeb] text-[#b54708] border-[#fedf89]",
  medium: "bg-[#fffaeb] text-[#dc6803] border-[#fedf89]",
  low: "bg-[#f2f4f7] text-[#475467] border-[#e4e7ec]",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold ${SEV[severity] || SEV.low}`}>{severity.toUpperCase()}</span>;
}

export function Skeleton({ className = "h-24" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-[#e4e7ec] ${className}`} aria-hidden="true" />;
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <Card className="py-10 text-center">
      <div className="text-lg font-semibold text-[#101828]">{title}</div>
      <p className="mx-auto mt-2 max-w-md text-sm text-[#667085]">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Buttons, fields, inputs                                             */
/* ------------------------------------------------------------------ */

export function Btn({ children, onClick, variant = "primary", disabled, type = "button", className = "" }: {
  children: ReactNode; onClick?: () => void; variant?: "primary" | "ghost" | "danger" | "outline";
  disabled?: boolean; type?: "button" | "submit"; className?: string;
}) {
  const styles = {
    primary: "bg-[#182230] text-white hover:bg-[#0b1526]",
    ghost: "bg-[#f2f4f7] text-[#344054] hover:bg-[#d0d5dd]",
    danger: "bg-[#b42318] text-white hover:bg-[#912018]",
    outline: "border border-[#d0d5dd] text-[#344054] hover:border-[#d0d5dd] hover:bg-[#f2f4f7]",
  }[variant];
  return (
    <button type={type} disabled={disabled} onClick={onClick}
      className={`rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}>
      {children}
    </button>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block text-sm"><span className="font-medium text-[#344054]">{label}</span><div className="mt-1">{children}</div></label>;
}

export const inputCls = "w-full rounded-lg border border-[#d0d5dd] bg-white px-3 py-2 text-sm text-[#101828] placeholder:text-[#98a2b3] focus:outline-none focus:border-[#175cd3] focus:ring-2 focus:ring-[#175cd3]/20 disabled:opacity-50";

/** Native <select> styling — identical to inputCls. */
export const selectCls = inputCls;

/* ------------------------------------------------------------------ */
/* Badge, spinner, alert                                               */
/* ------------------------------------------------------------------ */

export type BadgeTone = "slate" | "violet" | "cyan" | "emerald" | "amber" | "red";

const BADGE_TONES: Record<BadgeTone, string> = {
  slate: "border-[#d0d5dd] bg-[#f2f4f7] text-[#344054]",
  violet: "border-[#b2ddff] bg-[#eff8ff] text-[#175cd3]",
  cyan: "border-[#b2ddff] bg-[#eff8ff] text-[#175cd3]",
  emerald: "border-[#a6f4c5] bg-[#ecfdf3] text-[#067647]",
  amber: "border-[#fedf89] bg-[#fffaeb] text-[#b54708]",
  red: "border-[#fecdca] bg-[#fef3f2] text-[#b42318]",
};

export function Badge({ children, tone = "slate", className = "" }: { children: ReactNode; tone?: BadgeTone; className?: string }) {
  return <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${BADGE_TONES[tone]} ${className}`}>{children}</span>;
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return <span role="status" aria-label="Loading" className={`inline-block animate-spin rounded-full border-2 border-[#d0d5dd] border-t-[#182230] ${className}`} />;
}

const ALERT_TONES = {
  error: "border-[#fecdca] bg-[#fef3f2] text-[#b42318]",
  success: "border-[#a6f4c5] bg-[#ecfdf3] text-[#067647]",
  info: "border-[#b2ddff] bg-[#eff8ff] text-[#175cd3]",
  warning: "border-[#fedf89] bg-[#fffaeb] text-[#b54708]",
} as const;

export function Alert({ tone, children }: { tone: "error" | "success" | "info" | "warning"; children: ReactNode }) {
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`rounded-lg border px-4 py-3 text-sm ${ALERT_TONES[tone]}`}>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Modal / ConfirmDialog                                               */
/* ------------------------------------------------------------------ */

export function Modal({ open, onClose, title, children, footer }: {
  open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} aria-hidden="true" />
      <div ref={panelRef} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}
        className="relative w-full max-w-lg rounded-lg border border-[#d0d5dd] bg-white p-6 shadow-xl focus:outline-none">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold text-[#101828]">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close dialog"
            className="rounded-lg px-2 py-1 text-lg leading-none text-[#667085] hover:bg-[#f2f4f7] hover:text-[#101828]">&times;</button>
        </div>
        <div className="mt-3 text-sm text-[#344054]">{children}</div>
        {footer && <div className="mt-5 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}

export function ConfirmDialog({ open, onConfirm, onCancel, title, body, confirmLabel = "Confirm", danger }: {
  open: boolean; onConfirm: () => void; onCancel: () => void; title: string; body: string;
  confirmLabel?: string; danger?: boolean;
}) {
  return (
    <Modal open={open} onClose={onCancel} title={title}
      footer={
        <>
          <Btn variant="ghost" onClick={onCancel}>Cancel</Btn>
          <Btn variant={danger ? "danger" : "primary"} onClick={onConfirm}>{confirmLabel}</Btn>
        </>
      }>
      <p>{body}</p>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Tabs, pagination, search                                            */
/* ------------------------------------------------------------------ */

export function Tabs({ tabs, active, onChange }: {
  tabs: { id: string; label: string }[]; active: string; onChange: (id: string) => void;
}) {
  return (
    <div role="tablist" aria-label="Sections" className="flex gap-1 overflow-x-auto border-b border-[#e4e7ec]">
      {tabs.map((t) => (
        <button key={t.id} type="button" role="tab" aria-selected={active === t.id} onClick={() => onChange(t.id)}
          className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium ${
            active === t.id ? "border-[#182230] text-[#101828]" : "border-transparent text-[#667085] hover:text-[#101828]"
          }`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Pagination({ page, pageCount, onChange }: { page: number; pageCount: number; onChange: (page: number) => void }) {
  if (pageCount <= 1) return null;
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 text-sm">
      <Btn variant="outline" disabled={page <= 1} onClick={() => onChange(page - 1)}>Prev</Btn>
      <span className="text-[#667085]" aria-live="polite">Page {page} of {pageCount}</span>
      <Btn variant="outline" disabled={page >= pageCount} onClick={() => onChange(page + 1)}>Next</Btn>
    </nav>
  );
}

export function SearchInput({ value, onChange, placeholder = "Search…", onSubmit }: {
  value: string; onChange: (value: string) => void; placeholder?: string; onSubmit?: () => void;
}) {
  return (
    <form role="search" onSubmit={(e) => { e.preventDefault(); onSubmit?.(); }} className="relative w-full">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#98a2b3]" aria-hidden="true">
        <circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" />
      </svg>
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        aria-label={placeholder} className={`${inputCls} pl-9 pr-9`} />
      {value && (
        <button type="button" onClick={() => onChange("")} aria-label="Clear search"
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md px-1.5 py-0.5 text-[#667085] hover:bg-[#f2f4f7] hover:text-[#101828]">&times;</button>
      )}
    </form>
  );
}

/* ------------------------------------------------------------------ */
/* DataTable                                                           */
/* ------------------------------------------------------------------ */

export type DataTableColumn = { key: string; label: string; sortable?: boolean };

export function DataTable({ columns, rows, sortKey, sortDir = "asc", onSort, renderCell, empty }: {
  columns: DataTableColumn[]; rows: any[]; sortKey?: string; sortDir?: "asc" | "desc";
  onSort?: (key: string) => void; renderCell?: (row: any, col: DataTableColumn) => ReactNode; empty?: ReactNode;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[#e4e7ec] bg-white">
      <table className="w-full min-w-[560px] border-collapse text-sm">
        <thead className="sticky top-0 bg-white">
          <tr className="border-b border-[#e4e7ec] text-left">
            {columns.map((col) => (
              <th key={col.key} scope="col"
                aria-sort={col.sortable && sortKey === col.key ? (sortDir === "asc" ? "ascending" : "descending") : undefined}
                className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-[#667085]">
                {col.sortable && onSort ? (
                  <button type="button" onClick={() => onSort(col.key)}
                    className="inline-flex items-center gap-1 uppercase tracking-wide text-[#667085] hover:text-[#101828]">
                    {col.label}
                    <span aria-hidden="true" className="text-[10px]">{sortKey === col.key ? (sortDir === "asc" ? "▲" : "▼") : "△"}</span>
                  </button>
                ) : col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr><td colSpan={columns.length} className="px-4 py-8 text-center text-[#667085]">{empty ?? "No rows to show."}</td></tr>
          ) : rows.map((row, i) => (
            <tr key={row.id ?? i} className="border-b border-[#e4e7ec]/60 last:border-0 hover:bg-[#f8fafc]">
              {columns.map((col) => (
                <td key={col.key} className="px-4 py-3 text-[#344054]">
                  {renderCell ? renderCell(row, col) : String(row[col.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Charts (pure SVG, no dependencies)                                  */
/* ------------------------------------------------------------------ */

export function BarChart({ data, height = 180 }: { data: { label: string; value: number }[]; height?: number }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  const summary = data.map((d) => `${d.label} ${d.value}`).join(", ") || "No data";
  const rowH = data.length > 0 ? height / data.length : height;
  return (
    <svg role="img" aria-label={`Bar chart: ${summary}`} viewBox={`0 0 600 ${height}`} className="h-auto w-full">
      {data.length === 0 && <text x="10" y="20" fill="#64748b" fontSize="13">No data yet.</text>}
      {data.map((d, i) => {
        const y = i * rowH;
        const barW = Math.max(2, (d.value / max) * 400);
        return (
          <g key={d.label}>
            <text x="0" y={y + rowH / 2 + 4} fill="#667085" fontSize="12">{d.label.length > 16 ? `${d.label.slice(0, 15)}…` : d.label}</text>
            <rect x="130" y={y + 6} width={barW} height={Math.max(8, rowH - 12)} rx="3" fill="#182230" />
            <text x={130 + barW + 8} y={y + rowH / 2 + 4} fill="#344054" fontSize="12">{d.value}</text>
          </g>
        );
      })}
    </svg>
  );
}

export function DonutChart({ data, size = 180 }: { data: { label: string; value: number; color: string }[]; size?: number }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  const summary = data.map((d) => `${d.label} ${d.value}`).join(", ") || "No data";
  const r = 70;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="flex flex-wrap items-center gap-6">
      <svg role="img" aria-label={`Donut chart, total ${total}: ${summary}`} width={size} height={size} viewBox="0 0 180 180" className="shrink-0">
        <circle cx="90" cy="90" r={r} fill="none" stroke="#e4e7ec" strokeWidth="22" />
        {total > 0 && data.map((d) => {
          const len = (d.value / total) * c;
          const dashoffset = -offset;
          offset += len;
          return (
            <circle key={d.label} cx="90" cy="90" r={r} fill="none" stroke={d.color} strokeWidth="22"
              strokeDasharray={`${len} ${c - len}`} strokeDashoffset={dashoffset} transform="rotate(-90 90 90)" />
          );
        })}
        <text x="90" y="86" textAnchor="middle" fill="#101828" fontSize="24" fontWeight="700">{total}</text>
        <text x="90" y="106" textAnchor="middle" fill="#667085" fontSize="11">total</text>
      </svg>
      <ul className="space-y-1.5 text-sm">
        {data.map((d) => (
          <li key={d.label} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: d.color }} aria-hidden="true" />
            <span className="text-[#344054]">{d.label}</span>
            <span className="font-medium text-[#101828]">{d.value}</span>
          </li>
        ))}
        {data.length === 0 && <li className="text-[#667085]">No data yet.</li>}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Switch, copy, avatar, dropdown, page header                        */
/* ------------------------------------------------------------------ */

export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label ?? "Toggle"}
      onClick={() => onChange(!checked)} className="inline-flex items-center gap-2">
      <span className={`relative inline-flex h-6 w-10 shrink-0 items-center rounded-full ${checked ? "bg-[#182230]" : "bg-[#d0d5dd]"}`}>
        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${checked ? "translate-x-5" : "translate-x-1"}`} />
      </span>
      {label && <span className="text-sm text-[#344054]">{label}</span>}
    </button>
  );
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button type="button" onClick={copy} aria-live="polite"
      className="rounded-lg border border-[#d0d5dd] px-2.5 py-1 text-xs font-medium text-[#344054] hover:bg-[#f2f4f7] hover:text-[#101828]">
      {copied ? "Copied" : label}
    </button>
  );
}

export function Avatar({ name, className = "h-9 w-9 text-xs" }: { name: string; className?: string }) {
  const initials = name
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("") || "?";
  return (
    <span aria-hidden="true"
      className={`inline-flex shrink-0 items-center justify-center rounded-full border border-[#d0d5dd] bg-[#e4e7ec] font-semibold text-[#182230] ${className}`}>
      {initials}
    </span>
  );
}

export function Dropdown({ trigger, children, align = "right" }: {
  trigger: ReactNode; children: ReactNode; align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open ]);
  return (
    <div ref={ref} className="relative">
      <div onClick={() => setOpen((o) => !o)}>{trigger}</div>
      {open && (
        <div role="menu" className={`absolute z-50 mt-2 w-56 rounded-lg border border-[#d0d5dd] bg-white p-1.5 shadow-xl ${align === "right" ? "right-0" : "left-0"}`}>
          {children}
        </div>
      )}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold text-[#101828]">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-[#667085]">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Error boundary — one page's render error must never blank the app   */
/* ------------------------------------------------------------------ */

export class ErrorBoundary extends Component<
  { children: ReactNode; onReset?: () => void },
  { hasError: boolean; message: string }
> {
  state = { hasError: false, message: "" };
  static getDerivedStateFromError(err: Error) {
    return { hasError: true, message: err?.message || "Unknown error" };
  }
  componentDidCatch(err: Error) {
    console.error("CodeSentry page error:", err);
  }
  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <Card className="py-10 text-center">
        <div className="text-lg font-semibold text-[#101828]">This page hit a problem</div>
        <p className="mx-auto mt-2 max-w-md text-sm text-[#667085]">
          {this.state.message} — the rest of the app is still fine. Try again, or go back to the Overview.
        </p>
        <div className="mt-4 flex justify-center gap-2">
          <Btn onClick={() => this.setState({ hasError: false, message: "" })}>Try again</Btn>
          {this.props.onReset && (
            <Btn variant="outline" onClick={() => { this.setState({ hasError: false, message: "" }); this.props.onReset?.(); }}>
              Back to Overview
            </Btn>
          )}
        </div>
      </Card>
    );
  }
}
