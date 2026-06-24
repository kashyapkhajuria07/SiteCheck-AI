"use client";

import { useState } from "react";
import type { ElementResult } from "@/lib/api";
import { cn } from "@/lib/utils";

const statusStyles: Record<string, string> = {
  PASS: "bg-green-100 text-green-800",
  WARNING: "bg-yellow-100 text-yellow-800",
  FAIL: "bg-red-100 text-red-800",
  INCONCLUSIVE: "bg-slate-100 text-slate-600",
};

function confidenceColor(score: number): string {
  if (score >= 80) return "text-green-600";
  if (score >= 50) return "text-amber-600";
  return "text-red-600";
}

interface FindingsTableProps {
  elements: ElementResult[];
  filter?: string;
}

export function FindingsTable({ elements, filter }: FindingsTableProps) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const rows = filter
    ? elements.filter((e) => e.status === filter)
    : elements;

  if (rows.length === 0) {
    return <p className="text-sm text-slate-500">No findings to display.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-3">Element</th>
            <th className="px-3 py-3">Status</th>
            <th className="px-3 py-3">Confidence</th>
            <th className="px-3 py-3">Measured</th>
            <th className="px-3 py-3">Allowed</th>
            <th className="px-3 py-3">Deviation %</th>
            <th className="px-3 py-3">Severity</th>
            <th className="px-3 py-3">Explanation</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((el) => (
            <>
              <tr key={el.element_id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-3 py-3 font-medium">{el.label}</td>
                <td className="px-3 py-3">
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-xs font-semibold",
                      statusStyles[el.status],
                    )}
                  >
                    {el.status}
                  </span>
                </td>
                <td className={cn("px-3 py-3 text-xs font-medium", confidenceColor(el.confidence_score))}>
                  {el.confidence_score.toFixed(0)}%
                </td>
                <td className="px-3 py-3 font-mono text-xs">
                  {el.deviation != null ? `${el.deviation.toFixed(2)} ${el.unit}` : "—"}
                </td>
                <td className="px-3 py-3 font-mono text-xs">
                  {el.allowed_value ?? "—"}
                </td>
                <td className={cn(
                  "px-3 py-3 font-mono text-xs",
                  el.deviation_pct != null && el.deviation_pct > 10 ? "text-red-600" : "text-slate-600"
                )}>
                  {el.deviation_pct != null ? `${el.deviation_pct.toFixed(1)}%` : "—"}
                </td>
                <td className="px-3 py-3">
                  <span className={cn(
                    "rounded px-1.5 py-0.5 text-xs font-medium",
                    el.severity === "CRITICAL" ? "bg-red-100 text-red-800" :
                    el.severity === "MAJOR" ? "bg-orange-100 text-orange-800" :
                    el.severity === "MINOR" ? "bg-yellow-100 text-yellow-800" :
                    "bg-slate-100 text-slate-600"
                  )}>
                    {el.severity ?? "—"}
                  </span>
                </td>
                <td className="px-3 py-3">
                  <button
                    className="text-xs text-blue-600 hover:underline"
                    onClick={() => setExpanded(expanded === el.element_id ? null : el.element_id)}
                  >
                    {expanded === el.element_id ? "Hide" : "Explain"}
                  </button>
                </td>
              </tr>
              {expanded === el.element_id && (
                <tr key={`${el.element_id}-exp`} className="bg-blue-50">
                  <td colSpan={8} className="px-6 py-3">
                    <p className="text-xs font-semibold text-slate-700">Engineering Interpretation</p>
                    <p className="mt-1 text-sm text-slate-600">
                      {el.engineering_interpretation ?? el.message}
                    </p>
                    {el.recommendation && (
                      <>
                        <p className="mt-2 text-xs font-semibold text-slate-700">Recommendation</p>
                        <p className="mt-1 text-sm text-slate-600">{el.recommendation}</p>
                      </>
                    )}
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}
