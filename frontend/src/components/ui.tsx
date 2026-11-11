import React from "react";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-slate-800 bg-[#0b1226] p-5 ${className}`}>{children}</div>;
}

export function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <Card>
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-3xl font-bold text-white">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-400">{sub}</div>}
    </Card>
  );
}

const SEV: Record<string, string> = {
  critical: "bg-red-500/15 text-red-300 border-red-500/40",
  high: "bg-orange-500/15 text-orange-300 border-orange-500/40",
  medium: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  low: "bg-slate-500/15 text-slate-300 border-slate-500/40",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${SEV[severity] || SEV.low}`}>{severity.toUpperCase()}</span>;
}

export function Skeleton({ className = "h-24" }: { className?: string }) {
  return <div className={`animate-pulse rounded-2xl bg-slate-800/60 ${className}`} />;
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <Card className="text-center py-10">
      <div className="text-lg font-semibold text-white">{title}</div>
      <p className="mt-2 text-sm text-slate-400 max-w-md mx-auto">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </Card>
  );
}

export function Btn({ children, onClick, variant = "primary", disabled, type = "button" }: {
  children: React.ReactNode; onClick?: () => void; variant?: "primary" | "ghost" | "danger" | "outline";
  disabled?: boolean; type?: "button" | "submit";
}) {
  const styles = {
    primary: "bg-gradient-to-r from-violet-600 to-cyan-500 text-white hover:opacity-90",
    ghost: "bg-slate-800 text-slate-200 hover:bg-slate-700",
    danger: "bg-red-600/90 text-white hover:bg-red-600",
    outline: "border border-slate-700 text-slate-200 hover:bg-slate-800",
  }[variant];
  return <button type={type} disabled={disabled} onClick={onClick}
    className={`rounded-lg px-4 py-2 text-sm font-semibold transition disabled:opacity-50 ${styles}`}>{children}</button>;
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-sm"><span className="text-slate-400">{label}</span><div className="mt-1">{children}</div></label>;
}

export const inputCls = "w-full rounded-lg border border-slate-700 bg-[#070b16] px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-violet-500";
