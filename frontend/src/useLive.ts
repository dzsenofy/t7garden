/** Keeps systems + state in sync over the WebSocket, with REST fallback and auto-reconnect. */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, SystemSpec, SystemState, wsUrl } from "./api";

export type Conn = "connecting" | "live" | "offline" | "unauthorized";

export function useLive() {
  const [systems, setSystems] = useState<SystemSpec[]>([]);
  const [state, setState] = useState<Record<string, SystemState>>({});
  const [conn, setConn] = useState<Conn>("connecting");
  const [lastCommand, setLastCommand] = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const retry = useRef(1000);

  const loadRest = useCallback(async () => {
    try {
      const [s, st] = await Promise.all([api.systems(), api.state()]);
      setSystems(s);
      setState(st);
      return true;
    } catch (e: any) {
      if (e?.message === "unauthorized") setConn("unauthorized");
      return false;
    }
  }, []);

  useEffect(() => {
    let closed = false;
    const connect = () => {
      if (closed) return;
      setConn((c) => (c === "unauthorized" ? c : "connecting"));
      const ws = new WebSocket(wsUrl());
      wsRef.current = ws;
      ws.onopen = () => {
        retry.current = 1000;
        setConn("live");
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "snapshot") {
          setSystems(msg.systems);
          setState(msg.state);
        } else if (msg.type === "state") {
          const { type, ...st } = msg;
          setState((prev) => ({ ...prev, [st.system]: st }));
        } else if (msg.type === "command") {
          setLastCommand(msg);
        }
      };
      ws.onclose = (ev) => {
        wsRef.current = null;
        if (closed) return;
        if (ev.code === 4401) {
          setConn("unauthorized");
          return;
        }
        setConn("offline");
        void loadRest();
        setTimeout(connect, retry.current);
        retry.current = Math.min(retry.current * 2, 15000);
      };
      ws.onerror = () => ws.close();
    };
    void loadRest();
    connect();
    return () => {
      closed = true;
      wsRef.current?.close();
    };
  }, [loadRest]);

  const applyState = useCallback((st: SystemState) => setState((p) => ({ ...p, [st.system]: st })), []);

  return { systems, state, conn, lastCommand, applyState, reload: loadRest };
}
