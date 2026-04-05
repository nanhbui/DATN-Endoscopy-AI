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

interface Detection {
  label: string;
  confidence: number;
  bbox: { x: number; y: number; width: number; height: number };
  timestamp: number;
  anatomicalLocation: string;
}

interface AnalysisContextType {
  isPlaying: boolean;
  currentDetection: Detection | null;
  isListeningVoice: boolean;
  llmInsight: string;
  detections: Detection[];
  startMockAnalysis: () => void;
  ignoreDetection: () => void;
  explainMore: () => void;
  setIsPlaying: (playing: boolean) => void;
  addDetection: (detection: Detection) => void;
}

const AnalysisContext = createContext<AnalysisContextType | undefined>(undefined);

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentDetection, setCurrentDetection] = useState<Detection | null>(null);
  const [isListeningVoice, setIsListeningVoice] = useState(false);
  const [llmInsight, setLlmInsight] = useState("");
  const [detections, setDetections] = useState<Detection[]>([]);

  const detectionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const llmDelayTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const llmTypingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearSimulationTimers = useCallback(() => {
    if (detectionTimerRef.current) {
      clearTimeout(detectionTimerRef.current);
      detectionTimerRef.current = null;
    }

    if (llmDelayTimerRef.current) {
      clearTimeout(llmDelayTimerRef.current);
      llmDelayTimerRef.current = null;
    }

    if (llmTypingTimerRef.current) {
      clearInterval(llmTypingTimerRef.current);
      llmTypingTimerRef.current = null;
    }
  }, []);

  const startMockAnalysis = useCallback(() => {
    clearSimulationTimers();
    setIsPlaying(true);
    setCurrentDetection(null);
    setIsListeningVoice(false);
    setLlmInsight("");

    // TODO(backend): replace timeout with real WebSocket event from C++/GStreamer detector.
    detectionTimerRef.current = setTimeout(() => {
      const mockDetection: Detection = {
        label: "Viêm loét",
        confidence: 0.92,
        bbox: { x: 29, y: 34, width: 23, height: 19 },
        timestamp: 25.7,
        anatomicalLocation: "Dạ dày",
      };

      setIsPlaying(false);
      setCurrentDetection(mockDetection);
      setDetections((prev) => [mockDetection, ...prev]);
    }, 5000);
  }, [clearSimulationTimers]);

  const ignoreDetection = useCallback(() => {
    setCurrentDetection(null);
    setLlmInsight("");
    setIsListeningVoice(false);
    startMockAnalysis();
  }, [startMockAnalysis]);

  const explainMore = useCallback(() => {
    if (!currentDetection) {
      return;
    }

    clearSimulationTimers();
    setIsListeningVoice(true);
    setLlmInsight("");

    const mockInsight =
      "Phát hiện phù hợp với tổn thương dạng viêm loét dạ dày, bờ viền đáy không đều và có sung huyết xung quanh. Độ tin cậy của mô hình ở mức cao. Khuyến nghị: đối chiếu triệu chứng lâm sàng, cân nhắc sinh thiết nếu tổn thương không đáp ứng điều trị nội khoa.";

    // TODO(backend): replace this with streamed LLM chunks from API/WebSocket gateway.
    llmDelayTimerRef.current = setTimeout(() => {
      let index = 0;
      llmTypingTimerRef.current = setInterval(() => {
        index += 1;
        setLlmInsight(mockInsight.slice(0, index));

        if (index >= mockInsight.length) {
          if (llmTypingTimerRef.current) {
            clearInterval(llmTypingTimerRef.current);
            llmTypingTimerRef.current = null;
          }
          setIsListeningVoice(false);
        }
      }, 22);
    }, 900);
  }, [clearSimulationTimers, currentDetection]);

  const addDetection = useCallback((detection: Detection) => {
    setDetections((prev) => [detection, ...prev]);
  }, []);

  useEffect(() => {
    return () => {
      clearSimulationTimers();
    };
  }, [clearSimulationTimers]);

  const value = useMemo(
    () => ({
      isPlaying,
      currentDetection,
      isListeningVoice,
      llmInsight,
      detections,
      startMockAnalysis,
      ignoreDetection,
      explainMore,
      setIsPlaying,
      addDetection,
    }),
    [
      isPlaying,
      currentDetection,
      isListeningVoice,
      llmInsight,
      detections,
      startMockAnalysis,
      ignoreDetection,
      explainMore,
      addDetection,
    ]
  );

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>;
}

export function useAnalysis() {
  const context = useContext(AnalysisContext);
  if (!context) {
    throw new Error("useAnalysis must be used within an AnalysisProvider");
  }
  return context;
}