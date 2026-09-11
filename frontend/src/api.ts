/** Thin client for the backend REST + WebSocket API. */

export type ArgSpec = {
  type: "int" | "float" | "str" | "enum" | "bool";
  min?: number;
  max?: number;
  choices?: string[];
  default?: unknown;
};
export type CommandSpec = { name: string; label: string; args: Record<string, ArgSpec>; confirm: boolean };
export type SystemSpec = { system: string; title: string; icon: string; poll_seconds: number; commands: CommandSpec[] };
export type SystemState = {
  system: string;
  online: boolean;
  data: Record<string, any>;
  updated_at: number;
  error: string | null;
};
export type EventRow = { id: number; ts: number; system: string; kind: "state" | "command" | "error"; payload: any };

const TOKEN_KEY = "scc_token";

export function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}
export function setToken(t: string) {
  try {
    localStorage.setItem(TOKEN_KEY, t);
  } catch {
    /* private mode */
  }
}

function headers(): HeadersInit {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}`, "Content-Type": "application/json" } : { "Content-Type": "application/json" };
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { ...init, headers: { ...headers(), ...(init?.headers ?? {}) } });
  if (r.status === 401) throw new Error("unauthorized");
  if (!r.ok) {
    let detail = r.statusText;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {
      /* not json */
    }
    throw new Error(detail);
  }
  return r.json();
}

export const api = {
  systems: () => req<SystemSpec[]>("/api/systems"),
  state: () => req<Record<string, SystemState>>("/api/state"),
  events: (limit = 100) => req<EventRow[]>(`/api/events?limit=${limit}`),
  series: (system: string, key: string, hours = 24) => req<[number, number][]>(`/api/${system}/series/${key}?hours=${hours}`),
  refresh: (system: string) => req<SystemState>(`/api/${system}/refresh`, { method: "POST" }),
  command: (system: string, command: string, args: Record<string, unknown>) =>
    req<{ result: any; state: SystemState }>(`/api/${system}/command`, {
      method: "POST",
      body: JSON.stringify({ command, args }),
    }),
  /** snapshot <img> URLs need the token as a query param */
  withToken: (url: string) => {
    const t = getToken();
    return t ? `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(t)}` : url;
  },
};

export function wsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const t = getToken();
  return `${proto}://${location.host}/ws${t ? `?token=${encodeURIComponent(t)}` : ""}`;
}
