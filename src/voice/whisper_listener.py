"""
WhisperListener — Real-time speech recognition using OpenAI Whisper.

Luồng hoạt động:
  Mic → PyAudio chunks → VAD (phát hiện giọng nói) → buffer → Whisper transcribe → callback
"""

import queue
import threading
from typing import Callable, Optional

import numpy as np
from faster_whisper import WhisperModel


class WhisperListener:
    """
    Lắng nghe microphone liên tục, phát hiện khi có người nói,
    transcribe đoạn đó bằng faster-whisper và gọi callback với text kết quả.

    Tham số:
        model_size: kích thước model ("tiny", "base", "small", "medium")
                    "base" là lựa chọn cân bằng tốt cho tiếng Việt realtime
        language:   ngôn ngữ transcribe, mặc định "vi" (tiếng Việt)
    """

    SAMPLE_RATE = 44100        # Hz — dùng native rate của hardware, resample về 16kHz trước khi gửi Whisper
    WHISPER_RATE = 16000       # Hz — Whisper yêu cầu 16kHz
    CHANNELS = 2               # Stereo (hardware không hỗ trợ mono)
    CHUNK_SIZE = 2048          # số sample mỗi lần đọc từ mic
    SILENCE_THRESHOLD = 8000   # ngưỡng RMS để phân biệt im lặng / giọng nói (noise nền ~100)
    SILENCE_DURATION = 1.0     # giây im lặng liên tiếp → kết thúc đoạn nói
    MIN_SPEECH_DURATION = 0.3  # đoạn nói ngắn hơn giá trị này bị bỏ qua

    def __init__(self, model_size: str = "base", language: str = "vi"):
        print(f"[Whisper] Đang tải model '{model_size}'...")
        # float16 trên CUDA, fallback int8 CPU nếu không có GPU
        try:
            import ctranslate2
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        print(f"[Whisper] Chạy trên: {device} ({compute_type})")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.language = language

        self._audio_queue: queue.Queue = queue.Queue()
        self._is_running = False
        self._record_thread: Optional[threading.Thread] = None
        self._transcribe_thread: Optional[threading.Thread] = None

        # Callback được gọi mỗi khi có kết quả transcribe
        self.on_transcription: Optional[Callable[[str], None]] = None

        print(f"[Whisper] Model sẵn sàng — ngôn ngữ: {language}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Bắt đầu lắng nghe mic trong background threads."""
        self._is_running = True
        self._record_thread = threading.Thread(
            target=self._record_loop, daemon=True, name="whisper-record"
        )
        self._transcribe_thread = threading.Thread(
            target=self._transcribe_loop, daemon=True, name="whisper-transcribe"
        )
        self._record_thread.start()
        self._transcribe_thread.start()
        print("[Whisper] Đang lắng nghe mic...")

    def stop(self):
        """Dừng lắng nghe."""
        self._is_running = False
        print("[Whisper] Đã dừng.")

    # ------------------------------------------------------------------
    # Internal — Recording
    # ------------------------------------------------------------------

    def _record_loop(self):
        """
        Thread ghi âm liên tục từ mic.

        Thuật toán VAD đơn giản dựa trên năng lượng (RMS):
        - Khi RMS > SILENCE_THRESHOLD  → đang có giọng nói → buffer
        - Khi RMS <= threshold một lúc → im lặng → gửi buffer sang transcribe
        """
        import pyaudio  # import ở đây để tránh lỗi nếu pyaudio chưa cài

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=self.CHANNELS,
            rate=self.SAMPLE_RATE,
            input=True,
            frames_per_buffer=self.CHUNK_SIZE,
        )

        # Số chunk im lặng liên tiếp để kết thúc đoạn nói
        silence_chunks_threshold = int(
            self.SILENCE_DURATION * self.SAMPLE_RATE / self.CHUNK_SIZE
        )

        speech_buffer = []    # tích lũy các chunk âm thanh của một đoạn nói
        silence_count = 0     # đếm chunk im lặng liên tiếp
        is_speaking = False   # trạng thái hiện tại

        try:
            while self._is_running:
                raw = stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
                chunk = np.frombuffer(raw, dtype=np.int16)
                # Stereo → mono bằng cách lấy trung bình 2 kênh
                if self.CHANNELS == 2:
                    chunk = chunk.reshape(-1, 2).mean(axis=1).astype(np.int16)
                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))

                print(f"[RMS] {rms:.0f}  {'█' * min(int(rms/1000), 30)}", end="\r")

                if rms > self.SILENCE_THRESHOLD:
                    if not is_speaking:
                        print(f"\n[VAD] Bắt đầu nói (RMS={rms:.0f})")
                    is_speaking = True
                    silence_count = 0
                    speech_buffer.append(chunk)

                elif is_speaking:
                    silence_count += 1
                    speech_buffer.append(chunk)

                    if silence_count >= silence_chunks_threshold:
                        audio = np.concatenate(speech_buffer)
                        duration = len(audio) / self.SAMPLE_RATE
                        print(f"[VAD] Kết thúc nói — duration={duration:.2f}s")

                        if duration >= self.MIN_SPEECH_DURATION:
                            print("[VAD] Gửi vào queue transcribe")
                            self._audio_queue.put(audio)

                        speech_buffer = []
                        silence_count = 0
                        is_speaking = False
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

    # ------------------------------------------------------------------
    # Internal — Transcription
    # ------------------------------------------------------------------

    def _transcribe_loop(self):
        """
        Thread nhận audio buffer từ queue, chạy Whisper để lấy text,
        rồi gọi on_transcription callback.
        """
        while self._is_running:
            try:
                audio = self._audio_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            # Resample từ 44100Hz → 16000Hz cho Whisper
            import scipy.signal as sps
            resample_ratio = self.WHISPER_RATE / self.SAMPLE_RATE
            new_len = int(len(audio) * resample_ratio)
            audio = sps.resample(audio, new_len).astype(np.int16)

            # Whisper cần float32 trong khoảng [-1, 1]
            audio_float = audio.astype(np.float32) / 32768.0

            # faster-whisper trả về (segments_generator, info)
            segments, info = self.model.transcribe(
                audio_float,
                language=self.language,
                beam_size=1,                    # greedy decode → nhanh hơn cho lệnh ngắn
                vad_filter=True,                # Silero VAD nội bộ — lọc noise/hallucination
                condition_on_previous_text=False,  # không dùng context cũ → tránh hallucinate
                initial_prompt=(                # bias model về lệnh nội soi
                    "nhầm rồi bỏ qua sai không phải false positive "
                    "giải thích phân tích chi tiết tại sao "
                    "kiểm tra lại xem lại nhìn lại "
                    "đúng rồi xác nhận chuẩn ok"
                ),
            )

            text = " ".join(seg.text for seg in segments).strip()
            print(f"[Whisper] Transcribe xong: '{text}'")
            if text and self.on_transcription:
                self.on_transcription(text)
