"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AnnotatedImageViewer } from "@/components/AnnotatedImageViewer";
import { DownloadReportButton } from "@/components/DownloadReportButton";
import { FindingsTable } from "@/components/FindingsTable";
import { ScoreGauge } from "@/components/ScoreGauge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { fetchResults, type ResultsResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

function detectionModeLabel(mode: string): { text: string; className: string } {
  switch (mode) {
    case "custom_yolo":
      return { text: "Custom YOLOv8", className: "bg-green-100 text-green-800" };
    case "coco_yolo":
      return { text: "COCO YOLO (fallback)", className: "bg-amber-100 text-amber-800" };
    default:
      return { text: "Heuristic CV", className: "bg-slate-100 text-slate-600" };
  }
}

function severityColor(sev: string): string {
  switch (sev) {
    case "CRITICAL": return "bg-red-100 text-red-800";
    case "MAJOR": return "bg-orange-100 text-orange-800";
    case "MINOR": return "bg-yellow-100 text-yellow-800";
    default: return "bg-slate-100 text-slate-600";
  }
}

export default function ResultsPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const [results, setResults] = useState<ResultsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("");

  useEffect(() => {
    if (!sessionId) return;
    fetchResults(sessionId)
      .then(setResults)
      .catch(() => setError("Failed to load results."))
      .finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-slate-500">Loading inspection results…</p>
      </main>
    );
  }

  if (error || !results) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4">
        <p className="text-red-600">{error ?? "No results found."}</p>
        <Link href="/">
          <Button variant="outline">Back to upload</Button>
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-4 py-10">
      {/* Header */}
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Inspection Results</h1>
          <p className="text-sm text-slate-500">Session {results.session_id}</p>
          {results.detection_mode && (
            <span
              className={`mt-2 inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${detectionModeLabel(results.detection_mode).className}`}
            >
              Detector: {detectionModeLabel(results.detection_mode).text}
            </span>
          )}
        </div>
        <div className="flex gap-3">
          <Link href="/">
            <Button variant="outline">New Inspection</Button>
          </Link>
          <DownloadReportButton sessionId={results.session_id} />
        </div>
      </div>

      {/* Row 1: SQI Gauge + Annotated Photos */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="flex flex-col items-center justify-center lg:col-span-1">
          <CardHeader>
            <h2 className="text-center text-lg font-semibold">Compliance Score</h2>
          </CardHeader>
          <CardContent className="flex flex-col items-center pb-8">
            <ScoreGauge score={results.compliance_score} />
            <div className="mt-4 flex gap-4 text-sm">
              <span className="text-green-600">Pass {results.pass_count}</span>
              <span className="text-yellow-600">Warn {results.warning_count}</span>
              <span className="text-red-600">Fail {results.fail_count}</span>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <h2 className="text-lg font-semibold">Annotated Photos</h2>
          </CardHeader>
          <CardContent>
            <AnnotatedImageViewer images={results.annotated_images} />
          </CardContent>
        </Card>
      </div>

      {/* Row 2: Critical Findings + Coverage + AI Summary */}
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        {/* Critical Findings Card */}
        <Card className={cn(
          "lg:col-span-1",
          results.critical_findings.length > 0 ? "border-red-300" : "border-green-300"
        )}>
          <CardHeader className={cn(
            "rounded-t-lg",
            results.critical_findings.length > 0 ? "bg-red-50" : "bg-green-50"
          )}>
            <h2 className={cn(
              "text-lg font-semibold",
              results.critical_findings.length > 0 ? "text-red-800" : "text-green-800"
            )}>
              Critical Findings
            </h2>
          </CardHeader>
          <CardContent className="py-4">
            {results.critical_findings.length === 0 ? (
              <p className="text-sm text-green-700">No critical issues detected.</p>
            ) : (
              <div className="space-y-3">
                {results.critical_findings.slice(0, 5).map((cf) => (
                  <div key={cf.element_id} className="rounded border border-red-200 bg-red-50/50 p-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-red-800">{cf.label}</span>
                      <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium", severityColor(cf.severity))}>
                        {cf.severity}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-red-700">
                      {cf.engineering_interpretation ?? (cf.deviation_pct != null ? `${cf.deviation_pct.toFixed(0)}% deviation` : "")}
                    </p>
                    {cf.recommendation && (
                      <p className="mt-1 text-xs font-medium text-slate-700">Fix: {cf.recommendation}</p>
                    )}
                  </div>
                ))}
                {results.critical_findings.length > 5 && (
                  <p className="text-xs text-slate-500">+{results.critical_findings.length - 5} more</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* AI Inspection Summary Card */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <h2 className="text-lg font-semibold">Inspection Summary</h2>
          </CardHeader>
          <CardContent className="py-4">
            <p className="text-sm leading-relaxed text-slate-700">
              {results.inspection_summary?.text ?? (
                `${results.critical_findings.length} critical issues, ${results.warning_count} warnings, ${results.pass_count} passing elements.`
              )}
            </p>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded bg-slate-50 p-2">
                <dt className="text-xs text-slate-500">Average Confidence</dt>
                <dd className="font-semibold">
                  {results.coverage?.measurement_confidence_pct != null ? results.coverage.measurement_confidence_pct.toFixed(0) : "—"}%
                </dd>
              </div>
              <div className="rounded bg-slate-50 p-2">
                <dt className="text-xs text-slate-500">Most Severe Deviation</dt>
                <dd className="font-semibold">
                  {results.inspection_summary?.most_severe_deviation_pct != null ? `${results.inspection_summary.most_severe_deviation_pct.toFixed(0)}%` : "—"}
                </dd>
              </div>
              <div className="rounded bg-slate-50 p-2">
                <dt className="text-xs text-slate-500">Avg Severity</dt>
                <dd className="font-semibold">{results.inspection_summary?.most_severe_element ?? "—"}</dd>
              </div>
              <div className="rounded bg-slate-50 p-2">
                <dt className="text-xs text-slate-500">Status</dt>
                <dd className="font-semibold">
                  {results.compliance_score >= 80 ? "✅ Compliant" :
                   results.compliance_score >= 50 ? "⚠ Needs Review" :
                   "❌ Non-Compliant"}
                </dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {/* Inspection Coverage Card */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <h2 className="text-lg font-semibold">Inspection Coverage</h2>
          </CardHeader>
          <CardContent className="py-4">
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">Elements Found</span>
                <span className="font-semibold">{results.coverage?.total_detected ?? results.elements.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Successfully Measured</span>
                <span className="font-semibold">{results.coverage?.successfully_measured ?? (results.pass_count + results.warning_count + results.fail_count)}</span>
              </div>
              <div className="flex justify-between border-t border-slate-200 pt-2">
                <span className="text-slate-500">Coverage</span>
                <span className={cn(
                  "font-semibold",
                  (results.coverage?.coverage_pct ?? 0) >= 90 ? "text-green-600" :
                  (results.coverage?.coverage_pct ?? 0) >= 70 ? "text-amber-600" : "text-red-600"
                )}>
                  {results.coverage?.coverage_pct != null ? results.coverage.coverage_pct.toFixed(0) : "—"}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Measurement Confidence</span>
                <span className={cn(
                  "font-semibold",
                  (results.coverage?.measurement_confidence_pct ?? 0) >= 80 ? "text-green-600" :
                  (results.coverage?.measurement_confidence_pct ?? 0) >= 50 ? "text-amber-600" : "text-red-600"
                )}>
                  {results.coverage?.measurement_confidence_pct != null ? results.coverage.measurement_confidence_pct.toFixed(0) : "—"}%
                </span>
              </div>
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Recommendations Card */}
      {results.recommendation_groups && results.recommendation_groups.length > 0 && (
        <Card className="mt-6">
          <CardHeader>
            <h2 className="text-lg font-semibold">Recommendations</h2>
          </CardHeader>
          <CardContent className="space-y-4">
            {results.recommendation_groups.map((group) => (
              <div key={group.priority} className={cn(
                "rounded-lg border p-4",
                group.priority === "IMMEDIATE" ? "border-red-200 bg-red-50" :
                group.priority === "MONITOR" ? "border-amber-200 bg-amber-50" :
                "border-green-200 bg-green-50"
              )}>
                <h3 className={cn(
                  "text-sm font-bold",
                  group.priority === "IMMEDIATE" ? "text-red-800" :
                  group.priority === "MONITOR" ? "text-amber-800" :
                  "text-green-800"
                )}>
                  {group.title}
                </h3>
                <ul className="mt-2 space-y-2">
                  {group.items.map((item) => (
                    <li key={item.element_id} className="text-sm text-slate-700">
                      <span className="font-medium">{item.label}</span>
                      {item.engineering_interpretation && (
                        <span className="ml-1 text-xs text-slate-500">— {item.engineering_interpretation}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Element Findings Table */}
      <Card className="mt-6">
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Element Findings</h2>
          <select
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="PASS">Pass</option>
            <option value="WARNING">Warning</option>
            <option value="FAIL">Fail</option>
            <option value="INCONCLUSIVE">Inconclusive</option>
          </select>
        </CardHeader>
        <CardContent>
          <FindingsTable elements={results.elements} filter={filter || undefined} />
        </CardContent>
      </Card>

      {/* Future-proof layout sections */}
      <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { title: "Structural Quality", value: `${results.compliance_score}%`, description: "Overall structural compliance score" },
          { title: "Dimensional Compliance", value: `${results.coverage?.coverage_pct ?? 0}%`, description: "Measurement coverage completeness" },
          { title: "Plan vs Actual", value: results.critical_findings.length > 0 ? `${results.critical_findings.length} issues` : "Compliant", description: "Deviation from approved plans" },
          { title: "Reinforcement Compliance", value: results.elements.length > 0 ? `${results.warning_count + results.fail_count} flags` : "N/A", description: "Reinforcement element assessment" },
        ].map((section) => (
          <div key={section.title} className="rounded-lg border border-slate-200 bg-white p-4 text-center">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{section.title}</h3>
            <p className="mt-1 text-lg font-bold text-slate-800">{section.value}</p>
            <p className="mt-0.5 text-xs text-slate-400">{section.description}</p>
          </div>
        ))}
      </div>

      {/* Photo Quality Notes */}
      {results.photos.some((p) => p.quality_flags.length > 0) && (
        <Card className="mt-6 border-yellow-200 bg-yellow-50">
          <CardHeader>
            <h2 className="text-lg font-semibold text-yellow-800">Photo Quality Notes</h2>
          </CardHeader>
          <CardContent>
            <ul className="list-inside list-disc text-sm text-yellow-900">
              {results.photos.flatMap((p) =>
                p.quality_flags.map((f, i) => (
                  <li key={`${p.photo_id}-${i}`}>
                    {p.file_name}: {f}
                  </li>
                )),
              )}
            </ul>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
