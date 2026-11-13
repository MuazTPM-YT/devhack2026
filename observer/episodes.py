# per-service sick spells for orchestration: opens when a service turns unhealthy, ends on a healthy
# reading. A service with no reading stays open (missing telemetry is unknown, not healthy). Pure.
import uuid
from collections.abc import Callable

from schemas.orchestration import SignalEpisode, Symptom


def symptom_of(reading: dict, err_threshold: float) -> Symptom:
    errors = (reading.get("err_ratio") or 0) > err_threshold
    pods = (reading.get("bad_pods") or 0) > 0
    if pods and reading.get("breaching"):
        return "mixed"
    if pods:
        return "pods"
    return "errors" if errors else "latency"


class EpisodeTracker:
    def __init__(self, err_threshold: float, start_revision: int = 0, cluster: str = "local",
                 namespace: str = "shop", new_id: Callable[[], str] = lambda: f"ep-{uuid.uuid4().hex[:16]}"):
        self.err_threshold, self.revision = err_threshold, start_revision
        self.cluster, self.namespace, self.new_id = cluster, namespace, new_id
        self.open: dict[str, SignalEpisode] = {}

    # after a restart: carry on the episodes the database still has open
    def restore(self, episodes: list[SignalEpisode]) -> None:
        self.open = {e.service: e for e in episodes}
        self.revision = max([self.revision, *(e.source_revision for e in episodes)])

    # changes only: opened, symptom changed, recovered. last_observed_at rides along with each change
    def update(self, health: dict) -> list[SignalEpisode]:
        now, changes = health["ts"], []
        for service, reading in sorted(health["services"].items()):
            ep = self.open.get(service)
            if reading.get("unhealthy"):
                kind = symptom_of(reading, self.err_threshold)
                if ep is None:
                    self.revision += 1
                    ep = SignalEpisode(episode_id=self.new_id(), cluster=self.cluster, namespace=self.namespace,
                                       service=service, symptom=kind, first_breach_at=reading.get("first_breach_ts"),
                                       sustained_at=now, last_observed_at=now, source_revision=self.revision)
                    changes.append(ep)
                elif ep.symptom != kind:
                    self.revision += 1
                    ep = ep.model_copy(update={"symptom": kind, "last_observed_at": now,
                                               "source_revision": self.revision})
                    changes.append(ep)
                else:
                    ep = ep.model_copy(update={"last_observed_at": now})
                self.open[service] = ep
            elif ep is not None and reading.get("unhealthy") is False:
                self.revision += 1
                changes.append(ep.model_copy(update={"recovered_at": now, "last_observed_at": now,
                                                     "source_revision": self.revision}))
                del self.open[service]
        return changes
