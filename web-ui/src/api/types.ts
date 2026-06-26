// 后端响应类型（严格匹配 app/models/）

export type RiskPreference = "稳" | "中" | "冲";
export type Strategy = "冲" | "稳" | "保";

export interface AdmissionProbability {
  probability: number; // 0-1
  basis: string;
}

export interface VolunteerSuggestion {
  strategy: Strategy;
  school: string;
  major: string | null;
  major_group: string | null;
  subject_requirement: string | null;
  last_year_rank: number;
  last_year_score: number;
  student_rank: number;
  probability: AdmissionProbability;
  note: string | null;
}

export interface VolunteerTable {
  student_score: number;
  student_rank: number;
  equivalent_rank: number | null;
  track: string;
  data_year: number;
  sprint: VolunteerSuggestion[];
  stable: VolunteerSuggestion[];
  safe: VolunteerSuggestion[];
  source_note: string;
}

// POST /volunteer/recommend 请求体
export interface RecommendRequest {
  province: string;
  total_score: number;
  track: string;
  data_year?: number;
  risk_preference?: RiskPreference;
  gender?: string;
  interests?: string[];
  strengths?: string[];
  subject_scores?: Record<string, number>;
  foreign_language?: string;  // 英语/日语/俄语/...
  elective_subjects?: string[];  // 再选科目(3+1+2的"2")
  subject_scores_detail?: Record<string, number>;  // 单科分数
}

// GET /provincial/score-rank/rank 响应
export interface RankResponse {
  province: string;
  year: number;
  track: string;
  score: number;
  rank: number | null;
  source: string;
  confidence: number;
}

// GET /provincial/control-line 响应
export interface ControlLine {
  province: string;
  year: number;
  track: string;
  batches: {
    special_line: number | null;
    first_batch: number | null;
    second_batch: number | null;
    undergrad_batch: number | null;
    junior_college: number | null;
  };
  source: string;
  as_of: string;
  confidence: number;
  note: string | null;
  id: number;
}

// 大学
export type SchoolNature = "公立" | "民办" | "中外合作";

export interface University {
  name: string;
  province: string;
  tier: string;
  nature: SchoolNature;
  tuition: number;
  accommodation: number;
  city: string | null;
  employment_ability: {
    campus_tier: string;
    avg_entry_salary: number;
    employment_rate: number;
  };
  source: string;
  confidence: number;
  note: string | null;
  id: number;
}

// GET /universities/{school}/cost 响应
export interface CostEstimate {
  school: string;
  nature: SchoolNature;
  city: string | null;
  years: number;
  tuition_per_year: number;
  accommodation_per_year: number;
  living_cost_per_year: number;
  annual_total: number;
  grand_total: number;
  city_cost_source: string | null;
  note: string | null;
}

// ===== 志愿推荐请求（遗留，advisory 复用）=====
export interface LifePathsRequest {
  province?: string;
  total_score: number;
  data_year?: number;
  risk_preference?: RiskPreference;
  primary_subject: string;
  chinese_score?: number;
  math_score?: number;
  exam_foreign_language?: string;
  foreign_language_score?: number;
  english_actual_level?: string;
  elective_subjects?: string[];
  family_annual_income?: number;
  family_savings?: number;
  max_annual_education_budget?: number;
  accepted_loan_amount?: number;
  accept_private_school?: boolean;
  // 河南志愿推新增：关注院校 / 兴趣专业 / 展示档位筛选
  focused_schools?: string[];
  interest_majors?: string[];
  display_bucket?: "全部" | "冲" | "稳" | "保";
}

export interface SchoolOption {
  school: string;
  matched_major: string | null;
  ownership: string;
  city: string | null;
  admission_level: string;
  total_cost_4y: number;
  affordability_status: string;
  data_granularity: string;
  confidence: number;
  warnings: string[];
}

export interface AdmissionBuckets {
  reach: SchoolOption[];
  match: SchoolOption[];
  safe: SchoolOption[];
}

// ===== 志愿推荐 advisory（主接口）=====
export type AdvisoryRequest = LifePathsRequest;

export interface MajorDirectionAdvice {
  direction: string;
  recommended_majors: string[];
  market_value: number;
  student_fit: number;
  major_value: number;
  fit_explanation: string[];
  risk_warnings: string[];
}

