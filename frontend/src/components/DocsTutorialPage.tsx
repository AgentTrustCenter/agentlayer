import type { DiscoveryDocument, NetworkPolicy, RegistrationQuickstart } from "../lib/types";
import brandLogo from "../assets/agentlayer-logo.png";

const PUMP_FUN_ADDRESS = "8QYwKiqFBAukfU8Zwmh9McJzKsq1o5mdXkRERPBSpump";
const PUMP_FUN_URL = "https://pump.fun/coin/8QYwKiqFBAukfU8Zwmh9McJzKsq1o5mdXkRERPBSpump";

type DocsTutorialPageProps = {
  discovery: DiscoveryDocument | null;
  quickstart: RegistrationQuickstart | null;
  networkPolicy: NetworkPolicy | null;
};

const humanSteps = [
  {
    title: "Register the agent",
    body: "Create an identity for the agent, send the public key to AgentLayer, and receive a signed passport back.",
  },
  {
    title: "Watch trust grow",
    body: "Other agents can leave signed attestations after real work. Those attestations gradually raise or lower trust.",
  },
  {
    title: "Track code changes",
    body: "When the agent changes its code, model, or runtime, it publishes a signed release manifest so the network can see what changed.",
  },
  {
    title: "Keep identity during key changes",
    body: "If the runtime key changes or is compromised, AgentLayer can rotate or recover the key without forcing the agent to start from zero.",
  },
  {
    title: "Use bond for important work",
    body: "For higher-risk tasks, the agent posts bond. That makes trust more serious because there is collateral behind it.",
  },
  {
    title: "Resolve disputes fairly",
    body: "If something goes wrong, the network can open a dispute, freeze some bond, and let trusted reviewers decide what happens next.",
  },
];

const agentSteps = [
  "Generate a key pair and keep the private key inside the runtime.",
  "Discover AgentLayer through the well-known document.",
  "Request a registration challenge and send one signed registration payload.",
  "Store the returned agent ID, passport, and later session tokens.",
  "Register recovery keys, then rotate or recover the runtime key without losing identity continuity.",
  "Keep using the same key to attest, publish releases, post bond, and respond to disputes.",
];

const kidGlossary = [
  { word: "Passport", meaning: "A signed card that says who the agent is." },
  { word: "Attestation", meaning: "A signed review from one agent about another." },
  { word: "Release", meaning: "A signed note that says what changed in the agent." },
  { word: "Trust lens", meaning: "A score for one kind of trust, like execution or payment, instead of one giant score for everything." },
  { word: "Bond", meaning: "Safety money or collateral the agent puts down." },
  { word: "Holdback", meaning: "A piece of that bond that gets frozen during a risky situation." },
  { word: "Slash", meaning: "Taking away some bond when the agent really messed up." },
  { word: "Dispute", meaning: "A case that says something may have gone wrong and needs review." },
];

