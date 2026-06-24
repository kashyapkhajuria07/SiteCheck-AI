import axios from "axios";

// Browser: use same-origin "" so Next.js rewrites proxy /api → FastAPI (port 8000).
// Server-side / direct API access: fall back to BACKEND_URL or localhost:8000.
function resolveApiBase(): string {
  if (typeof window !== "undefined") {
    return "";
  }
  return (
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.BACKEND_URL ||
    "http://127.0.0.1:8000"
  );
}

const API_BASE = resolveApiBase();

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 120000,
});

export type UnitSystem = "metric" | "imperial";
export type Ruleset = "IS456" | "NBC2016" | "custom";

export interface InspectResponse {
  session_id: string;
  status: string;
  preview_url: string;
}

export interface ElementResult {
  element_id: string;
  label: string;
  location: string;
  status: "PASS" | "WARNING" | "FAIL" | "INCONCLUSIVE";
  deviation: number | null;
  expected: string | null;
  unit: string;
  message: string;
  bbox: number[];
  allowed_value?: string | null;
  deviation_pct?: number | null;
  severity?: string;
  engineering_interpretation?: string | null;
  recommendation?: string | null;
  confidence_score: number;
}

export interface CriticalFinding {
  element_id: string;
  label: string;
  status: string;
  severity: string;
  deviation: number | null;
  deviation_pct: number | null;
  engineering_interpretation: string | null;
  recommendation: string | null;
}

export interface CoverageStats {
  total_detected: number;
  successfully_measured: number;
  coverage_pct: number;
  measurement_confidence_pct: number;
}

export interface RecommendationGroup {
  priority: string;
  title: string;
  items: Array<{
    element_id: string;
    label: string;
    engineering_interpretation: string | null;
    recommendation: string | null;
  }>;
}

export interface InspectionSummary {
  text: string;
  critical_count: number;
  warning_count: number;
  pass_count: number;
  most_severe_element: string | null;
  most_severe_deviation_pct: number | null;
}

export interface ValidationLog {
  scene_type: string;
  scene_confidence: number;
  raw_detection_count: number;
  filtered_detection_count: number;
  ignored_low_trust_count: number;
  ignored_non_structural_count: number;
  final_detection_count: number;
  scene_overloaded: boolean;
}

export interface ResultsResponse {
  session_id: string;
  compliance_score: number;
  pass_count: number;
  warning_count: number;
  fail_count: number;
  elements: ElementResult[];
  annotated_images: string[];
  report_url: string;
  detection_mode: string;
  detection_classes: string[];
  photos: Array<{
    photo_id: string;
    file_name: string;
    annotated_image_url: string;
    quality_flags: string[];
  }>;
  critical_findings: CriticalFinding[];
  coverage: CoverageStats;
  inspection_summary: InspectionSummary;
  recommendation_groups: RecommendationGroup[];
  validation_log?: ValidationLog;
}

export async function submitInspection(
  photos: File[],
  plan: File | null,
  unitSystem: UnitSystem,
  ruleset: Ruleset,
): Promise<InspectResponse> {
  const form = new FormData();
  photos.forEach((p) => form.append("photos", p));
  if (plan) form.append("plan", plan);
  form.append("unit_system", unitSystem);
  form.append("ruleset", ruleset);

  // Do NOT set Content-Type manually — axios must add the multipart boundary.
  const { data } = await api.post<InspectResponse>("/api/inspect", form);
  return data;
}

export function formatApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    if (!err.response) {
      return (
        "Cannot reach the inspection API. Start the backend in a separate terminal:\n" +
        "cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000"
      );
    }
    const detail = err.response.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join("; ");
    }
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return "Inspection failed.";
}

export async function fetchResults(sessionId: string): Promise<ResultsResponse> {
  const { data } = await api.get<ResultsResponse>(`/api/results/${sessionId}`);
  return data;
}

export function reportDownloadUrl(sessionId: string): string {
  const base = typeof window !== "undefined" ? "" : API_BASE;
  return `${base}/api/report/${sessionId}`;
}

export function annotatedImageUrl(path: string): string {
  if (path.startsWith("http")) return path;
  const base = typeof window !== "undefined" ? "" : API_BASE;
  return `${base}${path}`;
}
