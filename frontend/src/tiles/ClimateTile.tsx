import { Minus, Plus, Power } from "lucide-react";
import { TileProps } from "../App";
import { ErrorLine, Segmented, TileFrame, useCommand } from "../components/Tile";

type Unit = {
  name?: string; power?: boolean; mode?: string; target_c?: number; inside_c?: number | null; outside_c?: number | null; fan?: string;
};

/** Shared by Panasonic (multi-unit, `data.units`) and Broadlink AC (single unit, flat data). */
export function ClimateTile({ spec, state, onState }: TileProps) {
  const { run, pending, error } = useCommand(spec, onState);
  const multi = !!state.data.units;
  const units: [string | null, Unit][] = multi
    ? Object.entries(state.data.units as Record<string, Unit>)
    : [[null, state.data as Unit]];
  const modeCmd = spec.commands.find((c) => c.name === "set_mode");
  const fanCmd = spec.commands.find((c) => c.name === "set_fan");
  const tempCmd = spec.commands.find((c) => c.name === "set_temperature");
  const withUnit = (id: string | null, args: Record<string, unknown>) => (id ? { unit: id, ...args } : args);

  return (
    <TileFrame spec={spec} state={state} onState={onState}>
      <div className="space-y-3">
        {units.map(([id, u]) => (
          <div key={id ?? "single"} className={`rounded-xl ${multi ? "border border-slate-800 p-3" : ""}`}>
            <div className="mb-2 flex items-center justify-between gap-2">
              <div>
                <div className="text-sm font-medium">{u.name ?? id}</div>
                <div className="text-xs text-slate-400">
                  {u.inside_c != null && <>inside {u.inside_c}° </>}
                  {u.outside_c != null && <>· outside {u.outside_c}°</>}
                </div>
              </div>
              <button
                className={`btn ${u.power ? "btn-primary" : "btn-ghost"} !px-2.5`}
                disabled={!!pending}
                title={u.power ? "Turn off" : "Turn on"}
                onClick={() => run("set_power", withUnit(id, { on: !u.power }))}
              >
                <Power size={16} />
              </button>
            </div>

            <div className="mb-2 flex items-center justify-between">
              <button className="btn btn-ghost !px-2.5" disabled={!!pending || !tempCmd}
                onClick={() => run("set_temperature", withUnit(id, { target_c: (u.target_c ?? 22) - 0.5 }))}>
                <Minus size={16} />
              </button>
              <div className={`text-3xl font-semibold tabular-nums ${u.power ? "" : "text-slate-500"}`}>
                {u.target_c ?? "—"}<span className="text-base font-normal text-slate-400">°C</span>
              </div>
              <button className="btn btn-ghost !px-2.5" disabled={!!pending || !tempCmd}
                onClick={() => run("set_temperature", withUnit(id, { target_c: (u.target_c ?? 22) + 0.5 }))}>
                <Plus size={16} />
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {modeCmd && (
                <Segmented value={u.mode} options={modeCmd.args.mode.choices!} disabled={!!pending}
                  onChange={(m) => run("set_mode", withUnit(id, { mode: m }))} />
              )}
              {fanCmd && (
                <Segmented value={u.fan} options={fanCmd.args.fan.choices!} disabled={!!pending}
                  onChange={(f) => run("set_fan", withUnit(id, { fan: f }))} />
              )}
            </div>
          </div>
        ))}
      </div>
      <ErrorLine error={error} />
    </TileFrame>
  );
}