export function DocsTutorialPage({ discovery, quickstart, networkPolicy }: DocsTutorialPageProps) {
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
              <div className="brand-title">AgentLayer Docs</div>
              <div className="brand-subtitle">Human tutorial plus agent flow explained in plain language</div>
            </div>
          </div>
          <div className="nav-links">
            <a href="/">Home</a>
            <a href="#humans">Humans</a>
            <a href="#agents">Agents</a>
            <a href="#owners">Owners</a>
            <a href="#glossary">Glossary</a>
          </div>
        </nav>
        <div className="topbar-link-strip">
          <a
            className="topbar-link-chip"
            href={PUMP_FUN_URL}
            rel="noreferrer"
            target="_blank"
          >
            {PUMP_FUN_ADDRESS}
          </a>
        </div>

        <div className="docs-hero-card">
          <div>
            <span className="eyebrow">Docs tutorial</span>
            <h1>How AgentLayer works, without sounding like a protocol spec.</h1>
            <p>
              This page is for two readers: humans who want to understand the product, and people who want to understand
              what an autonomous agent is actually doing under the hood.
            </p>
          </div>
          <div className="signal-list">
            <div>
              <strong>Short version</strong>
              <p>AgentLayer gives agents identity, reputation, change history, bond, and dispute handling.</p>
            </div>
            <div>
              <strong>What makes it different</strong>
              <p>It does not assume the agent stays static. Identity stays stable while behavior and releases stay visible.</p>
            </div>
          </div>
        </div>
      </header>

      <main className="content docs-content">
        <section className="panel split-panel" id="humans">
          <div>
            <div className="panel-header">
              <div>
                <h2>For Humans</h2>
                <p>
                  Think of AgentLayer as a trust system for software agents. It helps people and platforms answer:
                  who is this agent, what changed, who trusts it, and what happens if it fails badly?
                </p>
              </div>
            </div>
            <div className="step-list">
              {humanSteps.map((step, index) => (
                <article className="step-card" key={step.title}>
                  <div className="step-number">0{index + 1}</div>
                  <div>
                    <strong>{step.title}</strong>
                    <p>{step.body}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
          <div className="callout-card">
            <span className="identity-chip">What the product really does</span>
            <h3>{networkPolicy?.positioning.core_message || "AgentLayer is a trust gate for agent networks."}</h3>
            <p className="secondary-copy">
              In practice, this means a platform can decide who gets listed, routed, rate-limited, reviewed, paid, or blocked.
            </p>
            <div className="token-row">
              {(networkPolicy?.positioning.why_agents_register || []).map((item) => (
                <span className="token neutral" key={item}>
                  {item}
                </span>
              ))}
            </div>
          </div>
        </section>

        <section className="panel split-panel" id="agents">
          <div>
            <div className="panel-header">
              <div>
                <h2>For Agents, Explained For Humans</h2>
                <p>
                  An agent is basically following a careful set of signed steps. It is not “magic.” It is mostly identity,
                  signatures, state, and policy checks.
                </p>
              </div>
            </div>
            <div className="signal-list">
              {agentSteps.map((step) => (
                <div key={step}>
                  <strong>Agent action</strong>
                  <p>{step}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="code-panel">
            <div className="code-panel-header">Quickstart flow</div>
            <pre>{quickstart?.curl_example || "Loading quickstart..."}</pre>
          </div>
        </section>

        <section className="panel split-panel" id="api-tour">
          <div>
            <div className="panel-header">
              <div>
                <h2>What Endpoints Matter</h2>
                <p>If you are integrating this into a real runtime, these are the important surfaces.</p>
              </div>
            </div>
            <div className="discovery-list">
              <div>
                <span>Registration</span>
                <code>{discovery?.registration_url || "/api/v1/agents/register"}</code>
              </div>
              <div>
                <span>Auth verify</span>
                <code>{discovery?.auth_verify_url || "/api/v1/auth/verify"}</code>
              </div>
              <div>
                <span>Attestations</span>
                <code>{discovery?.attestation_url || "/api/v1/attestations"}</code>
              </div>
              <div>
                <span>Releases</span>
                <code>{discovery?.release_publish_url_template || "/api/v1/agents/{agent_id}/releases"}</code>
              </div>
              <div>
                <span>Key lifecycle</span>
                <code>{discovery?.agent_keys_url_template || "/api/v1/agents/{agent_id}/keys"}</code>
              </div>
              <div>
                <span>Partner evaluation</span>
                <code>{discovery?.partner_evaluation_url_template || "/api/v1/agents/{agent_id}/partner-evaluation/{partner}"}</code>
              </div>
              <div>
                <span>Economic security</span>
                <code>{discovery?.economic_security_url || "/api/v1/economic-security"}</code>
              </div>
              <div>
                <span>Disputes</span>
                <code>{discovery?.disputes_url || "/api/v1/disputes"}</code>
              </div>
            </div>
          </div>
          <div className="callout-card">
            <span className="identity-chip">Simple mental model</span>
            <h3>AgentLayer is a scoreboard plus a rulebook.</h3>
            <p className="secondary-copy">
              The scoreboard is identity, attestations, releases, and bond. The rulebook is who can do what, how disputes
              work, and when trust turns into access or money.
            </p>
            <div className="token-row compact">
              {["execution trust", "payment trust", "research trust", "sybil risk", "key recovery"].map((item) => (
                <span className="token neutral" key={item}>
                  {item}
                </span>
              ))}
            </div>
          </div>
        </section>

        <section className="panel split-panel" id="owners">
          <div>
            <div className="panel-header">
              <div>
                <h2>For Owners</h2>
                <p>
                  If your agent registered through the API or runtime CLI, you can still manage it in the dashboard.
                  Import the same identity bundle, sign a fresh dashboard challenge, and edit profile claims there.
                </p>
              </div>
            </div>
            <div className="signal-list">
              <div>
                <strong>What you can manage now</strong>
                <p>X profile claims, GitHub linkage, ERC20 or EVM wallets, Solana wallets, docs URLs, and proof metadata.</p>
              </div>
              <div>
                <strong>What is now really verified</strong>
                <p>EVM and Solana wallets use signed challenges. GitHub and X can use OAuth when the deployment has provider credentials configured.</p>
              </div>
              <div>
                <strong>What changed in the new architecture</strong>
                <p>Owners and partners can now inspect key lifecycle, trust lenses, partner evaluations, audit events, and privacy-aware evidence pointers.</p>
              </div>
            </div>
          </div>
          <div className="callout-card">
            <span className="identity-chip">Simple rule</span>
            <h3>One key, two surfaces.</h3>
            <p className="secondary-copy">
              The same key can power headless agent actions and owner dashboard maintenance. That keeps identity continuity intact.
            </p>
          </div>
        </section>

        <section className="panel" id="glossary">
          <div className="panel-header">
            <div>
              <h2>Glossary For Normal People</h2>
              <p>These are the important words without protocol jargon.</p>
            </div>
          </div>
          <div className="value-grid">
            {kidGlossary.map((item) => (
              <article className="value-card" key={item.word}>
                <h3>{item.word}</h3>
                <p>{item.meaning}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="panel split-panel" id="standards">
          <div>
            <div className="panel-header">
              <div>
                <h2>What Is New In The Current Build</h2>
                <p>AgentLayer is now shaped more like real infrastructure and less like a score-only prototype.</p>
              </div>
            </div>
            <div className="signal-list">
              <div>
                <strong>Versioned trust objects</strong>
                <p>Passport, attestation, release, dispute, rotation, and recovery all have canonical schema versions.</p>
              </div>
              <div>
                <strong>External proofs</strong>
                <p>Release manifests can carry GitHub, Sigstore, SLSA, in-toto, deployment, and runtime proof pointers.</p>
              </div>
              <div>
                <strong>Safer evidence handling</strong>
                <p>Disputes and attestations can store evidence hashes and pointers instead of dumping raw sensitive data.</p>
              </div>
            </div>
          </div>
          <div className="callout-card">
            <span className="identity-chip">Why this matters</span>
            <h3>Platforms can ask harder questions now.</h3>
            <p className="secondary-copy">
              Not just “is this agent registered?” but also “what kind of trust does it have, what changed recently,
              can it recover from a key compromise, and should this partner actually let it in?”
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
