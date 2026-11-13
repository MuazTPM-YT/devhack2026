import type { ReactNode } from "react";

import s from "./sheet.module.css";

// one fold of the incident sheet: the header says the gist, the body opens on a click
export function SheetSection({ id, title, aside, open = true, children }: {
  id: string; title: string; aside?: ReactNode; open?: boolean; children: ReactNode;
}) {
  return (
    <details className={`${s.sec} ${s.fold}`} open={open}>
      <summary className={s.head}>
        <h2 id={id} className={s.title}>{title}</h2>
        <span className={s.aside}>{aside}</span>
      </summary>
      <div className={s.body}>{children}</div>
    </details>
  );
}
