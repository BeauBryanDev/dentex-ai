// Type definitions for DentalVision.
//

/** Pixel coordinates in the ORIGINAL uploaded image, not the 640x640 model space. */
export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface ToothOut {
  /** FDI number, e.g. 26. Quadrants 1/4 are the PATIENT's right, which renders on the
   *  viewer's LEFT half of the image — the standard radiographic mirror. Never derive
   *  side from box x-coordinate assuming left-of-image means "left". */
  fdi: number;
  /** e.g. "upper_left_first_molar" */
  anatomy: string;
  confidence: number;
  box: BoundingBox;
}

export interface RestorationOut {
  /** Crown, Bridge or Implant. Note there is no `fdi` — the backend does not attribute
   *  restorations to teeth, so neither may the frontend. Render them as their own layer. */
  kind: string;
  confidence: number;
  box: BoundingBox;
}

export type FindingLabel = "Cavities" | "Damage" | "Infection" | "Wisdom";

export interface FindingOut {
  /** "Damage" denotes a MISSING tooth, not damage to a present one. */
  label: FindingLabel | string;
  confidence: number;
  box: BoundingBox;
  /** null when no tooth sufficiently contains the lesion — expected for "Damage", since a
   *  missing tooth has no box to sit inside. Such findings are still real; show them in the
   *  unattributed list rather than dropping them. */
  tooth_fdi: number | null;
  tooth_anatomy: string | null;
  /** Fraction of the lesion inside the assigned tooth. This is the evidence for the
   *  attribution, and it is containment, not IoU. */
  containment: number;
}

export interface AnalyzeResponse {
  /** Send this back on POST /chat. It is the only thing joining the analysis to the
   *  conversation — the agent is handed the findings, it never asks for them. */
  session_id: string;
  image_width: number;
  image_height: number;
  teeth: ToothOut[];
  restorations: RestorationOut[];
  findings: FindingOut[];
  /** FDI numbers claimed by more than one tooth box. Only worth surfacing when a finding's
   *  tooth_fdi appears here; otherwise it concerns a tooth carrying no finding. */
  ambiguous_fdi: number[];
  summary: string;
}

export interface DentalOfficeOut {
  name: string;
  address: string;
  rating?: number | null;
  user_ratings_total?: number | null;
  open_now?: boolean | null;
  /** Google Maps link for this practice. */
  maps_url?: string | null;
}

export interface ToolCallOut {
  name: string;
  /** The query Claude wrote, not the dentist's wording. */
  query: string;
  /** Passages or offices returned. 0 means nothing matched. */
  result_count: number;
  /** Geocoded town or city for a dental office search. */
  resolved_location?: string | null;
  /** Structured listings when the agent searched for nearby dentists. */
  dental_offices?: DentalOfficeOut[];
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  /** False when no X-ray is attached to this session — the reply is general dental
   *  knowledge, not a reading of this patient's imaging. Worth showing in the UI. */
  grounded_in_analysis: boolean;
  /** Empty when the agent answered without consulting the corpus. */
  tool_calls: ToolCallOut[];
  input_tokens: number;
  output_tokens: number;
}


export interface HealthResponse {
  status: string;
  lesion_model: boolean;
  fdi_model: boolean;
  faiss_index: boolean;
  embedding_model: boolean;
}

/** What a tooth cell/row shows. Every value is derived — see utils/derive.ts. */
export type ToothStatus = "Healthy" | "Caries" | "Infection" | "Wisdom" | "Undetected";
export type ToothPosition = "Upper" | "Lower";
/** The PATIENT's side, from the FDI quadrant. Not the side of the screen it appears on. */
export type ToothSide = "Left" | "Right";

export interface ToothView {
  fdi: number;
 
  name: string;
  position: ToothPosition;
  side: ToothSide;
  status: ToothStatus;
  /** Short clinical word for the STATUS column: "Good", "Caries", "Not detected"… */
  condition: string;
  /** Detector confidence 0-100. For an undetected tooth this is 0. */
  confidence: number;
  /** Findings attributed to this tooth, strongest first. */
  findings: FindingOut[];
  box: BoundingBox | null;
  /** True when more than one box claimed this FDI number — the label is not trustworthy. */
  ambiguous: boolean;
}

/** Counts for the dashboard tiles and the condition pie. */
export interface ConditionCounts {
  detected: number;
  healthy: number;
  caries: number;
  infection: number;
  wisdom: number;
  missing: number;
  restorations: number;
}

/** One bar of the confidence-distribution chart. */
export interface ConfidenceBand {
  label: string;
  count: number;
  percent: number;
}

export interface AnalysisView {
  sessionId: string;
  imageWidth: number;
  imageHeight: number;
  /** All 32 permanent teeth, in viewer order, present or not. */
  teeth: ToothView[];
  counts: ConditionCounts;
  confidence: ConfidenceBand[];
  /** Findings with no tooth attribution — missing teeth, and lesions no box contained. */
  unattributed: FindingOut[];
  restorations: RestorationOut[];
  ambiguousFdi: number[];
  summary: string;
  createdAt: string;
}

export interface ChatMessage {
  id: string;
  role: "assistant" | "user" | "system";
  text: string;
  timestamp: string;
  /** Retrievals the agent made for this reply. Surfaced so the dentist can see what a
   *  clinical claim was grounded in. */
  toolCalls?: ToolCallOut[];
  /** False marks a reply given without an X-ray attached. */
  groundedInAnalysis?: boolean;
  /** Set on locally-generated error bubbles so they can be styled apart from real replies. */
  isError?: boolean;
}

export interface UploadedImage {
  name: string;
  size: number;
  type: string;
  dataUrl: string;
}
