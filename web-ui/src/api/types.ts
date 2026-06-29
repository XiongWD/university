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
  // 排序与偏好（problem2/3/4）
  sort_mode?: "rank" | "probability";
  prefer_local?: boolean;
  prefer_public?: boolean;
  prefer_same_language_major?: boolean;
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
  scope?: {
    source_province: "河南";
    year: 2026;
    track: "历史类";
    batch: "本科批";
  };
  data_ready?: boolean;
  pilot_ready?: boolean;
  production_ready?: boolean;
  coverage_status?: string;
  coverage_notes?: string[];
  coverage?: Record<string, unknown>;
  data_evidence?: Record<string, unknown>;
}

// ===== 河南志愿推：志愿推荐（首页主链路）=====
export interface HenanRecommendationRequest {
  score: number;
  rank?: number | null;
  track: "历史类";
  source_province?: "河南";
  primary_subject: "历史";
  elective_subjects?: string[];
  exam_foreign_language?: string;
  subject_scores_detail?: Record<string, number>;
  strategy?: "自动" | "保守" | "均衡" | "积极";
  // 排序与偏好（problem2/3/4）
  sort_mode?: "rank" | "probability";
  prefer_local?: boolean;
  prefer_public?: boolean;
  interest_majors?: string[];
}

export interface HenanRecommendationResult {
  data_ready: boolean;
  pilot_ready: boolean;
  production_ready: boolean;
  coverage_status: string;
  coverage_notes: string[];
  readiness_errors: string[];
  coverage: Record<string, unknown>;
  data_evidence: Record<string, unknown>;
  buckets: Record<"搏" | "冲" | "稳" | "保" | "垫" | "不推荐" | "需人工复核", HenanTargetItem[]>;
  volunteer_table?: HenanVolunteerTable | null;
  language_restriction_summary?: LanguageRestrictionSummary | null;
}

// 语种限制汇总（日语考生顶部提示）
export interface LanguageRestrictionSummary {
  exam_foreign_language: string;
  hard_blocked_count: number;   // 要求英语语种，不可录取
  soft_warning_count: number;   // 可录取但公共外语仅开英语
  missing_data_count: number;   // 缺少公共外语语种数据
  same_language_major_group_count: number; // 检出的同语种专业组数量
  reachable_same_language_major_group_count: number; // 当前可达结果中的同语种专业组数量
  note: string;
}

// 冲稳保计算明细（位次差比 + 阈值 + 成功率）
export interface BucketDetail {
  student_rank: number | null;
  adjusted_min_rank: number | null;
  rank_gap_ratio: number | null;
  admission_probability: number;   // 投档成功率 0-1
  baseline_year: number | null;
  baseline_granularity: string | null;
  confidence: number;
  thresholds: Record<string, string>;
  formula: string;
}

// 48 志愿草案（策略感知的配额与排序）
export interface HenanVolunteerTable {
  policy_count: number;
  strategy_used: string;          // 自动 / 积极 / 保守 / 均衡
  sort_mode: string;              // rank(位次差比) | probability(成功率)
  prefer_local: boolean;          // 省内优先
  prefer_public: boolean;         // 公办优先
  quota: Record<"冲" | "稳" | "保", [number, number]>;
  used: Record<"冲" | "稳" | "保", number>;
  total: number;
  items: HenanTargetItem[];
}

export interface HenanTargetEvaluationRequest {
  score: number;
  rank?: number | null;
  track: "历史类";
  source_province?: "河南";
  target_school: string;
  target_majors?: string[];
  target_group?: string | null;
  exam_foreign_language?: string;
  primary_subject?: "历史";
  elective_subjects?: string[];
  subject_scores_detail?: Record<string, number>;
  obey_adjustment?: boolean;
}

export interface HenanTargetItem {
  school_name: string;
  major_name: string;
  major_group_code: string;
  major_group_name?: string;
  bucket: string;            // 搏 / 冲 / 稳 / 保 / 垫 / 不推荐 / 需人工复核
  // 三层状态（design §8.3 重构）
  eligibility_status?: "eligible" | "ineligible" | "uncertain";
  admission_tier?: "搏" | "冲" | "稳" | "保" | "垫" | null;
  recommendation_status?: "recommended" | "conditional" | "not_recommended";
  data_confidence?: "high" | "medium" | "low";
  group_bucket?: string;
  major_bucket?: string;
  rank_gap?: number;
  qualified?: boolean;
  bucket_reason?: string;
  blocked_reasons?: string[];
  warnings?: string[];
  missing_data_items?: string[];
  selected_majors?: string[];
  plan_count?: number;
  review_status?: string;
  data_evidence?: Record<string, unknown>;
  // 费用（问题3）：真实学费/住宿费 + 城市生活费 + 4年合计
  tuition?: number | null;
  accommodation?: number | null;
  accommodation_is_estimate?: boolean;
  living_cost_per_year?: number;
  school_system_years?: number;
  four_year_total?: number;
  // 学校性质（问题4）：公办/民办/中外 + 省内/省外 + 985/211
  school_ownership?: string;
  school_province?: string;
  school_city?: string;
  school_level?: string;
  school_tags?: string[];
  is_henan_local?: boolean;
  // 冲稳保计算明细（问题2）+ 投档成功率（problem1）
  admission_probability?: number;
  bucket_detail?: BucketDetail;
  // 语种限制（日语考生场景）
  language_restriction?: { level: "hard_blocked" | "soft_warning" | "missing_data" | "none"; note: string };
}

export interface HenanTargetEvaluationResult {
  school_name: string;
  overall_bucket: string;    // 可评估 / 不推荐
  items: HenanTargetItem[];
  reasons: string[];
  data_ready?: boolean;
  pilot_ready?: boolean;
  production_ready?: boolean;
  coverage_status?: string;
  coverage_notes?: string[];
  coverage?: Record<string, unknown>;
  data_evidence?: Record<string, unknown>;
}

// ============================================================================
// AI 分析相关类型
// ============================================================================

/** AI 志愿推荐请求 */
export interface AIRecommendationRequest {
  score: number;
  rank?: number | null;
  track: "历史类";
  source_province: "河南";
  primary_subject: "历史";
  elective_subjects: string[];
  exam_foreign_language: string;
  subject_scores_detail: Record<string, number>;
  obey_adjustment: boolean;
  extra_preferences: string;  // 额外偏好（如"省内优先、不选民办"）
}

/** AI 目标评估请求 */
export interface AITargetEvaluationRequest {
  score: number;
  rank?: number | null;
  track: "历史类";
  source_province: "河南";
  target_school: string;
  target_majors: string[];
  target_group?: string | null;
  primary_subject: "历史";
  elective_subjects: string[];
  exam_foreign_language: string;
  subject_scores_detail: Record<string, number>;
  obey_adjustment: boolean;
}

/** SSE 流中的单个事件数据 */
export interface SSEChunk {
  delta?: string;
  error?: string;
}
