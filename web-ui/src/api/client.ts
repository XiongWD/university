// API 客户端：统一 /api/v1 前缀 + 错误处理
// dev 时 vite proxy 把 /api 转发到 8000，无需配置 base url
//
// 注意：后端 /volunteer/life-paths、/volunteer/life-trajectory 端点已 deprecated，
// 仅为兼容旧调用与回归测试保留，前端主入口已切换到 /volunteer/advisory。
// 后续若完整移除 deprecated 后端模块，需先把 SchoolOption/AdmissionBuckets 从
// life_path 迁出到 advisory/shared 模型。
import type {
  RecommendRequest,
  VolunteerTable,
  RankResponse,
  ControlLine,
  University,
  CostEstimate,
  SchoolNature,
  AdvisoryRequest,
  VolunteerAdvisoryResult,
  TargetEvaluationRequest,
  TargetEvaluationResult,
  HenanOptions,
  HenanTargetEvaluationRequest,
  HenanTargetEvaluationResult,
  HenanRecommendationRequest,
  HenanRecommendationResult,
  AIRecommendationRequest,
  AITargetEvaluationRequest,
  SSEChunk,
  UserVolunteerGroup,
  AddVolunteerItemRequest,
  ApplyLayoutRequest,
  ConflictResponse,
} from "./types";

const BASE = "/api/v1";

// ── 测试 owner 隔离（E2E 用）─────────────────────────────────────────────
// 设置后所有志愿组请求带 X-Owner-Key header，后端在 VOLUNTEER_OWNER_ISOLATION=1 时
// 据此隔离不同 owner 的志愿组。生产环境不设置，保持 "default" 单用户。
// 可由测试通过 window.__test_owner_key__ 注入；Playwright E2E 当前直接用浏览器上下文
// extraHTTPHeaders 注入，同样会随 fetch 发出。测试 Node fetch 需自行带同一 header。
const OWNER_STORAGE_KEY = "__test_owner_key__";
function currentOwnerKey(): string | null {
  try {
    return (window as unknown as { [k: string]: string | undefined })[OWNER_STORAGE_KEY] ?? null;
  } catch {
    return null;  // Node 环境（无 window），由测试 Node fetch 自行带 header
  }
}
function ownerHeaders(): Record<string, string> {
  const k = currentOwnerKey();
  return k ? { "X-Owner-Key": k } : {};
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...ownerHeaders(), ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(text || `请求失败 (${res.status})`, res.status);
  }
  return res.json() as Promise<T>;
}

