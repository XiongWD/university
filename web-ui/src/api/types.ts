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

// ===== 人生轨迹（志愿推荐+费用+就业+回本集成）=====
export interface CostSummary {
  tuition_total: number;
  accommodation_total: number;
  living_total: number;
  grand_total: number;
  annual_total: number;
  years: number;
  nature: SchoolNature;
  city: string | null;
  city_cost_source: string | null;
}

export interface CareerProspect {
  major_name: string | null;
  entry_salary_low: number;
  entry_salary_mid: number;
  entry_salary_high: number;
  mid_salary_5y: number | null;
  ceil_salary_15y: number | null;
  stability: number | null;
  establishment_type: string | null;
  source: string;
}

export interface PaybackAnalysis {
  total_investment: number;
  annual_income_after_grad: number;
  years_to_break_even: number;
  lifetime_15y_net: number;
  note: string;
}

export interface TrajectoryItem {
  strategy: string;
  school: string;
  major: string | null;
  major_group: string | null;
  subject_requirement: string | null;
  batch?: string;
  degree_level?: string;
  foreign_language_required?: string;
  single_subject_requirements?: Record<string, number>;
  last_year_rank: number;
  last_year_score: number;
  student_rank: number;
  probability: number;
  cost: CostSummary | null;
  career: CareerProspect | null;
  payback: PaybackAnalysis | null;
  note: string | null;
}

export interface LifeTrajectory {
  student_score: number;
  student_rank: number;
  track: string;
  data_year: number;
  sprint: TrajectoryItem[];
  stable: TrajectoryItem[];
  safe: TrajectoryItem[];
  source_note: string;
}

// ===== V2.2 人生路径 =====
export interface LifePathsRequest {
  province?: string;
  total_score: number;
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

export interface LifePath {
  path_type: string;
  title: string;
  summary: string;
  major_direction: string;
  recommended_majors: string[];
  target_careers: string[];
  university_cost_4y: number;
  pressure_coefficient: number;
  affordability_status: string;
  expected_start_salary_p50: number;
  major_value_score: number;
  overall_score: number;
  risk_level: string;
  key_benefits: string[];
  key_risks: string[];
  school_buckets: AdmissionBuckets;
}

export interface LifePathResult {
  paths: LifePath[];
  notes: string[];
  model_version: string;
}
