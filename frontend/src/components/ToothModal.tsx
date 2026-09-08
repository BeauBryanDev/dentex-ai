import { useEffect } from "react";
import { X } from "lucide-react";
import type { ToothView } from "../types";
import { findingColor } from "../utils/palette";

// Opened by clicking a tooth on the odontogram. Its job is to show the provenance of a
// finding, not to restate it: which model produced it, how confident it was, and how much
// of the lesion actually lay inside this tooth. That last number is the fusion evidence —
// without it "caries on 16" is an assertion the dentist has no way to weigh.

export default function ToothModal({
  tooth,
  onClose,
}: {
  tooth: ToothView;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const worst = tooth.findings[0];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="relative w-full max-w-sm border border-[#2A2A2A] bg-[#0B0B0D] p-4"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`Tooth ${tooth.fdi} detail`}
      >
        <span className="absolute -left-px -top-px h-3 w-3 border-l border-t border-[#909090]" />
        <span className="absolute -right-px -top-px h-3 w-3 border-r border-t border-[#909090]" />
        <span className="absolute -bottom-px -left-px h-3 w-3 border-b border-l border-[#909090]" />
        <span className="absolute -bottom-px -right-px h-3 w-3 border-b border-r border-[#909090]" />

        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center border border-[#2A2A2A] bg-[#0E0E10] text-[#A5A5A5] hover:border-[#909090] hover:text-[#E5E5E5]"
        >
          <X className="h-3 w-3" />
        </button>

        <div className="text-[11px] tracking-[0.22em] text-[#707070] mono">TOOTH</div>
        <div className="mt-0.5 text-2xl font-bold tracking-[0.05em] text-[#E5E5E5] mono">
          {tooth.fdi}
        </div>
        <div className="mt-0.5 text-[13px] tracking-[0.12em] text-[#A5A5A5]">{tooth.name}</div>

        <div className="mt-3 space-y-2 border-t border-[#1a1a1a] pt-3">
          {tooth.status === "Undetected" ? (
            // Said plainly. An undetected tooth is missing EVIDENCE, not a healthy tooth and
            // not an absent one, and the modal is where that distinction has room to be made.
            <Row
              label="AI FINDING"
              value="Not detected — the FDI model reported no box at this position. This is absent evidence, not a finding of a healthy or missing tooth."
            />
          ) : worst ? (
            <>
              <Row label="AI FINDING" value={worst.label} color={findingColor(worst.label)} />
              <Row label="CONFIDENCE" value={`${(worst.confidence * 100).toFixed(1)}%`} />
              <Row label="SOURCE" value="Lesion Detection Model (YOLOv8)" />
              <Row
                label="CONTAINMENT"
                value={`${(worst.containment * 100).toFixed(1)}% of the lesion lies inside this tooth`}
              />
            </>
          ) : (
            <>
              <Row label="AI FINDING" value="None" />
              <Row label="CONFIDENCE" value={`${tooth.confidence}% (tooth detection)`} />
              <Row label="SOURCE" value="FDI Tooth Model (YOLOv8)" />
            </>
          )}

          <Row label="FDI" value={String(tooth.fdi)} />
          <Row label="ARCH / SIDE" value={`${tooth.position} · patient's ${tooth.side}`} />

          {tooth.ambiguous && (
            // Surfaced rather than resolved: more than one box claimed this number, and no
            // overlap test can decide between two non-overlapping boxes sharing an FDI.
            <p className="mt-2 border border-[#E6B800]/40 bg-[#1a1405] p-2 text-[12px] leading-relaxed text-[#E6B800]">
              FDI numbering is ambiguous here — more than one detected box claimed number{" "}
              {tooth.fdi}. Treat this attribution as uncertain.
            </p>
          )}

          {tooth.findings.length > 1 && (
            <p className="text-[12px] text-[#707070] mono">
              +{tooth.findings.length - 1} further finding
              {tooth.findings.length > 2 ? "s" : ""} on this tooth
            </p>
          )}
        </div>

        <p className="mt-3 border-t border-[#1a1a1a] pt-2 text-[11px] leading-relaxed text-[#555]">
          AI-generated finding. Requires clinical confirmation; not a diagnosis.
        </p>
      </div>
    </div>
  );
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="grid grid-cols-[92px_1fr] items-start gap-2">
      <span className="text-[11px] tracking-[0.2em] text-[#707070] mono">{label}</span>
      <span className="text-[13px] leading-relaxed" style={{ color: color ?? "#D6D6D6" }}>
        {value}
      </span>
    </div>
  );
}
