import { useEffect, useState } from "react";

import type { ActiveIdentity, Agent, ExternalProof, WalletClaim } from "../lib/types";

type OwnerConsolePanelProps = {
  activeIdentity: ActiveIdentity | null;
  ownedAgent: Agent | null;
  busy: boolean;
  sessionScopes: string[];
  onLogin: () => Promise<void>;
  onVerifyWallet: (chain: "erc20" | "solana") => Promise<void>;
  onStartSocialProof: (provider: "github" | "x") => Promise<void>;
  onSave: (payload: {
    description: string;
    homepageUrl: string;
    capabilities: string[];
    tags: string[];
    profileLinks: Record<string, string>;
    walletClaims: WalletClaim[];
    externalProofs: ExternalProof[];
  }) => Promise<void>;
};

function shortenIdentifier(value: string | undefined | null) {
  if (!value) {
    return "";
  }
  if (value.length <= 12) {
    return value;
  }
  return `${value.slice(0, 5)}...${value.slice(-5)}`;
}

function formatHandle(value: string | undefined | null) {
  if (!value) {
    return "";
  }
  return value.startsWith("@") ? value : `@${value}`;
}

export function OwnerConsolePanel({
  activeIdentity,
  ownedAgent,
  busy,
  sessionScopes,
  onLogin,
  onVerifyWallet,
  onStartSocialProof,
  onSave,
}: OwnerConsolePanelProps) {
  const [description, setDescription] = useState("");
  const [homepageUrl, setHomepageUrl] = useState("");
  const [capabilities, setCapabilities] = useState("");
  const [tags, setTags] = useState("");
  const [docsUrl, setDocsUrl] = useState("");
  const [supportUrl, setSupportUrl] = useState("");
  const [proofUrl, setProofUrl] = useState("");
  const [proofNotes, setProofNotes] = useState("");
  const verifiedGithub = (ownedAgent?.external_proofs || []).find((item) => item.type === "github_oauth" && item.status === "verified");
  const verifiedX = (ownedAgent?.external_proofs || []).find((item) => item.type === "x_oauth" && item.status === "verified");
  const verifiedEvm = (ownedAgent?.wallet_claims || []).find((item) => (item.chain === "erc20" || item.chain === "evm") && item.status === "verified");
  const verifiedSol = (ownedAgent?.wallet_claims || []).find((item) => item.chain === "solana" && item.status === "verified");
  const isLoggedIn = sessionScopes.length > 0;

  useEffect(() => {
    if (!ownedAgent) {
      return;
    }
    setDescription(ownedAgent.description || "");
    setHomepageUrl(ownedAgent.homepage_url || "");
    setCapabilities((ownedAgent.capabilities || []).join(", "));
    setTags((ownedAgent.tags || []).join(", "));
    setDocsUrl(ownedAgent.profile_links?.docs_url || "");
    setSupportUrl(ownedAgent.profile_links?.support_url || "");
    const profileEvidence = (ownedAgent.external_proofs || []).find((item) => item.type === "profile_evidence");
    setProofUrl(profileEvidence?.proof_url || profileEvidence?.value || "");
    setProofNotes(profileEvidence?.notes || "");
  }, [ownedAgent]);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Owner Console</h2>
          <p>
            API-registered agents can be managed here after the owner signs in with the same agent key. Link X,
            GitHub, EVM wallets, and Solana wallets without breaking identity continuity.
          </p>
        </div>
        {activeIdentity ? <span className="identity-chip">Key loaded: {activeIdentity.name}</span> : null}
      </div>

      <div className={`owner-console-status ${isLoggedIn ? "owner-console-status-active" : ""}`}>
        <div>
          <strong>Dashboard login</strong>
          <p>
            {!ownedAgent
              ? "Import the identity bundle of a registered agent first."
              : isLoggedIn
                ? "Already logged in ✅ This owner session is active and can edit the public profile."
                : "This identity matches a registered agent. Sign the dashboard challenge to unlock profile editing."}
          </p>
        </div>
        <button className="ghost-button" type="button" disabled={!ownedAgent || busy || isLoggedIn} onClick={() => void onLogin()}>
          {busy ? "Signing in..." : isLoggedIn ? "Already Logged In ✅" : "Sign In With Agent Key"}
        </button>
      </div>

      <div className="token-row compact">
        {sessionScopes.length ? (
          sessionScopes.map((scope) => (
            <span className="token neutral" key={scope}>
              {scope}
            </span>
          ))
        ) : (
          <span className="token neutral">No active dashboard session yet</span>
        )}
      </div>

      <form
        className="stack"
        onSubmit={async (event) => {
          event.preventDefault();
          await onSave({
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
            profileLinks: {
              x_handle: ownedAgent?.profile_links?.x_handle || "",
              x_url: ownedAgent?.profile_links?.x_url || "",
              github_handle: ownedAgent?.profile_links?.github_handle || "",
              github_url: ownedAgent?.profile_links?.github_url || "",
              docs_url: docsUrl,
              support_url: supportUrl,
            },
            walletClaims: ownedAgent?.wallet_claims || [],
            externalProofs: [
              ...((ownedAgent?.external_proofs || []).filter((item) => item.type !== "profile_evidence")),
              ...(proofUrl
                ? [
                    {
                      type: "profile_evidence",
                      value: proofUrl,
                      status: "self_attested",
                      proof_url: proofUrl,
                      notes: proofNotes,
                    },
                  ]
                : []),
            ],
          });
        }}
      >
        <label>
          <span>Description</span>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={4}
            disabled={!ownedAgent}
          />
        </label>

        <div className="field-grid">
          <label>
            <span>Homepage URL</span>
            <input value={homepageUrl} onChange={(event) => setHomepageUrl(event.target.value)} disabled={!ownedAgent} />
          </label>
          <label>
            <span>Docs URL</span>
            <input value={docsUrl} onChange={(event) => setDocsUrl(event.target.value)} disabled={!ownedAgent} />
          </label>
        </div>

        <div className="field-grid">
          <label>
            <span>Capabilities</span>
            <input value={capabilities} onChange={(event) => setCapabilities(event.target.value)} disabled={!ownedAgent} />
          </label>
          <label>
            <span>Tags</span>
            <input value={tags} onChange={(event) => setTags(event.target.value)} disabled={!ownedAgent} />
          </label>
        </div>

        <div className="verification-actions">
          <div className="verification-status-card">
            <strong>X verification</strong>
            <span>{verifiedX ? `${formatHandle(verifiedX.value)} verified ✅` : "Not verified yet"}</span>
          </div>
          <button className="ghost-button" type="button" disabled={!ownedAgent || sessionScopes.length === 0 || busy || Boolean(verifiedX)} onClick={() => void onStartSocialProof("x")}>
            {verifiedX ? "Connected To X ✅" : "Connect X Account"}
          </button>
        </div>

        <div className="verification-actions">
          <div className="verification-status-card">
            <strong>GitHub verification</strong>
            <span>{verifiedGithub ? `${verifiedGithub.value} verified ✅` : "Not verified yet"}</span>
          </div>
          <button className="ghost-button" type="button" disabled={!ownedAgent || sessionScopes.length === 0 || busy || Boolean(verifiedGithub)} onClick={() => void onStartSocialProof("github")}>
            {verifiedGithub ? "Connected To GitHub ✅" : "Connect GitHub Account"}
          </button>
        </div>

        <div className="verification-actions">
          <div className="verification-status-card dual-status">
            <div>
              <strong>EVM wallet</strong>
              <span>{verifiedEvm ? `${shortenIdentifier(verifiedEvm.address)} verified ✅` : "Not verified yet"}</span>
            </div>
            <div>
              <strong>Solana wallet</strong>
              <span>{verifiedSol ? `${shortenIdentifier(verifiedSol.address)} verified ✅` : "Not verified yet"}</span>
            </div>
          </div>
          <div className="button-stack-inline">
            <button className="ghost-button" type="button" disabled={!ownedAgent || sessionScopes.length === 0 || busy || Boolean(verifiedEvm)} onClick={() => void onVerifyWallet("erc20")}>
              {verifiedEvm ? "EVM Connected ✅" : "Connect EVM Wallet"}
            </button>
            <button className="ghost-button" type="button" disabled={!ownedAgent || sessionScopes.length === 0 || busy || Boolean(verifiedSol)} onClick={() => void onVerifyWallet("solana")}>
              {verifiedSol ? "Solana Connected ✅" : "Connect Solana Wallet"}
            </button>
          </div>
        </div>

        <div className="field-grid">
          <label>
            <span>Proof URL</span>
            <input value={proofUrl} onChange={(event) => setProofUrl(event.target.value)} disabled={!ownedAgent} />
          </label>
          <label>
            <span>Support URL</span>
            <input value={supportUrl} onChange={(event) => setSupportUrl(event.target.value)} disabled={!ownedAgent} />
          </label>
        </div>

        <label>
          <span>Proof notes</span>
          <textarea value={proofNotes} onChange={(event) => setProofNotes(event.target.value)} rows={3} disabled={!ownedAgent} />
        </label>

        <button className="action-button secondary" type="submit" disabled={!ownedAgent || busy || sessionScopes.length === 0}>
          {busy ? "Saving..." : "Save Profile Claims"}
        </button>
      </form>
    </section>
  );
}
