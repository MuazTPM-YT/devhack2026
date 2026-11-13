"use client";

import { useSyncExternalStore } from "react";

import { DEFAULT_PREFS, type PrefKey, type Prefs, PREFS_KEY, readPrefs, togglePref } from "./prefs.ts";

const listeners = new Set<() => void>();
let cache: { raw: string | null; prefs: Prefs } | null = null;

// same object while storage is unchanged, or useSyncExternalStore would loop
function snapshot(): Prefs {
  let raw: string | null = null;
  try { raw = window.localStorage.getItem(PREFS_KEY); } catch { /* storage blocked: all open */ }
  if (!cache || cache.raw !== raw) cache = { raw, prefs: readPrefs(raw) };
  return cache.prefs;
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  window.addEventListener("storage", fn);
  return () => { listeners.delete(fn); window.removeEventListener("storage", fn); };
}

// is this panel folded, and a way to flip it; the server renders everything open
export function usePref(key: PrefKey): [boolean, () => void] {
  const prefs = useSyncExternalStore(subscribe, snapshot, () => DEFAULT_PREFS);
  const toggle = () => {
    try { window.localStorage.setItem(PREFS_KEY, JSON.stringify(togglePref(snapshot(), key))); } catch { /* not kept */ }
    listeners.forEach((fn) => fn());
  };
  return [prefs[key], toggle];
}
