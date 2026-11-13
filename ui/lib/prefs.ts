// which side panels the viewer folded away; kept in localStorage, so it is theirs and survives a reload
export interface Prefs { nav: boolean; list: boolean; sheet: boolean }
export type PrefKey = keyof Prefs;

export const PREFS_KEY = "akira.panels";
export const DEFAULT_PREFS: Prefs = { nav: false, list: false, sheet: false };

// anything unreadable (old shape, hand-edited, blocked storage) falls back to "all open"
export function readPrefs(raw: string | null): Prefs {
  try {
    const v = JSON.parse(raw ?? "null") as Partial<Record<PrefKey, unknown>> | null;
    if (!v || typeof v !== "object") return DEFAULT_PREFS;
    return { nav: v.nav === true, list: v.list === true, sheet: v.sheet === true };
  } catch {
    return DEFAULT_PREFS;
  }
}

export function togglePref(prefs: Prefs, key: PrefKey): Prefs {
  return { ...prefs, [key]: !prefs[key] };
}
