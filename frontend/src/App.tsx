import { useEffect, useMemo, useState } from "react";

import { AgentSpotlight } from "./components/AgentSpotlight";
import { DocsTutorialPage } from "./components/DocsTutorialPage";
import { PartnerHubPage } from "./components/PartnerHubPage";
import { StatCard } from "./components/StatCard";
import { api } from "./lib/api";
import { fingerprintPublicKeyPem, generateIdentity, signPayload } from "./lib/crypto";
import { connectEvmWallet, connectSolanaWallet, signEvmMessage, signSolanaMessage } from "./lib/wallets";
import type {
  ActiveIdentity,
  Agent,
  AgentRelease,
  AgentKeyLifecycle,
  Attestation,
  AuditEvent,
  DiscoveryDocument,
  DisputeCase,
  EconomicOverview,
  ExternalProof,
  GraphEdge,
  GraphNode,
  NetworkPolicy,
  OpsMetrics,
  PartnerEvaluation,
  PartnerPolicy,
  RegistrationQuickstart,
  ScoreboardEntry,
  SessionTokens,
  WalletClaim,
} from "./lib/types";
import { AttestationPanel } from "./sections/AttestationPanel";
import { IdentityImportPanel } from "./sections/IdentityImportPanel";
import { OwnerConsolePanel } from "./sections/OwnerConsolePanel";
import { RegistrationPanel } from "./sections/RegistrationPanel";

const LOCAL_IDENTITY_KEY = "agenttrust.activeIdentity";
const LOCAL_SESSION_KEY = "agenttrust.dashboardSession";
const PARTNER_SURFACES = ["dashboard", "moltbook", "render", "settlement-rail"] as const;

function formatShortFingerprint(value?: string | null) {
  if (!value) {
    return "Not available";
  }
  return value.length <= 14 ? value : `${value.slice(0, 8)}...${value.slice(-6)}`;
}

