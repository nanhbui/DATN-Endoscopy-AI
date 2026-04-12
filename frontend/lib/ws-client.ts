/**
 * ws-client.ts — Typed WebSocket wrapper for the endoscopy analysis server.
 *
 * Connects to: ws://localhost:8001/ws/analysis/{videoId}
 * Upload via:  POST http://localhost:8001/upload
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001";
export const WS_BASE  = API_BASE.replace(/^http/, "ws");

// ── Inbound event types (server → client) ────────────────────────────────────

export interface DetectionData {
  frame_index: number;
  timestamp_ms: number;
  location: string;
  lesion: { label: string; confidence: number; bbox: [number, number, number, number] };
  frame_b64?: string;
}

export type ServerEvent =
  | { event: "DETECTION_FOUND";  data: DetectionData }
  | { event: "STATE_CHANGE";     data: { state: string } }
  | { event: "LLM_CHUNK";        data: { chunk: string } }
  | { event: "LLM_DONE";         data: Record<string, never> }
  | { event: "VIDEO_FINISHED";   data: { detections: DetectionData[] } }
  | { event: "ERROR";            data: { message: string } };

// ── Outbound action types (client → server) ───────────────────────────────────

export type ClientAction =
  | { action: "ACTION_IGNORE" }
  | { action: "ACTION_EXPLAIN" }
  | { action: "ACTION_RESUME" };

// ── Upload / connect helpers ──────────────────────────────────────────────────

/**
 * Register a live source (RTSP URL or device path) with the server.
 * Returns a video_id that can be used to open a WebSocket session.
 */
export async function connectLiveStream(source: string): Promise<{ video_id: string }> {
  const res = await fetch(`${API_BASE}/stream/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source }),
  });
  if (!res.ok) throw new Error(`Stream connect failed: ${res.statusText}`);
  return res.json() as Promise<{ video_id: string }>;
}

/**
 * Upload a video file with optional progress callback (0–100).
 * Uses XHR so we get real upload progress events.
 */
export function uploadVideo(
  file: File,
  onProgress?: (pct: number) => void,
): Promise<{ video_id: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);

    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error("Invalid JSON response"));
        }
      } else {
        reject(new Error(`Upload failed: ${xhr.statusText}`));
      }
    };

    xhr.onerror = () => reject(new Error("Upload network error"));

    xhr.open("POST", `${API_BASE}/upload`);
    xhr.send(form);
  });
}

// ── EndoscopyWsClient ─────────────────────────────────────────────────────────

export class EndoscopyWsClient {
  private ws: WebSocket | null = null;
  private readonly videoId: string;
  onMessage: (evt: ServerEvent) => void = () => {};
  onClose: () => void = () => {};

  constructor(videoId: string) {
    this.videoId = videoId;
  }

  connect(): void {
    const url = `${WS_BASE}/ws/analysis/${this.videoId}`;
    this.ws = new WebSocket(url);

    this.ws.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data) as ServerEvent;
        this.onMessage(evt);
      } catch { /* ignore malformed frames */ }
    };

    this.ws.onclose = () => this.onClose();
    this.ws.onerror = (e) => console.error("[WS] error", e);
  }

  send(action: ClientAction): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(action));
    }
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }
}
