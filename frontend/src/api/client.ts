const API_BASE =
  import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "" : "http://localhost:8000");

export function token(): string | null {
  return localStorage.getItem("cs_token") ?? sessionStorage.getItem("cs_token");
}
export function setToken(t: string | null, persist = true) {
  if (t) {
    if (persist) {
      localStorage.setItem("cs_token", t);
      sessionStorage.removeItem("cs_token");
    } else {
      sessionStorage.setItem("cs_token", t);
      localStorage.removeItem("cs_token");
    }
  } else {
    localStorage.removeItem("cs_token");
    sessionStorage.removeItem("cs_token");
  }
}
export function clearToken() {
  localStorage.removeItem("cs_token");
  sessionStorage.removeItem("cs_token");
}

export async function api(path: string, opts: RequestInit = {}): Promise<any> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const t = token();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers: { ...headers, ...(opts.headers as any) } });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch { /* keep status text */ }
    throw new Error(`${res.status}: ${msg}`);
  }
  return res.json();
}

export const get = (p: string) => api(p);
export const post = (p: string, body?: any) =>
  api(p, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined });
export const patch = (p: string, body: any) => api(p, { method: "PATCH", body: JSON.stringify(body) });

export type Repo = { id: number; full_name: string; name: string; index_status: string; languages: string[]; head_sha: string; is_demo: boolean; symbols?: number };
export type Finding = {
  id: number; source: string; category: string; severity: string; title: string;
  description: string; file_path: string; start_line: number; end_line: number;
  evidence: string; cwe_id?: string | null; cwe_title?: string | null; owasp_ref?: string | null;
  confidence: number; patch?: string | null; patch_valid: boolean; model_version: string;
  context_provenance: Record<string, any>; state: string; suppressed_reason?: string | null;
  pr_number: number; repo_id: number;
};
