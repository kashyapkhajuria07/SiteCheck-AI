"use client";

import { useCallback, useState } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";

interface UploadZoneProps {
  label: string;
  accept: string;
  multiple?: boolean;
  files: File[];
  onFilesChange: (files: File[]) => void;
}

export function UploadZone({
  label,
  accept,
  multiple = false,
  files,
  onFilesChange,
}: UploadZoneProps) {
  const [dragOver, setDragOver] = useState(false);

  const handleFiles = useCallback(
    (incoming: FileList | null) => {
      if (!incoming) return;
      const list = Array.from(incoming);
      onFilesChange(multiple ? [...files, ...list] : list.slice(0, 1));
    },
    [files, multiple, onFilesChange],
  );

  return (
    <div
      className={cn(
        "flex min-h-[160px] cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 transition",
        dragOver ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-slate-50",
      )}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
      onClick={() => document.getElementById(`file-${label}`)?.click()}
    >
      <Upload className="mb-2 h-8 w-8 text-slate-400" />
      <p className="text-sm font-medium text-slate-700">{label}</p>
      <p className="mt-1 text-xs text-slate-500">Drag & drop or click to browse</p>
      {files.length > 0 && (
        <p className="mt-3 text-xs text-brand-600">
          {files.length} file{files.length > 1 ? "s" : ""} selected
        </p>
      )}
      <input
        id={`file-${label}`}
        type="file"
        accept={accept}
        multiple={multiple}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}
