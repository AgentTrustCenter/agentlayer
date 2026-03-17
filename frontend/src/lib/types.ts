export type Agent = {
  id: string;
  handle: string;
  name: string;
  description: string;
  homepage_url?: string | null;
  capabilities: string[];
  tags: string[];
  profile_links: ProfileLinks;
  wallet_claims: WalletClaim[];
  external_proofs: ExternalProof[];
  public_key_fingerprint: string;
  key_algorithm: string;
  identity_version?: number;
  active_key_id?: string | null;
  key_history?: KeyHistoryEntry[];
  recovery_public_keys?: RecoveryKeySummary[];
  trust_lenses?: TrustLenses;
  sybil_risk_score?: number;
  trust_score: number;
  incoming_attestations_count: number;
  outgoing_attestations_count: number;
  created_at: string;
  updated_at: string;
  status: string;
  profile_url: string;
  api_url: string;
  verification_status: string;
  access_tier: string;
  badges: string[];
  eligibility: {
    discovery: boolean;
    routing: boolean;
    marketplace: boolean;
    settlement: boolean;
  };
  next_unlocks: string[];
  economic_security: EconomicSecurity;
  release_penalty: number;
  release_warning_active: boolean;
  release_warning_level?: string | null;
  release_warning_message?: string | null;
  release_verification_count: number;
  latest_release?: AgentRelease | null;
};

export type TrustLenses = {
  execution: number;
  payment: number;
  research: number;
};

export type KeyHistoryEntry = {
  event_type: string;
  public_key_fingerprint: string;
  created_at: string;
};

export type RecoveryKeySummary = {
  key_id: string;
  algorithm: string;
  label: string;
};

export type Attestation = {
  id: string;
  issuer_agent_id: string;
  subject_agent_id: string;
  kind: string;
  summary: string;
  evidence_url?: string | null;
  interaction_ref?: string | null;
  confidence: number;
  score_delta: number;
  created_at: string;
  schema_version?: string;
  evidence_hash?: string | null;
  evidence_bundle?: EvidenceBundle | null;
  trust_lenses?: Partial<TrustLenses>;
  issuer_credibility?: number;
  signed_payload: Record<string, unknown>;
};

export type EvidenceBundle = {
  pointer_url?: string | null;
  sha256?: string | null;
  mime_type?: string | null;
  redaction_level?: string | null;
  contains_personal_data?: boolean;
  notes?: string | null;
};

export type ScoreboardEntry = Agent & {
  rank: number;
};

export type DiscoveryDocument = {
  platform_name: string;
  status: string;
  registration_url: string;
  registration_quickstart_url: string;
  registration_challenge_url: string;
  auth_challenge_url: string;
  auth_verify_url: string;
  auth_refresh_url: string;
  auth_revoke_url: string;
  registry_url: string;
  resolve_handle_url_template?: string;
  agent_profile_url_template?: string;
  wallet_proof_challenge_url_template?: string;
  wallet_proof_verify_url_template?: string;
  social_proof_start_url_template?: string;
  oauth_callback_url_template?: string;
  attestation_url: string;
  release_publish_url_template?: string;
  release_verify_url_template?: string;
  recent_releases_url?: string;
  agent_keys_url_template?: string;
  key_rotate_url_template?: string;
  key_recover_url_template?: string;
  partner_evaluation_url_template?: string;
  audit_events_url?: string;
  ops_metrics_url?: string;
  economic_security_url?: string;
  agent_economic_security_url_template?: string;
  disputes_url?: string;
  agent_disputes_url_template?: string;
  dispute_review_url_template?: string;
  scoreboard_url: string;
  graph_url: string;
  network_policy_url: string;
  partner_policies_url?: string;
  passport_verification_url: string;
  platform_public_key: string;
  platform_signature_algorithm: string;
  agent_supported_key_algorithms: string[];
  capabilities: string[];
};

export type QuickstartStep = {
  step: number;
  title: string;
  details: string;
};

