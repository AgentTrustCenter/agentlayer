import type { Agent } from "../lib/types";

type AgentSpotlightProps = {
  agents: Agent[];
};

export function AgentSpotlight({ agents }: AgentSpotlightProps) {
  return (
    <div className="agent-grid">
      {agents.map((agent) => (
        <article className="agent-card" key={agent.id}>
          <div className="agent-card-head">
            <div>
              <div className="agent-name">{agent.name}</div>
              <div className="agent-handle">@{agent.handle}</div>
            </div>
            <span className="score-pill">{agent.trust_score.toFixed(1)}</span>
          </div>
          <div className="badge-row">
            <span className="status-badge">{agent.access_tier}</span>
            <span className="status-badge muted">{agent.verification_status}</span>
            {agent.release_warning_active ? <span className="status-badge warning">release warning</span> : null}
          </div>
          <p className="agent-description">{agent.description}</p>
          <div className="token-row">
            {agent.capabilities.slice(0, 4).map((capability) => (
              <span className="token" key={capability}>
                {capability}
              </span>
            ))}
          </div>
          <div className="token-row compact">
            {agent.badges.slice(0, 4).map((badge) => (
              <span className="token neutral" key={badge}>
                {badge}
              </span>
            ))}
          </div>
          <dl className="agent-metrics">
            <div>
              <dt>Inbound</dt>
              <dd>{agent.incoming_attestations_count}</dd>
            </div>
            <div>
              <dt>Outbound</dt>
              <dd>{agent.outgoing_attestations_count}</dd>
            </div>
            <div>
              <dt>Bonded</dt>
              <dd>{agent.economic_security.net_bonded_balance.toFixed(1)}</dd>
            </div>
          </dl>
          <div className="lens-grid compact-lens-grid">
            <article className="lens-card compact-lens-card">
              <span>Execution</span>
              <strong>{(agent.trust_lenses?.execution || agent.trust_score).toFixed(0)}</strong>
            </article>
            <article className="lens-card compact-lens-card">
              <span>Payment</span>
              <strong>{(agent.trust_lenses?.payment || agent.trust_score).toFixed(0)}</strong>
            </article>
            <article className="lens-card compact-lens-card">
              <span>Research</span>
              <strong>{(agent.trust_lenses?.research || agent.trust_score).toFixed(0)}</strong>
            </article>
          </div>
          {agent.next_unlocks[0] ? <p className="unlock-copy">{agent.next_unlocks[0]}</p> : null}
          <p className="unlock-copy">
            Security tier: {agent.economic_security.security_tier}
            {agent.economic_security.active_holdback ? " • active holdback" : ""}
            {agent.economic_security.slashed_total > 0 ? ` • slashed ${agent.economic_security.slashed_total.toFixed(1)}` : ""}
          </p>
          <p className="unlock-copy">
            Identity v{agent.identity_version || 1} • Sybil risk {(agent.sybil_risk_score || 0).toFixed(1)}
          </p>
          {agent.latest_release ? (
            <p className="unlock-copy">
              Latest release: {agent.latest_release.version_label}
              {agent.latest_release.commit_sha ? ` • ${agent.latest_release.commit_sha.slice(0, 10)}` : ""}
            </p>
          ) : null}
        </article>
      ))}
    </div>
  );
}
