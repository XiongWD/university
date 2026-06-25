import { useState } from "react";
import { AlertCircle, Rocket, ShieldCheck, Anchor } from "lucide-react";
import ScoreForm from "../components/ScoreForm";
import TrajectoryCard from "../components/TrajectoryCard";
import { lifeTrajectory, ApiError } from "../api/client";
import type { RecommendRequest, LifeTrajectory } from "../api/types";

const BUCKETS = [
  { key: "sprint" as const, label: "冲", icon: Rocket, color: "text-orange-300", desc: "有希望但冒险" },
  { key: "stable" as const, label: "稳", icon: ShieldCheck, color: "text-emerald-300", desc: "匹配度最高" },
  { key: "safe" as const, label: "保", icon: Anchor, color: "text-sky-300", desc: "稳妥兜底" },
];

export default function HomePage() {
  const [loading, setLoading] = useState(false);
  const [traj, setTraj] = useState<LifeTrajectory | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(req: RecommendRequest) {
    setLoading(true);
    setError(null);
    try {
      const t = await lifeTrajectory(req);
      setTraj(t);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "请求失败，请确认后端服务已启动");
      setTraj(null);
    } finally {
      setLoading(false);
    }
  }

  const total = traj ? traj.sprint.length + traj.stable.length + traj.safe.length : 0;

  return (
    <div className="space-y-6">
      {/* Hero */}
      {!traj && (
        <div className="text-center py-6 animate-fade-in">
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
            <span className="bg-gradient-to-r from-pink-400 via-fuchsia-400 to-indigo-400 bg-clip-text text-transparent">
              填报志愿，看见孩子的人生轨迹
            </span>
          </h1>
          <p className="text-white/60 mt-3 text-sm sm:text-base">
            输入分数 → 冲稳保志愿 → 大学花费 · 毕业收入 · 回本周期，一目了然
          </p>
        </div>
      )}

      <ScoreForm loading={loading} onSubmit={handleSubmit} />

      {error && (
        <div className="glass rounded-2xl p-4 border border-red-400/30 flex items-start gap-2 text-sm text-red-200">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <div>
            <p className="font-medium">出错了</p>
            <p className="text-red-200/70 text-xs mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {traj && (
        <div className="animate-slide-up">
          {/* 考生摘要 */}
          <div className="glass rounded-3xl p-6 mb-6 shadow-xl">
            <div className="flex flex-wrap items-center justify-around gap-4 text-center">
              <div>
                <div className="text-3xl font-bold bg-gradient-to-r from-pink-400 to-indigo-400 bg-clip-text text-transparent">
                  {traj.student_score}
                </div>
                <div className="text-xs text-white/50 mt-1">高考分数</div>
              </div>
              <div className="w-px h-12 bg-white/10" />
              <div>
                <div className="text-3xl font-bold text-white">
                  {traj.student_rank.toLocaleString()}
                </div>
                <div className="text-xs text-white/50 mt-1">全省位次</div>
              </div>
              <div className="w-px h-12 bg-white/10" />
              <div>
                <div className="text-xl font-bold text-white">{traj.track}</div>
                <div className="text-xs text-white/50 mt-1">{traj.data_year}年数据</div>
              </div>
            </div>
          </div>

          {total === 0 ? (
            <div className="glass rounded-3xl p-10 text-center text-white/50">
              该分数段暂无匹配院校数据，可尝试切换数据年份或科类。
            </div>
          ) : (
            <>
              {BUCKETS.map((b) => {
                const list = traj[b.key];
                if (list.length === 0) return null;
                return (
                  <div key={b.key} className="mb-7">
                    <div className="flex items-center gap-2 mb-3 px-1">
                      <b.icon className={`w-5 h-5 ${b.color}`} />
                      <h3 className="font-bold text-lg">{b.label}</h3>
                      <span className="text-xs text-white/40">{b.desc}</span>
                      <span className="ml-auto text-xs text-white/40">{list.length} 所</span>
                    </div>
                    <div className="grid sm:grid-cols-2 gap-3">
                      {list.map((item, i) => (
                        <TrajectoryCard key={`${item.school}-${i}`} item={item} index={i} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </>
          )}

          {/* 来源说明 */}
          <div className="glass rounded-2xl p-4 mt-6 text-xs text-white/50 leading-relaxed">
            {traj.source_note}
          </div>
        </div>
      )}
    </div>
  );
}
