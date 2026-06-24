"use client";

import { useState } from "react";
import { annotatedImageUrl } from "@/lib/api";

interface AnnotatedImageViewerProps {
  images: string[];
}

export function AnnotatedImageViewer({ images }: AnnotatedImageViewerProps) {
  const [index, setIndex] = useState(0);
  if (images.length === 0) return null;

  const src = annotatedImageUrl(images[index]);

  return (
    <div>
      <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-slate-900">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={`Annotated inspection ${index + 1}`}
          className="max-h-[480px] w-full object-contain"
        />
        {/* Legend overlay */}
        <div className="absolute bottom-2 left-2 flex gap-3 rounded-lg bg-black/60 px-3 py-1.5 text-xs text-white">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-red-500" />
            Fail
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-amber-400" />
            Warning
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-gray-400" />
            Pass
          </span>
        </div>
      </div>
      {images.length > 1 && (
        <div className="mt-3 flex items-center justify-center gap-2">
          <button
            className="rounded border px-3 py-1 text-sm disabled:opacity-40"
            disabled={index === 0}
            onClick={() => setIndex((i) => i - 1)}
          >
            Prev
          </button>
          <span className="text-sm text-slate-500">
            {index + 1} / {images.length}
          </span>
          <button
            className="rounded border px-3 py-1 text-sm disabled:opacity-40"
            disabled={index === images.length - 1}
            onClick={() => setIndex((i) => i + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