// POST /volunteer/recommend
export function recommend(req: RecommendRequest): Promise<VolunteerTable> {
  return request<VolunteerTable>("/volunteer/recommend", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// POST /volunteer/advisory
export function advisory(req: AdvisoryRequest): Promise<VolunteerAdvisoryResult> {
  return request<VolunteerAdvisoryResult>("/volunteer/advisory", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// POST /target/evaluate
export function evaluateTarget(req: TargetEvaluationRequest): Promise<TargetEvaluationResult> {
  return request<TargetEvaluationResult>("/target/evaluate", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// GET /henan/options（河南志愿推：院校/专业/专业组联动下拉）
export function getHenanOptions(): Promise<HenanOptions> {
  return request<HenanOptions>("/henan/options");
}

// POST /henan/recommendation（河南志愿推：首页志愿推荐主链路）
export function henanRecommendation(req: HenanRecommendationRequest): Promise<HenanRecommendationResult> {
  return request<HenanRecommendationResult>("/henan/recommendation", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// POST /henan/target-evaluation（河南志愿推：目标院校评估，复用首页冲稳保逻辑）
export function evaluateHenanTarget(req: HenanTargetEvaluationRequest): Promise<HenanTargetEvaluationResult> {
  return request<HenanTargetEvaluationResult>("/henan/target-evaluation", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// GET /provincial/score-rank/rank
export function scoreToRank(
  province: string,
  year: number,
  track: string,
  score: number
): Promise<RankResponse> {
  const q = new URLSearchParams({ province, year: String(year), track, score: String(score) });
  return request<RankResponse>(`/provincial/score-rank/rank?${q}`);
}

// GET /provincial/score-rank/score
export function rankToScore(
  province: string,
  year: number,
  track: string,
  rank: number
): Promise<RankResponse & { score: number | null }> {
  const q = new URLSearchParams({ province, year: String(year), track, rank: String(rank) });
  return request(`/provincial/score-rank/score?${q}`);
}

// GET /provincial/control-line
export function getControlLine(
  province?: string,
  year?: number,
  track?: string
): Promise<ControlLine[]> {
  const q = new URLSearchParams();
  if (province) q.set("province", province);
  if (year) q.set("year", String(year));
  if (track) q.set("track", track);
  return request(`/provincial/control-line?${q}`);
}

// GET /universities
export function listUniversities(
  nature?: SchoolNature,
  province?: string
): Promise<University[]> {
  const q = new URLSearchParams();
  if (nature) q.set("nature", nature);
  if (province) q.set("province", province);
  return request(`/universities?${q}`);
}

// GET /universities/{school}/cost
export function estimateCost(school: string, years?: number): Promise<CostEstimate | null> {
  const q = years ? `?years=${years}` : "";
  return request(`/universities/${encodeURIComponent(school)}/cost${q}`);
}

// ============================================================================
// SSE 流式 AI 调用（非标准 JSON 响应，需手动处理 ReadableStream）
// ============================================================================

/**
 * 通用 SSE 流式读取器
 * 调用后端 SSE 端点，逐条 yield 解析后的 SSEChunk
 */
export async function* streamSSE(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<SSEChunk, void, undefined> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(text || `AI 服务请求失败 (${res.status})`, res.status);
  }

  const reader = res.body?.getReader();
  if (!reader) {
    throw new ApiError("AI 服务未返回流式响应", 500);
  }

  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      // SSE 事件以 \n\n 分隔
      const lines = buffer.split("\n\n");
      // 保留最后一个可能不完整的片段
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data: ")) continue;

        const jsonStr = trimmed.slice(6); // 去掉 "data: " 前缀
        if (jsonStr === "[DONE]") return;

        try {
          const chunk: SSEChunk = JSON.parse(jsonStr);
          yield chunk;
        } catch {
          // 忽略解析失败的行
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/** POST /henan/ai/recommend — AI 志愿推荐（SSE 流式） */
export function streamAiRecommend(
  req: AIRecommendationRequest,
  signal?: AbortSignal,
): AsyncGenerator<SSEChunk, void, undefined> {
  return streamSSE("/henan/ai/recommend", req, signal);
}

/** POST /henan/ai/evaluate — AI 目标评估（SSE 流式） */
export function streamAiEvaluate(
  req: AITargetEvaluationRequest,
  signal?: AbortSignal,
): AsyncGenerator<SSEChunk, void, undefined> {
  return streamSSE("/henan/ai/evaluate", req, signal);
}

// ============================================================================
// 我的志愿组（志愿编排工作台）
// ============================================================================

/** 志愿组操作结果：成功返回 group，409 冲突返回 ConflictResponse（含最新 group） */
export type VolunteerResult =
  | { ok: true; group: UserVolunteerGroup }
  | { ok: false; conflict: ConflictResponse };

/** 统一处理志愿组写操作：200→成功，409→冲突（带最新group），其他→抛 ApiError */
async function volunteerRequest(path: string, init: RequestInit): Promise<VolunteerResult> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...ownerHeaders(), ...(init.headers ?? {}) },
  });
  if (res.status === 409) {
    const body = (await res.json().catch(() => ({}))) as ConflictResponse;
    return { ok: false, conflict: body };
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(text || `请求失败 (${res.status})`, res.status);
  }
  const group = (await res.json()) as UserVolunteerGroup;
  return { ok: true, group };
}

/** GET /my-volunteers — 获取志愿组（重算 latest_algorithm_tier + stats） */
export function getMyVolunteers(): Promise<UserVolunteerGroup> {
  return request<UserVolunteerGroup>("/my-volunteers");
}

/** heao 权威评估：{校名: {school_name, yxdh, groups: [{zyzh, requirement, min_score_2025, ...}]}} */
export type HeaoMajorHistory = {
  year: string;
  min_score: number | null;
  max_score: number | null;
  min_rank: number | null;
  avg_score: string | null;
  admit_count: number | null;
};
export type HeaoMajor = {
  major_name: string;
  major_code: string;
  history: HeaoMajorHistory[];
};
export type HeaoGroup = {
  zyzh: string;
  requirement: string;
  min_score_2025: number | null;
  min_rank_2025: number | null;
  equiv_score_2026: number | null;
  advantage: number | null;
  advantage_ratio: number | null;
  tier: string;
  majors: HeaoMajor[];
};
export type HeaoSchoolAssessment = {
  school_name: string;
  yxdh: string;
  ownership: string;
  province: string;
  city: string;
  tuition: number | null;
  groups: HeaoGroup[];
};

/** GET /my-volunteers/heao-assessment — heao 权威评估数据（2025 历年专业组录取） */
export function getHeaoAssessment(): Promise<Record<string, HeaoSchoolAssessment>> {
  return request<Record<string, HeaoSchoolAssessment>>("/my-volunteers/heao-assessment");
}

/** 国贸/商务推荐候选（heao 验证） */
export type BizRecommendation = {
  school: string;
  zyzh: string;
  req: string;
  score: number;
  rank: number;
  gap: number;
  biz: string[];
  majors: string[];
  ownership?: string;
  province?: string;
  city?: string;
  tuition?: number;
  tier?: string;
};

/** 完整评估报告：评估+推荐+建议 */
export type FullAssessment = {
  heao_assessment: Record<string, HeaoSchoolAssessment>;
  biz_recommendations: BizRecommendation[];
  recommendation_text: string;
};

/** GET /my-volunteers/full-assessment — 完整评估报告 */
export function getFullAssessment(): Promise<FullAssessment> {
  return request<FullAssessment>("/my-volunteers/full-assessment");
}

/** 志愿建议项 */
export type SuggestionMajor = { major_code: string; major_name: string };
export type SuggestionItem = {
  index: number;
  school: string;
  yxdh: string;
  ownership: string;
  province: string;
  city: string;
  zyzh: string;
  requirement: string;
  min_score_2025: number | null;
  min_rank_2025: number | null;
  equiv_score_2026: number | null;
  gap: number | null;
  tier: string;
  majors: SuggestionMajor[];
  tuition: number | null;
  accommodation: number;
  monthly_cost: number;
  four_year_total: number;
  source: string; // brother(弟弟选) / recommended(推荐)
  planned_tier?: string | null; // 弟弟原设定档位
  eligible?: boolean;
  eligibility_status?: string; // 可填 / 有风险 / 不可填
  eligibility_reasons?: string[];
};
export type SuggestionStats = {
  total: number;
  by_tier: Record<string, number>;
  by_source?: { brother: number; recommended: number };
  by_ownership: Record<string, number>;
  by_province: Record<string, number>;
  tuition_min: number;
  tuition_max: number;
  four_year_min: number;
  four_year_max: number;
  local_count: number;
};
export type VolunteerSuggestion = {
  items: SuggestionItem[];
  stats: SuggestionStats;
  pool_total: number;
  skipped_ineligible: SuggestionItem[];
  brother_profile: {
    score: number; rank: number | null; track: string;
    primary_subject: string; elective_subjects: string[];
    exam_foreign_language: string;
  };
};

/** GET /my-volunteers/volunteer-suggestion — 生成志愿建议 */
export function getVolunteerSuggestion(rush: number, steady: number, safe: number): Promise<VolunteerSuggestion> {
  return request<VolunteerSuggestion>(
    `/my-volunteers/volunteer-suggestion?rush=${rush}&steady=${steady}&safe=${safe}`,
  );
}

/** POST /my-volunteers/items — 添加志愿（服务端重新校验） */
export function addVolunteerItem(req: AddVolunteerItemRequest): Promise<VolunteerResult> {
  return volunteerRequest("/my-volunteers/items", {
    method: "POST", body: JSON.stringify(req),
  });
}

/** PATCH /my-volunteers/layout — 原子布局更新（跨档拖拽专用） */
export function applyVolunteerLayout(req: ApplyLayoutRequest): Promise<VolunteerResult> {
  return volunteerRequest("/my-volunteers/layout", {
    method: "PATCH", body: JSON.stringify(req),
  });
}

/** PATCH /my-volunteers/items/{id}/tier — 单改规划档位（null=恢复算法档） */
export function updateVolunteerTier(itemId: number, plannedTier: string | null, version: number): Promise<VolunteerResult> {
  return volunteerRequest(`/my-volunteers/items/${itemId}/tier`, {
    method: "PATCH", body: JSON.stringify({ planned_tier: plannedTier, version }),
  });
}

/** DELETE /my-volunteers/items/{id} — 删除单个志愿（version 走 query） */
export function deleteVolunteerItem(itemId: number, version: number): Promise<VolunteerResult> {
  return volunteerRequest(`/my-volunteers/items/${itemId}?version=${version}`, {
    method: "DELETE",
  });
}

/** POST /my-volunteers/clear — 清空全部 */
export function clearVolunteers(version: number): Promise<VolunteerResult> {
  return volunteerRequest("/my-volunteers/clear", {
    method: "POST", body: JSON.stringify({ confirm: true, version }),
  });
}
