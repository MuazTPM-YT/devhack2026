"use client";

import { useEffect, useReducer, useState } from "react";

import { DEMO_SCRIPT } from "./demo.ts";
import { type BusRecord, EVENT_TYPES, initialState, reduce } from "./live.ts";

export type Link = "connecting" | "live" | "down" | "demo";

// gateway SSE through the Next rewrite; the browser re-sends Last-Event-ID on reconnect
export function useLive(demo: boolean) {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [link, setLink] = useState<Link>(demo ? "demo" : "connecting");
  const [run, setRun] = useState(0);

  useEffect(() => {
    if (!demo) return;
    setLink("demo");
    const start = Date.now() / 1000;
    // each replay is a new incident, so the old one stays intact in the list
    const id = `inc-demo-${run + 1}`;
    const timers = DEMO_SCRIPT.map((step, i) => {
      const card = step.payload.card as Record<string, unknown> | undefined;
      const payload = card ? { ...step.payload, card: { ...card, incident_id: id } } : step.payload;
      return setTimeout(() => dispatch({
        seq: run * 1000 + i + 1,
        ts: start + step.at,
        event: { type: step.type, incident_id: id, payload },
      }), step.at * 1000);
    });
    return () => timers.forEach(clearTimeout);
  }, [demo, run]);

  useEffect(() => {
    if (demo) return;
    const source = new EventSource("/api/gateway/events");
    const onRecord = (e: MessageEvent<string>) => {
      try {
        dispatch(JSON.parse(e.data) as BusRecord);
      } catch {
        // one bad line must not kill the stream
      }
    };
    EVENT_TYPES.forEach((type) => source.addEventListener(type, onRecord));
    source.onopen = () => setLink("live");
    source.onerror = () => setLink(source.readyState === EventSource.CLOSED ? "down" : "connecting");
    return () => source.close();
  }, [demo]);

  return { state, link, replay: () => setRun((n) => n + 1) };
}
