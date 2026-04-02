# ENDOSCOPY AI PIPELINE - IMPLEMENTATION GUIDE FOR AI AGENT

## 1. PROJECT OVERVIEW
You are assisting in building an AI-Assisted Endoscopy Video Analysis System. This system processes gastrointestinal endoscopy videos, detects anatomical locations and mucosal lesions in real-time, and provides an interactive workflow for endoscopists.

**Core Objective:** Implement a seamless, non-blocking workflow from video ingestion to a final EOS (End of Stream) summary report, incorporating "Smart Ignore" memory and LLM-powered medical insights.

## 2. TECHNOLOGY STACK CONSTRAINTS
* **Frontend Interface:** React.js (Handles UI, Video Canvas, WebSocket client, Web Speech API for voice commands).
* **Backend / Middleware:** Node.js / Express (Acts as a Controller, WebSocket server, interacts with LLM API).
* **Video & AI Engine:** GStreamer with custom C++ plugins/elements (Handles `filesrc`, `decodebin`, `tensor_filter` for AI inference, and pipeline state management).
* **Communication:** WebSockets (Real-time bi-directional messaging between GStreamer Engine, Node Controller, and React Frontend).

## 3. SYSTEM STATE MACHINE
The system revolves around controlling the GStreamer pipeline states based on AI triggers and user inputs.

* `STATE_PLAYING`: Normal video playback. AI continuously infers frames.
* `STATE_PAUSED_WAITING_INPUT`: Triggered when a new, unignored lesion is detected. Video pauses. Listening for user action (Voice/UI).
* `STATE_PROCESSING_LLM`: Triggered if the user requests an explanation. UI shows loading while fetching LLM response.
* `STATE_EOS_SUMMARY`: Triggered when the video ends. Displays the final dashboard.

## 4. DETAILED WORKFLOW LOGIC (THE PIPELINE)

### Phase 1: Real-time Playing & Detection
1. Initialize GStreamer pipeline: `filesrc ! decodebin ! videoconvert ! tensor_filter ! appsink`.
2. `tensor_filter` continuously outputs bounding boxes, confidence scores, and labels (Anatomy Location + Lesion Type).
3. **Interceptor Logic (Pad Probe / AppSink):**
   * For every frame with a detection (Confidence > Threshold), execute **Smart Ignore Check** (Phase 4).
   * If the detection is NEW (not ignored), send a WebSocket event `DETECTION_FOUND` to the UI and immediately set pipeline to `GST_STATE_PAUSED`.

### Phase 2: User Interaction (The Pause State)
1. Upon receiving `DETECTION_FOUND`, the React Frontend displays the bounding box on the video canvas.
2. The Frontend activates the Voice Listener (Web Speech API) and reveals UI action buttons: **[Ignore]** and **[Explain More]**.
3. Wait for user action.

### Phase 3: Action Execution
**Action A: "Ignore" (Bỏ qua)**
1. Frontend sends `ACTION_IGNORE` to Controller.
2. Controller updates the `ignored_detections` local JSON database with the current frame's metadata.
3. Controller commands GStreamer to resume `GST_STATE_PLAYING`.

**Action B: "Explain More" (Giải thích thêm)**
1. Frontend sends `ACTION_EXPLAIN` to Controller.
2. Controller formats a prompt using the current metadata (Location, Lesion Label) and calls the LLM API (Phase 5).
3. Controller streams the LLM response to the Frontend.
4. User reads the explanation on the UI. User manually triggers "Resume Playback" -> Controller commands GStreamer to `GST_STATE_PLAYING`.

### Phase 4: "Smart Ignore" Logic (Core Algorithmic Requirement)
When the GStreamer engine detects a lesion, before pausing, it MUST verify against the `ignored_metadata.json` for the specific video.
* **Condition to Bypass Pause:**
  1. `abs(current_frame_index - ignored_frame_index) <= ALLOWED_FRAME_DRIFT` (e.g., 15 frames).
  2. Calculate **IoU (Intersection over Union)** between `current_bbox` and `ignored_bbox`. If `IoU > 0.8`, the detection is considered identical.
* **Result:** If matched, DO NOT pause. Continue sending frames to UI, but without the auto-stop trigger.

### Phase 5: LLM Integration Requirements
When `ACTION_EXPLAIN` is triggered, the LLM must return a structured response.
* **System Prompt:** "You are an expert gastroenterology assistant analyzing an endoscopy finding."
* **Input Context:** "Location: [Antrum/Corpus/etc.], Detection: [Polyp/Ulcer], Confidence: [X%]."
* **Required Output Structure (Strict):**
  1. **Medical Classification Suggestion:** (e.g., "Based on the visual features provided by the detection, this polyp may align with the Paris 0-Is or 0-Ip classification. Further observation of the pit pattern is required.")
  2. **Checklist for the Doctor:** Actionable steps. (e.g., "Antral ulcer detected - Recommended Action: Perform biopsy of 2-4 fragments at the ulcer margins for HP testing and malignancy screening.")

### Phase 6: End of Stream (EOS) Final Summary
1. When GStreamer bus catches the `EOS` message, send `VIDEO_FINISHED` to Frontend.
2. Controller aggregates all confirmed detections (detections where the pipeline paused and the user did NOT click "Ignore").
3. Frontend renders a Grid Dashboard containing:
   * Cropped image of the frame (or the frame with bounding box).
   * Timestamp.
   * Location & Lesion Label.
   * LLM notes (if "Explain More" was clicked).

## 5. DATA SCHEMAS

### 5.1 Real-time Detection Payload (WS from Backend to Frontend)
```json
{
 "event": "DETECTION_FOUND",
 "data": {
  "timestamp_ms": 14500,
  "frame_index": 435,
  "location": "Antrum",
  "lesion": {
   "label": "Ulcer",
   "confidence": 0.92,
   "bbox": [x_min, y_min, x_max, y_max]
  }
 }
}
```

### 5.2 Ignored Memory Schema ([video_id]_metadata.json)
{
 "video_id": "endoscopy_001",
 "ignored_detections": [
  {
   "frame_index": 435,
   "bbox": [100, 150, 300, 350],
   "label": "Ulcer"
  }
 ]
}

## 6. INSTRUCTIONS FOR THE AI AGENT
When generating code for this system, strictly follow these rules:

Decouple UI from Video Processing: Do not attempt to run heavy inference logic in the React frontend. Frontend only draws bounding boxes and handles UI state.

C++ / GStreamer Accuracy: Ensure that buffer extraction in GStreamer (to get frame data for the final report) does not cause memory leaks. Use proper gst_buffer_map and unmap.

Modular Components: Build the React UI using modular components for the VideoPlayer, BoundingBoxOverlay, VoiceControlIndicator, LLMInsightPanel, and SummaryDashboard.

Error Handling: Implement fallback states if the LLM API fails or STT misinterprets voice commands.