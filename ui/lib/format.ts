const rules = new Intl.PluralRules("en");

// "4.3 s", "2m 42s", "1h 2m"; seconds are floored so 119.6 never reads "1m 60s"
export function duration(s: number): string {
  const v = Math.max(0, s);
  if (v < 60) return `${v.toFixed(1)} s`;
  if (v < 3600) return `${Math.floor(v / 60)}m ${String(Math.floor(v % 60)).padStart(2, "0")}s`;
  return `${Math.floor(v / 3600)}h ${Math.floor((v % 3600) / 60)}m`;
}

export function since(ts: number | null | undefined, base: number): string {
  return ts == null ? "–" : `+${duration(ts - base)}`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${rules.select(n) === "one" ? one : many}`;
}

export function clock(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("en-GB", { hour12: false });
}

export function words(snake: string): string {
  return snake.replace(/_/g, " ");
}

// a long card or note as its first line plus the rest: the gist stays on screen, the rest folds away
export function lead(text: string): { head: string; rest: string } {
  const t = text.trim();
  const at = t.indexOf("\n");
  if (at >= 0) return { head: t.slice(0, at).trim(), rest: t.slice(at + 1).trim() };
  // one long paragraph: cut after its first sentence, never inside a number like 40.7
  const end = t.search(/[.!?](?=\s+\S)/);
  return end >= 0 && t.length > 140 ? { head: t.slice(0, end + 1), rest: t.slice(end + 1).trim() } : { head: t, rest: "" };
}
