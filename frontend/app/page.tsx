"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { UploadZone } from "@/components/UploadZone";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatApiError, submitInspection, type Ruleset, type UnitSystem } from "@/lib/api";
import { useInspectionStore } from "@/store/inspectionStore";

export default function HomePage() {
  const router = useRouter();
  const { setSessionId, setLoading, setError, loading, error } = useInspectionStore();
  const [photos, setPhotos] = useState<File[]>([]);
  const [plan, setPlan] = useState<File[]>([]);
  const [unitSystem, setUnitSystem] = useState<UnitSystem>("metric");
  const [ruleset, setRuleset] = useState<Ruleset>("IS456");

  const handleInspect = async () => {
    if (photos.length === 0) {
      setError("Please upload at least one site photo.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await submitInspection(
        photos,
        plan[0] ?? null,
        unitSystem,
        ruleset,
      );
      setSessionId(res.session_id);
      router.push(`/results/${res.session_id}`);
    } catch (err: unknown) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-4 py-12">
      <div className="mb-10 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-slate-900">
          AI-Powered Construction Inspection
        </h1>
        <p className="mt-3 text-slate-600">
          Upload site photos to detect structural elements, measure alignment, and
          generate a compliance report.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Site Photos</h2>
            <p className="text-sm text-slate-500">JPG / PNG — multiple allowed</p>
          </CardHeader>
          <CardContent>
            <UploadZone
              label="Drop construction photos here"
              accept="image/jpeg,image/png"
              multiple
              files={photos}
              onFilesChange={setPhotos}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Architectural Plan (optional)</h2>
            <p className="text-sm text-slate-500">PDF or image with dimensions</p>
          </CardHeader>
          <CardContent>
            <UploadZone
              label="Drop building plan here"
              accept="application/pdf,image/*"
              files={plan}
              onFilesChange={setPlan}
            />
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardContent className="flex flex-wrap items-center gap-6 pt-6">
          <div>
            <label className="text-sm font-medium text-slate-700">Unit system</label>
            <select
              className="mt-1 block rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={unitSystem}
              onChange={(e) => setUnitSystem(e.target.value as UnitSystem)}
            >
              <option value="metric">Metric (cm / m)</option>
              <option value="imperial">Imperial (in / ft)</option>
            </select>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Ruleset</label>
            <select
              className="mt-1 block rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={ruleset}
              onChange={(e) => setRuleset(e.target.value as Ruleset)}
            >
              <option value="IS456">IS:456:2000</option>
              <option value="NBC2016">NBC 2016</option>
              <option value="custom">Custom</option>
            </select>
          </div>
          <div className="ml-auto">
            <Button onClick={handleInspect} disabled={loading || photos.length === 0}>
              {loading ? "Analysing…" : "Run Inspection"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <p className="mt-4 whitespace-pre-line text-center text-sm text-red-600">{error}</p>
      )}
    </main>
  );
}
