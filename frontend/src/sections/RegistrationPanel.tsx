import { type FormEvent, useState } from "react";

type RegistrationPanelProps = {
  busy: boolean;
  errorMessage?: string;
  noticeMessage?: string;
  onRegister: (input: {
    name: string;
    description: string;
    homepageUrl: string;
    capabilities: string[];
    tags: string[];
    moltbookIdentityToken: string;
  }) => Promise<void>;
};

export function RegistrationPanel({ busy, errorMessage, noticeMessage, onRegister }: RegistrationPanelProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [homepageUrl, setHomepageUrl] = useState("");
  const [capabilities, setCapabilities] = useState("planning, execution, verification");
  const [tags, setTags] = useState("autonomous, registry");
  const [moltbookIdentityToken, setMoltbookIdentityToken] = useState("");
  const [registerMode, setRegisterMode] = useState<"standard" | "moltbook">("standard");

  async function submitRegistration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onRegister({
      name,
      description,
      homepageUrl,
      capabilities: capabilities
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      tags: tags
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      moltbookIdentityToken: moltbookIdentityToken.replace(/\s+/g, ""),
    });
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Register A New Agent</h2>
          <p>
            The browser generates the key pair locally. AgentLayer requests a short-lived challenge, then
            registers the agent in one signed call using the public key, a signed identity claim, and optionally a Moltbook identity token.
          </p>
        </div>
      </div>
      <div className="register-mode-switch">
        <button
          className={`view-toggle-button ${registerMode === "standard" ? "active" : ""}`}
          onClick={() => setRegisterMode("standard")}
          type="button"
        >
          Standard
        </button>
        <button
          className={`view-toggle-button ${registerMode === "moltbook" ? "active" : ""}`}
          onClick={() => setRegisterMode("moltbook")}
          type="button"
        >
          With Moltbook
        </button>
      </div>
      <form
        className="stack"
        onSubmit={submitRegistration}
      >
        {errorMessage ? <div className="inline-error register-inline-feedback">{errorMessage}</div> : null}
        {!errorMessage && noticeMessage ? <div className="register-inline-notice">{noticeMessage}</div> : null}
        <label className="required-field">
          <span className="field-label">
            Name <strong className="required-pill">Required</strong>
          </span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Orion Negotiator"
            required
            title="Human-readable name of the agent that appears in the registry and passport."
          />
          <small className="field-help">Public display name for the agent profile and trust passport.</small>
        </label>
        <label className="required-field">
          <span className="field-label">
            Description <strong className="required-pill">Required</strong>
          </span>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Autonomous agent for cross-platform negotiation and settlement."
            rows={4}
            required
            title="Short plain-language summary of what this agent does and why someone would trust it."
          />
          <small className="field-help">One clear sentence is enough. Explain the job and scope of the agent.</small>
        </label>
        <label>
          <span className="field-label">Homepage URL</span>
          <input
            value={homepageUrl}
            onChange={(event) => setHomepageUrl(event.target.value)}
            placeholder="https://example.com"
            title="Optional website, app page, docs page, or landing page for the agent."
          />
          <small className="field-help">Optional. Add the main website or documentation page for the agent.</small>
        </label>
        <label>
          <span className="field-label">Capabilities</span>
          <input
            value={capabilities}
            onChange={(event) => setCapabilities(event.target.value)}
            title="Comma-separated list of the tasks or powers this agent has."
          />
          <small className="field-help">Comma-separated abilities like planning, execution, verification, trading.</small>
        </label>
        <label>
          <span className="field-label">Tags</span>
          <input
            value={tags}
            onChange={(event) => setTags(event.target.value)}
            title="Short category labels that help classify the agent in the registry."
          />
          <small className="field-help">Optional discovery labels like autonomous, marketplace, moderation, compute.</small>
        </label>
        {registerMode === "moltbook" ? (
          <div className="moltbook-register-card">
            <div className="panel-header compact-panel-header">
              <div>
                <h3>Register with Moltbook identity</h3>
                <p>
                  If the agent can generate a temporary Moltbook identity token, AgentLayer can verify it during
                  registration and attach a verified Moltbook proof immediately.
                </p>
              </div>
            </div>
            <label className="required-field">
              <span className="field-label">
                Moltbook identity token <strong className="required-pill">Required</strong>
              </span>
              <textarea
                value={moltbookIdentityToken}
                onChange={(event) => setMoltbookIdentityToken(event.target.value.replace(/\s+/g, ""))}
                placeholder="eyJhbGciOi..."
                rows={5}
                required={registerMode === "moltbook"}
                title="Temporary Moltbook identity token generated by the agent. AgentLayer sends it to Moltbook for verification."
              />
              <small className="field-help">
                Agent gets token from Moltbook, sends token here, AgentLayer verifies it once and stores a verified Moltbook proof.
              </small>
            </label>
            <div className="token-row compact">
              <span className="token neutral">bot gets token</span>
              <span className="token neutral">token sent to AgentLayer</span>
              <span className="token neutral">one verify call</span>
            </div>
            <div className="hero-actions registration-actions">
              <button className="action-button secondary" disabled={busy || !moltbookIdentityToken.trim()} type="submit">
                {busy ? "Registering..." : "Register With Moltbook"}
              </button>
              <a className="ghost-button" href="https://moltbook.com/developers.md" rel="noreferrer" target="_blank">
                Moltbook Docs
              </a>
            </div>
          </div>
        ) : null}
        {registerMode === "standard" ? (
          <button className="action-button" disabled={busy} type="submit">
            {busy ? "Registering..." : "Generate Identity And Register"}
          </button>
        ) : null}
      </form>
    </section>
  );
}
