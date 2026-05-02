"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  EndoscopyWsClient,
  uploadVideo,
  connectLiveStream,
  selectLibraryVideo,
  type DetectionData,
  type ServerEvent,
} from "@/lib/ws-client";

// ── Domain types ──────────────────────────────────────────────────────────────

/** Outcome of a detection after doctor interaction. */
export type DetectionStatus = "detected" | "ignored" | "confirmed" | "analyzed";

/** Detection as used internally by the context (mirrors DetectionData). */
export interface Detection {
  label: string;
  confidence: number;
  bbox: { x: number; y: number; width: number; height: number };
  timestamp: number;
  anatomicalLocation: string;
  frame_b64?: string;
  llmInsight?: string;
  status?: DetectionStatus;
}

export type PipelineState =
  | "IDLE"
  | "PLAYING"
  | "PAUSED_WAITING_INPUT"
  | "PROCESSING_LLM"
  | "EOS_SUMMARY";

interface AnalysisContextType {
  // ── connection state ──
  isConnected: boolean;
  pipelineState: PipelineState;
  videoId: string | null;

  // ── legacy UI compat props ──
  isPlaying: boolean;
  currentDetection: Detection | null;
  isListeningVoice: boolean;
  llmInsight: string;
  detections: Detection[];

  // ── actions ──
  uploadOnly: (file: File, onProgress?: (pct: number) => void) => Promise<void>;
  uploadAndConnect: (file: File, onProgress?: (pct: number) => void) => Promise<void>;
  connectLive: (source: string) => Promise<void>;
  prepareFromLibrary: (libraryId: string) => Promise<string>;
  selectFromLibrary: (libraryId: string) => Promise<void>;
  startMockAnalysis: () => void;
  /** Reset WS + pipeline state to IDLE while keeping videoId — allows re-running analysis on the same video. */
  resetPipeline: () => void;
  ignoreDetection: () => void;
  explainMore: () => void;
  followUpChat: (text: string) => void;
  /** Confirm detection as valid → resume pipeline. */
  confirmDetection: () => void;
  resumePlayback: () => void;
  setIsPlaying: (v: boolean) => void;
  addDetection: (d: Detection) => void;
  removeDetection: (timestamp: number) => void;
  resetAnalysis: () => void;
}

const AnalysisContext = createContext<AnalysisContextType | undefined>(undefined);

// ── helpers ───────────────────────────────────────────────────────────────────

const FRAME_W = 1920;
const FRAME_H = 1080;

