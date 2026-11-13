// 20 px line icons drawn for this app; stroke follows currentColor
const PATHS = {
  grid: "M3.5 3.5h5v5h-5zM11.5 3.5h5v5h-5zM3.5 11.5h5v5h-5zM11.5 11.5h5v5h-5z",
  live: "M2.5 10.5h3.5l2-5 3.5 9 2-4h4",
  chaos: "M11 2.5 4.5 11h5l-1 6.5L15.5 9h-5z",
  receipts: "M5 2.5h10v15l-2-1.3-1.7 1.3-1.3-1.3-1.3 1.3L7 16.2l-2 1.3zM7.5 6.5h5M7.5 9.5h5M7.5 12.5h3",
  menu: "M3.5 5.5h13M3.5 10h13M3.5 14.5h13",
  close: "M5 5l10 10M15 5 5 15",
  copy: "M7 7h9.5v9.5H7zM13 7V3.5H3.5V13H7",
  check: "M4.5 10.5 8 14l7.5-8",
  out: "M11.5 3.5h5v5M16.5 3.5 9.5 10.5M14.5 11.5v5h-11v-11h5",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path d={PATHS[name]} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
        strokeLinejoin="round" />
    </svg>
  );
}