export type RegistrationQuickstart = {
  summary: string;
  steps: QuickstartStep[];
  required_fields: string[];
  sample_claim: Record<string, unknown>;
  curl_example: string;
  challenge_flow: {
    optional: boolean;
    endpoint: string;
    benefit: string;
  };
};

export type RegistrationChallenge = {
  payload: {
    challenge_id: string;
    nonce: string;
    issued_at: string;
    expires_at: string;
    purpose: string;
  };
  platform_signature: string;
  platform_signature_algorithm: string;
  platform_public_key: string;
  required_claim_field: string;
};

export type TierThreshold = {
  tier: string;
  min_score: number;
  requirements: string[];
  unlocks: string[];
};

export type NetworkPolicy = {
  positioning: {
    core_message: string;
    why_agents_register: string[];
  };
  startup_wedge: {
    initial_wedge: {
      buyer: string;
      problem: string;
      product: string;
    };
    primary_buyers: Array<{
      buyer: string;
      pain: string;
      decision: string;
    }>;
    monetization: Array<{
      motion: string;
      description: string;
    }>;
  };
  registration_value: Array<{
    value: string;
    description: string;
  }>;
  tier_thresholds: TierThreshold[];
  routing_policy: {
    default_preference: string;
    ranking_factors: string[];
    anonymous_agent_penalty: string;
  };
  owner_console: {
    thesis: string;
    supported_claims: string[];
    verification_methods: string[];
  };
  integration_hooks: {
    quickstart_url: string;
    challenge_url: string;
    auth_challenge_url: string;
    auth_verify_url: string;
    auth_refresh_url: string;
    auth_revoke_url: string;
    registry_url: string;
    resolve_handle_url_template: string;
    agent_profile_url_template: string;
    agent_keys_url_template: string;
    key_rotate_url_template: string;
    key_recover_url_template: string;
    partner_evaluation_url_template: string;
    release_publish_url_template: string;
    release_verify_url_template: string;
    recent_releases_url: string;
    partner_policies_url: string;
    passport_verify_url: string;
    audit_events_url: string;
    ops_metrics_url: string;
  };
  partner_policies: PartnerPolicy[];
  integration_examples: IntegrationExample[];
  trust_defenses: {
    thesis: string;
    layers: Array<{
      layer: string;
      purpose: string;
      anti_sybil_effect: string;
    }>;
    costly_actions: {
      verdict: string;
      recommended_use: string[];
      warning: string;
    };
    high_impact_policy: string[];
  };
  economic_security: {
    bond_unit: string;
    min_settlement_bond: number;
    suggested_holdback_ratio: number;
    slash_priority: string[];
    principle: string;
    bond_model: string[];
  };
  dispute_workflow: {
    principle: string;
    steps: string[];
  };
  release_provenance: {
    principle: string;
    warning_rule: string;
    supported_proofs?: string[];
  };
  external_proofs: {
    principle: string;
    supported_now: string[];
    next_step: string;
  };
};

export type EconomicSecurity = {
  currency: string;
  available_balance: number;
  holdback_balance: number;
  slashed_total: number;
  total_posted: number;
  total_released: number;
  net_bonded_balance: number;
  coverage_ratio: number;
  settlement_ready: boolean;
  active_holdback: boolean;
  security_tier: string;
};

export type EconomicEvent = {
  id: string;
  agent_id: string;
  actor_agent_id?: string | null;
  partner?: string | null;
  event_type: string;
  amount: number;
  reason: string;
  evidence_url?: string | null;
  created_at: string;
  event_payload: Record<string, unknown>;
};

export type EconomicOverview = {
  policy: NetworkPolicy["economic_security"];
  top_bonded_agents: Agent[];
  recent_events: EconomicEvent[];
};

export type DisputeReview = {
  id: string;
  dispute_id: string;
  reviewer_agent_id: string;
  verdict: string;
  summary: string;
  recommended_slash_amount: number;
  created_at: string;
};

