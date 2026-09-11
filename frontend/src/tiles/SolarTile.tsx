import { useEffect, useState } from "react";
import { api } from "../api";
import { TileProps } from "../App";
import { Sparkline } from "../components/Sparkline";
import { KV, TileFrame } from "../components/Tile";

const kwh = (wh?: number) => (wh == null ? "—" : `${(wh / 1000).toFixed(1)} kWh`);

export function SolarTile({ spec, state, onState }: TileProps) {
  const d = state.data;
  const [series, setSeries] = useState<[number, number][]>([]);
  useEffect(() => {
    api.series("solaredge", "power_w", 24).then(setSeries).catch(() => {});
  }, [state.updated_at]);

  const kw = d.power_w != null ? d.power_w / 1000 : null;
  return (
    <TileFrame spec={spec} state={state} onState={onState}>
      <div className="mb-2 flex items-end justify-between">
        <div>
          <div className="text-3xl font-semibold tabular-nums">
            {kw == null ? "—" : kw.toFixed(2)} <span className="text-base font-normal text-slate-400">kW</span>
          </div>
          <div className="text-xs text-slate-400">now · peak {d.peak_power_kwp ?? "?"} kWp</div>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-xs ${d.inverter_status === "OK" ? "bg-emerald-900/60 text-emerald-300" : "bg-amber-900/60 text-amber-300"}`}>
          {d.inverter_status ?? "?"}
        </span>
      </div>
      <Sparkline points={series} className="text-amber-400" />
      <KV
        rows={[
          ["Today", kwh(d.energy_today_wh)],
          ["This month", kwh(d.energy_month_wh)],
          ["Lifetime", d.energy_lifetime_wh != null ? `${(d.energy_lifetime_wh / 1e6).toFixed(1)} MWh` : "—"],
          ["Portal update", d.last_update ?? "—"],
        ]}
      />
    </TileFrame>
  );
}
