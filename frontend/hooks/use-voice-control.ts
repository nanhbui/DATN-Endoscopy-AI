/**
 * use-voice-control.ts — Real-time voice command hook using Web Speech API.
 *
 * Uses browser SpeechRecognition for instant word-by-word transcript,
 * with keyword matching for intent classification (no backend needed).
 *
 * Audio level meter via Web Audio API AnalyserNode (for the level bar UI).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/ws-client";

export type VoiceIntent = "BO_QUA" | "GIAI_THICH" | "XAC_NHAN" | "UNKNOWN";

interface UseVoiceControlOptions {
  onIntent: (intent: VoiceIntent, transcript: string) => void;
}

// Quick keyword pass — fires instantly for obvious short commands
const QUICK_KEYWORDS: [VoiceIntent, string[]][] = [
  ["BO_QUA",     ["bỏ qua", "loại bỏ", "không phải", "bắt sai", "nhận sai", "nhầm", "sai rồi", "false positive"]],
  ["GIAI_THICH", ["giải thích", "phân tích", "nói thêm", "chi tiết", "tại sao", "vì sao"]],
  ["XAC_NHAN",   ["xác nhận", "đúng rồi", "ghi lại", "lưu lại", "chính xác", "chuẩn rồi"]],
];

function quickMatch(text: string): VoiceIntent | null {
  const lower = text.toLowerCase();
  for (const [intent, kws] of QUICK_KEYWORDS) {
    if (kws.some(kw => lower.includes(kw))) return intent;
  }
  return null;
}

/** Classify intent: keyword-first (<1ms), LLM fallback for ambiguous sentences. */
async function classifyIntent(transcript: string): Promise<VoiceIntent> {
  const quick = quickMatch(transcript);
  if (quick) return quick; // instant — no network call

  // Ambiguous utterance → LLM understands full context
  try {
    const res = await fetch(`${API_BASE}/voice/classify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript }),
    });
    if (!res.ok) return "UNKNOWN";
    const data = await res.json() as { intent: VoiceIntent };
    return data.intent ?? "UNKNOWN";
  } catch {
    return "UNKNOWN";
  }
}

// Minimal type shims for SpeechRecognition (not fully typed in all lib.dom versions)
interface ISpeechRecognitionEvent {
  resultIndex: number;
  results: { isFinal: boolean; 0: { transcript: string } }[];
}
interface ISpeechRecognition extends EventTarget {
  lang: string; continuous: boolean; interimResults: boolean; maxAlternatives: number;
  start(): void; stop(): void; abort(): void;
  onresult: ((e: ISpeechRecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
}

export function useVoiceControl({ onIntent }: UseVoiceControlOptions) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState(""); // current interim text
  const [supported, setSupported] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [micError, setMicError] = useState<string | null>(null);

  const recognitionRef = useRef<ISpeechRecognition | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const onIntentRef = useRef(onIntent);
  onIntentRef.current = onIntent;

  useEffect(() => {
    console.log("[VoiceControl] mount — checking SpeechRecognition support");
    console.log("[VoiceControl] window.SpeechRecognition:", !!window.SpeechRecognition);
    console.log("[VoiceControl] window.webkitSpeechRecognition:", !!window.webkitSpeechRecognition);
    setSupported(
      typeof window !== "undefined" &&
      ("SpeechRecognition" in window || "webkitSpeechRecognition" in window),
    );
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    audioCtxRef.current?.close();
    audioCtxRef.current = null;
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    setIsListening(false);
    setAudioLevel(0);
    setTranscript("");
  }, []);

  const startListening = useCallback(() => {
    console.log("[VoiceControl] startListening called", { supported, isListening });
    if (!supported || isListening) return;

    // ── Speech recognition (synchronous — must stay within user gesture) ──────
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SRClass = (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;
    console.log("[VoiceControl] SRClass:", SRClass);
    if (!SRClass) return;

    const recognition: ISpeechRecognition = new SRClass();
    recognition.lang = "vi-VN";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognitionRef.current = recognition;

    recognition.onresult = (event) => {
      console.log("[VoiceControl] onresult — results:", event.results.length, "resultIndex:", event.resultIndex);
      let interim = "";
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const text = event.results[i][0].transcript;
        console.log(`[VoiceControl] result[${i}]: isFinal=${event.results[i].isFinal}, transcript="${text}"`);
        if (event.results[i].isFinal) finalText += text;
        else interim += text;
      }
      if (interim) {
        console.log("[VoiceControl] interim:", interim);
        setTranscript(interim);
      }
      if (finalText.trim()) {
        console.log("[VoiceControl] final:", finalText);
        setTranscript(finalText);
        classifyIntent(finalText.trim()).then(intent => {
          onIntentRef.current(intent, finalText.trim());
        });
      }
    };

    recognition.onerror = (event) => {
      console.error("[VoiceControl] error:", event.error);
      setMicError(event.error);
    };

    // Auto-restart after silence — Chrome stops the session automatically
    recognition.onend = () => {
      console.log("[VoiceControl] onend — recognitionRef:", !!recognitionRef.current);
      if (recognitionRef.current) {
        try { recognitionRef.current.start(); } catch (e) { console.warn("[VoiceControl] restart failed:", e); }
      }
    };

    try {
      recognition.start();
      console.log("[VoiceControl] recognition.start() OK");
      setIsListening(true);
      setMicError(null);
    } catch (err) {
      console.error("[VoiceControl] start failed:", err);
      setMicError(String(err));
      return;
    }

    // ── Audio level meter (async — getUserMedia after recognition is already running) ──
    navigator.mediaDevices?.getUserMedia({ audio: true, video: false })
      .then(stream => {
        streamRef.current = stream;
        const ctx = new AudioContext();
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 512;
        analyser.smoothingTimeConstant = 0.6;
        ctx.createMediaStreamSource(stream).connect(analyser);
        audioCtxRef.current = ctx;
        const buf = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
          analyser.getByteTimeDomainData(buf);
          let sum = 0;
          for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; sum += v * v; }
          setAudioLevel(Math.min(1, Math.sqrt(sum / buf.length) * 6));
          rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
      })
      .catch(() => { /* level meter optional */ });
  }, [supported, isListening]);

  useEffect(() => () => stopListening(), [stopListening]);

  return { isListening, transcript, audioLevel, supported, micError, startListening, stopListening };
}
