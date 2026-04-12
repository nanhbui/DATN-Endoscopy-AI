/**
 * use-voice-control.ts — Hands-free voice command hook using MediaRecorder + Whisper.
 *
 * Flow (per SYSTEM_REQUIREMENTS §4 Phase 2):
 *   Browser mic → MediaRecorder (WebM/OPUS chunks) → POST /voice/command
 *   → faster-Whisper on GPU → IntentClassifier → action dispatched here
 *
 * Intent values returned by the server:
 *   bo_qua      → ignoreDetection()
 *   giai_thich  → explainMore()
 *   xac_nhan    → no automatic action (visual feedback only)
 *   unknown     → ignored
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/ws-client";

export type VoiceIntent = "BO_QUA" | "GIAI_THICH" | "XAC_NHAN" | "UNKNOWN";

interface UseVoiceControlOptions {
  /** Called each time a non-unknown intent is recognised */
  onIntent: (intent: VoiceIntent, transcript: string) => void;
  /** How long each recording chunk is before being sent (ms). Default 3000. */
  chunkMs?: number;
}

export function useVoiceControl({ onIntent, chunkMs = 3000 }: UseVoiceControlOptions) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [supported, setSupported] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const onIntentRef = useRef(onIntent);
  onIntentRef.current = onIntent;

  useEffect(() => {
    setSupported(
      typeof window !== "undefined" &&
      !!navigator.mediaDevices?.getUserMedia &&
      typeof MediaRecorder !== "undefined",
    );
  }, []);

  /** Send one audio blob to the backend and dispatch the intent. */
  const sendChunk = useCallback(async (blob: Blob) => {
    if (blob.size < 1000) return; // skip near-empty chunks (silence)
    try {
      const form = new FormData();
      form.append("audio", blob, "chunk.webm");
      const res = await fetch(`${API_BASE}/voice/command`, { method: "POST", body: form });
      if (!res.ok) return;
      const data = await res.json() as { intent: VoiceIntent; transcript: string; confidence: number };
      if (data.transcript) setTranscript(data.transcript);
      if (data.intent && data.intent !== "UNKNOWN") {
        onIntentRef.current(data.intent, data.transcript ?? "");
      }
    } catch {
      // Network error — silently ignore; mic keeps recording
    }
  }, []);

  const stopListening = useCallback(() => {
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setIsListening(false);
    setTranscript("");
  }, []);

  const startListening = useCallback(async () => {
    if (!supported || isListening) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      const mr = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mr;

      mr.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) sendChunk(e.data);
      };

      // onStop fires when pipeline resumes — no extra action needed
      mr.onstop = () => setIsListening(false);

      mr.start(chunkMs); // emit a chunk every chunkMs milliseconds
      setIsListening(true);
    } catch (err) {
      console.warn("[VoiceControl] Mic access denied or unavailable:", err);
    }
  }, [supported, isListening, chunkMs, sendChunk]);

  // Cleanup on unmount
  useEffect(() => () => stopListening(), [stopListening]);

  return { isListening, transcript, supported, startListening, stopListening };
}
