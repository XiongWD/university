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
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
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
