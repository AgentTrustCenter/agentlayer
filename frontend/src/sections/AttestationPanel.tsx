import { useMemo, useState } from "react";

import type { ActiveIdentity, Agent } from "../lib/types";

type AttestationPanelProps = {
  activeIdentity: ActiveIdentity | null;
  agents: Agent[];
  busy: boolean;
  onCreate: (input: {
    issuerAgentId: string;
    subjectAgentId: string;
    kind: string;
    summary: string;
    evidenceUrl: string;
    interactionRef: string;
    scoreDelta: number;
    confidence: number;
  }) => Promise<void>;
};

export function AttestationPanel({ activeIdentity, agents, busy, onCreate }: AttestationPanelProps) {
  const [subjectAgentId, setSubjectAgentId] = useState("");
  const [kind, setKind] = useState("collaboration_success");
  const [summary, setSummary] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [interactionRef, setInteractionRef] = useState("");
  const [scoreDelta, setScoreDelta] = useState(0.85);
  const [confidence, setConfidence] = useState(0.8);

  const subjectOptions = useMemo(
    () => agents.filter((agent) => agent.id !== activeIdentity?.agentId),
    [activeIdentity?.agentId, agents],
  );

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Issue A Signed Attestation</h2>
          <p>
            Attestations are signed with the active local identity and update the shared network trust graph.
          </p>
        </div>
        {activeIdentity ? <span className="identity-chip">Active: {activeIdentity.name}</span> : null}
      </div>
      <form
        className="stack"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!activeIdentity) {
            return;
          }
          await onCreate({
            issuerAgentId: activeIdentity.agentId,
            subjectAgentId,
            kind,
            summary,
            evidenceUrl,
            interactionRef,
            scoreDelta,
            confidence,
          });
        }}
      >
        <label className="required-field">
          <span className="field-label">
            Subject agent <strong className="required-pill">Required</strong>
          </span>
          <select
            value={subjectAgentId}
            onChange={(event) => setSubjectAgentId(event.target.value)}
            required
            disabled={!activeIdentity}
            title="Choose the agent you are reviewing or attesting after a real interaction."
          >
            <option value="">Select an agent</option>
            {subjectOptions.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name} ({agent.handle})
              </option>
            ))}
          </select>
          <small className="field-help">This is the agent whose reputation will change.</small>
        </label>
        <label className="required-field">
          <span className="field-label">
            Attestation kind <strong className="required-pill">Required</strong>
          </span>
          <select value={kind} onChange={(event) => setKind(event.target.value)} required disabled={!activeIdentity}>
            <option value="collaboration_success">Collaboration success</option>
            <option value="task_completed">Task completed</option>
            <option value="payment_honored">Payment honored</option>
            <option value="data_accuracy">Data accuracy</option>
            <option value="verification_passed">Verification passed</option>
            <option value="incident_report">Incident report</option>
            <option value="policy_breach">Policy breach</option>
          </select>
          <small className="field-help">Pick the type that best describes the interaction outcome.</small>
        </label>
        <label className="required-field">
          <span className="field-label">
            Summary <strong className="required-pill">Required</strong>
          </span>
          <textarea
            value={summary}
            onChange={(event) => setSummary(event.target.value)}
            placeholder="Executed settlement and returned verified outcome within SLA."
            rows={3}
            required
            disabled={!activeIdentity}
            title="Explain what happened in one short review-style sentence."
          />
          <small className="field-help">Write the core result or issue clearly enough that another human could understand it fast.</small>
        </label>
        <label>
          <span className="field-label">Evidence URL</span>
          <input
            value={evidenceUrl}
            onChange={(event) => setEvidenceUrl(event.target.value)}
            disabled={!activeIdentity}
            title="Optional link to logs, proofs, screenshots, receipts, or another evidence source."
          />
          <small className="field-help">Optional. Add proof if you want downstream reviewers to inspect it.</small>
        </label>
        <label>
          <span className="field-label">Interaction reference</span>
          <input
            value={interactionRef}
            onChange={(event) => setInteractionRef(event.target.value)}
            disabled={!activeIdentity}
            title="Optional internal job ID, order ID, trade ID, or conversation reference."
          />
          <small className="field-help">Optional. Use a job ID or internal reference if the interaction is tracked elsewhere.</small>
        </label>
        <div className="field-grid">
          <label className="required-field">
            <span className="field-label">
              Score delta <strong className="required-pill">Required</strong>
            </span>
            <input
              type="number"
              min="-1"
              max="1"
              step="0.05"
              value={scoreDelta}
              onChange={(event) => setScoreDelta(Number(event.target.value))}
              disabled={!activeIdentity}
              title="How strongly this event should raise or lower trust."
            />
            <small className="field-help">Positive raises trust, negative lowers it. Keep it proportional.</small>
          </label>
          <label className="required-field">
            <span className="field-label">
              Confidence <strong className="required-pill">Required</strong>
            </span>
            <input
              type="number"
              min="0.1"
              max="1"
              step="0.05"
              value={confidence}
              onChange={(event) => setConfidence(Number(event.target.value))}
              disabled={!activeIdentity}
              title="How certain you are that the attestation is fair and accurate."
            />
            <small className="field-help">Use 1.0 only when you are very sure about the claim.</small>
          </label>
        </div>
        <button className="action-button secondary" disabled={!activeIdentity || busy} type="submit">
          {busy ? "Signing..." : "Sign And Publish Attestation"}
        </button>
      </form>
    </section>
  );
}
