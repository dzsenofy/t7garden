import { LockOpen } from "lucide-react";
import { TileProps } from "../App";
import { ErrorLine, KV, TileFrame, useCommand } from "../components/Tile";

export function DoorbellTile({ spec, state, onState }: TileProps) {
  const { run, pending, error } = useCommand(spec, onState);
  const d = state.data;
  const dev = (d.devices ?? [])[0] ?? d;
  const ringing = String(d.call_status ?? "").toLowerCase().includes("ring");
  return (
    <TileFrame spec={spec} state={state} onState={onState}>
      <div className={`mb-2 rounded-lg px-3 py-2 text-sm ${ringing ? "animate-pulse bg-rose-900/60 text-rose-200" : "bg-slate-800/60 text-slate-300"}`}>
        {ringing ? "🔔 Ringing now" : `Status: ${typeof d.call_status === "object" ? JSON.stringify(d.call_status) : d.call_status ?? "idle"}`}
      </div>
      <KV
        rows={[
          ["Device", d.name ?? "—"],
          ["Online", dev.online ? "yes" : "no"],
          ["Local IP", dev.local_ip ?? "—"],
          ["Wi-Fi signal", dev.wifi_signal ?? "—"],
        ]}
      />
      <button className="btn btn-primary mt-3 w-full" disabled={!!pending} onClick={() => run("unlock", {})}>
        <LockOpen size={16} /> Unlock door
      </button>
      <ErrorLine error={error} />
    </TileFrame>
  );
}
