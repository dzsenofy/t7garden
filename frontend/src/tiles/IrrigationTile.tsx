import { useState } from "react";
import { CloudRain, Square } from "lucide-react";
import { TileProps } from "../App";
import { ErrorLine, TileFrame, useCommand } from "../components/Tile";

export function IrrigationTile({ spec, state, onState }: TileProps) {
  const { run, pending, error } = useCommand(spec, onState);
  const d = state.data;
  const zones = Object.entries((d.zones ?? {}) as Record<string, { name: string; running: boolean }>);
  const [minutes, setMinutes] = useState(5);
  return (
    <TileFrame
      spec={spec} state={state} onState={onState}
      extra={
        <button className="btn btn-danger !min-h-8 !px-2" title="Stop all" disabled={!!pending || d.active_zone == null} onClick={() => run("stop")}>
          <Square size={14} />
        </button>
      }
    >
      <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
        <span>
          {d.active_zone ? <span className="text-sky-300">zone {d.active_zone} running</span> : "idle"} · {d.model}
        </span>
        <span className={`inline-flex items-center gap-1 ${d.rain_sensor ? "text-sky-300" : ""}`}>
          <CloudRain size={12} /> {d.rain_sensor ? "rain sensor active" : d.rain_delay_days ? `rain delay ${d.rain_delay_days}d` : "no rain hold"}
        </span>
      </div>
      <div className="mb-3 flex items-center gap-2 text-xs text-slate-400">
        run for
        <input type="range" min={1} max={30} value={minutes} onChange={(e) => setMinutes(+e.target.value)} className="w-28 accent-sky-500" />
        <span className="w-10 tabular-nums text-slate-200">{minutes} min</span>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {zones.map(([id, z]) => (
          <button
            key={id}
            disabled={!!pending}
            onClick={() => run("run_zone", { zone: Number(id), minutes })}
            className={`btn ${z.running ? "btn-primary animate-pulse" : "btn-ghost"} flex-col !gap-0 !py-1.5`}
            title={`Run ${z.name} for ${minutes} min`}
          >
            <span className="text-base font-semibold">{id}</span>
            <span className="text-[10px] font-normal opacity-70">{z.running ? "running" : "run"}</span>
          </button>
        ))}
      </div>
      <ErrorLine error={error} />
    </TileFrame>
  );
}
