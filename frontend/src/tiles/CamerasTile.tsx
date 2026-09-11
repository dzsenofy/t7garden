import { useEffect, useState } from "react";
import { HardDrive, X } from "lucide-react";
import { api } from "../api";
import { TileProps } from "../App";
import { TileFrame } from "../components/Tile";

type Channel = { id: number; name: string; online: boolean; snapshot: string; stream: string };

export function CamerasTile({ spec, state, onState }: TileProps) {
  const d = state.data;
  const channels = (d.channels ?? []) as Channel[];
  const [tick, setTick] = useState(0);
  const [open, setOpen] = useState<Channel | null>(null);
  useEffect(() => {
    const t = setInterval(() => setTick((x) => x + 1), 20000); // snapshot refresh
    return () => clearInterval(t);
  }, []);

  return (
    <TileFrame
      spec={spec} state={state} onState={onState}
      extra={
        <span className="inline-flex items-center gap-1 text-xs text-slate-400" title="Recorder storage">
          <HardDrive size={12} /> {d.hdd_status ?? "?"} {d.hdd_free_pct != null && `· ${d.hdd_free_pct}% free`}
        </span>
      }
    >
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {channels.map((c) => (
          <button key={c.id} className="group relative aspect-video overflow-hidden rounded-lg bg-slate-950 text-left" onClick={() => c.online && setOpen(c)} disabled={!c.online}>
            {c.online ? (
              <img src={api.withToken(`${c.snapshot}?t=${tick}`)} alt={c.name} className="h-full w-full object-cover transition group-hover:scale-105"
                onError={(e) => ((e.target as HTMLImageElement).style.opacity = "0.2")} />
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-slate-500">offline</div>
            )}
            <span className="absolute bottom-1 left-1 rounded bg-black/60 px-1.5 py-0.5 text-[11px]">{c.name}</span>
            {!c.online && <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-amber-400" />}
          </button>
        ))}
      </div>
      {d.last_motion && (
        <p className="mt-2 text-xs text-slate-400">last motion: channel {d.last_motion.channel} at {d.last_motion.at}</p>
      )}
      {open && <StreamModal ch={open} onClose={() => setOpen(null)} />}
    </TileFrame>
  );
}

/** Live view through go2rtc (proxied under /stream). MSE/WebRTC handled by go2rtc's own player page. */
function StreamModal({ ch, onClose }: { ch: Channel; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-3" onClick={onClose}>
      <div className="w-full max-w-4xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-2 flex items-center justify-between text-sm">
          <span>{ch.name} · live</span>
          <button className="btn btn-ghost !min-h-8 !px-2" onClick={onClose}><X size={16} /></button>
        </div>
        <iframe
          title={ch.name}
          src={`/stream/stream.html?src=${encodeURIComponent(ch.stream)}&mode=webrtc,mse,hls`}
          className="aspect-video w-full rounded-lg bg-black"
          allow="autoplay; fullscreen"
        />
      </div>
    </div>
  );
}
