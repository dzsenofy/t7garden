/** Tiny dependency-free SVG sparkline for a [ts, value] series. */
export function Sparkline({ points, height = 40, className = "" }: { points: [number, number][]; height?: number; className?: string }) {
  if (points.length < 2) return <div className={`h-10 text-xs text-slate-500 ${className}`}>collecting history…</div>;
  const w = 200;
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y1 = Math.max(...ys, 1);
  const path = points
    .map(([x, y], i) => `${i ? "L" : "M"}${(((x - x0) / (x1 - x0 || 1)) * w).toFixed(1)},${(height - (y / y1) * (height - 2)).toFixed(1)}`)
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${height}`} className={`h-10 w-full ${className}`} preserveAspectRatio="none" aria-hidden>
      <path d={`${path} L${w},${height} L0,${height} Z`} fill="currentColor" opacity="0.15" />
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