function toDetection(d: DetectionData): Detection {
  const [x1, y1, x2, y2] = d.lesion.bbox;
  return {
    label: d.lesion.label,
    confidence: d.lesion.confidence,
    bbox: {
      x: (x1 / FRAME_W) * 100,
      y: (y1 / FRAME_H) * 100,
      width: ((x2 - x1) / FRAME_W) * 100,
      height: ((y2 - y1) / FRAME_H) * 100,
    },
    timestamp: d.timestamp_ms / 1000,
    anatomicalLocation: d.location,
    frame_b64: d.frame_b64,
  };
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [pipelineState, setPipelineState] = useState<PipelineState>("IDLE");
  const [isConnected, setIsConnected] = useState(false);
  const [videoId, setVideoId] = useState<string | null>(null);
  const [currentDetection, setCurrentDetection] = useState<Detection | null>(null);
  const [isListeningVoice, setIsListeningVoice] = useState(false);
  const [llmInsight, setLlmInsight] = useState("");
  const [detections, setDetections] = useState<Detection[]>([]);

  const wsRef = useRef<EndoscopyWsClient | null>(null);
  const llmInsightRef = useRef("");
  // Prevents duplicate ACTION_EXPLAIN before server STATE_CHANGE PROCESSING_LLM arrives
  const explainInFlightRef = useRef(false);

  const detectionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const llmTypingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearMockTimers = useCallback(() => {
    if (detectionTimerRef.current) { clearTimeout(detectionTimerRef.current); detectionTimerRef.current = null; }
    if (llmTypingTimerRef.current) { clearInterval(llmTypingTimerRef.current); llmTypingTimerRef.current = null; }
  }, []);

  const isPlaying = pipelineState === "PLAYING";

  // ── WebSocket event handler ───────────────────────────────────────────────

  const handleServerEvent = useCallback((evt: ServerEvent) => {
    switch (evt.event) {
      case "STATE_CHANGE": {
        const s = evt.data.state as PipelineState;
        setPipelineState(s);
        if (s === "PLAYING") {
          setCurrentDetection(null);
          setIsListeningVoice(false);
        }
        if (s === "PROCESSING_LLM") {
          setIsListeningVoice(true);
          llmInsightRef.current = ""; setLlmInsight("");
        }
        break;
      }
      case "DETECTION_FOUND": {
        const det = toDetection(evt.data);
        setCurrentDetection(det);
        setDetections((prev) => [det, ...prev]);
        break;
      }
      case "LLM_CHUNK":
        llmInsightRef.current += evt.data.chunk;
        setLlmInsight(llmInsightRef.current);
        break;
      case "LLM_DONE": {
        explainInFlightRef.current = false;
        setIsListeningVoice(false);
        setPipelineState("PAUSED_WAITING_INPUT");
        const insight = llmInsightRef.current;
        setDetections(prev => prev.map((d, i) => i === 0 ? { ...d, llmInsight: insight || d.llmInsight, status: "analyzed" } : d));
        break;
      }
      case "VIDEO_FINISHED": {
        setPipelineState("EOS_SUMMARY");
        setIsConnected(false);
        // Null out the client ref so stale ignoreDetection/confirmDetection calls
        // don't override EOS_SUMMARY with PLAYING via the wsRef.current check.
        wsRef.current?.disconnect();
        wsRef.current = null;
        break;
      }
      case "ERROR":
        console.error("[WS] server error:", evt.data.message);
        if (evt.data.message?.includes("Session not found")) {
          wsRef.current?.disconnect();
          wsRef.current = null;
          setIsConnected(false);
          setPipelineState("IDLE");
          setVideoId(null);
        }
        break;
    }
  }, []);

  // ── WebSocket connect ─────────────────────────────────────────────────────

  const connectWs = useCallback((vid: string) => {
    wsRef.current?.disconnect();
    const client = new EndoscopyWsClient(vid);
    client.onMessage = handleServerEvent;
    client.onClose = () => setIsConnected(false);
    client.connect();
    wsRef.current = client;
    setIsConnected(true);
    setPipelineState("PLAYING");
  }, [handleServerEvent]);

  // ── Public actions ────────────────────────────────────────────────────────

  const uploadOnly = useCallback(async (
    file: File,
    onProgress?: (pct: number) => void,
  ) => {
    const { video_id } = await uploadVideo(file, onProgress);
    setVideoId(video_id);
  }, []);

  const uploadAndConnect = useCallback(async (
    file: File,
    onProgress?: (pct: number) => void,
  ) => {
    const { video_id } = await uploadVideo(file, onProgress);
    setVideoId(video_id);
    connectWs(video_id);
  }, [connectWs]);

  const connectLive = useCallback(async (source: string) => {
    const { video_id } = await connectLiveStream(source);
    setVideoId(video_id);
    connectWs(video_id);
  }, [connectWs]);

  /** Registers the library video with the backend and stores video_id — no WS connection.
   *  Returns the video_id so the caller can build a preview URL. */
  const prepareFromLibrary = useCallback(async (libraryId: string): Promise<string> => {
    const { video_id } = await selectLibraryVideo(libraryId);
    setVideoId(video_id);
    return video_id;
  }, []);

  const selectFromLibrary = useCallback(async (libraryId: string) => {
    const { video_id } = await selectLibraryVideo(libraryId);
    setVideoId(video_id);
    connectWs(video_id);
  }, [connectWs]);

  const startMockAnalysis = useCallback(() => {
    if (videoId) {
      connectWs(videoId);
      return;
    }
    clearMockTimers();
    setPipelineState("PLAYING");
    setCurrentDetection(null);
    setIsListeningVoice(false);
    llmInsightRef.current = ""; setLlmInsight("");

    detectionTimerRef.current = setTimeout(() => {
      const mock: Detection = {
        label: "Viêm loét",
        confidence: 0.92,
        bbox: { x: 29, y: 34, width: 23, height: 19 },
        timestamp: 25.7,
        anatomicalLocation: "Dạ dày",
      };
      setPipelineState("PAUSED_WAITING_INPUT");
      setCurrentDetection(mock);
      setDetections((prev) => [mock, ...prev]);
    }, 5000);
  }, [videoId, connectWs, clearMockTimers]);

  const ignoreDetection = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.send({ action: "ACTION_IGNORE" });
      setDetections(prev => prev.map((d, i) => i === 0 ? { ...d, status: "ignored" } : d));
      setPipelineState("PLAYING");
      setCurrentDetection(null);
      llmInsightRef.current = ""; setLlmInsight("");
      setIsListeningVoice(false);
    } else {
      // Pure mock mode (no real session). Never call startMockAnalysis when a videoId
      // exists — that would reconnect to the backend and restart from frame 0.
      setDetections(prev => prev.map((d, i) => i === 0 ? { ...d, status: "ignored" } : d));
      setCurrentDetection(null);
      llmInsightRef.current = ""; setLlmInsight("");
      setIsListeningVoice(false);
      if (!videoId) startMockAnalysis();
    }
  }, [startMockAnalysis, videoId]);

  const explainMore = useCallback(() => {
    if (wsRef.current) {
      if (explainInFlightRef.current) return; // block duplicate before server acks
      explainInFlightRef.current = true;
      // Optimistic state update — voice pipelineStateRef check blocks any next call
      setPipelineState("PROCESSING_LLM");
      setIsListeningVoice(true);
      llmInsightRef.current = ""; setLlmInsight("");
      wsRef.current.send({ action: "ACTION_EXPLAIN" });
      return;
    }
    // mock fallback
    clearMockTimers();
    setIsListeningVoice(true);
    llmInsightRef.current = ""; setLlmInsight("");
    const text =
`**Phân loại Paris:** 0-III (loét) — Tổn thương lõm sâu, bờ viền không đều, có vùng sung huyết xung quanh, kích thước ước tính 8–12mm.

**Nhận định lâm sàng:** Tiền ung thư / nghi ngờ — bờ fibrin không đều, sung huyết lan toả gợi ý nguy cơ loét ác tính. Cần phân biệt với ung thư dạ dày type 0-III sớm.

**Checklist hành động:**
- [ ] Sinh thiết ≥ 5 mảnh từ bờ và đáy tổn thương
- [ ] Nhuộm CLO-test tại chỗ để kiểm tra H. pylori
- [ ] Chụp ảnh NBI/ChromoEndoscopy nếu có thiết bị
- [ ] Ghi nhận vị trí (hang vị / thân vị / tâm vị) trong biên bản
- [ ] Hẹn tái khám 6–8 tuần sau điều trị ức chế acid`;
    let idx = 0;
    llmTypingTimerRef.current = setInterval(() => {
      idx++;
      setLlmInsight(text.slice(0, idx));
      if (idx >= text.length) {
        clearInterval(llmTypingTimerRef.current!);
        llmTypingTimerRef.current = null;
        setIsListeningVoice(false);
        setPipelineState("PAUSED_WAITING_INPUT");
      }
    }, 22);
  }, [clearMockTimers]);

  const followUpChat = useCallback((text: string) => {
    if (wsRef.current) {
      wsRef.current.send({ action: "ACTION_FOLLOW_UP", payload: { text } });
      llmInsightRef.current = ""; setLlmInsight("");
    }
  }, []);

  const confirmDetection = useCallback(() => {
    if (!wsRef.current) return; // no-op if session is gone (e.g. already EOS)
    wsRef.current.send({ action: "ACTION_CONFIRM" });
    setDetections(prev => prev.map((d, i) => i === 0 ? { ...d, status: "confirmed" } : d));
    setPipelineState("PLAYING");
    setCurrentDetection(null);
    llmInsightRef.current = ""; setLlmInsight("");
  }, []);

  const resumePlayback = useCallback(() => {
    wsRef.current?.send({ action: "ACTION_RESUME" });
    setPipelineState("PLAYING");
    setCurrentDetection(null);
  }, []);

  const setIsPlaying = useCallback((v: boolean) => {
    if (!v) {
      clearMockTimers();
      setPipelineState("IDLE");
      wsRef.current?.disconnect();
    }
  }, [clearMockTimers]);

  const addDetection = useCallback((d: Detection) => {
    setDetections((prev) => [d, ...prev]);
  }, []);

  const removeDetection = useCallback((timestamp: number) => {
    setDetections((prev) => prev.filter((d) => d.timestamp !== timestamp));
  }, []);

  const resetPipeline = useCallback(() => {
    clearMockTimers();
    wsRef.current?.disconnect();
    wsRef.current = null;
    explainInFlightRef.current = false;
    setPipelineState("IDLE");
    setIsConnected(false);
    setCurrentDetection(null);
    setIsListeningVoice(false);
    llmInsightRef.current = ""; setLlmInsight("");
    setDetections([]);
  }, [clearMockTimers]);

  const resetAnalysis = useCallback(() => {
    resetPipeline();
    setVideoId(null);
  }, [resetPipeline]);

  useEffect(() => {
    return () => {
      clearMockTimers();
      wsRef.current?.disconnect();
    };
  }, [clearMockTimers]);

  const value = useMemo<AnalysisContextType>(
    () => ({
      isConnected,
      pipelineState,
      videoId,
      isPlaying,
      currentDetection,
      isListeningVoice,
      llmInsight,
      detections,
      uploadOnly,
      uploadAndConnect,
      connectLive,
      prepareFromLibrary,
      selectFromLibrary,
      startMockAnalysis,
      resetPipeline,
      ignoreDetection,
      explainMore,
      followUpChat,
      confirmDetection,
      resumePlayback,
      setIsPlaying,
      addDetection,
      removeDetection,
      resetAnalysis,
    }),
    [
      isConnected, pipelineState, videoId, isPlaying,
      currentDetection, isListeningVoice, llmInsight, detections,
      uploadOnly, uploadAndConnect, connectLive, prepareFromLibrary, selectFromLibrary,
      startMockAnalysis, resetPipeline, ignoreDetection,
      explainMore, followUpChat, confirmDetection, resumePlayback, setIsPlaying, addDetection, removeDetection, resetAnalysis,
    ],
  );

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>;
}

export function useAnalysis(): AnalysisContextType {
  const ctx = useContext(AnalysisContext);
  if (!ctx) throw new Error("useAnalysis must be used within AnalysisProvider");
  return ctx;
}
