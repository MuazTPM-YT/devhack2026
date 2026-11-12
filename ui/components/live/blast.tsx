import type { Incident } from "@/lib/live";

import styles from "./blast.module.css";

export function Blast({ incident, className }: { incident: Incident | null; className?: string }) {
  const services = incident?.unhealthy ?? [];
  return (
    <article className={`card ${className ?? ""}`}>
      <div className="card-head">
        <h2 className="card-title">Blast radius</h2>
        {incident?.fromTraces != null && (
          <span className="pill">{incident.fromTraces ? "from traces" : "deepest service guess"}</span>
        )}
      </div>

      <div className={styles.counts}>
        <div>
          <div className="figure">{String(services.length).padStart(2, "0")}</div>
          <div className="label">unhealthy services</div>
        </div>
        <div>
          <div className="figure">{String(incident?.groupings ?? 0).padStart(2, "0")}</div>
          <div className="label">alerts grouped in</div>
        </div>
      </div>

      <div className={styles.culpritBox}>
        <span className="label">Culprit</span>
        <span className={styles.name}>{incident?.culprit ?? "not found yet"}</span>
      </div>

      {services.length > 0 ? (
        <ul className={styles.list}>
          {services.map((svc) => {
            const role = svc === incident?.culprit ? "culprit" : incident?.victims.includes(svc) ? "victim" : "unhealthy";
            return (
              <li key={svc} className={styles.row}>
                <span className={`${styles.mark} ${styles[role]}`} />
                <span>{svc}</span>
                <span className={styles.role}>{role}</span>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="empty">All services inside their baselines.</p>
      )}
    </article>
  );
}
