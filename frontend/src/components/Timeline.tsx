import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { api, EventRow } from "../api";

export function Timeline({ onClose }: { onClose: () => void }) {
  const [rows, setRows] = useState<EventRow[]>([]);
  useEffect(() => {
    api.events(150).then(setRows).catch(() => setRows([]));
  }, []);
  return (
    <div className="tile mb-4 max-h-80 overflow-y-auto">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Recent events</h2>
        <button className="btn btn-ghost !min-h-8 !px-2" onClick={onClose}>
          <X size={14} />
        </button>
      </div>
      <ul className="space-y-1 text-xs">
        {rows.map((r) => (
          <li key={r.id} className="flex gap-2 border-b border-slate-800/60 py-1">
            <span className="w-24 shrink-0 tabular-nums text-slate-500">{new Date(r.ts * 1000).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" })}</span>
            <span className="w-24 shrink-0 text-slate-400">{r.system}</span>
            <span className={r.kind === "command" ? "text-sky-300" : r.kind === "error" ? "text-amber-300" : "text-slate-300"}>
              {describe(r)}
            </span>
          </li>
        ))}
        {rows.length === 0 && <li className="text-slate-500">nothing yet</li>}
      </ul>
    </div>
  );
}

function describe(r: EventRow): string {
  if (r.kind === "command") {
    const a = Object.entries(r.payload.args ?? {}).map(([k, v]) => `${k}=${v}`).join(" ");
    return `${r.payload.command} ${a} ${r.payload.ok ? "✓" : "✗ " + r.payload.result}`;
  }
  if (r.kind === "error") return `offline: ${r.payload.error}`;
  return "state changed";
}
