"use client";

import { Download } from "lucide-react";
import { reportDownloadUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface DownloadReportButtonProps {
  sessionId: string;
}

export function DownloadReportButton({ sessionId }: DownloadReportButtonProps) {
  return (
    <a href={reportDownloadUrl(sessionId)} download>
      <Button className="gap-2">
        <Download className="h-4 w-4" />
        Download PDF Report
      </Button>
    </a>
  );
}
