import { useMemo, useState } from "react";
import { Odontogram, type ToothDetail } from "react-odontogram";
import "react-odontogram/style.css";
import { useAppStore } from "../stores/appStore";
import ToothModal from "./ToothModal";
import type { ToothView } from "../types";
import { FINDING_COLORS, TOOTH_COLOR, UNDETECTED_COLOR, tint } from "../utils/palette";

// The odontogram is the second view of the same fusion result the radiograph overlay shows:
// the panoramic says *where* a lesion is, the chart says *which tooth* it is on. Both are
// driven by `finding.tooth_fdi`, so they cannot disagree.
//
// Only Cavities and Infection are plotted here, and that is a measured limitation rather
// than an oversight. Crowns, bridges, implants and missing teeth have no FDI attribution:
// a crowned tooth is detected AS `Crown` and not as `T16`, so no tooth box exists beneath
// it to attribute to, and a missing tooth has no box by definition. Placing those on a
// chart would mean inferring which slot they belong to, which is guesswork. They are listed
// as unlocalised findings instead — see fusion.py for the numbers.
//
// Tooth ids in this library are `teeth-<FDI>` and its default notation is already FDI, so
// no numbering translation happens anywhere in this file.

// Same hues as the radiograph overlay — see utils/palette.ts for why that is not optional.
const CARIES = FINDING_COLORS.Cavities;
const INFECTION = FINDING_COLORS.Infection;
const DETECTED = TOOTH_COLOR;

const toId = (fdi: number) => `teeth-${fdi}`;

export default function OdontogramPanel() {
  const { analysis } = useAppStore();
  const [selected, setSelected] = useState<ToothView | null>(null);

  const teeth = analysis?.teeth ?? [];

  const teethConditions = useMemo(() => {
    const pick = (s: string) =>
      teeth.filter((t) => t.status === s).map((t) => toId(t.fdi));

    const caries = pick("Caries");
    const infection = pick("Infection");
    // Everything the FDI model actually found and had nothing on. Rendered faintly so an
    // *undetected* slot stays visually distinct from a detected-and-clear one — the chart
    // must not imply the model examined a tooth it never reported.
    const healthy = teeth
      .filter((t) => t.status === "Healthy" || t.status === "Wisdom")
      .map((t) => toId(t.fdi));

    const groups = [];
    if (healthy.length)
      groups.push({ label: "Detected", teeth: healthy, ...swatch(DETECTED, 0.18) });
    if (infection.length)
      groups.push({ label: "Infection", teeth: infection, ...swatch(INFECTION, 0.5) });
    if (caries.length) groups.push({ label: "Caries", teeth: caries, ...swatch(CARIES, 0.5) });
    return groups;
  }, [teeth]);

  const onChange = (sel: ToothDetail[]) => {
    // singleSelect, so at most one. Deselecting sends an empty array — close the modal.
    const first = sel[0];
    if (!first) return setSelected(null);
    const fdi = Number(first.notations.fdi);
    setSelected(teeth.find((t) => t.fdi === fdi) ?? null);
  };

  const counts = analysis?.counts;

  return (
    <div className="relative border border-[#1a1a1a] bg-[#0a0a0a] p-3">
      <div className="mb-2 flex items-center justify-between text-[11px] tracking-[0.22em] text-[#707070] mono">
        <span>ODONTOGRAM — FDI</span>
        <span>{analysis ? "CLICK A TOOTH" : "AWAITING ANALYSIS"}</span>
      </div>

      <div className="flex justify-center [&_svg]:max-w-full">
        <Odontogram
          notation="FDI"
          theme="dark"
          // The library's palette slots are named after its default blues; these are the
          // HUD greys mapped onto them so an unflagged tooth recedes into the panel.
          colors={{ darkBlue: "#8A8A8A", baseBlue: "#141414", lightBlue: "#2A2A2A" }}
          teethConditions={teethConditions}
          singleSelect
          // Without an analysis there is nothing to inspect, so the chart is inert rather
          // than clickable-but-empty.
          readOnly={!analysis}
          showTooltip
          tooltip={{
            placement: "top",
            content: (payload) => <Tip fdi={Number(payload?.notations?.fdi)} teeth={teeth} />,
          }}
          onChange={onChange}
          styles={{ maxWidth: "320px" }}
        />
      </div>

      {/* Legend — only the conditions this chart can actually express. */}
      <div className="mt-2 flex flex-wrap items-center justify-center gap-3 text-[11px] tracking-[0.2em] text-[#8A8A8A] mono">
        <Dot color={CARIES} label={`CARIES${counts ? ` ${counts.caries}` : ""}`} />
        <Dot color={INFECTION} label={`INFECTION${counts ? ` ${counts.infection}` : ""}`} />
        <Dot color={DETECTED} label="DETECTED" />
        <Dot color={UNDETECTED_COLOR} label="NOT DETECTED" />
      </div>

      {selected && <ToothModal tooth={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

/** The library takes `fillColor`/`outlineColor`: one hue, solid outline over a tinted fill. */
function swatch(hex: string, alpha: number) {
  return { fillColor: tint(hex, alpha), outlineColor: hex };
}

function Tip({ fdi, teeth }: { fdi: number; teeth: ToothView[] }) {
  const t = teeth.find((x) => x.fdi === fdi);
  return (
    <div className="border border-[#2A2A2A] bg-[#0B0B0D] px-2 py-1 text-[12px] text-[#D6D6D6] mono">
      <div>FDI {fdi}</div>
      <div className="text-[#8A8A8A]">{t ? t.status : "Not detected"}</div>
    </div>
  );
}

function Dot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="h-2 w-2" style={{ background: color }} />
      <span>{label}</span>
    </span>
  );
}