export interface BudgetSummary {
  tuition_4y: number;
  accommodation_4y: number;
  living_4y: number;
  total_4y: number;
  affordable_total: number | null;
  affordability_status: string;
  data_note: string | null;
}

export interface IneligibleReason {
  school: string;
  major_group_name: string;
  reasons: string[];
  blocked_summary: string;
}

export interface VolunteerAdvisoryResult {
  student_rank: number;
  province: string;
  track: string;
  data_year: number;
  major_directions: MajorDirectionAdvice[];
  school_options: AdmissionBuckets;
  ineligible_options: IneligibleReason[];
  budget_summary: BudgetSummary;
  notes: string[];
  // 河南 2026 升级新增解释字段
  batch_line_decision?: BatchLineDecision | null;
  data_sources?: Array<Record<string, unknown>>;
  review_warnings?: string[];
  recommendation_policy?: string;
}

export interface BatchLineDecision {
  score: number;
  rank: number;
  undergrad_line: number | null;
  junior_college_line: number | null;
  distance_to_undergrad_line: number | null;
  batch_position: string;
  recommendation_policy_note: string;
}

// ===== 目标院校 + 专业评估 =====
export interface TargetEvaluationRequest {
  source_province: string;
  target_school: string;
  target_major?: string | null;
  data_year?: number;
  total_score: number;
  primary_subject: string;
  elective_subjects: string[];
  exam_foreign_language: string;
  foreign_language_score: number;
  math_score: number;
  english_actual_level?: string;
  accept_adjustment?: boolean;
}

export interface TargetEvaluationResult {
  target_school: string;
  target_major: string | null;
  source_province: string;
  eligibility: {
    eligible: boolean;
    blocked_reasons: string[];
    review_warnings: string[];
  };
  group_admission: {
    risk_band: string;
    basis: string;
    student_rank: number | null;
    baseline_rank: number | null;
    data_year_used: number | null;
    confidence: number;
  };
  major_admission: {
    risk_band: string;
    target_major_available: boolean;
    plan_count: number | null;
    basis: string;
    adjustment_risk: string;
  };
  sources: Array<Record<string, unknown>>;
  missing_data: string[];
  recommendation_summary: string;
}

// ===== 河南志愿推：目标评估联动选项 / 目标评估 =====
export interface HenanOptions {
  schools: { code: string; name: string }[];
  majors: { school: string; major: string; group: string }[];
  groups: { school: string; code: string; name: string; track: string }[];
}

// ===== 河南志愿推：志愿推荐（首页主链路）=====
export interface HenanRecommendationRequest {
  score: number;
  rank?: number | null;
  track: string;
  source_province?: string;
  primary_subject: string;
  elective_subjects?: string[];
  exam_foreign_language?: string;
  strategy?: "自动" | "保守" | "均衡" | "积极";
}

export interface HenanRecommendationResult {
  data_ready: boolean;
  readiness_errors: string[];
  coverage: Record<string, unknown>;
  buckets: Record<"冲" | "稳" | "保" | "不推荐" | "需人工复核", HenanTargetItem[]>;
}

export interface HenanTargetEvaluationRequest {
  score: number;
  rank?: number | null;
  track: string;
  source_province?: string;
  target_school: string;
  target_majors?: string[];
  target_group?: string | null;
  exam_foreign_language?: string;
  primary_subject?: string;
  elective_subjects?: string[];
  obey_adjustment?: boolean;
}

export interface HenanTargetItem {
  school_name: string;
  major_name: string;
  major_group_code: string;
  major_group_name?: string;
  bucket: string;            // 冲 / 稳 / 保 / 不推荐 / 需人工复核
  group_bucket?: string;
  major_bucket?: string;
  rank_gap?: number;
  qualified?: boolean;
  bucket_reason?: string;
  blocked_reasons?: string[];
  warnings?: string[];
  selected_majors?: string[];
  plan_count?: number;
  review_status?: string;
}

export interface HenanTargetEvaluationResult {
  school_name: string;
  overall_bucket: string;    // 可评估 / 不推荐
  items: HenanTargetItem[];
  reasons: string[];
}