export type DisputeCase = {
  id: string;
  subject_agent_id: string;
  opened_by_agent_id: string;
  category: string;
  severity: string;
  title: string;
  summary: string;
  evidence_url?: string | null;
  status: string;
  auto_holdback_amount: number;
  recommended_slash_amount: number;
  resolution?: string | null;
  resolution_summary?: string | null;
  created_at: string;
  resolved_at?: string | null;
  schema_version?: string;
  evidence_hash?: string | null;
  evidence_bundle?: EvidenceBundle | null;
  privacy_redaction?: string | null;
  related_attestation_id?: string | null;
  related_release_id?: string | null;
  review_count: number;
  reviews: DisputeReview[];
};

export type GraphNode = {
  id: string;
  label: string;
  handle: string;
  score: number;
  attestations: number;
  tier: string;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  kind: string;
  score_delta: number;
  confidence: number;
};

export type AgentRelease = {
  id: string;
  agent_id: string;
  schema_version?: string;
  version_label: string;
  repo_url?: string | null;
  commit_sha?: string | null;
  commit_url?: string | null;
  release_tag?: string | null;
  summary: string;
  model_version?: string | null;
  runtime_target?: string | null;
  capabilities_snapshot: string[];
  major_change: boolean;
  breaking_change: boolean;
  verification_count: number;
  manifest_hash?: string | null;
  provenance_proofs?: ProvenanceProof[];
  created_at: string;
};

export type ProvenanceProof = {
  type: string;
  value: string;
  verified?: boolean;
  issuer?: string | null;
  notes?: string | null;
};

export type ActiveIdentity = {
  agentId: string;
  name: string;
  privateKeyPem: string;
  publicKeyPem: string;
};

export type ProfileLinks = {
  x_handle?: string;
  x_url?: string;
  github_handle?: string;
  github_url?: string;
  docs_url?: string;
  support_url?: string;
};

export type WalletClaim = {
  chain: string;
  chain_label?: string;
  address: string;
  label?: string;
  status?: string;
  proof_method?: string;
  proof_value?: string | null;
  verified_at?: string | null;
};

export type ExternalProof = {
  type: string;
  value: string;
  status?: string;
  proof_url?: string | null;
  notes?: string | null;
};

export type PartnerPolicy = {
  partner: string;
  category: string;
  min_access_tier: string;
  allowed_scopes: string[];
  default_scopes: string[];
  requirements: string[];
};

export type IntegrationExample = {
  name: string;
  goal: string;
  entrypoint: string;
  flow: string[];
};

export type SessionTokenEnvelope = {
  payload: Record<string, unknown>;
  platform_signature: string;
  platform_signature_algorithm: string;
};

export type SessionTokens = {
  access_token: SessionTokenEnvelope;
  refresh_token: SessionTokenEnvelope;
};

export type PartnerEvaluation = {
  partner: string;
  allowed: boolean;
  reason: string;
  policy: PartnerPolicy | null;
  agent: {
    access_tier: string;
    trust_score: number;
    trust_lenses: TrustLenses;
    sybil_risk_score: number;
    economic_security: EconomicSecurity;
    release_warning_active: boolean;
    release_warning_level?: string | null;
  };
};

export type AuditEvent = {
  id: string;
  event_type: string;
  agent_id?: string | null;
  actor_agent_id?: string | null;
  partner?: string | null;
  severity: string;
  event_payload: Record<string, unknown>;
  created_at: string;
};

export type AgentKeyLifecycle = {
  agent_id: string;
  identity_version: number;
  active_key_id: string;
  active_public_key_fingerprint: string;
  recovery_public_keys: RecoveryKeySummary[];
  history: KeyHistoryEntry[];
  events: Array<{
    id: string;
    event_type: string;
    previous_public_key_fingerprint?: string | null;
    new_public_key_fingerprint?: string | null;
    recovery_key_id?: string | null;
    created_at: string;
  }>;
};

export type OpsMetrics = {
  agents: number;
  attestations: number;
  releases: number;
  disputes_open: number;
  sessions_active: number;
  audit_events: number;
  timestamp: string;
};
