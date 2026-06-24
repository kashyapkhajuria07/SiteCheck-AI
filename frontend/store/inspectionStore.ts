import { create } from "zustand";
import type { ResultsResponse } from "@/lib/api";

interface InspectionState {
  sessionId: string | null;
  results: ResultsResponse | null;
  loading: boolean;
  error: string | null;
  setSessionId: (id: string | null) => void;
  setResults: (results: ResultsResponse | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useInspectionStore = create<InspectionState>((set) => ({
  sessionId: null,
  results: null,
  loading: false,
  error: null,
  setSessionId: (id) => set({ sessionId: id }),
  setResults: (results) => set({ results }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  reset: () => set({ sessionId: null, results: null, loading: false, error: null }),
}));
