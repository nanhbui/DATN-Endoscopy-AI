# ENDOSCOPY AI PIPELINE - SYSTEM REQUIREMENT & IMPLEMENTATION GUIDE

## 1. PROJECT OVERVIEW
You are assisting in building an AI-Assisted Endoscopy Video Analysis System. This system processes gastrointestinal endoscopy videos, detects anatomical locations and mucosal lesions in real-time, and provides an interactive, **hands-free (voice-first)** workflow for endoscopists.

**Core Objective:** Implement a seamless, non-blocking workflow accommodating two modes:
1. **Batch Mode:** Ingesting and processing pre-recorded video files.
2. **Live Mode:** Real-time processing of live camera streams.
The system incorporates "Smart Ignore" memory and a robust, LLM-powered Voice User Interface (VUI) that understands natural clinical dialogue to extract actionable commands.

## 2. TECHNOLOGY STACK CONSTRAINTS
* **Frontend Interface:** React.js (Handles UI, Video Stream Player, WebSocket client, Web Audio API to capture voice).
* **Backend / Middleware:** **Python 3.x / FastAPI** (Runs on the Remote GPU Server. Acts as the asynchronous Controller, WebSocket server, manages state, and handles Audio/LLM APIs).
* **Voice & NLP Engine:** * **STT (Speech-to-Text):** OpenAI Whisper (running locally on GPU or via API) to transcribe clinical speech.
  * **Intent Router:** A lightweight LLM call to classify the doctor's natural language transcript into strict system actions.
* **Video & AI Engine (Core):** GStreamer with NVIDIA DeepStream / TensorRT.
  * Controlled via **GstPython** bindings or running as a standalone C++ daemon communicating with FastAPI.
  * Utilizes GPU hardware acceleration (`nvvideoconvert`, `nvinfer`) for YOLO object detection.
* **Communication:** WebSockets (FastAPI `websockets`) for real-time bi-directional messaging (Controls, Metadata, Voice Transcripts, AI Flags) and WebRTC/RTSP for video streaming.

## 3. SYSTEM STATE MACHINE
* `STATE_PLAYING`: Normal video playback/streaming. TensorRT continuously infers frames.
* `STATE_PAUSED_LISTENING`: Triggered when a new, unignored lesion is detected. Pipeline pauses. Microphone activates and streams audio via WebSocket to the FastAPI backend.
* `STATE_PROCESSING_INTENT`: Audio is transcribed by Whisper and parsed by the LLM Intent Router to determine the doctor's command.
* `STATE_PROCESSING_EXPLANATION`: Triggered if the intent is "Explain". UI shows loading while fetching the detailed medical LLM response.
* `STATE_EOS_SUMMARY`: Triggered when the video or live session ends. Displays the final dashboard.

## 4. DETAILED WORKFLOW LOGIC (THE PIPELINE)

### Phase 1: Real-time Playing & Detection
1. Initialize GStreamer pipeline using NVIDIA elements accommodating both modes (`filesrc` or `v4l2src`/`rtspsrc`).
2. `nvinfer` (TensorRT) continuously outputs bounding boxes, confidence scores, and labels.
3. **Interceptor Logic (Pad Probe):**
   * If a detection is NEW (passes the Smart Ignore Check), send a WebSocket event `DETECTION_FOUND` to the UI and immediately set pipeline to `GST_STATE_PAUSED`.

### Phase 2: Hands-Free Interaction & Intent Routing (The Pause State)
1. Upon pausing, the React Frontend automatically starts recording audio and streams chunks to the FastAPI backend via WebSocket. UI buttons for manual override are also displayed.
2. The doctor speaks naturally (e.g., *"Cái này không phải đâu, máy sai rồi, tắt đi để xem tiếp"* OR *"Dừng lại, phân tích kỹ xem có phải ung thư sớm không"*).
3. FastAPI passes the audio to **Whisper STT** to get the transcript.
4. FastAPI passes the transcript to the **LLM Intent Router** with a strict prompt:
   * *Context:* "You are an intent classifier for an endoscopy AI. The doctor just spoke: '{transcript}'."
   * *Task:* Return ONLY one of three exact strings: `ACTION_IGNORE`, `ACTION_EXPLAIN`, or `NO_COMMAND`.
   * *Logic:* Identify synonyms for ignore ("bỏ qua", "sai rồi", "không phải", "đi tiếp") or explain ("phân tích", "giải thích", "xem nào", "gợi ý"). Filter out background chatter.
