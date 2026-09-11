import { useEffect, useState } from "react";
import { Activity, KeyRound, RefreshCw, Wifi, WifiOff } from "lucide-react";
import { api, getToken, setToken, SystemSpec, SystemState } from "./api";
import { useLive } from "./useLive";
import { Timeline } from "./components/Timeline";
import { SolarTile } from "./tiles/SolarTile";
import { ClimateTile } from "./tiles/ClimateTile";
import { RouterTile } from "./tiles/RouterTile";
import { IrrigationTile } from "./tiles/IrrigationTile";
import { CamerasTile } from "./tiles/CamerasTile";
import { DoorbellTile } from "./tiles/DoorbellTile";
import { GenericTile } from "./tiles/GenericTile";

export type TileProps = { spec: SystemSpec; state: SystemState; onState: (s: SystemState) => void };

const TILES: Record<string, (p: TileProps) => JSX.Element> = {
  solaredge: SolarTile,
  panasonic: ClimateTile,
  broadlink_ac: ClimateTile,
  zte: RouterTile,
  rainbird: IrrigationTile,
  hik_nvr: CamerasTile,
  doorbell: DoorbellTile,
};

// display order: what you glance at first goes first
const ORDER = ["hik_nvr", "doorbell", "panasonic", "broadlink_ac", "rainbird", "solaredge", "zte"];

export default function App() {
  const { systems, state, conn, lastCommand, applyState, reload } = useLive();
  const [showTimeline, setShowTimeline] = useState(false);
  const [clock, setClock] = useState(Date.now());

  useEffect(() => {
    const t = setInterval(() => setClock(Date.now()), 15000);
    return () => clearInterval(t);
  }, []);

  if (conn === "unauthorized") return <TokenGate onSaved={() => location.reload()} />;

  const ordered = [...systems].sort((a, b) => ORDER.indexOf(a.system) - ORDER.indexOf(b.system));
  const offline = ordered.filter((s) => state[s.system] && !state[s.system].online).length;

  return (
    <div className="mx-auto min-h-dvh max-w-7xl px-3 pb-8 pt-[max(0.75rem,env(safe-area-inset-top))] sm:px-5">
      <header className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight sm:text-xl">Siófok Command Control</h1>
          <p className="text-xs text-slate-400">
            {ordered.length} systems · {offline ? <span className="text-amber-400">{offline} offline</span> : "all online"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ConnBadge conn={conn} />
          <button className="btn btn-ghost" onClick={() => setShowTimeline((v) => !v)} title="Event timeline">
            <Activity size={16} /> <span className="hidden sm:inline">Timeline</span>
          </button>
          <button className="btn btn-ghost" onClick={() => void reload()} title="Reload">
            <RefreshCw size={16} />
          </button>
        </div>
      </header>

      {showTimeline && <Timeline key={String(lastCommand?.ts ?? 0)} onClose={() => setShowTimeline(false)} />}

      {ordered.length === 0 && (
        <div className="tile text-sm text-slate-400">
          No systems configured yet. Fill in <code>.env</code> on the server or set <code>DEMO_MODE=true</code>.
        </div>
      )}

      <main className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {ordered.map((spec) => {
          const st = state[spec.system];
          if (!st) return null;
          const Tile = TILES[spec.system] ?? GenericTile;
          const wide = spec.system === "hik_nvr";
          return (
            <section key={spec.system} className={`flex flex-col ${wide ? "sm:col-span-2" : ""}`}>
              <Tile spec={spec} state={st} onState={applyState} />
              <p className="mt-1 px-1 text-[11px] text-slate-500">
                {st.online ? `updated ${ago(st.updated_at, clock)}` : <span className="text-amber-400">offline · {st.error}</span>}
              </p>
            </section>
          );
        })}
      </main>
    </div>
  );
}

function ConnBadge({ conn }: { conn: string }) {
  const live = conn === "live";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs ${
        live ? "bg-emerald-900/60 text-emerald-300" : "bg-amber-900/60 text-amber-300"
      }`}
    >
      {live ? <Wifi size={12} /> : <WifiOff size={12} />}
      {live ? "live" : conn}
    </span>
  );
}

function TokenGate({ onSaved }: { onSaved: () => void }) {
  const [t, setT] = useState(getToken());
  return (
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-4 px-4">
      <div className="tile">
        <h1 className="mb-1 flex items-center gap-2 text-lg font-semibold">
          <KeyRound size={18} /> Dashboard token
        </h1>
        <p className="mb-3 text-sm text-slate-400">
          This server requires the shared token from <code>DASHBOARD_TOKEN</code> in its <code>.env</code>.
        </p>
        <input
          className="mb-3 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          type="password"
          value={t}
          onChange={(e) => setT(e.target.value)}
          placeholder="token"
          autoFocus
        />
        <button
          className="btn btn-primary w-full"
          onClick={async () => {
            setToken(t.trim());
            try {
              await api.state();
              onSaved();
            } catch {
              alert("Token rejected");
            }
          }}
        >
          Save
        </button>
      </div>
    </div>
  );
}

export function ago(ts: number, now = Date.now()): string {
  if (!ts) return "never";
  const s = Math.max(0, Math.round(now / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${(s / 3600).toFixed(1)}h ago`;
}
