import { ReactNode, useState } from "react";
import {
  Bell, Box, Droplets, LoaderCircle, RefreshCw, Sun, Thermometer, Video, Wifi, Wind,
} from "lucide-react";
import { api, SystemSpec, SystemState } from "../api";

const ICONS: Record<string, typeof Box> = {
  sun: Sun, thermometer: Thermometer, wifi: Wifi, droplets: Droplets, wind: Wind, video: Video, bell: Bell, box: Box,
};

export function TileFrame({
  spec, state, onState, children, extra,
}: {
  spec: SystemSpec; state: SystemState; onState: (s: SystemState) => void; children: ReactNode; extra?: ReactNode;
}) {
  const Icon = ICONS[spec.icon] ?? Box;
  const [busy, setBusy] = useState(false);
  return (
    <div className={`tile flex-1 ${state.online ? "" : "border-amber-900/60"}`}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <span className={`rounded-lg p-1.5 ${state.online ? "bg-sky-950 text-sky-300" : "bg-amber-950 text-amber-300"}`}>
            <Icon size={16} />
          </span>
          {spec.title}
        </h2>
        <div className="flex items-center gap-1">
          {extra}
          <button
            className="btn btn-ghost !min-h-8 !px-2"
            title="Refresh now"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                onState(await api.refresh(spec.system));
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? <LoaderCircle size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          </button>
        </div>
      </div>
      {children}
    </div>
  );
}

/** Runs a command, handles confirm + errors, reports the new state. */
export function useCommand(spec: SystemSpec, onState: (s: SystemState) => void) {
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (name: string, args: Record<string, unknown> = {}) => {
    const cmd = spec.commands.find((c) => c.name === name);
    if (cmd?.confirm && !confirm(`${cmd.label} — are you sure?`)) return;
    setPending(name);
    setError(null);
    try {
      const r = await api.command(spec.system, name, args);
      onState(r.state);
    } catch (e: any) {
      setError(e.message ?? String(e));
    } finally {
      setPending(null);
    }
  };
  return { run, pending, error };
}

export function ErrorLine({ error }: { error: string | null }) {
  return error ? <p className="mt-2 rounded-md bg-rose-950/60 px-2 py-1 text-xs text-rose-300">{error}</p> : null;
}

export function KV({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="divide-y divide-slate-800/80">
      {rows.map(([k, v]) => (
        <div className="kv" key={k}>
          <dt>{k}</dt>
          <dd>{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Segmented<T extends string>({
  value, options, onChange, disabled,
}: { value: T | undefined; options: T[]; onChange: (v: T) => void; disabled?: boolean }) {
  return (
    <div className="seg" role="group">
      {options.map((o) => (
        <button key={o} aria-pressed={o === value} disabled={disabled} onClick={() => onChange(o)}>
          {o}
        </button>
      ))}
    </div>
  );
}
