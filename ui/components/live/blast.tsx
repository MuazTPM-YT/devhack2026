import { Tag } from "@/components/ui/tag";
import { plural } from "@/lib/format";
import type { Incident } from "@/lib/live";

import { SheetSection } from "./sheet-section";
import s from "./sheet.module.css";

export function Blast({ incident }: { incident: Incident }) {
  const services = incident.unhealthy;
  return (
    <SheetSection id="sec-blast" title="Blast radius" open={false}
      aside={<span className="label">{plural(services.length, "service")}</span>}>
      {incident.fromTraces != null && (
        <p className={s.note}>{incident.fromTraces ? "Culprit found from error traces." : "Culprit is the deepest unhealthy service, a guess."}</p>
      )}
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
    </SheetSection>
  );
}
