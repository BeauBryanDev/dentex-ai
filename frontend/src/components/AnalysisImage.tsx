import { useState } from "react";
import { useAppStore } from "../stores/appStore";
import { PanelHeader } from "./UploadPanel";
import { Layers, Eye, ScanLine, Circle } from "lucide-react";
import type { BoundingBox, ToothView } from "../types";
import { MISSING_LABEL } from "../utils/derive";
import {
  FINDING_COLORS,
  OTHER_COLOR,
  RESTORATION_COLORS,
  TOOTH_COLOR,
  findingColor,
  restorationColor,
} from "../utils/palette";

// The overlay is the product: two networks ran over one image and fusion turned their boxes
// into "finding on tooth NN". This panel has to show that on the actual pixels.
//
// The previous version drew FDI numbers as two evenly-spaced flex rows, so every tooth
// appeared at a fixed position regardless of where it really was, and the image used
// `object-cover`, which CROPS a panoramic — the molars at both ends were being cut off the
// screen entirely.
//
// Geometry: the backend returns boxes in ORIGINAL image pixels and tells us the image size,
// so the fix is to give the image wrapper the X-ray's own aspect ratio and place boxes as
// percentages. Percentages then map exactly, at any container width, with no measurement,
// no resize listener and nothing to drift.

/** Box -> CSS percentages against the original image dimensions. */
function place(box: BoundingBox, w: number, h: number) {
  return {
    left: `${(box.x1 / w) * 100}%`,
    top: `${(box.y1 / h) * 100}%`,
    width: `${((box.x2 - box.x1) / w) * 100}%`,
    height: `${((box.y2 - box.y1) / h) * 100}%`,
  };
}

type LayerKey = "teeth" | "findings" | "restorations";

