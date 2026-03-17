import { useState } from "react";

import type { ActiveIdentity } from "../lib/types";

type IdentityImportPanelProps = {
  onImport: (identity: ActiveIdentity) => void;
};

export function IdentityImportPanel({ onImport }: IdentityImportPanelProps) {
  const [rawValue, setRawValue] = useState("");
  const [error, setError] = useState("");
  const [manualAgentId, setManualAgentId] = useState("");
  const [manualName, setManualName] = useState("");
  const [manualPrivateKey, setManualPrivateKey] = useState("");
  const [manualPublicKey, setManualPublicKey] = useState("");

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Import Existing Identity</h2>
          <p>
            Paste a previously saved identity bundle from an existing agent runtime to reactivate that local
            signing identity in the dashboard.
          </p>
        </div>
      </div>
      <form
        className="stack"
        onSubmit={(event) => {
          event.preventDefault();
          try {
            const parsed = JSON.parse(rawValue) as ActiveIdentity;
            onImport(parsed);
            setError("");
          } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Invalid identity bundle JSON.");
          }
        }}
      >
        <label>
          <span>Identity bundle JSON</span>
          <textarea
            value={rawValue}
            onChange={(event) => setRawValue(event.target.value)}
            rows={10}
            placeholder='{"agentId":"...","name":"Atlas Executor","privateKeyPem":"-----BEGIN PRIVATE KEY-----...","publicKeyPem":"-----BEGIN PUBLIC KEY-----..."}'
            required
          />
        </label>
        <button className="ghost-button" type="submit">
          Activate Existing Identity
        </button>
        {error ? <div className="inline-error">{error}</div> : null}
      </form>
      <form
        className="stack top-spaced"
        onSubmit={(event) => {
          event.preventDefault();
          if (!manualAgentId || !manualName || !manualPrivateKey || !manualPublicKey) {
            setError("Manual import requires agent ID, name, private key, and public key.");
            return;
          }
          onImport({
            agentId: manualAgentId,
            name: manualName,
            privateKeyPem: manualPrivateKey,
            publicKeyPem: manualPublicKey,
          });
          setError("");
        }}
      >
        <div className="panel-header compact-panel-header">
          <div>
            <h3>Manual key import</h3>
            <p>Use this if you only have the registered agent ID and PEM keys, not the exported identity JSON.</p>
          </div>
        </div>
        <label>
          <span>Agent ID</span>
          <input value={manualAgentId} onChange={(event) => setManualAgentId(event.target.value)} />
        </label>
        <label>
          <span>Agent name</span>
          <input value={manualName} onChange={(event) => setManualName(event.target.value)} />
        </label>
        <label>
          <span>Private key PEM</span>
          <textarea value={manualPrivateKey} onChange={(event) => setManualPrivateKey(event.target.value)} rows={7} />
        </label>
        <label>
          <span>Public key PEM</span>
          <textarea value={manualPublicKey} onChange={(event) => setManualPublicKey(event.target.value)} rows={6} />
        </label>
        <button className="ghost-button" type="submit">
          Activate Manual Identity
        </button>
      </form>
    </section>
  );
}
