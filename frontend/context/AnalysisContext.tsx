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
  type DetectionData,
  type ServerEvent,
} from "@/lib/ws-client";

// ── Domain types ──────────────────────────────────────────────────────────────

/** Detection as used internally by the context (mirrors DetectionData). */
export interface Detection {
  label: string;
  confidence: number;
  bbox: { x: number; y: number; width: number; height: number };
  timestamp: number;
  anatomicalLocation: string;
  frame_b64?: string;
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
  /** Upload a video file to the server and obtain a videoId. */
  uploadAndConnect: (file: File) => Promise<void>;
  /** Start analysis on the current videoId (sends WS connection). */
  startMockAnalysis: () => void;
  ignoreDetection: () => void;
  explainMore: () => void;
  resumePlayback: () => void;
  setIsPlaying: (v: boolean) => void;
  addDetection: (d: Detection) => void;
}

const AnalysisContext = createContext<AnalysisContextType | undefined>(undefined);

// ── helpers ───────────────────────────────────────────────────────────────────

function toDetection(d: DetectionData): Detection {
  const [x1, y1, x2, y2] = d.lesion.bbox;
  return {
    label: d.lesion.label,
    confidence: d.lesion.confidence,
    bbox: { x: x1, y: y1, width: x2 - x1, height: y2 - y1 },
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

  // ── mock fallback timers (used when backend is offline) ───────────────────
  const detectionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const llmTypingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearMockTimers = useCallback(() => {
    if (detectionTimerRef.current) { clearTimeout(detectionTimerRef.current); detectionTimerRef.current = null; }
    if (llmTypingTimerRef.current) { clearInterval(llmTypingTimerRef.current); llmTypingTimerRef.current = null; }
  }, []);

  // ── derived compat props ──────────────────────────────────────────────────
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
          setLlmInsight("");
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
        setLlmInsight((prev) => prev + evt.data.chunk);
        break;
      case "LLM_DONE":
        setIsListeningVoice(false);
        break;
      case "VIDEO_FINISHED": {
        setPipelineState("EOS_SUMMARY");
        const confirmed = evt.data.detections.map(toDetection);
        setDetections(confirmed);
        setIsConnected(false);
        break;
      }
      case "ERROR":
        console.error("[WS] server error:", evt.data.message);
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

  /** Upload file → get videoId → open WebSocket. */
  const uploadAndConnect = useCallback(async (file: File) => {
    const { video_id } = await uploadVideo(file);
    setVideoId(video_id);
    connectWs(video_id);
  }, [connectWs]);

  /** Fallback / demo: used when no real video is loaded yet. */
  const startMockAnalysis = useCallback(() => {
    if (videoId) {
      connectWs(videoId);
      return;
    }
    // Pure mock for demo without backend
    clearMockTimers();
    setPipelineState("PLAYING");
    setCurrentDetection(null);
    setIsListeningVoice(false);
    setLlmInsight("");

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
    } else {
      // mock fallback
      setCurrentDetection(null);
      setLlmInsight("");
      setIsListeningVoice(false);
      startMockAnalysis();
    }
  }, [startMockAnalysis]);

  const explainMore = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.send({ action: "ACTION_EXPLAIN" });
      return;
    }
    // mock fallback — simulate LLM streaming
    clearMockTimers();
    setIsListeningVoice(true);
    setLlmInsight("");
    const text =
      "Phát hiện phù hợp với tổn thương dạng viêm loét dạ dày, bờ viền đáy không đều và có sung huyết xung quanh. Độ tin cậy của mô hình ở mức cao. Khuyến nghị: đối chiếu triệu chứng lâm sàng, cân nhắc sinh thiết nếu tổn thương không đáp ứng điều trị nội khoa.";
    let idx = 0;
    llmTypingTimerRef.current = setInterval(() => {
      idx++;
      setLlmInsight(text.slice(0, idx));
      if (idx >= text.length) {
        clearInterval(llmTypingTimerRef.current!);
        llmTypingTimerRef.current = null;
        setIsListeningVoice(false);
      }
    }, 22);
  }, [clearMockTimers]);

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

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      clearMockTimers();
      wsRef.current?.disconnect();
    };
  }, [clearMockTimers]);

  // ── Context value ─────────────────────────────────────────────────────────
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
      uploadAndConnect,
      startMockAnalysis,
      ignoreDetection,
      explainMore,
      resumePlayback,
      setIsPlaying,
      addDetection,
    }),
    [
      isConnected, pipelineState, videoId, isPlaying,
      currentDetection, isListeningVoice, llmInsight, detections,
      uploadAndConnect, startMockAnalysis, ignoreDetection,
      explainMore, resumePlayback, setIsPlaying, addDetection,
    ],
  );

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>;
}

export function useAnalysis(): AnalysisContextType {
  const ctx = useContext(AnalysisContext);
  if (!ctx) throw new Error("useAnalysis must be used within AnalysisProvider");
  return ctx;
}
