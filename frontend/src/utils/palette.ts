// One palette for every view of a detection: the radiograph overlay, the odontogram, the
// condition pie and the tables.
//
// It lives in its own module because the same fact is drawn in four places, and a caries
// that is amber on the X-ray but red in the table reads as two different findings. Colour is
// the only thing tying those views together, so it has exactly one definition.
//
// The hues are deliberately saturated rather than drawn from the greyscale HUD: these are
// painted over a grayscale panoramic, where a grey box is nearly invisible. Each class gets
// its own hue rather than a shade of one, so they stay separable without relying on
// lightness.

/** A tooth the FDI model located. Green means "found", nothing about its health. */
export const TOOTH_COLOR = "#22C55E";

/** A chart slot the model never reported. Absent evidence — deliberately inert, not a colour
 *  that competes for attention, because "not detected" is not a finding. */
export const UNDETECTED_COLOR = "#2A2A2A";

/** Fallback for any class not named below, e.g. a new class after a retrain. Purple is
 *  reserved for exactly this so an unknown class is visible and obviously unclassified,
 *  rather than silently inheriting some other class's colour. */
export const OTHER_COLOR = "#A855F7";

/** Lesion-model classes. `Damage` is the model's name for a MISSING tooth. */
export const FINDING_COLORS: Record<string, string> = {
  Damage: "#EF4444", // red
  Cavities: "#F59E0B", // amber
  Infection: "#EC4899", // magenta
  Wisdom: "#22D3EE", // cyan
};

/** FDI-model restoration classes. */
export const RESTORATION_COLORS: Record<string, string> = {
  Bridge: "#3B82F6", // blue
  Implant: "#9CA3AF", // grey
  Crown: "#FB923C", // orange
};

export const findingColor = (label: string) => FINDING_COLORS[label] ?? OTHER_COLOR;
export const restorationColor = (kind: string) => RESTORATION_COLORS[kind] ?? OTHER_COLOR;

/** Derived tooth statuses (see utils/derive.ts) mapped onto the same hues as the raw model
 *  classes they came from — "Caries" is the view name for a `Cavities` detection, so it must
 *  be the same amber. */
export const statusColor = (status: string): string => {
  switch (status) {
    case "Caries":
      return FINDING_COLORS.Cavities;
    case "Infection":
      return FINDING_COLORS.Infection;
    case "Wisdom":
      return FINDING_COLORS.Wisdom;
    case "Healthy":
      return TOOTH_COLOR;
    default:
      return UNDETECTED_COLOR;
  }
};

/** Same colour at low opacity, for fills behind an outline. */
export const tint = (hex: string, alpha: number) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
};
