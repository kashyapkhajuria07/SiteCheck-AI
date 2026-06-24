"use client";

interface ScoreGaugeProps {
  score: number;
}

function scoreColour(score: number): string {
  if (score >= 85) return "#22c55e";
  if (score >= 70) return "#eab308";
  if (score >= 50) return "#f97316";
  return "#ef4444";
}

export function ScoreGauge({ score }: ScoreGaugeProps) {
  const colour = scoreColour(score);
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="relative flex h-40 w-40 items-center justify-center">
      <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="54" fill="none" stroke="#e2e8f0" strokeWidth="10" />
        <circle
          cx="60"
          cy="60"
          r="54"
          fill="none"
          stroke={colour}
          strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute text-center">
        <p className="text-3xl font-bold" style={{ color: colour }}>
          {score}
        </p>
        <p className="text-xs text-slate-500">/ 100</p>
      </div>
    </div>
  );
}
