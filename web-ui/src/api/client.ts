// API 客户端：统一 /api/v1 前缀 + 错误处理
// dev 时 vite proxy 把 /api 转发到 8000，无需配置 base url
import type {
  RecommendRequest,
  VolunteerTable,
  RankResponse,
  ControlLine,
  University,
  CostEstimate,
  SchoolNature,
  LifeTrajectory,
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

// POST /volunteer/life-trajectory（志愿推荐+费用+就业+回本集成）
export function lifeTrajectory(req: RecommendRequest): Promise<LifeTrajectory> {
  return request<LifeTrajectory>("/volunteer/life-trajectory", {
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
