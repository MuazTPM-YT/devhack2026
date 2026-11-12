export function since(ts: number | null | undefined, base: number): string {
  if (ts == null) return "–";
  const s = Math.max(0, ts - base);
  return s < 60 ? `+${s.toFixed(1)} s` : `+${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export function clock(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("en-GB", { hour12: false });
}

export function words(snake: string): string {
  return snake.replace(/_/g, " ");
}
