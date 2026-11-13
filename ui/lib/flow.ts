// the /flow map: which part of the system each event belongs to, and what each part is doing now
import type { Incident } from "./live.ts";

export type NodeId = "chaos" | "shop" | "observer" | "brain" | "llm" | "gateway" | "kube" | "verifier" | "human";
export type NodeState = "idle" | "done" | "active" | "failed";

export interface FlowNode {
  id: NodeId;
  name: string;
  where: string;
  does: string;
  may: string;
  never: string;
}

// plain words for the side panel; facts come from IMPLEMENTATION.md §1.1 and §6
export const NODES: Record<NodeId, FlowNode> = {
  chaos: { id: "chaos", name: "Chaos panel", where: "port 7004, admin", does: "Breaks the shop on purpose so we can test the agent.",
    may: "Inject one of six faults, then reset the shop.", never: "Talk to the agent. The agent never reads its answers." },
  shop: { id: "shop", name: "The shop", where: "Kubernetes, namespace shop", does: "The web store under load: payment, checkout, cart and more.",
    may: "Send metrics to Prometheus and traces to Jaeger.", never: "Know the agent exists." },
  observer: { id: "observer", name: "Observer", where: "port 7001, read-only identity", does: "Checks every service every 5 s and opens an incident when one stays bad for 30 s.",
    may: "Read metrics, pods and every change made to the cluster.", never: "Change anything." },
  brain: { id: "brain", name: "Brain", where: "port 7002, read-only identity", does: "Finds the culprit from traces and recent changes, then picks one fix by rule.",
    may: "Read the cluster and ask the LLM to explain.", never: "Write to the cluster. It can only ask the gateway." },
  llm: { id: "llm", name: "LLM", where: "outside, via the brain", does: "Explains the fix in plain words and predicts when errors drop.",
    may: "Propose a fix only when no rule matched, and then a human must approve.", never: "Choose the fix when a rule matched, or reach the cluster." },
  gateway: { id: "gateway", name: "Gateway", where: "port 7003, the only write identity", does: "Runs every proposed fix through 8 checks. The first failed check decides.",
    may: "Use six undoable tools on named services.", never: "Talk to an LLM." },
  kube: { id: "kube", name: "Kubernetes API", where: "RBAC + admission policy", does: "The last wall. It refuses anything outside the agent's allowed list, even if our code has a bug.",
    may: "Accept patches to named Deployments and the flag ConfigMap.", never: "Let the agent delete, create, read secrets or change images to unknown sources." },
  verifier: { id: "verifier", name: "Verifier", where: "inside the gateway", does: "Watches health after a fix. If things got worse or did not recover, it undoes the fix.",
    may: "Undo its own action and wake a human.", never: "Undo a change a human made." },
  human: { id: "human", name: "On-call human", where: "Discord", does: "Gets a quiet note for a fix, or a loud page with Approve and Reject.",
    may: "Approve, reject or acknowledge.", never: "Be woken for a fix the agent has already proven." },
};

export const GATES = ["schema", "hands_off", "policy", "dry_run", "net_benefit", "freshness", "trust_gate", "execute"];

// which node an event comes from (the audit rail colours by this)
export const EVENT_NODE: Record<string, NodeId> = {
  incident_opened: "observer", alerts_grouped: "observer",
  culprit_found: "brain", major_incident: "brain", bundle_built: "brain", rule_matched: "brain",
  diagnosis_ready: "brain", injection_quarantined: "brain", tool_called: "brain",
  llm_called: "llm",
  checklist_step: "gateway",
  approval_requested: "human", approval_decided: "human",
  action_executed: "kube", blocked: "kube",
  verify_tick: "verifier", early_abort: "verifier", action_undone: "verifier", harm_check: "verifier",
  incident_resolved: "verifier", escalated: "human", handed_off: "human",
};

export interface Edge { from: NodeId; to: NodeId; label: string }

export const EDGES: Edge[] = [
  { from: "chaos", to: "shop", label: "faults" },
  { from: "shop", to: "observer", label: "metrics, pods, changes" },
  { from: "observer", to: "brain", label: "incident" },
  { from: "brain", to: "llm", label: "evidence" },
  { from: "brain", to: "gateway", label: "one fix, over MCP" },
  { from: "gateway", to: "human", label: "asks" },
  { from: "gateway", to: "kube", label: "patch" },
  { from: "kube", to: "shop", label: "rollout" },
  { from: "observer", to: "verifier", label: "health every 5 s" },
  { from: "verifier", to: "human", label: "card" },
];

// the order a healthy incident walks; the newest step reached is the "active" one
const PATH: NodeId[] = ["observer", "brain", "llm", "gateway", "human", "kube", "verifier"];

export interface FlowState {
  nodes: Record<NodeId, NodeState>;
  active: NodeId | null;
  gates: Record<string, "idle" | "passed" | "failed">;
}

function reached(inc: Incident): Record<NodeId, boolean> {
  const failedStep = inc.checklist.some((s) => !s.passed);
  return {
    chaos: false,
    shop: true,
    observer: true,
    brain: inc.culprit !== null || inc.pattern !== null,
    llm: inc.llmCalls > 0,
    gateway: inc.checklist.length > 0,
    human: inc.approval !== null || inc.outcome === "escalated" || inc.outcome === "handed_off"
      || (failedStep && inc.action === null),
    kube: inc.action !== null || inc.blocked > 0,
    verifier: inc.ticks.length > 0 || inc.harmClean !== null,
  };
}

// node colours for one incident; `last` is the type of the newest event seen for it
export function flowState(inc: Incident | null, last: string | null): FlowState {
  const nodes = Object.fromEntries(Object.keys(NODES).map((k) => [k, "idle"])) as Record<NodeId, NodeState>;
  const gates = Object.fromEntries(GATES.map((g) => [g, "idle"])) as FlowState["gates"];
  if (!inc) return { nodes, active: null, gates };
  for (const step of inc.checklist) if (step.name in gates) gates[step.name] = step.passed ? "passed" : "failed";

  const hit = reached(inc);
  for (const id of PATH) if (hit[id]) nodes[id] = "done";
  nodes.shop = "done";
  let active: NodeId | null = (last && EVENT_NODE[last]) || [...PATH].reverse().find((id) => hit[id]) || null;

  if (inc.outcome === "resolved") {
    active = null;
  } else if (inc.outcome) {
    // the agent stopped and woke someone: show where it stopped, and the person it woke
    if (inc.checklist.some((s) => !s.passed) && inc.action === null) nodes.gateway = "failed";
    if (inc.action !== null && inc.outcome === "escalated") nodes.verifier = "failed";  // fix did not hold
    nodes.human = "active";
    active = "human";
  } else if (active) {
    nodes[active] = "active";
  }
  if (inc.blocked > 0) nodes.kube = "failed";
  return { nodes, active, gates };
}

// the edge an incident is travelling on right now: the one that ends at the active node
export function liveEdge(state: FlowState): Edge | null {
  if (!state.active) return null;
  const into = EDGES.filter((e) => e.to === state.active && state.nodes[e.from] !== "idle");
  return into[into.length - 1] ?? null;
}
