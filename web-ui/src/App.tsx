import { useEffect } from "react";
import { Routes, Route, NavLink } from "react-router-dom";
import { GraduationCap, Calculator, LineChart, Target, Layers } from "lucide-react";
import HomePage from "./pages/HomePage";
import RankPage from "./pages/RankPage";
import ControlLinePage from "./pages/ControlLinePage";
import TargetEvaluationPage from "./pages/TargetEvaluationPage";
import MyGroupsPage from "./pages/MyGroupsPage";
import Toaster from "./components/Toaster";
import VolunteerDock from "./components/VolunteerDock";
import { useVolunteerStore } from "./store/volunteerStore";

const navItems = [
  { to: "/", label: "志愿推荐", icon: GraduationCap, end: true },
  { to: "/target-evaluation", label: "目标评估", icon: Target },
  { to: "/my-groups", label: "志愿编排", icon: Layers },
  { to: "/rank", label: "位次工具", icon: LineChart },
  { to: "/control-line", label: "省控线", icon: Calculator },
];

export default function App() {
  // 应用启动时加载志愿组（跨页面共享），离开前 flush 待删除项
  const loadGroup = useVolunteerStore((s) => s.loadGroup);
  const flushPendingDeletes = useVolunteerStore((s) => s.flushPendingDeletes);

  useEffect(() => {
    void loadGroup();
    return () => { void flushPendingDeletes(); };
  }, [loadGroup, flushPendingDeletes]);

  return (
    <div className="min-h-screen">
      {/* 顶栏 */}
      <header className="sticky top-0 z-20 glass border-b border-white/10">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center gap-2">
          <div className="flex items-center gap-2 mr-auto">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-pink-500 to-indigo-500 flex items-center justify-center shadow-lg">
              <GraduationCap className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-lg tracking-tight">河南志愿推</span>
            <span className="text-xs text-white/50 hidden sm:inline">河南高考志愿推荐与目标评估</span>
          </div>
          <nav className="flex items-center gap-1">
            {navItems.map((it) => (
              <NavLink
                key={it.to}
                to={it.to}
                end={it.end}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition ${
                    isActive
                      ? "bg-white/20 text-white"
                      : "text-white/60 hover:text-white hover:bg-white/10"
                  }`
                }
              >
                <it.icon className="w-4 h-4" />
                <span className="hidden sm:inline">{it.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      {/* 内容区 */}
      <main className="max-w-5xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/target-evaluation" element={<TargetEvaluationPage />} />
          <Route path="/my-groups" element={<MyGroupsPage />} />
          <Route path="/rank" element={<RankPage />} />
          <Route path="/control-line" element={<ControlLinePage />} />
        </Routes>
      </main>

      {/* 悬浮志愿组（跨页面常驻，桌面端） */}
      <VolunteerDock />
      {/* Toast 通知（跨页面常驻） */}
      <Toaster />

      {/* 底部免责 */}
      <footer className="max-w-5xl mx-auto px-4 py-8 text-center text-xs text-white/40">
        数据基于历年录取信息模拟，仅供志愿填报参考，正式填报请以省考试院公布为准。
      </footer>
    </div>
  );
}
