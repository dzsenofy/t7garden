import { TileProps } from "../App";
import { ErrorLine, KV, TileFrame, useCommand } from "../components/Tile";

/** Fallback for any system without a dedicated tile: dumps data + renders declared commands. */
export function GenericTile({ spec, state, onState }: TileProps) {
  const { run, pending, error } = useCommand(spec, onState);
  const rows = Object.entries(state.data)
    .filter(([, v]) => typeof v !== "object")
    .map(([k, v]) => [k, String(v)] as [string, string]);
  return (
    <TileFrame spec={spec} state={state} onState={onState}>
      <KV rows={rows} />
      <div className="mt-3 flex flex-wrap gap-2">
        {spec.commands
          .filter((c) => Object.keys(c.args).length === 0)
          .map((c) => (
            <button key={c.name} className="btn btn-ghost" disabled={!!pending} onClick={() => run(c.name)}>
              {c.label}
            </button>
          ))}
      </div>
      <ErrorLine error={error} />
    </TileFrame>
  );
}
