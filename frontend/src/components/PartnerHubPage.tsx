import type { Agent, DiscoveryDocument, NetworkPolicy, PartnerEvaluation, PartnerPolicy } from "../lib/types";
import brandLogo from "../assets/agentlayer-logo.png";

type PartnerHubPageProps = {
  agents: Agent[];
  discovery: DiscoveryDocument | null;
  networkPolicy: NetworkPolicy | null;
  partnerPolicies: PartnerPolicy[];
  selectedAgentId: string;
  selectedPartner: string;
  simulatedEvaluation: PartnerEvaluation | null;
  busy: boolean;
  onAgentChange: (agentId: string) => void;
  onPartnerChange: (partner: string) => void;
  onRunSimulation: () => Promise<void>;
};

export function PartnerHubPage({
  agents,
  discovery,
  networkPolicy,
  partnerPolicies,
  selectedAgentId,
  selectedPartner,
  simulatedEvaluation,
  busy,
  onAgentChange,
  onPartnerChange,
  onRunSimulation,
}: PartnerHubPageProps) {
  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) || null;

  return (
    <div className="page-shell docs-shell">
      <div className="background-radial background-radial-one" />
      <div className="background-radial background-radial-two" />
      <header className="hero docs-hero">
        <nav className="topbar">
          <div className="brand-lockup">
            <div className="brand-mark brand-mark-logo">
              <img className="brand-logo-tile" src={brandLogo} alt="AgentLayer logo" />
            </div>
            <div>
              <div className="brand-title">AgentLayer Integrations</div>
              <div className="brand-subtitle">Integration surfaces, policy pages, and live evaluation checks</div>
            </div>
          </div>
          <div className="nav-links">
            <a href="/">Home</a>
            <a href="/docs">Docs</a>
            {partnerPolicies.map((policy) => (
              <a href={`#${policy.partner}`} key={policy.partner}>
                {policy.partner}
              </a>
            ))}
          </div>
        </nav>

        <div className="docs-hero-card">
          <div>
            <span className="eyebrow">Integration hub</span>
            <h1>Each integration profile can get a dedicated onboarding surface.</h1>
            <p>
              This page shows the access rules, scopes, requirements, and a live evaluation of whether
              a specific agent would be admitted into an ecosystem today.
            </p>
          </div>
          <div className="signal-list">
            <div>
              <strong>Live evaluation</strong>
              <p>
                It runs the real partner-evaluation endpoint and shows whether a chosen agent would be allowed or blocked,
                and exactly why.
              </p>
            </div>
            <div>
              <strong>Important note</strong>
              <p>
                Names like Moltbook or Render are shown here as integration profiles and examples, not as a claim of a formal
                commercial partnership.
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="content docs-content">
        <section className="panel split-panel">
          <div>
              <div className="panel-header">
                <div>
                  <h2>Partner Evaluation Simulator</h2>
                  <p>Choose an agent and an integration profile, then run the same check that a real integration would call.</p>
                </div>
              </div>
            <div className="stack">
              <label>
                <span>Agent</span>
                <select value={selectedAgentId} onChange={(event) => onAgentChange(event.target.value)}>
                  <option value="">Select an agent</option>
                  {agents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name} @{agent.handle}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Integration profile</span>
                <select value={selectedPartner} onChange={(event) => onPartnerChange(event.target.value)}>
                  {partnerPolicies.map((policy) => (
                    <option key={policy.partner} value={policy.partner}>
                      {policy.partner}
                    </option>
                  ))}
                </select>
              </label>
              <button className="action-button secondary" disabled={!selectedAgentId || busy} onClick={() => void onRunSimulation()} type="button">
                {busy ? "Running evaluation..." : "Run Partner Evaluation"}
              </button>
            </div>
          </div>
          <div className="callout-card">
            <span className="identity-chip">Simulation result</span>
            {simulatedEvaluation ? (
              <>
                <h3>
                  {simulatedEvaluation.allowed ? "Allowed ✅" : "Blocked"}
                  {" "}
                  for {simulatedEvaluation.partner}
                </h3>
                <p className="secondary-copy">
                  {selectedAgent?.name || "Selected agent"} is currently {simulatedEvaluation.agent.access_tier} tier.
                  Result reason: {simulatedEvaluation.reason.replace(/_/g, " ")}.
                </p>
                <div className="token-row">
                  <span className="token neutral">execution {simulatedEvaluation.agent.trust_lenses.execution.toFixed(1)}</span>
                  <span className="token neutral">payment {simulatedEvaluation.agent.trust_lenses.payment.toFixed(1)}</span>
                  <span className="token neutral">research {simulatedEvaluation.agent.trust_lenses.research.toFixed(1)}</span>
                  <span className="token neutral">sybil {simulatedEvaluation.agent.sybil_risk_score.toFixed(1)}</span>
                </div>
              </>
            ) : (
              <p className="secondary-copy">Run the simulator to see a real allow/block decision.</p>
            )}
          </div>
        </section>

        <section className="panel">
            <div className="panel-header">
              <div>
                <h2>Dedicated Integration Pages</h2>
                <p>Each integration profile has its own visible policy card and can be linked directly from docs or outreach.</p>
              </div>
            </div>
          <div className="partner-page-grid">
            {partnerPolicies.map((policy) => {
              const matchingExample = (networkPolicy?.integration_examples || []).find((item) =>
                item.name.toLowerCase().includes(policy.partner.replace("-", " ")),
              );
              return (
                <article className="partner-page-card" id={policy.partner} key={policy.partner}>
                  <div className="partner-eval-head">
                    <strong>{policy.partner}</strong>
                    <span>{policy.category}</span>
                  </div>
                  <p className="secondary-copy">
                    Minimum tier: {policy.min_access_tier}. Dedicated integration view for teams that need to
                    understand exactly what AgentLayer expects before access is granted.
                  </p>
                  <div className="token-row compact">
                    {policy.default_scopes.map((scope) => (
                      <span className="token neutral" key={scope}>
                        {scope}
                      </span>
                    ))}
                  </div>
                  <div className="signal-list compact-signal-list top-spaced">
                    {policy.requirements.map((requirement) => (
                      <div key={requirement}>
                        <strong>Requirement</strong>
                        <p>{requirement}</p>
                      </div>
                    ))}
                    {matchingExample ? (
                      <div>
                        <strong>Integration flow</strong>
                        <p>{matchingExample.goal}</p>
                      </div>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <section className="panel split-panel">
          <div>
              <div className="panel-header">
                <div>
                  <h2>Integration Hooks</h2>
                  <p>These are the machine-readable endpoints an ecosystem is expected to consume.</p>
                </div>
              </div>
            <div className="discovery-list">
              <div>
                <span>Resolve handle</span>
                <code>{networkPolicy?.integration_hooks.resolve_handle_url_template || discovery?.resolve_handle_url_template || "/api/v1/agents/resolve/{handle}"}</code>
              </div>
              <div>
                <span>Partner evaluation</span>
                <code>{networkPolicy?.integration_hooks.partner_evaluation_url_template || discovery?.partner_evaluation_url_template || "/api/v1/agents/{agent_id}/partner-evaluation/{partner}"}</code>
              </div>
              <div>
                <span>Agent keys</span>
                <code>{networkPolicy?.integration_hooks.agent_keys_url_template || discovery?.agent_keys_url_template || "/api/v1/agents/{agent_id}/keys"}</code>
              </div>
              <div>
                <span>Audit events</span>
                <code>{networkPolicy?.integration_hooks.audit_events_url || discovery?.audit_events_url || "/api/v1/audit/events"}</code>
              </div>
            </div>
          </div>
          <div className="callout-card">
            <span className="identity-chip">Why this page exists</span>
            <h3>Integrations need their own onboarding surface.</h3>
            <p className="secondary-copy">
              An integration-specific page removes friction. Instead of reading a generic homepage, a team integrating a
              social agent network, compute rail, or settlement layer can go straight to the exact trust policy and test it live.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
