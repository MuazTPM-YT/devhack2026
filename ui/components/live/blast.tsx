import { Tag } from "@/components/ui/tag";
import type { Incident } from "@/lib/live";

import s from "./sheet.module.css";

export function Blast({ incident }: { incident: Incident }) {
  const services = incident.unhealthy;
  return (
    <section className={s.sec} aria-labelledby="sec-blast">
      <div className={s.head}>
        <h2 id="sec-blast" className={s.title}>Blast radius</h2>
        {incident.fromTraces != null && (
          <span className="label">{incident.fromTraces ? "culprit from traces" : "deepest service guess"}</span>
        )}
      </div>
      <div className={s.counts}>
        <div><span className={s.big}>{services.length}</span><span className={s.small}>unhealthy</span></div>
        <div><span className={s.big}>{incident.groupings}</span><span className={s.small}>alerts folded in</span></div>
      </div>
      {services.length > 0 ? (
        <ul className={s.rows}>
          {services.map((svc) => (
            <li key={svc}>
              <span>{svc}</span>
              {svc === incident.culprit ? <Tag tone="dark">Culprit</Tag>
                : incident.victims.includes(svc) ? <Tag tone="warn">Victim</Tag>
                : <Tag tone="idle">Unhealthy</Tag>}
            </li>
          ))}
        </ul>
      ) : (
        <p className={s.empty}>All services inside their baselines.</p>
      )}
    </section>
  );
}
