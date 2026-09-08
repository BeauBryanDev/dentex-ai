import { useAppStore } from "../stores/appStore";
import { PanelHeader } from "./UploadPanel";
import type { ToothStatus, ToothView } from "../types";
import { statusColor } from "../utils/palette";

// Colour comes from the shared palette so a caries row matches its box on the radiograph
// and its tooth on the odontogram. Applied inline rather than as Tailwind classes because
// the palette is plain hex values, not part of the theme.
const dot = (status: ToothStatus) => ({ background: statusColor(status) });
const text = (status: ToothStatus) => ({ color: statusColor(status) });

interface TeethTableProps {
  number?: string;
  compact?: boolean;
  scrollMaxHeight?: string;
}

export default function TeethTable({ number = "02", scrollMaxHeight = "max-h-[420px]" }: TeethTableProps) {
  const { analysis } = useAppStore();
  // Only teeth the detector actually reported. The view model carries all 32 chart slots so
  // the dentition chart can draw gaps, but a table row for a tooth that was never detected
  // would read as a negative finding rather than as absent evidence.
  const teeth = (analysis?.teeth ?? []).filter((t) => t.status !== "Undetected");

  return (
    <section className="hud-panel hud-corners flex flex-col">
      <span className="hud-c-bl" />
      <span className="hud-c-br" />
      <PanelHeader
        number={number}
        title="TEETH DETECTED"
        subtitle="FDI MAPPING"
        right={
          <span className="hidden sm:flex items-center gap-1.5 text-[11px] tracking-[0.2em] text-[#8A8A8A] mono">
            TOTAL: <span className="text-[#D6D6D6]">{analysis ? teeth.length : "—"}</span>
          </span>
        }
      />

      {/* Header row */}
      <div className="hidden md:grid grid-cols-[60px_1fr_80px_80px_70px] gap-2 border-b border-[#141414] bg-[#070707] px-3 py-2 text-[11px] tracking-[0.22em] text-[#707070] mono">
        <span>FDI</span>
        <span>TOOTH</span>
        <span>STATUS</span>
        <span>CONDITION</span>
        <span className="text-right">CONF.</span>
      </div>

      {/* Mobile compact header */}
      <div className="md:hidden border-b border-[#141414] bg-[#070707] px-3 py-2 text-[11px] tracking-[0.22em] text-[#707070] mono">
        DETECTED TEETH — {analysis ? teeth.length : "—"}
      </div>

      <div className={`overflow-y-auto ${scrollMaxHeight} divide-y divide-[#141414]`}>
        {teeth.length === 0 ? (
          <EmptyTeeth />
        ) : (
          teeth.map((t) => (
            <TeethRow key={t.fdi} tooth={t} />
          ))
        )}
      </div>

      {/* Bottom legend */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[#141414] bg-[#080808] px-3 py-2">
        <div className="flex flex-wrap items-center gap-2 text-[11px] tracking-[0.2em] text-[#8A8A8A] mono">
          <LegendDot label="HEALTHY" status="Healthy" />
          <LegendDot label="CARIES" status="Caries" />
          <LegendDot label="INFECTION" status="Infection" />
          <LegendDot label="WISDOM" status="Wisdom" />
        </div>
      </div>
    </section>
  );
}

function TeethRow({ tooth }: { tooth: ToothView }) {
  return (
    <>
      {/* Desktop row */}
      <div className="hidden md:grid grid-cols-[60px_1fr_80px_80px_70px] items-center gap-2 px-3 py-1.5 hover:bg-[#101010]">
        <span className="text-[12px] tracking-[0.1em] text-[#D6D6D6] mono">{tooth.fdi}</span>
        <span className="text-[12.5px] tracking-[0.12em] text-[#A5A5A5] truncate">
          {tooth.name}
        </span>
        <span className="flex items-center gap-1.5 text-[12px] tracking-[0.2em] mono" style={text(tooth.status)}>
          <span className="h-1.5 w-1.5" style={dot(tooth.status)} />
          {tooth.status}
        </span>
        <span className="text-[12px] tracking-[0.15em] text-[#A5A5A5]">{tooth.condition}</span>
        <span className="text-right text-[12px] tracking-[0.1em] text-[#D6D6D6] mono">
          {tooth.confidence}%
        </span>
      </div>

      {/* Mobile compact row */}
      <div className="md:hidden flex items-center gap-2 px-3 py-2 hover:bg-[#101010]">
        <span className="h-1.5 w-1.5" style={dot(tooth.status)} />
        <span className="text-[13px] tracking-[0.1em] text-[#D6D6D6] mono w-7">{tooth.fdi}</span>
        <span className="flex-1 text-[12.5px] tracking-[0.18em] mono" style={text(tooth.status)}>
          {tooth.status}
        </span>
        <span className="text-[11.5px] tracking-[0.1em] text-[#707070] mono">{tooth.confidence}%</span>
      </div>
    </>
  );
}

function EmptyTeeth() {
  return (
    <div className="px-3 py-6 text-center">
      <p className="text-[12px] tracking-[0.22em] text-[#555] mono">AWAITING ANALYSIS</p>
      <p className="mt-1 text-[11px] tracking-[0.22em] text-[#3A3A3A] mono">
        UPLOAD AN IMAGE TO POPULATE
      </p>
    </div>
  );
}

function LegendDot({ label, status }: { label: string; status: ToothStatus }) {
  return (
    <span className="flex items-center gap-1">
      <span className="h-1.5 w-1.5" style={dot(status)} />
      <span>{label}</span>
    </span>
  );
}
