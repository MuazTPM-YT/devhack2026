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
