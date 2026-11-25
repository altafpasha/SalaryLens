export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  organization_id: string;
  organization_name: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
  user_id: string;
  organization_id: string;
  role: string;
}

export interface DashboardSummary {
  total_statements?: number;
  total_statements_processed?: number;
  likely_salary_count: number;
  possible_salary_count: number;
  multiple_candidates_count?: number;
  multiple_salary_candidates_count?: number;
  insufficient_evidence_count: number;
  requires_human_review_count: number;
  pending_reviews_count: number;
  average_salary_usd?: number;
  average_monthly_salary_usd?: number;
  total_spend_usd?: number;
  total_ai_spend_usd?: number;
}

export interface StatementItem {
  statement_id: string;
  filename: string;
  file_size_bytes: number;
  page_count: number;
  duration_months?: number | null;
  status: 'pending' | 'processing' | 'completed' | 'requires_human_review' | 'failed';
  is_scanned: boolean;
  workbook_status?: string | null;
  total_transactions_count?: number;
  included_in_salary_count?: number;
  excluded_from_salary_count?: number;
  detected_employer?: string | null;
  salary_status?: string | null;
  average_salary?: number | null;
  currency?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CandidateGroup {
  employer_name: string;
  aliases: string[];
  transaction_count: number;
  months_count: number;
  missing_months: (string | number)[];
  average_amount: number;
  median_amount: number;
  min_amount: number;
  max_amount: number;
  amount_variation_pct: number;
  recurrence_score: number;
  is_primary: boolean;
}

export interface JevDecision {
  status: string;
  recommended_employer?: string | null;
  estimated_monthly_salary?: number | null;
  confidence_score?: number | null;
  reasoning: string;
  supporting_transaction_ids: string[];
  supporting_months: (string | number)[];
  reason_codes: string[];
  uncertainties: string[];
  requires_human_review: boolean;
  model_name?: string | null;
  prompt_version?: string | null;
}

export interface ModelDiagnostic {
  stage: string;
  model_name: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms: number;
  provider_cost_usd: number;
  is_simulated: boolean;
  success: boolean;
}

export interface StatementResults {
  statement_id: string;
  status: string;
  detected_employer?: string | null;
  supporting_transaction_ids: string[];
  supporting_months: (string | number)[];
  reason_codes: string[];
  explanation: string;
  uncertainties: string[];
  requires_human_review: boolean;
  candidate_groups: CandidateGroup[];
  total_ai_cost_usd: number;
  total_tokens: number;
  is_demo: boolean;
  currency?: string;
  confidence_score?: number | null;
  estimated_monthly_salary?: number | null;
  salary_transaction_count?: number;
  months_analyzed_count?: number;
  jev_decision?: JevDecision | null;
  model_diagnostics?: ModelDiagnostic[];
  analysis_completed_at?: string | null;
}

export interface EngineSettings {
  ocr_engine: string;
  local_llm_provider: string;
  local_llm_model: string;
  salary_finder_model: string;
  decision_model: string;
  available_ocr_engines?: string[];
  available_local_models?: string[];
  available_cloud_models?: string[];
}

export interface StatementTransaction {
  id: string;
  transaction_date: string;
  value_date?: string | null;
  raw_description: string;
  normalized_description: string;
  credit_amount?: number | null;
  debit_amount?: number | null;
  balance?: number | null;
  currency: string;
  page_number: number;
  transaction_direction?: string | null;
  category?: string | null;
  included_in_salary_analysis?: boolean;
  exclusion_reason?: string | null;
  inclusion_reason?: string | null;
  validation_status?: string | null;
  is_salary_candidate?: boolean;
  candidate_employer?: string | null;
  is_reversal?: boolean;
  is_duplicate?: boolean;
}

export interface PaginatedTransactions {
  statement_id: string;
  total_count: number;
  page: number;
  page_size: number;
  transactions: StatementTransaction[];
}

export interface HealthStatus {
  status: string;
  environment: string;
  timestamp: string;
  version?: string;
}

export interface PipelineLogEntry {
  timestamp: string;
  stage: string;
  level: string;
  title: string;
  message: string;
  metadata?: Record<string, any>;
}

