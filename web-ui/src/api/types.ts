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
