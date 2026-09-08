// Turns one AnalyzeResponse into the view model the panels render.
//
// This module exists so the UI can keep the shape it was designed around — a row per tooth
// with a status and a confidence — while the backend keeps sending what it actually knows:
// three independent lists of boxes. All the interpretation happens here, in one place, and
// every rule in it is a decision worth reading before changing.
//
// The one rule that is *not* here: attributing a lesion to a tooth. That is fusion, it is
// geometric, and `services/fusion.py` already did it against the real box coordinates. The
// frontend consumes `finding.tooth_fdi` and never recomputes it.

import type {
  AnalysisView,
  AnalyzeResponse,
  ConditionCounts,
  ConfidenceBand,
  FindingOut,
  ToothPosition,
  ToothSide,
  ToothStatus,
  ToothView,
} from "../types";

/** Chart layout, in VIEWER order, left to right — mirrors app/utils/teeth_geometry.py.
 *
 *  Quadrants 1 and 4 are the patient's right, and a panoramic is read as if facing the
 *  patient, so they sit on the viewer's LEFT. Iterate these arrays as given. Sorting by FDI
 *  number puts 11 at the far left and mirrors the entire chart — which looks plausible and
 *  is clinically backwards. */
export const UPPER_ROW = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
export const LOWER_ROW = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];
export const ALL_FDI = [...UPPER_ROW, ...LOWER_ROW];

/** "Damage" is the lesion model's name for a MISSING tooth, not damage to a present one.
 *  It is the one label that describes an absence, which is why it almost always arrives
 *  with `tooth_fdi: null` — there is no box for a tooth that is not there. */
export const MISSING_LABEL = "Damage";

/** Ranked worst-first. When several findings land on one tooth the row shows the worst. */
const STATUS_RANK: Record<string, number> = {
  Infection: 3,
  Cavities: 2,
  Wisdom: 1,
};

const LABEL_TO_STATUS: Record<string, ToothStatus> = {
  Cavities: "Caries",
  Infection: "Infection",
  Wisdom: "Wisdom",
};

const CONDITION_TEXT: Record<ToothStatus, string> = {
  Healthy: "Good",
  Caries: "Caries",
  Infection: "Periapical",
  Wisdom: "Third molar",
  Undetected: "Not detected",
};

export function quadrantOf(fdi: number): number {
  return Math.floor(fdi / 10);
}

export function positionOf(fdi: number): number {
  return fdi % 10;
}

export function archOf(fdi: number): ToothPosition {
  const q = quadrantOf(fdi);
  return q === 1 || q === 2 ? "Upper" : "Lower";
}

/** The PATIENT's side, which is what the FDI number encodes — NOT the side of the screen.
 *  Quadrants 1 and 4 are the patient's right and render on the viewer's left. */
export function patientSideOf(fdi: number): ToothSide {
  const q = quadrantOf(fdi);
  return q === 1 || q === 4 ? "Right" : "Left";
}

/** "upper_left_first_molar" -> "Upper Left First Molar". Falls back to an FDI-derived name
 *  for chart slots the detector never reported, which have no `anatomy` string to humanise. */
export function humaniseAnatomy(anatomy: string | null, fdi: number): string {
  if (anatomy) {
    return anatomy
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  }
  const ordinals = ["", "Central Incisor", "Lateral Incisor", "Canine", "First Premolar",
    "Second Premolar", "First Molar", "Second Molar", "Third Molar"];
  return `${archOf(fdi)} ${patientSideOf(fdi)} ${ordinals[positionOf(fdi)] ?? ""}`.trim();
}

/** Confidence bands for the distribution chart.
 *
 *  Deliberately labelled as DETECTION CONFIDENCE, not severity. The models output a
 *  detection score; nothing in this system grades how bad a lesion is. Presenting a
 *  confidence histogram under a "severity" heading would be inventing a clinical claim the
 *  backend never made, which is the exact failure this app is built to avoid. */
const BANDS: Array<{ label: string; min: number; max: number }> = [
  { label: "0.40-0.55", min: 0.4, max: 0.55 },
  { label: "0.55-0.70", min: 0.55, max: 0.7 },
  { label: "0.70-0.85", min: 0.7, max: 0.85 },
  { label: "0.85-1.00", min: 0.85, max: 1.01 },
];

function confidenceBands(findings: FindingOut[]): ConfidenceBand[] {
  const total = findings.length;
  return BANDS.map((b) => {
    const count = findings.filter((f) => f.confidence >= b.min && f.confidence < b.max).length;
    return {
      label: b.label,
      count,
      percent: total ? Math.round((count / total) * 100) : 0,
    };
  });
}

export function deriveAnalysis(res: AnalyzeResponse): AnalysisView {
  const byFdi = new Map(res.teeth.map((t) => [t.fdi, t]));
  const ambiguous = new Set(res.ambiguous_fdi);

  // Attributed findings, grouped onto their tooth. `tooth_fdi` comes from fusion's
  // containment test — trust it rather than re-deriving it from boxes here.
  const findingsByFdi = new Map<number, FindingOut[]>();
  const unattributed: FindingOut[] = [];
  for (const f of res.findings) {
    if (f.tooth_fdi == null) {
      unattributed.push(f);
      continue;
    }
    const list = findingsByFdi.get(f.tooth_fdi) ?? [];
    list.push(f);
    findingsByFdi.set(f.tooth_fdi, list);
  }
  for (const list of findingsByFdi.values()) {
    list.sort((a, b) => (STATUS_RANK[b.label] ?? 0) - (STATUS_RANK[a.label] ?? 0)
      || b.confidence - a.confidence);
  }

  // The chart is static: all 32 slots, detected or not. A tooth the model did not report is
  // "Undetected", NOT "Missing" — the detector failing to fire and a tooth being absent are
  // different claims, and only the lesion model's `Damage` class asserts the second one.
  const teeth: ToothView[] = ALL_FDI.map((fdi) => {
    const detected = byFdi.get(fdi);
    const found = findingsByFdi.get(fdi) ?? [];
    const worst = found[0];
    const status: ToothStatus = !detected
      ? "Undetected"
      : worst
        ? LABEL_TO_STATUS[worst.label] ?? "Healthy"
        : "Healthy";

    return {
      fdi,
      name: humaniseAnatomy(detected?.anatomy ?? null, fdi),
      position: archOf(fdi),
      side: patientSideOf(fdi),
      status,
      condition: CONDITION_TEXT[status],
      confidence: detected ? Math.round(detected.confidence * 100) : 0,
      findings: found,
      box: detected?.box ?? null,
      ambiguous: ambiguous.has(fdi),
    };
  });

  const counts: ConditionCounts = {
    detected: res.teeth.length,
    healthy: teeth.filter((t) => t.status === "Healthy").length,
    caries: teeth.filter((t) => t.status === "Caries").length,
    infection: teeth.filter((t) => t.status === "Infection").length,
    wisdom: teeth.filter((t) => t.status === "Wisdom").length,
    // Missing teeth are counted from findings, not from empty chart slots, for the reason
    // above: an undetected slot is not evidence of an absent tooth.
    missing: res.findings.filter((f) => f.label === MISSING_LABEL).length,
    restorations: res.restorations.length,
  };

  return {
    sessionId: res.session_id,
    imageWidth: res.image_width,
    imageHeight: res.image_height,
    teeth,
    counts,
    confidence: confidenceBands(res.findings),
    unattributed,
    restorations: res.restorations,
    ambiguousFdi: res.ambiguous_fdi,
    summary: res.summary,
    createdAt: new Date().toISOString(),
  };
}
