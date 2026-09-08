import { useAppStore } from "../stores/appStore";
import { PanelHeader } from "./UploadPanel";
import { useAnalysis } from "../hooks/useAnalysis";
import { Download, FileText, Activity, AlertTriangle, CheckCircle2 } from "lucide-react";
import PieChartPanel from "./PieChart";
import { FINDING_COLORS, OTHER_COLOR, TOOTH_COLOR } from "../utils/palette";
import OdontogramPanel from "./OdontogramPanel";
import FindingsList from "./FindingsList";

export default function Dashboard() {
  const { analysis } = useAppStore();
  const { exportReport } = useAnalysis();
  const c = analysis?.counts;

  // An em dash before an upload, not a plausible-looking number. The tiles used to default
  // to 32/22/5/3, so an untouched app displayed a completed reading.
  const show = (v: number | undefined) => (c ? String(v ?? 0) : "—");

  const stats = [
    {
      label: "TEETH DETECTED",
      value: show(c?.detected),
      icon: Activity,
      color: TOOTH_COLOR,
    },
    {
      label: "HEALTHY",
      value: show(c?.healthy),
      icon: CheckCircle2,
      color: TOOTH_COLOR,
    },
    {
      label: "LESIONS",
      value: show(c ? c.caries + c.infection : undefined),
      icon: AlertTriangle,
      color: FINDING_COLORS.Cavities,
    },
    {
      label: "RESTORATIONS",
      value: show(c?.restorations),
      icon: FileText,
      color: OTHER_COLOR,
    },
  ];

  return (
    <section className="hud-panel hud-corners flex flex-col">
      <span className="hud-c-bl" />
      <span className="hud-c-br" />
      <PanelHeader
        number="05"
        title="DIAGNOSTIC DASHBOARD"
        subtitle="ANALYTICS MODULE"
        right={
          <button
            onClick={exportReport}
            className="flex items-center gap-1.5 border border-[#3A3A3A] bg-[#0E0E10] px-2 py-1 text-[11px] tracking-[0.22em] text-[#D6D6D6] hover:border-[#909090] hover:bg-[#161616] mono"
          >
            <Download className="h-3 w-3" />
            EXPORT REPORT
          </button>
        }
      />

      <div className="space-y-3 p-3 md:space-y-4 md:p-4">
        {/* Quick stats */}
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4 md:gap-3">
          {stats.map((s) => {
            const Icon = s.icon;
            return (
              <div
                key={s.label}
                className="relative border border-[#1a1a1a] bg-[#0a0a0a] p-2 md:p-3"
              >
                <span className="absolute left-1 top-1 h-1.5 w-1.5 border-l border-t border-[#707070]" />
                <span className="absolute right-1 top-1 h-1.5 w-1.5 border-r border-t border-[#707070]" />
                <div className="flex items-center justify-between">
                  <span className="text-[11px] tracking-[0.22em] text-[#707070] mono">
                    {s.label}
                  </span>
                  <Icon className="h-3 w-3" style={{ color: s.color }} />
                </div>
                <div className="mt-1.5 text-2xl font-bold tracking-[0.05em] md:text-3xl" style={{ color: s.color }}>
                  {s.value}
                </div>
              </div>
            );
          })}
        </div>

        {/* SPEC layout: odontogram on the left, findings + distribution on the right. */}
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 lg:gap-4">
          <OdontogramPanel />
          <div className="flex flex-col gap-3">
            <PieChartPanel />
            <FindingsList />
          </div>
        </div>
      </div>
    </section>
  );
}
