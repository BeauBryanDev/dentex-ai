import { useAppStore } from "../stores/appStore";
import { PanelHeader } from "./UploadPanel";
import { FINDING_COLORS, TOOTH_COLOR } from "../utils/palette";
import { PieChart as RPieChart, Pie, Cell, ResponsiveContainer } from "recharts";

export default function PieChartPanel() {
  const { analysis } = useAppStore();
  const c = analysis?.counts;

  // No placeholder numbers before an upload. The chart previously fell back to an invented
  // 22/5/3/1 split, which rendered as a finished reading of an X-ray that did not exist.
  const data = c
    ? [
        { name: "Healthy", value: c.healthy, color: TOOTH_COLOR },
        { name: "Caries", value: c.caries, color: FINDING_COLORS.Cavities },
        { name: "Infection", value: c.infection, color: FINDING_COLORS.Infection },
        { name: "Wisdom", value: c.wisdom, color: FINDING_COLORS.Wisdom },
        { name: "Missing", value: c.missing, color: FINDING_COLORS.Damage },
      ].filter((d) => d.value > 0)
    : [];

  // Detected teeth, not 32: the denominator is what the model actually found, and dividing
  // by a full dentition would quietly understate every percentage.
  const total = data.reduce((a, b) => a + b.value, 0);

  return (
    <section className="hud-panel hud-corners flex flex-col">
      <span className="hud-c-bl" />
      <span className="hud-c-br" />
      <PanelHeader number="" title="CONDITION DISTRIBUTION" subtitle="TOOTH STATUS" />

      {data.length === 0 ? (
        <div className="flex h-40 items-center justify-center px-4 text-center text-[11px] tracking-[0.22em] text-[#3A3A3A] mono">
          AWAITING ANALYSIS
        </div>
      ) : (
      <div className="flex flex-col items-center gap-2 p-3 md:flex-row md:gap-3 md:p-4">
        {/* Donut chart */}
        <div className="relative h-36 w-full md:h-40 md:w-44">
          <ResponsiveContainer>
            <RPieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius="62%"
                outerRadius="92%"
                paddingAngle={2}
                dataKey="value"
                stroke="#080808"
                strokeWidth={2}
                startAngle={90}
                endAngle={-270}
                isAnimationActive
                animationDuration={800}
              >
                {data.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
            </RPieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-[10.5px] tracking-[0.22em] text-[#707070] mono">TOTAL</span>
            <span className="mt-0.5 text-2xl font-bold text-[#E5E5E5]">{total}</span>
            <span className="text-[10.5px] tracking-[0.22em] text-[#707070] mono">TEETH</span>
          </div>
        </div>

        {/* Legend with percentages */}
        <div className="w-full space-y-1.5 md:flex-1">
          {data.map((d) => {
            const pct = total > 0 ? ((d.value / total) * 100).toFixed(1) : "0";
            return (
              <div
                key={d.name}
                className="flex items-center gap-2 border border-[#1a1a1a] bg-[#080808] px-2 py-1.5"
              >
                <span className="h-2.5 w-2.5 shrink-0" style={{ background: d.color }} />
                <span className="flex-1 text-[12px] tracking-[0.2em] text-[#D6D6D6] mono">
                  {d.name}
                </span>
                <span className="text-[12px] tracking-[0.1em] text-[#A5A5A5] mono">
                  {pct}% ({d.value})
                </span>
              </div>
            );
          })}
        </div>
      </div>
      )}
    </section>
  );
}
