import { create } from "zustand";
import type { AnalysisView, ChatMessage, UploadedImage } from "../types";



const WELCOME: ChatMessage = {
  id: "ai-welcome",
  role: "assistant",
  text:
    "Hello Dr. Bryan, I'm DentalVision. Upload a panoramic X-ray and I'll analyse it, " +
    "then answer questions about the findings.",
  timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
};

interface AppState {
  /** Issued by POST /analyze, replayed on every POST /chat. The single thread joining the
   *  X-ray to the conversation — lose it and the agent believes no image was ever uploaded.
   *  Kept for the whole browser session, across re-uploads: passing it back to /analyze
   *  re-points the same consultation at a new X-ray instead of starting over. */
  sessionId: string | null;
  uploadedImage: UploadedImage | null;
  analysis: AnalysisView | null;
  chatMessages: ChatMessage[];
  isAnalyzing: boolean;
  isChatLoading: boolean;
  /** Analysis-side failure, shown in the upload panel. Chat failures become error bubbles
   *  in the transcript instead, where the dentist is already looking. */
  errorMessage: string | null;

  setSessionId: (id: string | null) => void;
  setUploadedImage: (img: UploadedImage | null) => void;
  setAnalysis: (res: AnalysisView | null) => void;
  setChatMessages: (msgs: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;
  setIsAnalyzing: (v: boolean) => void;
  setIsChatLoading: (v: boolean) => void;
  setErrorMessage: (m: string | null) => void;
  reset: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  sessionId: null,
  uploadedImage: null,
  analysis: null,
  chatMessages: [WELCOME],
  isAnalyzing: false,
  isChatLoading: false,
  errorMessage: null,

  setSessionId: (id) => set({ sessionId: id }),
  setUploadedImage: (img) => set({ uploadedImage: img }),
  setAnalysis: (res) => set({ analysis: res }),
  setChatMessages: (msgs) =>
    set((state) => ({
      chatMessages:
        typeof msgs === "function"
          ? (msgs as (p: ChatMessage[]) => ChatMessage[])(state.chatMessages)
          : msgs,
    })),
  setIsAnalyzing: (v) => set({ isAnalyzing: v }),
  setIsChatLoading: (v) => set({ isChatLoading: v }),
  setErrorMessage: (m) => set({ errorMessage: m }),

  // Clears the image and findings but deliberately keeps `sessionId`: the backend still
  // holds that conversation, and dropping the id here would strand it in memory until the
  // TTL expires while the next upload silently started a second one.
  reset: () =>
    set({
      uploadedImage: null,
      analysis: null,
      chatMessages: [WELCOME],
      isAnalyzing: false,
      errorMessage: null,
    }),
}));
