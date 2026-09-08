import { useAppStore } from "../stores/appStore";
import { MISSING_LABEL } from "../utils/derive";
import { findingColor, restorationColor } from "../utils/palette";

// SPEC's "AI FINDINGS" column: every finding the models produced, in one place.
//
// It is split in two on purpose. Attributed findings name a tooth because fusion put them
// there geometrically. Unlocalised ones — missing teeth, crowns, implants, bridges, and any
// lesion no tooth box contained — are listed WITHOUT an FDI number rather than being given a
// plausible one. That split is the honest shape of what this system knows, and collapsing it
// would make the odontogram look more complete than the evidence supports.

export default function FindingsList() {
  const { analysis } = useAppStore();

  const attributed = (analysis?.teeth ?? []).flatMap((t) =>
    t.findings.map((f) => ({ tooth: t, finding: f }))
  );
  const unlocalised = analysis?.unattributed ?? [];
  const restorations = analysis?.restorations ?? [];

  return (
    <div className="flex-1 border border-[#1a1a1a] bg-[#0a0a0a] p-3">
      <div className="mb-2 flex items-center justify-between text-[11px] tracking-[0.22em] text-[#707070] mono">
        <span>AI FINDINGS</span>
        <span>{analysis ? attributed.length + unlocalised.length + restorations.length : "—"}</span>
      </div>

      {!analysis ? (
        <p className="py-6 text-center text-[11px] tracking-[0.22em] text-[#3A3A3A] mono">
          AWAITING ANALYSIS
        </p>
      ) : attributed.length + unlocalised.length + restorations.length === 0 ? (
        <p className="py-6 text-center text-[11px] tracking-[0.22em] text-[#555] mono">
          NO FINDINGS DETECTED
        </p>
      ) : (
        <div className="space-y-1">
          {attributed.map(({ tooth, finding }, i) => (
            <div
              key={`a-${i}`}
              className="flex items-center justify-between border-b border-[#141414] py-1 text-[12.5px] last:border-0"
            >
              <span className="flex items-center gap-2">
                <span className="mono text-[#D6D6D6]">{tooth.fdi}</span>
                <span style={{ color: findingColor(finding.label) }}>{finding.label}</span>
                {tooth.ambiguous && <span className="mono text-[10.5px] text-[#E6B800]">?</span>}
              </span>
              <span className="mono text-[#8A8A8A]">
                {Math.round(finding.confidence * 100)}%
              </span>
            </div>
          ))}

          {(unlocalised.length > 0 || restorations.length > 0) && (
            <div className="pt-2">
              <div className="mb-1 text-[10.5px] tracking-[0.22em] text-[#555] mono">
                NOT PLACED ON CHART — NO FDI ATTRIBUTION
              </div>

              {unlocalised.map((f, i) => (
                <div
                  key={`u-${i}`}
                  className="flex items-center justify-between border-b border-[#141414] py-1 text-[12.5px] last:border-0"
                >
                  <span className="flex items-center gap-2">
                    <span className="mono text-[#555]">—</span>
                    <span className="text-[#8A8A8A]">
                      {f.label === MISSING_LABEL ? "Missing tooth" : f.label}
                    </span>
                  </span>
                  <span className="mono text-[#8A8A8A]">
                    {Math.round(f.confidence * 100)}%
                  </span>
                </div>
              ))}

              {restorations.map((r, i) => (
                <div
                  key={`r-${i}`}
                  className="flex items-center justify-between border-b border-[#141414] py-1 text-[12.5px] last:border-0"
                >
                  <span className="flex items-center gap-2">
                    <span className="mono text-[#555]">—</span>
                    <span style={{ color: restorationColor(r.kind) }}>{r.kind}</span>
                  </span>
                  <span className="mono text-[#8A8A8A]">
                    {Math.round(r.confidence * 100)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
