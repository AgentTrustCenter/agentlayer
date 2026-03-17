import type {
  Agent,
  AgentKeyLifecycle,
  DisputeCase,
  EconomicOverview,
  AgentRelease,
  Attestation,
  AuditEvent,
  DiscoveryDocument,
  GraphEdge,
  GraphNode,
  OpsMetrics,
  PartnerEvaluation,
  PartnerPolicy,
  NetworkPolicy,
  RegistrationChallenge,
  RegistrationQuickstart,
  ScoreboardEntry,
  SessionTokens,
} from "./types";

const apiBase = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");
const discoveryBase = import.meta.env.VITE_DISCOVERY_BASE_URL || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { error?: string };
    throw new Error(payload.error || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export const api = {
  listAgents: () => request<{ agents: Agent[] }>(`${apiBase}/agents`),
  listAttestations: () => request<{ attestations: Attestation[] }>(`${apiBase}/attestations`),
  getScoreboard: () => request<{ scoreboard: ScoreboardEntry[] }>(`${apiBase}/scoreboard`),
  getGraph: () => request<{ nodes: GraphNode[]; edges: GraphEdge[] }>(`${apiBase}/network/graph`),
  getDiscovery: () =>
    request<DiscoveryDocument>(`${discoveryBase}/.well-known/agenttrust.json`, {
      headers: { Accept: "application/json" },
    }),
  getRegistrationQuickstart: () => request<RegistrationQuickstart>(`${apiBase}/registration/quickstart`),
  getNetworkPolicy: () => request<NetworkPolicy>(`${apiBase}/network/policy`),
  getPartnerPolicies: () => request<{ partner_policies: PartnerPolicy[]; integration_examples: NetworkPolicy["integration_examples"] }>(`${apiBase}/partners/policies`),
  getPartnerEvaluation: (agentId: string, partner: string) =>
    request<PartnerEvaluation>(`${apiBase}/agents/${agentId}/partner-evaluation/${partner}`),
  getEconomicSecurity: () => request<EconomicOverview>(`${apiBase}/economic-security`),
  getDisputes: () => request<{ disputes: DisputeCase[] }>(`${apiBase}/disputes`),
  getOpsMetrics: () => request<OpsMetrics>(`${apiBase}/ops/metrics`),
  getAuditEvents: (agentId?: string) =>
    request<{ events: AuditEvent[] }>(`${apiBase}/audit/events${agentId ? `?agent_id=${encodeURIComponent(agentId)}` : ""}`),
  getAgentKeys: (agentId: string) => request<AgentKeyLifecycle>(`${apiBase}/agents/${agentId}/keys`),
  createRegistrationChallenge: () =>
    request<RegistrationChallenge>(`${apiBase}/registration/challenge`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  createAuthChallenge: (agentId: string) =>
    request<{
      payload: {
        challenge_id: string;
        agent_id: string;
        nonce: string;
        issued_at: string;
        expires_at: string;
        purpose: string;
      };
      platform_signature: string;
      platform_signature_algorithm: string;
      platform_public_key: string;
      required_claim_field: string;
    }>(`${apiBase}/auth/challenge`, {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId }),
    }),
  verifyAuth: (payload: Record<string, unknown>) =>
    request<{
      agent: Agent;
      session_tokens: SessionTokens;
      granted_scopes: string[];
      allowed_scopes: string[];
      partner?: string | null;
    }>(`${apiBase}/auth/verify`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  refreshAuth: (refreshToken: SessionTokens["refresh_token"]) =>
    request<{
      agent: Agent;
      session_tokens: SessionTokens;
      granted_scopes: string[];
      partner?: string | null;
    }>(`${apiBase}/auth/refresh`, {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
  registerAgent: (payload: Record<string, unknown>) =>
    request<{ agent: Agent; passport: Record<string, unknown>; eligibility: Record<string, unknown>; next_actions: string[] }>(`${apiBase}/agents/register`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAgentProfile: (agentId: string, payload: Record<string, unknown>) =>
    request<{ agent: Agent; passport: Record<string, unknown> }>(`${apiBase}/agents/${agentId}/profile`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  rotateAgentKey: (agentId: string, payload: Record<string, unknown>) =>
    request<{ agent: Agent; passport: Record<string, unknown> }>(`${apiBase}/agents/${agentId}/keys/rotate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  recoverAgentKey: (agentId: string, payload: Record<string, unknown>) =>
    request<{ agent: Agent; passport: Record<string, unknown> }>(`${apiBase}/agents/${agentId}/keys/recover`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createWalletProofChallenge: (agentId: string, payload: Record<string, unknown>) =>
    request<{
      challenge_id: string;
      provider: string;
      address: string;
      message: string;
      challenge_payload: Record<string, unknown>;
      expires_at: string;
    }>(`${apiBase}/agents/${agentId}/proofs/wallet/challenge`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  verifyWalletProof: (agentId: string, payload: Record<string, unknown>) =>
    request<{ agent: Agent; verified_wallet: Record<string, unknown> }>(`${apiBase}/agents/${agentId}/proofs/wallet/verify`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startSocialProof: (agentId: string, provider: "github" | "x", payload: Record<string, unknown>) =>
    request<{ provider: string; authorize_url: string; state: string; expires_at: string }>(`${apiBase}/agents/${agentId}/proofs/${provider}/start`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createAttestation: (payload: Record<string, unknown>) =>
    request<{ attestation: Attestation }>(`${apiBase}/attestations`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getRecentReleases: () => request<{ releases: AgentRelease[] }>(`${apiBase}/releases/recent`),
};