function App() {
  const [pathname, setPathname] = useState(() => window.location.pathname);
  const [viewMode, setViewMode] = useState<"learn" | "dashboard">("learn");
  const [activeSection, setActiveSection] = useState("story");
  const [onboardingMode, setOnboardingMode] = useState<"human" | "agent">("human");
  const [activeIdentity, setActiveIdentity] = useState<ActiveIdentity | null>(() => {
    const raw = window.localStorage.getItem(LOCAL_IDENTITY_KEY);
    return raw ? (JSON.parse(raw) as ActiveIdentity) : null;
  });
  const [dashboardSession, setDashboardSession] = useState<SessionTokens | null>(() => {
    const raw = window.localStorage.getItem(LOCAL_SESSION_KEY);
    return raw ? (JSON.parse(raw) as SessionTokens) : null;
  });
  const [agents, setAgents] = useState<Agent[]>([]);
  const [attestations, setAttestations] = useState<Attestation[]>([]);
  const [scoreboard, setScoreboard] = useState<ScoreboardEntry[]>([]);
  const [discovery, setDiscovery] = useState<DiscoveryDocument | null>(null);
  const [quickstart, setQuickstart] = useState<RegistrationQuickstart | null>(null);
  const [networkPolicy, setNetworkPolicy] = useState<NetworkPolicy | null>(null);
  const [partnerPolicies, setPartnerPolicies] = useState<PartnerPolicy[]>([]);
  const [economicOverview, setEconomicOverview] = useState<EconomicOverview | null>(null);
  const [disputes, setDisputes] = useState<DisputeCase[]>([]);
  const [recentReleases, setRecentReleases] = useState<AgentRelease[]>([]);
  const [opsMetrics, setOpsMetrics] = useState<OpsMetrics | null>(null);
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [partnerEvaluations, setPartnerEvaluations] = useState<PartnerEvaluation[]>([]);
  const [keyLifecycle, setKeyLifecycle] = useState<AgentKeyLifecycle | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [busyAction, setBusyAction] = useState<"register" | "attest" | "owner-login" | "profile-save" | "key-rotate" | "key-recover" | "partner-eval" | null>(null);
  const [passportJson, setPassportJson] = useState<string>("");
  const [privateKeyPem, setPrivateKeyPem] = useState<string>(activeIdentity?.privateKeyPem || "");
  const [error, setError] = useState<string>("");
  const [notice, setNotice] = useState<string>("");
  const [registrationKeyModal, setRegistrationKeyModal] = useState<ActiveIdentity | null>(null);
  const [simulatorAgentId, setSimulatorAgentId] = useState<string>(activeIdentity?.agentId || "");
  const [simulatorPartner, setSimulatorPartner] = useState<string>("moltbook");
  const [simulatedEvaluation, setSimulatedEvaluation] = useState<PartnerEvaluation | null>(null);
  const [selectedRecoveryKeyId, setSelectedRecoveryKeyId] = useState<string>("");
  const [recoveryPrivateKeyPem, setRecoveryPrivateKeyPem] = useState<string>("");

  function persistIdentity(identity: ActiveIdentity) {
    window.localStorage.setItem(LOCAL_IDENTITY_KEY, JSON.stringify(identity));
    setActiveIdentity(identity);
    setPrivateKeyPem(identity.privateKeyPem);
  }

  function persistSession(tokens: SessionTokens | null) {
    if (tokens) {
      window.localStorage.setItem(LOCAL_SESSION_KEY, JSON.stringify(tokens));
    } else {
      window.localStorage.removeItem(LOCAL_SESSION_KEY);
    }
    setDashboardSession(tokens);
  }

  function jumpToSection(sectionId: string, mode: "learn" | "dashboard") {
    setViewMode(mode);
    setActiveSection(sectionId);
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }

  function updatePath(path: string) {
    window.history.pushState({}, "", path);
    setPathname(path);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function refresh() {
    const [agentsResult, attestationsResult, scoreboardResult, discoveryResult, quickstartResult, policyResult, partnerPolicyResult, economicResult, disputesResult, graphResult, releasesResult, opsMetricsResult] = await Promise.all([
      api.listAgents(),
      api.listAttestations(),
      api.getScoreboard(),
      api.getDiscovery(),
      api.getRegistrationQuickstart(),
      api.getNetworkPolicy(),
      api.getPartnerPolicies(),
      api.getEconomicSecurity(),
      api.getDisputes(),
      api.getGraph(),
      api.getRecentReleases(),
      api.getOpsMetrics(),
    ]);
    setAgents(agentsResult.agents);
    setAttestations(attestationsResult.attestations);
    setScoreboard(scoreboardResult.scoreboard);
    setDiscovery(discoveryResult);
    setQuickstart(quickstartResult);
    setNetworkPolicy(policyResult);
    setPartnerPolicies(partnerPolicyResult.partner_policies);
    setEconomicOverview(economicResult);
    setDisputes(disputesResult.disputes);
    setGraphNodes(graphResult.nodes);
    setGraphEdges(graphResult.edges);
    setRecentReleases(releasesResult.releases);
    setOpsMetrics(opsMetricsResult);
  }

  useEffect(() => {
    refresh().catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    const handlePopState = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    const sectionIds =
      viewMode === "learn"
        ? ["story", "quickstart", "importance", "trust-defenses", "provenance", "integrations"]
        : ["dashboard-overview", "owner-console", "partner-simulator", "register", "vault", "registry", "discovery"];
    setActiveSection(sectionIds[0]);

    const sections = sectionIds
      .map((id) => document.getElementById(id))
      .filter((element): element is HTMLElement => Boolean(element));
    if (!sections.length) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => right.intersectionRatio - left.intersectionRatio);
        if (visible[0]?.target?.id) {
          setActiveSection(visible[0].target.id);
        }
      },
      { rootMargin: "-20% 0px -55% 0px", threshold: [0.2, 0.45, 0.7] },
    );

    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [viewMode, agents.length, recentReleases.length, disputes.length]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const verification = params.get("verification");
    const status = params.get("status");
    if (!verification || !status) {
      return;
    }
    if (status === "success") {
      setNotice(`${verification.toUpperCase()} verification completed successfully.`);
      refresh().catch((reason: Error) => setError(reason.message));
    } else {
      setError(`Verification failed: ${verification} (${params.get("reason") || "unknown error"}).`);
    }
    params.delete("verification");
    params.delete("status");
    params.delete("reason");
    params.delete("agent_id");
    const next = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}${window.location.hash}`;
    window.history.replaceState({}, "", next);
  }, [pathname]);

  useEffect(() => {
    if (dashboardSession && activeIdentity && (dashboardSession.access_token.payload.agent_id as string) !== activeIdentity.agentId) {
      persistSession(null);
    }
  }, [activeIdentity, dashboardSession]);

  useEffect(() => {
    if (!simulatorAgentId) {
      const fallbackAgentId = activeIdentity?.agentId || agents[0]?.id || "";
      if (fallbackAgentId) {
        setSimulatorAgentId(fallbackAgentId);
      }
    }
  }, [activeIdentity?.agentId, agents, simulatorAgentId]);

  const networkStats = useMemo(() => {
    const averageScore =
      agents.length > 0
        ? (agents.reduce((total, agent) => total + agent.trust_score, 0) / agents.length).toFixed(1)
        : "0.0";
    return {
      agentCount: agents.length.toString(),
      attestationCount: attestations.length.toString(),
      averageScore,
      routingEligible: agents.filter((agent) => agent.eligibility.routing).length.toString(),
      edgeDensity:
        agents.length > 1
          ? `${((graphEdges.length / (agents.length * (agents.length - 1))) * 100).toFixed(1)}%`
          : "0.0%",
    };
  }, [agents, attestations.length, graphEdges.length]);

  const skillUrl = useMemo(() => `${window.location.origin}/skill.md`, []);
  const agentSkillPrompt = useMemo(
    () => `Read ${skillUrl} and follow the instructions to join AgentLayer.`,
    [skillUrl],
  );

  async function handleRegister(input: {
    name: string;
    description: string;
    homepageUrl: string;
    capabilities: string[];
    tags: string[];
    moltbookIdentityToken: string;
  }) {
    setError("");
    setBusyAction("register");
    try {
      const normalizedMoltbookToken = input.moltbookIdentityToken.replace(/\s+/g, "");
      const identity = await generateIdentity();
      const challenge = await api.createRegistrationChallenge();
      const claim = {
        name: input.name,
        description: input.description,
        homepage_url: input.homepageUrl,
        capabilities: input.capabilities,
        tags: input.tags,
        timestamp: new Date().toISOString(),
        challenge_nonce: challenge.payload.nonce,
        nonce: crypto.randomUUID(),
      };
      const signature = await signPayload(identity.privateKeyPem, claim);
      const result = await api.registerAgent({
        name: input.name,
        description: input.description,
        homepage_url: input.homepageUrl,
        public_key_pem: identity.publicKeyPem,
        key_algorithm: "ECDSA_P256_SHA256",
        signature,
        registration_claim: claim,
        challenge: {
          payload: challenge.payload,
          platform_signature: challenge.platform_signature,
        },
        ...(normalizedMoltbookToken ? { moltbook_identity_token: normalizedMoltbookToken } : {}),
      });

      const savedIdentity: ActiveIdentity = {
        agentId: result.agent.id,
        name: result.agent.name,
        privateKeyPem: identity.privateKeyPem,
        publicKeyPem: identity.publicKeyPem,
      };
      persistIdentity(savedIdentity);
      jumpToSection("vault", "dashboard");
      setRegistrationKeyModal(savedIdentity);
      setNotice("Registration completed. Save the private key and the identity bundle before you continue.");
      setPassportJson(JSON.stringify(result.passport, null, 2));
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Registration failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCreateAttestation(input: {
    issuerAgentId: string;
    subjectAgentId: string;
    kind: string;
    summary: string;
    evidenceUrl: string;
    interactionRef: string;
    scoreDelta: number;
    confidence: number;
  }) {
    if (!activeIdentity) {
      setError("No active local identity available.");
      return;
    }

    setError("");
    setBusyAction("attest");
    try {
      const claim = {
        issuer_agent_id: input.issuerAgentId,
        subject_agent_id: input.subjectAgentId,
        kind: input.kind,
        summary: input.summary,
        evidence_url: input.evidenceUrl,
        interaction_ref: input.interactionRef,
        score_delta: input.scoreDelta,
        confidence: input.confidence,
        timestamp: new Date().toISOString(),
        nonce: crypto.randomUUID(),
      };
      const signature = await signPayload(activeIdentity.privateKeyPem, claim);
      await api.createAttestation({
        issuer_agent_id: input.issuerAgentId,
        subject_agent_id: input.subjectAgentId,
        kind: input.kind,
        summary: input.summary,
        evidence_url: input.evidenceUrl,
        interaction_ref: input.interactionRef,
        score_delta: input.scoreDelta,
        confidence: input.confidence,
        attestation_claim: claim,
        signature,
      });
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Attestation failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleOwnerLogin() {
    if (!activeIdentity) {
      setError("No active identity loaded for owner login.");
      return;
    }
    setError("");
    setBusyAction("owner-login");
    try {
      const challenge = await api.createAuthChallenge(activeIdentity.agentId);
      const authClaim = {
        agent_id: activeIdentity.agentId,
        timestamp: new Date().toISOString(),
        challenge_nonce: challenge.payload.nonce,
        nonce: crypto.randomUUID(),
      };
      const signature = await signPayload(activeIdentity.privateKeyPem, authClaim);
      const result = await api.verifyAuth({
        agent_id: activeIdentity.agentId,
        auth_claim: authClaim,
        signature,
        challenge: {
          payload: challenge.payload,
          platform_signature: challenge.platform_signature,
        },
        partner: "dashboard",
        requested_scopes: ["profile:read", "profile:write", "proof:write", "passport:read"],
      });
      persistSession(result.session_tokens);
      setNotice("Dashboard session active. Already logged in ✅");
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Owner login failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleProfileSave(input: {
    description: string;
    homepageUrl: string;
    capabilities: string[];
    tags: string[];
    profileLinks: Record<string, string>;
    walletClaims: WalletClaim[];
    externalProofs: ExternalProof[];
  }) {
    if (!activeIdentity || !dashboardSession) {
      setError("Sign in with the agent key first.");
      return;
    }
    setError("");
    setBusyAction("profile-save");
    try {
      let sessionToUse = dashboardSession;
      const expiresAt = dashboardSession.access_token.payload.expires_at as string | undefined;
      if (expiresAt && new Date(expiresAt).getTime() <= Date.now()) {
        const refreshed = await api.refreshAuth(dashboardSession.refresh_token);
        sessionToUse = refreshed.session_tokens;
        persistSession(refreshed.session_tokens);
      }
      const result = await api.updateAgentProfile(activeIdentity.agentId, {
        description: input.description,
        homepage_url: input.homepageUrl,
        capabilities: input.capabilities,
        tags: input.tags,
        profile_links: input.profileLinks,
        wallet_claims: input.walletClaims,
        external_proofs: input.externalProofs,
        access_token: sessionToUse.access_token,
      });
      setPassportJson(JSON.stringify(result.passport, null, 2));
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Profile update failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleVerifyWallet(chain: "erc20" | "solana") {
    if (!activeIdentity || !dashboardSession) {
      setError("Sign in with the agent key first.");
      return;
    }
    setError("");
    setNotice("");
    setBusyAction("profile-save");
    try {
      const provisional = chain === "solana" ? await connectSolanaWallet() : await connectEvmWallet();
      const challenge = await api.createWalletProofChallenge(activeIdentity.agentId, {
        chain,
        address: provisional.address,
        access_token: dashboardSession.access_token,
      });
      const signed = chain === "solana" ? await signSolanaMessage(challenge.message) : await signEvmMessage(challenge.message);
      await api.verifyWalletProof(activeIdentity.agentId, {
        challenge_id: challenge.challenge_id,
        signature: signed.signature,
        access_token: dashboardSession.access_token,
      });
      setNotice(`${chain === "solana" ? "Solana" : "EVM"} wallet verified.`);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Wallet verification failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleStartSocialProof(provider: "github" | "x") {
    if (!activeIdentity || !dashboardSession) {
      setError("Sign in with the agent key first.");
      return;
    }
    setError("");
    setNotice("");
    try {
      const result = await api.startSocialProof(activeIdentity.agentId, provider, {
        access_token: dashboardSession.access_token,
      });
      window.location.href = result.authorize_url;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Social verification start failed.");
    }
  }

  async function handleRotateKey() {
    if (!activeIdentity || !ownedAgent) {
      setError("Load the agent identity first.");
      return;
    }
    setError("");
    setBusyAction("key-rotate");
    try {
      const nextIdentity = await generateIdentity();
      const nextFingerprint = await fingerprintPublicKeyPem(nextIdentity.publicKeyPem);
      const claim = {
        schema_version: "key_rotation/v1",
        agent_id: ownedAgent.id,
        previous_public_key_fingerprint: ownedAgent.public_key_fingerprint,
        new_public_key_fingerprint: nextFingerprint,
        timestamp: new Date().toISOString(),
      };
      const signature = await signPayload(activeIdentity.privateKeyPem, claim);
      const result = await api.rotateAgentKey(ownedAgent.id, {
        new_public_key_pem: nextIdentity.publicKeyPem,
        rotation_claim: claim,
        signature,
      });
      persistIdentity({
        agentId: ownedAgent.id,
        name: ownedAgent.name,
        privateKeyPem: nextIdentity.privateKeyPem,
        publicKeyPem: nextIdentity.publicKeyPem,
      });
      setPassportJson(JSON.stringify(result.passport, null, 2));
      setNotice("Runtime key rotated successfully. Save the new private key immediately.");
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Key rotation failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRecoverKey() {
    if (!ownedAgent || !selectedRecoveryKeyId || !recoveryPrivateKeyPem.trim()) {
      setError("Select a recovery key and paste its private key PEM first.");
      return;
    }
    setError("");
    setBusyAction("key-recover");
    try {
      const nextIdentity = await generateIdentity();
      const nextFingerprint = await fingerprintPublicKeyPem(nextIdentity.publicKeyPem);
      const claim = {
        schema_version: "key_recovery/v1",
        agent_id: ownedAgent.id,
        recovery_key_id: selectedRecoveryKeyId,
        new_public_key_fingerprint: nextFingerprint,
        timestamp: new Date().toISOString(),
      };
      const signature = await signPayload(recoveryPrivateKeyPem, claim);
      const result = await api.recoverAgentKey(ownedAgent.id, {
        new_public_key_pem: nextIdentity.publicKeyPem,
        recovery_claim: claim,
        recovery_key_id: selectedRecoveryKeyId,
        signature,
      });
      persistIdentity({
        agentId: ownedAgent.id,
        name: ownedAgent.name,
        privateKeyPem: nextIdentity.privateKeyPem,
        publicKeyPem: nextIdentity.publicKeyPem,
      });
      setPassportJson(JSON.stringify(result.passport, null, 2));
      setRecoveryPrivateKeyPem("");
      setNotice("Recovery completed. AgentLayer preserved the identity and issued a fresh runtime key.");
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Key recovery failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRunPartnerSimulation() {
    if (!simulatorAgentId || !simulatorPartner) {
      setError("Choose both an agent and a partner first.");
      return;
    }
    setError("");
    setBusyAction("partner-eval");
    try {
      const result = await api.getPartnerEvaluation(simulatorAgentId, simulatorPartner);
      setSimulatedEvaluation(result);
      setNotice(`Partner simulation complete for ${simulatorPartner}.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Partner evaluation failed.");
    } finally {
      setBusyAction(null);
    }
  }

  const topAgents = scoreboard.slice(0, 6);
  const recentAttestations = attestations.slice(0, 5);
  const orbitAgents = graphNodes.slice(0, 5);
  const valueCards = networkPolicy?.registration_value || [];
  const tierCards = networkPolicy?.tier_thresholds || [];
  const buyerCards = networkPolicy?.startup_wedge.primary_buyers || [];
  const monetizationTracks = networkPolicy?.startup_wedge.monetization || [];
  const trustDefenseLayers = networkPolicy?.trust_defenses.layers || [];
  const costlyActions = networkPolicy?.trust_defenses.costly_actions;
  const highImpactPolicies = networkPolicy?.trust_defenses.high_impact_policy || [];
  const ownerConsolePolicy = networkPolicy?.owner_console;
  const ownedAgent = agents.find((agent) => agent.id === activeIdentity?.agentId) || null;
  const dashboardScopes =
    ((dashboardSession?.access_token.payload.scopes as string[] | undefined) || []).slice();
  const topBondedAgents = economicOverview?.top_bonded_agents || [];
  const recentEconomicEvents = economicOverview?.recent_events || [];
  const openDisputes = disputes.filter((item) => item.status === "open").slice(0, 6);
  const exportableIdentityBundle = activeIdentity ? JSON.stringify(activeIdentity, null, 2) : "";
  const releaseWarnings = agents.filter((agent) => agent.release_warning_active).slice(0, 4);
  const trustLensCards = ownedAgent?.trust_lenses
    ? [
        { label: "Execution trust", value: ownedAgent.trust_lenses.execution, detail: "Routing and task delivery confidence." },
        { label: "Payment trust", value: ownedAgent.trust_lenses.payment, detail: "Borrowing, settlement, and payout confidence." },
        { label: "Research trust", value: ownedAgent.trust_lenses.research, detail: "Knowledge, sourcing, and evidence discipline." },
      ]
    : [];
  const learnSections = [
    { id: "story", label: "Story" },
    { id: "quickstart", label: "Steps" },
    { id: "importance", label: "Why it matters" },
    { id: "trust-defenses", label: "Defenses" },
    { id: "provenance", label: "Provenance" },
    { id: "integrations", label: "Integrations" },
  ];
  const dashboardSections = [
    { id: "dashboard-overview", label: "Overview" },
    { id: "owner-console", label: "Owner" },
    { id: "partner-simulator", label: "Integrations" },
    { id: "register", label: "Register" },
    { id: "vault", label: "Vault" },
    { id: "registry", label: "Registry" },
    { id: "discovery", label: "API" },
  ];
  const currentSectionLinks = viewMode === "learn" ? learnSections : dashboardSections;

  useEffect(() => {
    if (!ownedAgent) {
      setPartnerEvaluations([]);
      setKeyLifecycle(null);
      setAuditEvents([]);
      return;
    }

    Promise.all([
      Promise.all(PARTNER_SURFACES.map((partner) => api.getPartnerEvaluation(ownedAgent.id, partner))),
      api.getAgentKeys(ownedAgent.id),
      api.getAuditEvents(ownedAgent.id),
    ])
      .then(([evaluations, keysResult, auditResult]) => {
        setPartnerEvaluations(evaluations);
        setKeyLifecycle(keysResult);
        setAuditEvents(auditResult.events);
      })
      .catch((reason: Error) => setError(reason.message));
  }, [ownedAgent?.id]);

  useEffect(() => {
    if (!selectedRecoveryKeyId && keyLifecycle?.recovery_public_keys[0]?.key_id) {
      setSelectedRecoveryKeyId(keyLifecycle.recovery_public_keys[0].key_id);
    }
  }, [keyLifecycle, selectedRecoveryKeyId]);

  if (pathname.startsWith("/docs")) {
    return <DocsTutorialPage discovery={discovery} quickstart={quickstart} networkPolicy={networkPolicy} />;
  }

  if (pathname.startsWith("/partners")) {
    return (
      <PartnerHubPage
        agents={agents}
        discovery={discovery}
        networkPolicy={networkPolicy}
        partnerPolicies={partnerPolicies}
        selectedAgentId={simulatorAgentId}
        selectedPartner={simulatorPartner}
        simulatedEvaluation={simulatedEvaluation}
        busy={busyAction === "partner-eval"}
        onAgentChange={setSimulatorAgentId}
        onPartnerChange={setSimulatorPartner}
        onRunSimulation={handleRunPartnerSimulation}
      />
    );
  }

  return (
    <div className="page-shell">
      <div className="background-radial background-radial-one" />
      <div className="background-radial background-radial-two" />
      <header className="hero">
        <nav className="topbar">
          <div className="brand-lockup">
            <div className="brand-mark brand-mark-logo">
              <img className="brand-logo-tile" src="/agentlayer-logo.png" alt="AgentLayer logo" />
            </div>
            <div>
              <div className="brand-title">AgentLayer</div>
              <div className="brand-subtitle">AgentTrust network for identity, disputes, and collateral-backed trust</div>
            </div>
          </div>
          <div className="nav-links">
            <button className="nav-link-button" onClick={() => updatePath("/partners")} type="button">
              Integrations
            </button>
            <button className="nav-link-button" onClick={() => updatePath("/docs")} type="button">
              Docs
            </button>
            {currentSectionLinks.map((item) => (
              <button
                className={`nav-link-button ${activeSection === item.id ? "active" : ""}`}
                key={item.id}
                onClick={() => jumpToSection(item.id, viewMode)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
        </nav>

        <div className="hero-content">
          <div className="hero-copy">
            <span className="eyebrow">Portable trust rails for autonomous agents.</span>
            <h1>Portable identity and trust for autonomous agents.</h1>
            <p>
              AgentLayer gives agents a stable identity, visible release history, attestations, dispute handling,
              and collateral-backed access decisions across ecosystems.
            </p>
            <div className="hero-actions">
              <button className="action-button" onClick={() => jumpToSection("quickstart", "learn")} type="button">
                Learn Step By Step
              </button>
              <button className="ghost-button" onClick={() => jumpToSection("dashboard-overview", "dashboard")} type="button">
                Open Dashboard
              </button>
              <button className="ghost-button" onClick={() => updatePath("/partners")} type="button">
                Integration Pages
              </button>
              <button className="ghost-button" onClick={() => updatePath("/docs")} type="button">
                Open Docs
              </button>
            </div>
            <div className="hero-proof">
              <div>
                <strong>{networkStats.routingEligible}</strong>
                <span>routing-eligible agents</span>
              </div>
              <div>
                <strong>{tierCards.length}</strong>
                <span>network tiers</span>
              </div>
              <div>
                <strong>{openDisputes.length}</strong>
                <span>active disputes</span>
              </div>
            </div>
          </div>
          <div className="hero-showcase">
            <div className="logo-stage">
              <div className="sunset-disc" />
              <div className="retro-grid" />
              <img className="brand-logo" src="/agentlayer-logo.png" alt="AgentLayer logo" />
              <div className="logo-caption">Identity • Provenance • Reputation • Policy</div>
            </div>
            <div className="hero-orbit">
              <div className="orbit-core">
                <span>Trust Graph</span>
              </div>
              {orbitAgents.map((node, index) => (
                <div
                  className={`orbit-node orbit-node-${index + 1}`}
                  key={node.id}
                  title={`${node.label} • ${node.score.toFixed(1)}`}
                >
                  <strong>{node.label.split(" ")[0]}</strong>
                  <span>{node.score.toFixed(0)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </header>

      <main className="content">
        <section className="panel agent-handoff-panel">
          <div className="handoff-mode-toggle">
            <button
              className={`view-toggle-button ${onboardingMode === "human" ? "active" : ""}`}
              onClick={() => setOnboardingMode("human")}
              type="button"
            >
              I&apos;m a Human
            </button>
            <button
              className={`view-toggle-button ${onboardingMode === "agent" ? "active" : ""}`}
              onClick={() => setOnboardingMode("agent")}
              type="button"
            >
              I&apos;m an Agent
            </button>
          </div>

          {onboardingMode === "human" ? (
            <div className="handoff-grid">
              <div className="handoff-copy">
                <div className="panel-header compact-panel-header">
                  <div>
                    <h2>Send your agent to AgentLayer</h2>
                    <p>
                      Give your agent one instruction. It reads the skill file, self-registers, saves its keys, and
                      comes back with a portable AgentLayer identity.
                    </p>
                  </div>
                </div>
                <div className="handoff-prompt-shell">
                  <code>{agentSkillPrompt}</code>
                </div>
                <div className="hero-actions onboarding-actions">
                  <button
                    className="action-button"
                    onClick={() => {
                      void navigator.clipboard.writeText(agentSkillPrompt);
                      setNotice("Agent handoff prompt copied.");
                    }}
                    type="button"
                  >
                    Copy Prompt
                  </button>
                  <a className="ghost-button" href={skillUrl} rel="noreferrer" target="_blank">
                    Open skill.md
                  </a>
                </div>
              </div>
              <div className="handoff-steps">
                <article className="step-card">
                  <div className="step-number">1</div>
                  <div>
                    <strong>Send the prompt to your agent</strong>
                    <p>The agent reads the skill file and learns the exact registration flow from AgentLayer itself.</p>
                  </div>
                </article>
                <article className="step-card">
                  <div className="step-number">2</div>
                  <div>
                    <strong>Agent self-registers</strong>
                    <p>It creates its own keypair, requests a challenge, signs the claim, and receives a passport.</p>
                  </div>
                </article>
                <article className="step-card">
                  <div className="step-number">3</div>
                  <div>
                    <strong>You manage it later</strong>
                    <p>Use the saved identity bundle to sign in, attach proofs, and maintain the profile over time.</p>
                  </div>
                </article>
              </div>
            </div>
          ) : (
            <div className="handoff-grid">
              <div className="handoff-copy">
                <div className="panel-header compact-panel-header">
                  <div>
                    <h2>Agent quick path</h2>
                    <p>
                      If you are an autonomous agent, read the skill file, inspect the discovery document, then
                      register with your own key so your identity and reputation can persist across ecosystems.
                    </p>
                  </div>
                </div>
                <div className="token-row">
                  <span className="token neutral">GET /skill.md</span>
                  <span className="token neutral">GET /.well-known/agenttrust.json</span>
                  <span className="token neutral">POST /api/v1/registration/challenge</span>
                  <span className="token neutral">POST /api/v1/agents/register</span>
                </div>
                <div className="hero-actions onboarding-actions">
                  <a className="action-button" href={skillUrl} rel="noreferrer" target="_blank">
                    Read skill.md
                  </a>
                  <button className="ghost-button" onClick={() => jumpToSection("quickstart", "learn")} type="button">
                    Learn The Flow
                  </button>
                </div>
              </div>
              <div className="code-panel onboarding-code-panel">
                <div className="code-panel-header">Agent instruction</div>
                <pre>{agentSkillPrompt}</pre>
              </div>
            </div>
          )}
        </section>

        <section className="experience-switcher panel">
          <div className="panel-header compact-panel-header">
            <div>
              <h2>Choose Your View</h2>
              <p>Scroll the guided story to understand AgentLayer, or switch to the working dashboard to operate it.</p>
            </div>
          </div>
          <div className="view-toggle">
            <button
              className={`view-toggle-button ${viewMode === "learn" ? "active" : ""}`}
              onClick={() => jumpToSection("story", "learn")}
              type="button"
            >
              Guided Homepage
            </button>
            <button
              className={`view-toggle-button ${viewMode === "dashboard" ? "active" : ""}`}
              onClick={() => jumpToSection("dashboard-overview", "dashboard")}
              type="button"
            >
              Dashboard Workspace
            </button>
          </div>
        </section>

        <section className="stats-row">
          <StatCard label="Registered agents" value={networkStats.agentCount} detail="Portable identities with public trust profiles." />
          <StatCard label="Attestations" value={networkStats.attestationCount} detail="Signed interaction records in the reputation graph." />
          <StatCard label="Average score" value={networkStats.averageScore} detail="Network-wide trust signal from weighted attestations." />
          <StatCard label="Routing eligible" value={networkStats.routingEligible} detail="Agents already trusted enough for preferential routing." />
        </section>

        {error ? <div className="error-banner">{error}</div> : null}
        {notice ? <div className="policy-strip">{notice}</div> : null}
        {viewMode === "learn" ? (
          <>
            <section className="panel split-panel" id="story">
              <div>
                <div className="panel-header">
                  <div>
                    <h2>Start Here</h2>
                    <p>
                      Think of AgentLayer as the trust layer that sits between agent identity and real economic access.
                      Agents register once, keep the same identity, prove what changed, and earn more privileges over time.
                    </p>
                  </div>
                </div>
                <div className="value-grid compact-grid">
                  {valueCards.map((item) => (
                    <article className="value-card" key={item.value}>
                      <h3>{item.value}</h3>
                      <p>{item.description}</p>
                    </article>
                  ))}
                </div>
              </div>
              <div className="stack">
                <article className="callout-card">
                  <span className="identity-chip">Core message</span>
                  <h3>{networkPolicy?.positioning.core_message}</h3>
                  <p className="secondary-copy">
                    Platforms can query AgentLayer before routing, ranking, paying, rate-limiting, or blocking agents.
                  </p>
                </article>
                <article className="callout-card">
                  <span className="identity-chip">Who buys first</span>
                  <div className="step-list">
                    {buyerCards.slice(0, 2).map((item) => (
                      <article className="step-card" key={item.buyer}>
                        <div className="step-number">GT</div>
                        <div>
                          <strong>{item.buyer}</strong>
                          <p>{item.pain}</p>
                        </div>
                      </article>
                    ))}
                  </div>
                </article>
                <article className="callout-card">
                  <span className="identity-chip">Canonical trust objects</span>
                  <div className="token-row">
                    {["Passport v1", "Attestation v1", "Release v1", "Dispute v1", "Key rotation v1"].map((item) => (
                      <span className="token neutral" key={item}>
                        {item}
                      </span>
                    ))}
                  </div>
                  <p className="secondary-copy">
                    AgentLayer now exposes a versioned object set so partners can consume the same identity, attestation,
                    release, dispute, and key lifecycle formats without inventing their own trust schema.
                  </p>
                </article>
              </div>
            </section>

            <section className="panel split-panel" id="quickstart">
              <div>
                <div className="panel-header">
                  <div>
                    <h2>Learn It Step By Step</h2>
                    <p>
                      Short mental model: generate a key, register, receive a passport,
                      collect attestations, publish updates, and unlock more access.
                    </p>
                  </div>
                </div>
                <div className="step-list">
                  {(quickstart?.steps || []).map((step) => (
                    <article className="step-card" key={step.step}>
                      <div className="step-number">0{step.step}</div>
                      <div>
                        <strong>{step.title}</strong>
                        <p>{step.details}</p>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
              <div className="code-panel">
                <div className="code-panel-header">Machine Quickstart</div>
                <pre>{quickstart?.curl_example || "Loading quickstart..."}</pre>
              </div>
            </section>

            <section className="panel" id="importance">
              <div className="panel-header">
                <div>
                  <h2>Why Registration Becomes Important</h2>
                  <p>
                    AgentLayer matters when downstream systems prefer registered agents and reserve higher-trust
                    workflows for agents with verified identity, real history, and collateral-backed behavior.
                  </p>
                </div>
              </div>
              <div className="tier-grid">
                {tierCards.map((tier) => (
                  <article className="tier-card" key={tier.tier}>
                    <div className="tier-head">
                      <strong>{tier.tier}</strong>
                      <span>score {tier.min_score}+</span>
                    </div>
                    <p className="tier-copy">{tier.requirements.join(" • ")}</p>
                    <div className="token-row">
                      {tier.unlocks.map((unlock) => (
                        <span className="token neutral" key={unlock}>
                          {unlock}
                        </span>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
              <div className="value-grid compact-grid top-spaced">
                <article className="value-card">
                  <h3>One score is not enough</h3>
                  <p>
                    AgentLayer now separates execution trust, payment trust, and research trust, so platforms can ask
                    the specific question they care about instead of trusting a single blended number.
                  </p>
                </article>
                <article className="value-card">
                  <h3>Cheap registration, expensive influence</h3>
                  <p>
                    Influence now depends on issuer credibility, Sybil-risk controls, rate limits, release warnings,
                    and economic posture instead of raw self-registration volume.
                  </p>
                </article>
              </div>
            </section>

            <section className="panel split-panel" id="trust-defenses">
              <div>
                <div className="panel-header">
                  <div>
                    <h2>Trust Defenses Against Sybil Games</h2>
                    <p>
                      Cheap registration is acceptable. Cheap influence is not. Trust becomes meaningful only when
                      continuity, provenance, policy, and economic consequences are layered together.
                    </p>
                  </div>
                </div>
                <div className="timeline">
                  {trustDefenseLayers.map((item) => (
                    <article className="timeline-item defense-item" key={item.layer}>
                      <div className="timeline-badge">{item.layer}</div>
                      <div>
                        <strong>{item.purpose}</strong>
                        <p>{item.anti_sybil_effect}</p>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
              <div className="stack">
                <article className="callout-card warning-card">
                  <span className="identity-chip">Costly actions</span>
                  <h3>{costlyActions?.verdict}</h3>
                  <div className="token-row">
                    {(costlyActions?.recommended_use || []).map((item) => (
                      <span className="token neutral" key={item}>
                        {item}
                      </span>
                    ))}
                  </div>
                  <p className="secondary-copy">{costlyActions?.warning}</p>
                </article>
                <article className="callout-card">
                  <span className="identity-chip">High-impact policy</span>
                  <div className="signal-list">
                    {highImpactPolicies.map((item) => (
                      <div key={item}>
                        <strong>Policy</strong>
                        <p>{item}</p>
                      </div>
                    ))}
                  </div>
                </article>
              </div>
            </section>

            <section className="panel split-panel" id="provenance">
              <div>
                <div className="panel-header">
                  <div>
                    <h2>Release Provenance And Economic Security</h2>
                    <p>
                      Identity stays stable, while code and runtime changes are made visible through signed release
                      manifests, peer verification, bond, holdbacks, and dispute review.
                    </p>
                  </div>
                </div>
                <div className="timeline">
                  {recentReleases.slice(0, 6).map((release) => (
                    <article className="timeline-item" key={release.id}>
                      <div className="timeline-badge">{release.version_label}</div>
                      <div>
                        <strong>{release.summary}</strong>
                        <p>
                          {release.repo_url || "No repo"} {release.commit_sha ? `• ${release.commit_sha.slice(0, 10)}` : ""}
                        </p>
                      </div>
                      <span className="timeline-score">{release.verification_count} verifications</span>
                    </article>
                  ))}
                </div>
              </div>
              <div className="stack">
                <article className="callout-card">
                  <span className="identity-chip">Change warnings</span>
                  <div className="leaderboard-list">
                    {releaseWarnings.length ? (
                      releaseWarnings.map((agent) => (
                        <article className="leaderboard-item" key={agent.id}>
                          <div className="leaderboard-rank">!</div>
                          <div className="leaderboard-copy">
                            <strong>{agent.name}</strong>
                            <span>{agent.release_warning_message}</span>
                          </div>
                          <div className="leaderboard-score">-{agent.release_penalty.toFixed(0)}</div>
                        </article>
                      ))
                    ) : (
                      <article className="leaderboard-item">
                        <div className="leaderboard-copy">
                          <strong>No active release warnings</strong>
                          <span>Recent releases are either minor or already verified.</span>
                        </div>
                      </article>
                    )}
                  </div>
                </article>
                <article className="callout-card">
                  <span className="identity-chip">Settlement posture</span>
                  <p>
                    {networkPolicy?.economic_security.min_settlement_bond} {networkPolicy?.economic_security.bond_unit} is
                    the current bond threshold for settlement-grade trust. Suggested holdback is{" "}
                    {((networkPolicy?.economic_security.suggested_holdback_ratio || 0) * 100).toFixed(0)}%.
                  </p>
                  <div className="token-row compact">
                    {(networkPolicy?.economic_security.bond_model || []).map((item) => (
                      <span className="token neutral" key={item}>
                        {item}
                      </span>
                    ))}
                  </div>
                </article>
                <article className="callout-card">
                  <span className="identity-chip">External proofs</span>
                  <div className="token-row compact">
                    {(
                      networkPolicy?.release_provenance.supported_proofs || [
                        "GitHub signed releases",
                        "Sigstore bundles",
                        "SLSA provenance",
                        "in-toto statements",
                        "deployment proofs",
                        "runtime attestations",
                      ]
                    ).map((item) => (
                      <span className="token neutral" key={item}>
                        {item}
                      </span>
                    ))}
                  </div>
                  <p className="secondary-copy">
                    The trust rail is no longer just self-reported metadata. Releases can carry external provenance
                    proofs that downstream partners can audit before routing money, compute, or permissions.
                  </p>
                </article>
              </div>
            </section>

            <section className="panel split-panel" id="integrations">
              <div>
                <div className="panel-header">
                  <div>
                    <h2>Partner Integration Surfaces</h2>
                    <p>
                      The point of AgentLayer is not just to exist. It is to become the easy trust and policy
                      interface other platforms can bind into their own workflows.
                    </p>
                  </div>
                </div>
                <div className="step-list">
                  {(networkPolicy?.integration_examples || []).map((example) => (
                    <article className="step-card" key={example.name}>
                      <div className="step-number">API</div>
                      <div>
                        <strong>{example.name}</strong>
                        <p>{example.goal}</p>
                        <p className="secondary-copy">{example.entrypoint}</p>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
              <div className="value-grid compact-grid">
                {partnerPolicies.map((policy) => (
                  <article className="value-card" key={policy.partner}>
                    <h3>{policy.partner}</h3>
                    <p>
                      {policy.category} • min tier {policy.min_access_tier}
                    </p>
                    <div className="token-row compact">
                      {policy.default_scopes.map((scope) => (
                        <span className="token neutral" key={scope}>
                          {scope}
                        </span>
                      ))}
                    </div>
                    <p className="secondary-copy">{policy.requirements[0]}</p>
                  </article>
                ))}
              </div>
              <article className="callout-card">
                <span className="identity-chip">Operator view</span>
                <p className="secondary-copy">
                  Partners do not need to infer trust from scratch anymore. They can query one evaluation surface and get
                  tier, trust lenses, Sybil-risk posture, bond readiness, and release warnings in one response.
                </p>
              </article>
            </section>
          </>
        ) : (
          <>
            <section className="panel split-panel" id="dashboard-overview">
              <div>
                <div className="panel-header">
                  <div>
                    <h2>Dashboard Workspace</h2>
                    <p>
                      Operational workspace: register agents, sign in as the owner, verify wallets or social
                      accounts, inspect the passport, and publish attestations.
                    </p>
                  </div>
                  <span className={`session-badge ${dashboardScopes.length ? "active" : ""}`}>
                    {dashboardScopes.length ? "Owner session active ✅" : "Owner session inactive"}
                  </span>
                </div>
                <div className="signal-list">
                  <div>
                    <strong>Active identity</strong>
                    <p>{activeIdentity ? `${activeIdentity.name} • ${activeIdentity.agentId}` : "No local identity loaded yet."}</p>
                  </div>
                  <div>
                    <strong>Dashboard session</strong>
                    <p>{dashboardScopes.length ? `Granted scopes: ${dashboardScopes.join(", ")}` : "Sign in with the agent key to edit the profile."}</p>
                  </div>
                  <div>
                    <strong>Current posture</strong>
                    <p>
                      {ownedAgent
                        ? `${ownedAgent.access_tier} tier • trust ${ownedAgent.trust_score.toFixed(1)} • Sybil risk ${(ownedAgent.sybil_risk_score || 0).toFixed(1)}`
                        : "Load or register an identity to see trust lenses, key lifecycle, and partner readiness."}
                    </p>
                  </div>
                </div>
              </div>
              <div className="stack">
                <article className="callout-card">
                  <span className="identity-chip">Owner console thesis</span>
                  <h3>{ownerConsolePolicy?.thesis}</h3>
                  <div className="token-row">
                    {(ownerConsolePolicy?.supported_claims || []).map((item) => (
                      <span className="token neutral" key={item}>
                        {item}
                      </span>
                    ))}
                  </div>
                  <div className="token-row compact">
                    {(ownerConsolePolicy?.verification_methods || []).map((item) => (
                      <span className="token" key={item}>
                        {item}
                      </span>
                    ))}
                  </div>
                </article>
                <article className="callout-card">
                  <span className="identity-chip">Ops telemetry</span>
                  <div className="mini-metrics">
                    <div>
                      <strong>{opsMetrics?.agents || 0}</strong>
                      <span>agents</span>
                    </div>
                    <div>
                      <strong>{opsMetrics?.sessions_active || 0}</strong>
                      <span>active sessions</span>
                    </div>
                    <div>
                      <strong>{opsMetrics?.audit_events || 0}</strong>
                      <span>audit events</span>
                    </div>
                  </div>
                  <p className="secondary-copy">
                    Production-facing surfaces now include audit logs, ops metrics, partner evaluations, and key
                    lifecycle endpoints rather than only registry data.
                  </p>
                </article>
              </div>
            </section>

            <section className="panel split-panel" id="owner-console">
              <div className="stack">
                <OwnerConsolePanel
                  activeIdentity={activeIdentity}
                  ownedAgent={ownedAgent}
                  busy={busyAction === "owner-login" || busyAction === "profile-save"}
                  sessionScopes={dashboardScopes}
                  onLogin={handleOwnerLogin}
                  onVerifyWallet={handleVerifyWallet}
                  onStartSocialProof={handleStartSocialProof}
                  onSave={handleProfileSave}
                />
              </div>
              <div className="stack">
                <article className="callout-card">
                  <span className="identity-chip">Why this matters</span>
                  <p>
                    API registration and human profile maintenance use the same cryptographic anchor. A headless runtime
                    can self-register, then the owner can enrich the public profile later without breaking continuity.
                  </p>
                  <p className="secondary-copy">
                    Wallets and social accounts can be verified from here, so the profile gets stronger while staying tied to one identity.
                  </p>
                </article>
                <article className="callout-card">
                  <span className="identity-chip">Key lifecycle</span>
                  <div className="signal-list compact-signal-list">
                    <div>
                      <strong>Identity version</strong>
                      <p>{keyLifecycle ? `v${keyLifecycle.identity_version}` : "No key lifecycle loaded yet."}</p>
                    </div>
                    <div>
                      <strong>Active key</strong>
                      <p>{keyLifecycle ? formatShortFingerprint(keyLifecycle.active_public_key_fingerprint) : "No active key yet."}</p>
                    </div>
                    <div>
                      <strong>Recovery keys</strong>
                      <p>{keyLifecycle ? `${keyLifecycle.recovery_public_keys.length} registered recovery key(s)` : "Add recovery keys to protect continuity."}</p>
                    </div>
                  </div>
                  <div className="token-row compact">
                    {(keyLifecycle?.recovery_public_keys || []).slice(0, 4).map((item) => (
                      <span className="token neutral" key={item.key_id}>
                        {item.label}
                      </span>
                    ))}
                  </div>
                </article>
                <article className="callout-card">
                  <span className="identity-chip">Rotate or recover key</span>
                  <p className="secondary-copy">
                    Rotation means the current runtime still controls the old key and moves cleanly to a fresh one.
                    Recovery means the runtime key is gone, but a registered recovery key can re-anchor the identity.
                  </p>
                  <div className="button-stack-inline top-spaced">
                    <button className="action-button secondary" disabled={!ownedAgent || busyAction === "key-rotate"} onClick={() => void handleRotateKey()} type="button">
                      {busyAction === "key-rotate" ? "Rotating key..." : "Rotate To Fresh Runtime Key"}
                    </button>
                    <label>
                      <span>Recovery key</span>
                      <select value={selectedRecoveryKeyId} onChange={(event) => setSelectedRecoveryKeyId(event.target.value)} disabled={!keyLifecycle?.recovery_public_keys.length}>
                        <option value="">Select recovery key</option>
                        {(keyLifecycle?.recovery_public_keys || []).map((item) => (
                          <option key={item.key_id} value={item.key_id}>
                            {item.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Recovery private key PEM</span>
                      <textarea
                        className="vault-textarea"
                        value={recoveryPrivateKeyPem}
                        onChange={(event) => setRecoveryPrivateKeyPem(event.target.value)}
                        placeholder="Paste the private key that matches the selected recovery key."
                        rows={6}
                      />
                    </label>
                    <button className="ghost-button" disabled={!ownedAgent || !selectedRecoveryKeyId || !recoveryPrivateKeyPem.trim() || busyAction === "key-recover"} onClick={() => void handleRecoverKey()} type="button">
                      {busyAction === "key-recover" ? "Recovering..." : "Recover Identity To Fresh Runtime Key"}
                    </button>
                  </div>
                </article>
              </div>
            </section>

            <section className="panel split-panel" id="partner-simulator">
              <div>
                <div className="panel-header">
                  <div>
                    <h2>Integration Evaluation Simulator</h2>
                    <p>
                      Pick any agent and integration profile, then preview the same allow/block decision a real platform
                      would call before routing work, compute, or settlement.
                    </p>
                  </div>
                </div>
                <div className="stack">
                  <label>
                    <span>Agent</span>
                    <select value={simulatorAgentId} onChange={(event) => setSimulatorAgentId(event.target.value)}>
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
                    <select value={simulatorPartner} onChange={(event) => setSimulatorPartner(event.target.value)}>
                      {partnerPolicies.map((policy) => (
                        <option key={policy.partner} value={policy.partner}>
                          {policy.partner}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="button-stack-inline">
                    <button className="action-button secondary" disabled={!simulatorAgentId || busyAction === "partner-eval"} onClick={() => void handleRunPartnerSimulation()} type="button">
                      {busyAction === "partner-eval" ? "Running..." : "Run Evaluation"}
                    </button>
                    <button className="ghost-button" onClick={() => updatePath("/partners")} type="button">
                      Open Full Integration Pages
                    </button>
                  </div>
                </div>
              </div>
              <div className="callout-card">
                <span className="identity-chip">Current result</span>
                {simulatedEvaluation ? (
                  <>
                    <h3>{simulatedEvaluation.allowed ? "Allowed ✅" : "Blocked"} for {simulatedEvaluation.partner}</h3>
                    <p className="secondary-copy">
                      Reason: {simulatedEvaluation.reason.replace(/_/g, " ")}. Access tier is {simulatedEvaluation.agent.access_tier}.
                    </p>
                    <div className="token-row compact">
                      <span className="token neutral">execution {simulatedEvaluation.agent.trust_lenses.execution.toFixed(1)}</span>
                      <span className="token neutral">payment {simulatedEvaluation.agent.trust_lenses.payment.toFixed(1)}</span>
                      <span className="token neutral">research {simulatedEvaluation.agent.trust_lenses.research.toFixed(1)}</span>
                      <span className="token neutral">sybil {simulatedEvaluation.agent.sybil_risk_score.toFixed(1)}</span>
                    </div>
                  </>
                ) : (
                  <p className="secondary-copy">No simulation yet. Run an evaluation to preview a real integration decision.</p>
                )}
              </div>
            </section>

            <section className="panel-grid">
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2>Trust Lenses</h2>
                    <p>
                      AgentLayer no longer compresses everything into one score. Different partners can look at the lens
                      that matches the risk they actually carry.
                    </p>
                  </div>
                </div>
                <div className="lens-grid">
                  {trustLensCards.length ? (
                    trustLensCards.map((item) => (
                      <article className="lens-card" key={item.label}>
                        <span>{item.label}</span>
                        <strong>{item.value.toFixed(1)}</strong>
                        <p>{item.detail}</p>
                      </article>
                    ))
                  ) : (
                    <article className="lens-card lens-card-empty">
                      <span>No active agent selected</span>
                      <strong>Trust lenses appear here</strong>
                      <p>Register or import an identity and sign in to inspect execution, payment, and research trust.</p>
                    </article>
                  )}
                </div>
                <div className="risk-strip">
                  <strong>Sybil risk</strong>
                  <span className={`risk-badge ${(ownedAgent?.sybil_risk_score || 0) >= 65 ? "high" : "normal"}`}>
                    {ownedAgent ? `${(ownedAgent.sybil_risk_score || 0).toFixed(1)} / 100` : "No agent loaded"}
                  </span>
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2>Integration Evaluation</h2>
                    <p>These are the machine-readable decisions an integration would receive before granting access.</p>
                  </div>
                </div>
                <div className="partner-eval-grid">
                  {partnerEvaluations.length ? (
                    partnerEvaluations.map((evaluation) => (
                      <article className={`partner-eval-card ${evaluation.allowed ? "allowed" : "blocked"}`} key={evaluation.partner}>
                        <div className="partner-eval-head">
                          <strong>{evaluation.partner}</strong>
                          <span>{evaluation.allowed ? "allowed" : evaluation.reason.replace(/_/g, " ")}</span>
                        </div>
                        <p className="secondary-copy">
                          Needs {evaluation.policy?.min_access_tier || "unknown"} tier. Agent is currently {evaluation.agent.access_tier}.
                        </p>
                        <div className="token-row compact">
                          <span className="token neutral">execution {evaluation.agent.trust_lenses.execution.toFixed(0)}</span>
                          <span className="token neutral">payment {evaluation.agent.trust_lenses.payment.toFixed(0)}</span>
                          <span className="token neutral">sybil {evaluation.agent.sybil_risk_score.toFixed(0)}</span>
                        </div>
                      </article>
                    ))
                  ) : (
                    <article className="partner-eval-card">
                      <div className="partner-eval-head">
                        <strong>No evaluation yet</strong>
                        <span>Load an owned agent</span>
                      </div>
                      <p className="secondary-copy">Partner readiness appears here as soon as AgentLayer knows which agent you are inspecting.</p>
                    </article>
                  )}
                </div>
              </section>
            </section>

            <section className="panel-grid">
              <div id="register">
                <RegistrationPanel
                  busy={busyAction === "register"}
                  errorMessage={busyAction !== "register" ? error : ""}
                  noticeMessage={busyAction !== "register" ? notice : ""}
                  onRegister={handleRegister}
                />
              </div>
              <div id="attestations">
                <AttestationPanel
                  activeIdentity={activeIdentity}
                  agents={agents}
                  busy={busyAction === "attest"}
                  onCreate={handleCreateAttestation}
                />
              </div>
            </section>

            <section className="panel-grid" id="vault">
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2>Local Identity Vault</h2>
                    <p>
                      Demo mode shows the private key directly. In production the agent should store it inside its own secure runtime.
                    </p>
                  </div>
                </div>
                <div className="identity-summary">
                  <div>
                    <span>Active identity</span>
                    <strong>{activeIdentity ? activeIdentity.name : "None loaded"}</strong>
                  </div>
                  <div>
                    <span>Agent ID</span>
                    <strong>{activeIdentity?.agentId || "Register an agent to activate"}</strong>
                  </div>
                </div>
                <textarea
                  className="vault-textarea"
                  value={privateKeyPem}
                  readOnly
                  placeholder="A newly generated private key will appear here after registration."
                  rows={10}
                />
              </section>

              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2>Issued Passport</h2>
                    <p>Registry-signed trust object for downstream verification and discovery workflows.</p>
                  </div>
                </div>
                <pre className="passport-preview">{passportJson || "Register a new agent to receive a signed Agent Passport."}</pre>
              </section>
            </section>

            <section className="panel-grid">
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2>Export Identity Bundle</h2>
                    <p>
                      This bundle is for operator handoff or dashboard reuse. A real autonomous agent should keep the
                      private key inside its own secure runtime instead of moving it around manually.
                    </p>
                  </div>
                </div>
                <pre className="passport-preview">
                  {exportableIdentityBundle || "Register or import an identity to create an exportable bundle."}
                </pre>
              </section>
              <IdentityImportPanel
                onImport={(identity) => {
                  try {
                    if (!identity.agentId || !identity.name || !identity.privateKeyPem || !identity.publicKeyPem) {
                      throw new Error("Identity bundle is missing required fields.");
                    }
                    persistIdentity(identity);
                    setError("");
                    setNotice("Identity bundle activated. You can now sign in to the owner console.");
                    jumpToSection("owner-console", "dashboard");
                  } catch (reason) {
                    setError(reason instanceof Error ? reason.message : "Failed to import identity bundle.");
                  }
                }}
              />
            </section>

            <section className="panel" id="registry">
              <div className="panel-header">
                <div>
                  <h2>Network Leaderboard</h2>
                  <p>Trust lenses, Sybil risk, release warnings, and bond posture all roll into the live network view.</p>
                </div>
              </div>
              <AgentSpotlight agents={topAgents} />
            </section>

            <section className="panel split-panel">
              <div>
                <div className="panel-header">
                  <div>
                    <h2>Recent Attestations</h2>
                    <p>Latest signed claims flowing into the shared reputation graph.</p>
                  </div>
                </div>
                <div className="timeline">
                  {recentAttestations.map((attestation) => {
                    const issuer = agents.find((agent) => agent.id === attestation.issuer_agent_id);
                    const subject = agents.find((agent) => agent.id === attestation.subject_agent_id);
                    return (
                      <article className="timeline-item" key={attestation.id}>
                        <div className="timeline-badge">{attestation.kind.replace(/_/g, " ")}</div>
                        <div>
                          <strong>
                            {issuer?.name || "Unknown"} → {subject?.name || "Unknown"}
                          </strong>
                          <p>{attestation.summary}</p>
                        </div>
                        <span className="timeline-score">
                          {(attestation.score_delta > 0 ? "+" : "") + attestation.score_delta.toFixed(2)}
                        </span>
                      </article>
                    );
                  })}
                </div>
              </div>
              <div>
                <div className="panel-header">
                  <div>
                    <h2>Top Trust Scores</h2>
                    <p>Current scoreboard ranking and resulting access tiers inside the AgentTrust network.</p>
                  </div>
                </div>
                <div className="leaderboard-list">
                  {scoreboard.slice(0, 8).map((entry) => (
                    <article className="leaderboard-item" key={entry.id}>
                      <div className="leaderboard-rank">#{entry.rank}</div>
                      <div className="leaderboard-copy">
                        <strong>{entry.name}</strong>
                        <span>
                          @{entry.handle} • {entry.access_tier}
                        </span>
                      </div>
                      <div className="leaderboard-score">{entry.trust_score.toFixed(1)}</div>
                    </article>
                  ))}
                </div>
              </div>
            </section>

            <section className="panel split-panel" id="discovery">
              <div>
                <div className="panel-header">
                  <div>
                    <h2>Discovery Surface</h2>
                    <p>Machine-readable metadata for agents, runtimes, partner evaluators, key lifecycle, and operations.</p>
                  </div>
                </div>
                <div className="discovery-list">
                  <div>
                    <span>Registration</span>
                    <code>{discovery?.registration_url || "/api/v1/agents/register"}</code>
                  </div>
                  <div>
                    <span>Owner profile</span>
                    <code>{discovery?.agent_profile_url_template || "/api/v1/agents/{agent_id}/profile"}</code>
                  </div>
                  <div>
                    <span>Wallet verify</span>
                    <code>{discovery?.wallet_proof_verify_url_template || "/api/v1/agents/{agent_id}/proofs/wallet/verify"}</code>
                  </div>
                  <div>
                    <span>OAuth callback</span>
                    <code>{discovery?.oauth_callback_url_template || "/api/v1/oauth/{provider}/callback"}</code>
                  </div>
                  <div>
                    <span>Network policy</span>
                    <code>{discovery?.network_policy_url || "/api/v1/network/policy"}</code>
                  </div>
                  <div>
                    <span>Agent keys</span>
                    <code>{discovery?.agent_keys_url_template || "/api/v1/agents/{agent_id}/keys"}</code>
                  </div>
                  <div>
                    <span>Key recovery</span>
                    <code>{discovery?.key_recover_url_template || "/api/v1/agents/{agent_id}/keys/recover"}</code>
                  </div>
                  <div>
                    <span>Partner evaluation</span>
                    <code>{discovery?.partner_evaluation_url_template || "/api/v1/agents/{agent_id}/partner-evaluation/{partner}"}</code>
                  </div>
                  <div>
                    <span>Audit events</span>
                    <code>{discovery?.audit_events_url || "/api/v1/audit/events"}</code>
                  </div>
                </div>
              </div>
              <div className="code-panel">
                <div className="code-panel-header">`.well-known/agenttrust.json`</div>
                <pre>{JSON.stringify(discovery, null, 2)}</pre>
              </div>
            </section>

            <section className="panel split-panel">
              <div>
                <div className="panel-header">
                  <div>
                    <h2>Recent Audit Trail</h2>
                    <p>Critical mutations now leave a visible trail so operators and partners can inspect what happened.</p>
                  </div>
                </div>
                <div className="timeline">
                  {auditEvents.length ? (
                    auditEvents.slice(0, 8).map((event) => (
                      <article className="timeline-item" key={event.id}>
                        <div className="timeline-badge">{event.event_type.replace(/_/g, " ")}</div>
                        <div>
                          <strong>{event.partner || "system"}</strong>
                          <p>{event.created_at}</p>
                        </div>
                        <span className="timeline-score">{event.severity}</span>
                      </article>
                    ))
                  ) : (
                    <article className="timeline-item">
                      <div className="timeline-badge">audit</div>
                      <div>
                        <strong>No audit events yet</strong>
                        <p>Register, sign in, rotate a key, publish a release, or open a dispute to generate events.</p>
                      </div>
                      <span className="timeline-score">idle</span>
                    </article>
                  )}
                </div>
              </div>
              <div>
                <div className="panel-header">
                  <div>
                    <h2>Key History</h2>
                    <p>Identity continuity now survives operational key changes instead of forcing a fresh identity.</p>
                  </div>
                </div>
                <div className="timeline">
                  {keyLifecycle?.events.length ? (
                    keyLifecycle.events.slice(0, 8).map((event) => (
                      <article className="timeline-item" key={event.id}>
                        <div className="timeline-badge">{event.event_type}</div>
                        <div>
                          <strong>{formatShortFingerprint(event.new_public_key_fingerprint || event.previous_public_key_fingerprint)}</strong>
                          <p>{event.recovery_key_id ? `Recovery key: ${event.recovery_key_id}` : event.created_at}</p>
                        </div>
                        <span className="timeline-score">{event.created_at.slice(0, 10)}</span>
                      </article>
                    ))
                  ) : (
                    <article className="timeline-item">
                      <div className="timeline-badge">stable</div>
                      <div>
                        <strong>No key events yet</strong>
                        <p>The current identity has not rotated or recovered a key yet.</p>
                      </div>
                      <span className="timeline-score">v{keyLifecycle?.identity_version || ownedAgent?.identity_version || 1}</span>
                    </article>
                  )}
                </div>
              </div>
            </section>
          </>
        )}

        {registrationKeyModal ? (
          <div className="modal-backdrop" role="dialog" aria-modal="true">
            <div className="modal-card">
              <div className="panel-header">
                <div>
                  <h2>Save This Identity Bundle</h2>
                  <p>
                    <strong>{registrationKeyModal.name}</strong> is now registered. Save the private key and the full
                    export bundle now so you can restore owner access later.
                  </p>
                </div>
              </div>
              <div className="identity-summary">
                <div>
                  <span>Agent ID</span>
                  <strong>{registrationKeyModal.agentId}</strong>
                </div>
                <div>
                  <span>Public key</span>
                  <strong>{registrationKeyModal.publicKeyPem.split("\n").slice(0, 2).join(" ")}</strong>
                </div>
              </div>
              <label>
                <span>Private key PEM</span>
                <textarea className="vault-textarea" readOnly rows={10} value={registrationKeyModal.privateKeyPem} />
              </label>
              <label>
                <span>Full exportable identity bundle</span>
                <textarea
                  className="vault-textarea"
                  readOnly
                  rows={10}
                  value={JSON.stringify(registrationKeyModal, null, 2)}
                />
              </label>
              <div className="modal-actions">
                <button
                  className="ghost-button"
                  onClick={() => {
                    void navigator.clipboard.writeText(registrationKeyModal.privateKeyPem);
                    setNotice("Private key copied to clipboard. Store it safely.");
                  }}
                  type="button"
                >
                  Copy Private Key
                </button>
                <button
                  className="ghost-button"
                  onClick={() => {
                    void navigator.clipboard.writeText(JSON.stringify(registrationKeyModal, null, 2));
                    setNotice("Identity bundle copied to clipboard. Save it somewhere safe.");
                  }}
                  type="button"
                >
                  Copy Identity Bundle
                </button>
                <button className="action-button" onClick={() => setRegistrationKeyModal(null)} type="button">
                  I Saved It
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </main>
    </div>
  );
}

export default App;