export default function AnalysisImage() {
  const { uploadedImage, analysis, isAnalyzing } = useAppStore();

  // The three detection layers are independently toggleable. On a full panoramic, 32 tooth
  // boxes plus their labels cover the lesions the dentist actually wants to look at, so
  // being able to drop back to findings-only is a working requirement, not a flourish.
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({
    teeth: true,
    findings: true,
    restorations: true,
  });
  const toggle = (k: LayerKey) => setLayers((s) => ({ ...s, [k]: !s[k] }));

  const detected = (analysis?.teeth ?? []).filter((t) => t.status !== "Undetected");
  const flagged = detected.filter((t) => t.findings.length > 0);
  const missing = (analysis?.unattributed ?? []).filter((f) => f.label === MISSING_LABEL);

  return (
    <section className="hud-panel hud-corners flex flex-col">
      <span className="hud-c-bl" />
      <span className="hud-c-br" />
      <PanelHeader
        number="04"
        title="ANALYSIS OUTPUT"
        subtitle="VISION MODULE"
        right={
          <div className="flex items-center gap-1.5">
            <LayerButton
              active={layers.teeth}
              onClick={() => toggle("teeth")}
              label="Toggle tooth boxes"
            >
              <Circle className="h-3 w-3" />
            </LayerButton>
            <LayerButton
              active={layers.findings}
              onClick={() => toggle("findings")}
              label="Toggle findings"
            >
              <Eye className="h-3 w-3" />
            </LayerButton>
            <LayerButton
              active={layers.restorations}
              onClick={() => toggle("restorations")}
              label="Toggle restorations"
            >
              <Layers className="h-3 w-3" />
            </LayerButton>
          </div>
        }
      />

      <div className="px-3 py-3 md:px-4 md:py-4">
        <div className="relative w-full overflow-hidden border border-[#1f1f1f] bg-black">
          {/* Corner brackets */}
          <span className="pointer-events-none absolute left-2 top-2 z-20 h-3 w-3 border-l border-t border-[#909090]" />
          <span className="pointer-events-none absolute right-2 top-2 z-20 h-3 w-3 border-r border-t border-[#909090]" />
          <span className="pointer-events-none absolute bottom-2 left-2 z-20 h-3 w-3 border-b border-l border-[#909090]" />
          <span className="pointer-events-none absolute bottom-2 right-2 z-20 h-3 w-3 border-b border-r border-[#909090]" />

          <div className="pointer-events-none absolute left-2 right-2 top-2 z-20 flex items-center justify-between text-[10.5px] tracking-[0.22em] text-[#909090] mono">
            <span>PANORAMIC X-RAY</span>
            <span>
              {analysis ? `2D / ${analysis.imageWidth}×${analysis.imageHeight}` : "AWAITING INPUT"}
            </span>
          </div>

          <div className="pointer-events-none absolute bottom-2 left-2 right-2 z-20 flex items-center justify-between text-[10.5px] tracking-[0.22em] text-[#707070] mono">
            <span>{analysis ? `FDI DETECTED: ${detected.length}` : "FDI DETECTED"}</span>
            <span>{analysis ? `FINDINGS: ${flagged.length + missing.length}` : "—"}</span>
          </div>

          {uploadedImage ? (
            <div
              className="relative w-full"
              // The X-ray's own aspect ratio, so the box percentages land on the right
              // pixels. Without an analysis yet we do not know the true dimensions, so fall
              // back to a typical panoramic ratio purely for layout.
              style={{
                aspectRatio: analysis
                  ? `${analysis.imageWidth} / ${analysis.imageHeight}`
                  : "2 / 1",
              }}
            >
              <img
                src={uploadedImage.dataUrl}
                alt="Panoramic X-ray"
                // object-contain, never object-cover: cropping a panoramic hides the third
                // molars, which are exactly where wisdom findings appear.
                className="absolute inset-0 h-full w-full object-contain"
                style={{ filter: "grayscale(1) contrast(1.15) brightness(0.9)" }}
              />

              {analysis && (
                <div className="pointer-events-none absolute inset-0 z-10">
                  {layers.teeth &&
                    detected.map((t) => (
                      <ToothBox key={`t-${t.fdi}`} tooth={t} w={analysis.imageWidth} h={analysis.imageHeight} />
                    ))}

                  {layers.restorations &&
                    analysis.restorations.map((r, i) => (
                      <div
                        key={`r-${i}`}
                        className="absolute border border-dashed"
                        style={{
                          ...place(r.box, analysis.imageWidth, analysis.imageHeight),
                          borderColor: restorationColor(r.kind),
                        }}
                      >
                        <span
                          className="mono absolute -top-3.5 left-0 whitespace-nowrap bg-black/70 px-[3px] text-[10px] leading-none"
                          style={{ color: restorationColor(r.kind) }}
                        >
                          {r.kind.toUpperCase()}
                        </span>
                      </div>
                    ))}

                  {layers.findings &&
                    analysis.teeth
                      .flatMap((t) => t.findings)
                      .concat(analysis.unattributed)
                      .map((f, i) => (
                        <div
                          key={`f-${i}`}
                          className="absolute border-2"
                          style={{
                            ...place(f.box, analysis.imageWidth, analysis.imageHeight),
                            borderColor: findingColor(f.label),
                          }}
                        >
                          <span
                            className="mono absolute -bottom-3.5 left-0 whitespace-nowrap bg-black/70 px-[3px] text-[10px] leading-none"
                            style={{ color: findingColor(f.label) }}
                          >
                            {/* Naming the tooth on the box is the whole point of fusion —
                                a lesion the dentist cannot locate is not a finding. */}
                            {f.label.toUpperCase()}
                            {f.tooth_fdi != null ? ` · ${f.tooth_fdi}` : ""}
                          </span>
                        </div>
                      ))}
                </div>
              )}

              {isAnalyzing && <div className="scan-line" />}
            </div>
          ) : (
            <div className="relative aspect-[2/1] w-full">
              <PanoramicPlaceholder />
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="mt-3 flex flex-wrap items-center justify-center gap-3 border border-[#1a1a1a] bg-[#0a0a0a] px-3 py-2 text-[11px] tracking-[0.22em] text-[#A5A5A5] mono md:gap-5">
          <LegendItem label="TOOTH" color={TOOTH_COLOR} />
          <LegendItem label="CAVITIES" color={FINDING_COLORS.Cavities} />
          <LegendItem label="MISSING" color={FINDING_COLORS.Damage} />
          <LegendItem label="INFECTION" color={FINDING_COLORS.Infection} />
          <LegendItem label="WISDOM" color={FINDING_COLORS.Wisdom} />
          <LegendItem label="CROWN" color={RESTORATION_COLORS.Crown} />
          <LegendItem label="BRIDGE" color={RESTORATION_COLORS.Bridge} />
          <LegendItem label="IMPLANT" color={RESTORATION_COLORS.Implant} />
          <LegendItem label="OTHER" color={OTHER_COLOR} />
        </div>

        {/* Findings list */}
        {analysis && (flagged.length > 0 || missing.length > 0) && (
          <div className="mt-3 border border-[#1a1a1a] bg-[#0a0a0a] p-2.5">
            <div className="mb-2 flex items-center gap-2 text-[11px] tracking-[0.22em] text-[#909090] mono">
              <ScanLine className="h-3 w-3" />
              <span>AI FINDINGS / FLAGGED REGIONS</span>
            </div>
            <div className="space-y-1.5">
              {flagged.map((t) =>
                t.findings.map((f, i) => (
                  <div
                    key={`${t.fdi}-${i}`}
                    className="flex items-center justify-between text-[12.5px] tracking-[0.1em]"
                  >
                    <div className="flex items-center gap-2">
                      <span className="mono text-[#D6D6D6]">FDI {t.fdi}</span>
                      <span className="text-[#555]">·</span>
                      <span className="text-[#A5A5A5]">{t.name}</span>
                      {t.ambiguous && (
                        <span
                          className="mono text-[10.5px] text-[#E6B800]"
                          title="More than one box claimed this FDI number — the label is uncertain."
                        >
                          [AMBIGUOUS FDI]
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span style={{ color: findingColor(f.label) }}>
                        {f.label.toUpperCase()}
                      </span>
                      <span className="text-[#555]">·</span>
                      {/* Containment, not IoU: the fraction of the lesion lying inside the
                          tooth box. It is the evidence for the attribution, so it is shown
                          next to it rather than hidden. */}
                      <span className="mono text-[#707070]">
                        IN {Math.round(f.containment * 100)}%
                      </span>
                      <span className="text-[#555]">·</span>
                      <span className="mono text-[#A5A5A5]">
                        CONF {Math.round(f.confidence * 100)}%
                      </span>
                    </div>
                  </div>
                ))
              )}

              {missing.map((f, i) => (
                <div
                  key={`m-${i}`}
                  className="flex items-center justify-between text-[12.5px] tracking-[0.1em]"
                >
                  <div className="flex items-center gap-2">
                    <span className="mono text-[#707070]">UNLOCALISED</span>
                    <span className="text-[#555]">·</span>
                    {/* A missing tooth has no tooth box to sit inside, so fusion cannot give
                        it an FDI number. Reported plainly rather than guessed. */}
                    <span className="text-[#A5A5A5]">Missing tooth — no FDI attribution</span>
                  </div>
                  <span className="mono text-[#A5A5A5]">
                    CONF {Math.round(f.confidence * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function ToothBox({ tooth, w, h }: { tooth: ToothView; w: number; h: number }) {
  if (!tooth.box) return null;
  // Green marks "the FDI model found a tooth here". A finding on it is drawn as its own box
  // in the findings layer, so recolouring the tooth box too would double-encode the same
  // fact and hide which of the two the colour refers to.
  const color = TOOTH_COLOR;
  return (
    <div
      className="absolute border"
      style={{ ...place(tooth.box, w, h), borderColor: color, opacity: 0.55 }}
    >
      <span
        className="mono absolute -top-3 left-0 whitespace-nowrap bg-black/60 px-[2px] text-[10px] font-semibold leading-none"
        style={{ color }}
      >
        {tooth.fdi}
      </span>
    </div>
  );
}

function LayerButton({
  active,
  onClick,
  label,
  children,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      title={label}
      className={`flex h-6 w-6 items-center justify-center border bg-[#0E0E10] ${
        active
          ? "border-[#909090] text-[#E5E5E5]"
          : "border-[#2A2A2A] text-[#4A4A4A] hover:border-[#606060]"
      }`}
    >
      {children}
    </button>
  );
}

function LegendItem({ label, color }: { label: string; color: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="h-2 w-2" style={{ background: color }} />
      <span>{label}</span>
    </span>
  );
}

function PanoramicPlaceholder() {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-2">
      <svg
        viewBox="0 0 400 200"
        className="h-3/5 w-3/4 opacity-30"
        fill="none"
        stroke="#555"
        strokeWidth="0.6"
      >
        <path d="M50 100 C50 60 80 40 120 40 C160 40 180 50 200 60 C220 50 240 40 280 40 C320 40 350 60 350 100" />
        <path d="M70 110 C70 130 75 150 85 165 C90 170 95 170 100 165 L110 130" />
        <path d="M330 110 C330 130 325 150 315 165 C310 170 305 170 300 165 L290 130" />
        <ellipse cx="200" cy="80" rx="8" ry="12" />
        <line x1="50" y1="100" x2="350" y2="100" stroke="#2A2A2A" strokeDasharray="2,2" />
      </svg>
      <p className="text-[12px] tracking-[0.22em] text-[#555] mono">AWAITING INPUT IMAGE</p>
      <p className="text-[11px] tracking-[0.22em] text-[#3A3A3A] mono">UPLOAD TO RENDER PANORAMIC</p>
    </div>
  );
}