5. FastAPI executes the routed action automatically.

### Phase 3: Action Execution
**Action A: `ACTION_IGNORE` (Bỏ qua)**
1. Controller updates the `ignored_detections` local JSON database with the current frame's metadata and location parameters.
2. Controller commands GStreamer to resume `GST_STATE_PLAYING`.

**Action B: `ACTION_EXPLAIN` (Giải thích thêm)**
1. Controller formats a prompt using the current metadata (Location, Lesion Label) and calls the Medical LLM API.
2. Controller streams the LLM response (Classification & Checklist) to the Frontend.
3. After the explanation is read/spoken, the system waits for a final voice confirmation (e.g., "Tiếp tục") or auto-resumes after a delay to `GST_STATE_PLAYING`.

### Phase 4: "Smart Ignore" Logic (Contextual Memory)
When the GStreamer engine detects a lesion, before pausing, it MUST verify against `ignored_metadata.json`.
* **Condition to Bypass Pause:**
  1. For Batch Mode: `abs(current_frame_index - ignored_frame_index) <= ALLOWED_FRAME_DRIFT`.
  2. For Live Mode: Time-based drift or anatomical zone tracking.
  3. Calculate **IoU (Intersection over Union)** between `current_bbox` and `ignored_bbox`. If `IoU > 0.8`, the detection is considered identical to a previously ignored false-positive.
* **Result:** If matched, the system silently ignores it. DO NOT pause. DO NOT trigger the microphone.

### Phase 5: LLM Integration Requirements (Medical Insight)
* **System Prompt:** "You are an expert gastroenterology assistant analyzing an endoscopy finding."
* **Input Context:** "Location: [Antrum/Corpus], Detection: [Polyp/Ulcer], Confidence: [X%]."
* **Required Output:**
  1. **Medical Classification Suggestion** (e.g., Paris classification).
  2. **Actionable Checklist** for the doctor (e.g., biopsy recommendations).

### Phase 6: End of Stream (EOS) Final Summary
1. When GStreamer bus catches the `EOS` message or the live session is manually terminated.
2. Controller aggregates all confirmed detections.
3. Frontend renders a Grid Dashboard containing cropped frames (extracted via NVMM buffer mapping), Timestamps, Labels, and generated LLM notes.

## 5. DATA SCHEMAS (FastAPI Pydantic Models)

### 5.1 WebSocket Incoming Audio/Command Payload
```json
{
 "type": "VOICE_STREAM",
 "audio_chunk": "<base64_encoded_audio>"
}

### 5.2 Intent Router Response (Internal to FastAPI)
{
 "transcript": "máy vớ vẩn xước tí bảo viêm loét, cho qua đi",
 "parsed_intent": "ACTION_IGNORE",
 "confidence": 0.98
}

## 6. INSTRUCTIONS FOR THE AI AGENT

1. FastAPI Implementation: Use asyncio to ensure that handling Whisper inference and LLM Intent Routing does not block the WebSocket connection or the GStreamer event loop.

2. Intent Classification Prompting: The prompt for the Intent Router must be heavily constrained to prevent hallucinations. Force the LLM to output a JSON object with strictly defined enums (ACTION_IGNORE, ACTION_EXPLAIN, NO_COMMAND).

3. Audio Handling: Ensure the React frontend captures audio using standard Web APIs (MediaRecorder) and sends optimal chunks to avoid overwhelming the Whisper model. Provide visual feedback (e.g., a glowing microphone icon) when the system enters STATE_PAUSED_LISTENING.

4. GPU Optimization: Both TensorRT (for vision) and Whisper (for voice) will share the GPU. Ensure VRAM allocation is explicitly managed if running both models locally on the lab server.
