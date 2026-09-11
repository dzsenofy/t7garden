import { RotateCcw } from "lucide-react";
import { TileProps } from "../App";
import { ErrorLine, KV, TileFrame, useCommand } from "../components/Tile";

export function RouterTile({ spec, state, onState }: TileProps) {
  const { run, pending, error } = useCommand(spec, onState);
  const d = state.data;
  const bars = Number(d.signal_bars ?? 0);
  return (
    <TileFrame
      spec={spec} state={state} onState={onState}
      extra={
        <button className="btn btn-danger !min-h-8 !px-2" title="Reboot router" disabled={!!pending} onClick={() => run("reboot")}>
          <RotateCcw size={14} />
        </button>
      }
    >
      <div className="mb-2 flex items-end justify-between">
        <div>
          <div className="text-2xl font-semibold">{d.network ?? "—"} <span className="text-sm font-normal text-slate-400">{d.band}</span></div>
          <div className="text-xs text-slate-400">{d.operator}</div>
        </div>
        <div className="flex items-end gap-0.5" title={`${bars}/5 bars`} aria-label={`signal ${bars} of 5`}>
          {[1, 2, 3, 4, 5].map((i) => (
            <span key={i} className={`w-1.5 rounded-sm ${i <= bars ? "bg-emerald-400" : "bg-slate-700"}`} style={{ height: 6 + i * 4 }} />
          ))}
        </div>
      </div>
      <KV
        rows={[
          ["RSRP / SINR", d.rsrp_dbm != null ? `${d.rsrp_dbm} dBm / ${d.sinr_db ?? "?"} dB` : "—"],
          ["Clients", d.clients],
          ["Data this month", d.data_month_gb != null ? `${d.data_month_gb} GB` : "—"],
          ["Uptime", d.uptime_h != null ? `${d.uptime_h} h` : "—"],
          ["WAN IP", d.wan_ip],
          ["SIM", d.sim_status],
        ]}
      />
      <ErrorLine error={error} />
    </TileFrame>
  );
}
