"use client";

import { motion } from "framer-motion";
import { AlertTriangle, Loader2, Mic, Pause, Play, Square, Waves } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAnalysis } from "@/context/AnalysisContext";

export default function Workspace() {
  const {
    isPlaying,
    currentDetection,
    isListeningVoice,
    llmInsight,
    startMockAnalysis,
    ignoreDetection,
    explainMore,
    setIsPlaying,
  } = useAnalysis();

  const status = isPlaying
    ? {
        text: "Đang chạy",
        style: "border-emerald-400/40 bg-emerald-500/15 text-emerald-200",
      }
    : currentDetection
      ? {
          text: "Tạm dừng do AI phát hiện",
          style: "border-amber-400/40 bg-amber-500/15 text-amber-100",
        }
      : isListeningVoice
        ? {
            text: "Đang lắng nghe giọng nói",
            style: "border-sky-400/40 bg-sky-500/15 text-sky-100",
          }
        : {
            text: "Chờ khởi động",
            style: "border-zinc-500/40 bg-zinc-500/15 text-zinc-200",
          };

  return (
    <div className="min-h-[calc(100vh-130px)] px-5 py-8 lg:px-8">
      <div className="mx-auto grid w-full max-w-[1440px] gap-4 lg:grid-cols-[7fr_3fr]">
        <Card className="glass-card rounded-3xl border-white/10 p-0">
          <CardHeader className="border-b border-white/10">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-zinc-100">Luồng video nội soi</CardTitle>
                <CardDescription className="text-zinc-400">
                  Overlay bbox được cập nhật khi AI phát hiện tổn thương
                </CardDescription>
              </div>
              <Badge className={status.style} variant="outline">
                {status.text}
              </Badge>
            </div>
          </CardHeader>

          <CardContent className="p-4 lg:p-5">
            <div className="relative aspect-video w-full overflow-hidden rounded-2xl border border-white/10 bg-black">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_20%,rgba(39,39,42,0.6),rgba(0,0,0,0.95))]" />
              <div className="absolute inset-0 flex items-center justify-center text-zinc-500">
                <div className="text-center">
                  <Waves className="mx-auto mb-2 size-8" />
                  <p>Luồng camera nội soi (mock)</p>
                </div>
              </div>

              {currentDetection ? (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="absolute border-2 border-amber-300 bg-amber-300/15"
                  style={{
                    left: `${currentDetection.bbox.x}%`,
                    top: `${currentDetection.bbox.y}%`,
                    width: `${currentDetection.bbox.width}%`,
                    height: `${currentDetection.bbox.height}%`,
                  }}
                >
                  <div className="absolute -top-8 left-0 rounded-md border border-amber-300/30 bg-zinc-950/95 px-2 py-1 text-xs text-amber-200">
                    {currentDetection.label} · {(currentDetection.confidence * 100).toFixed(0)}%
                  </div>
                </motion.div>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card rounded-3xl border-white/10">
          <CardHeader className="border-b border-white/10">
            <CardTitle className="text-zinc-100">Điều khiển & LLM</CardTitle>
            <CardDescription className="text-zinc-400">
              Tương tác với trợ lý AI sau khi hệ thống tự động tạm dừng.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4 p-5">
            <div className="grid grid-cols-2 gap-2">
              <Button
                onClick={() => {
                  if (isPlaying) {
                    setIsPlaying(false);
                  } else {
                    startMockAnalysis();
                  }
                }}
                className="bg-teal-500 text-zinc-950 hover:bg-teal-400"
              >
                {isPlaying ? <Pause className="mr-2" /> : <Play className="mr-2" />}
                {isPlaying ? "Tạm dừng" : "Chạy"}
              </Button>
              <Button
                variant="outline"
                className="border-white/20 bg-zinc-900/40"
                onClick={() => setIsPlaying(false)}
              >
                <Square className="mr-2" /> Dừng
              </Button>
            </div>

            {currentDetection ? (
              <div className="rounded-2xl border border-amber-400/35 bg-amber-500/12 p-4">
                <div className="mb-2 flex items-center gap-2 text-amber-100">
                  <AlertTriangle className="size-4" />
                  <p className="text-sm font-medium">AI phát hiện bất thường</p>
                </div>
                <p className="text-sm text-amber-50/90">
                  Nhãn: {currentDetection.label} | Độ tin cậy {(currentDetection.confidence * 100).toFixed(0)}%
                </p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <Button
                    variant="outline"
                    className="border-white/20 bg-zinc-900/35"
                    onClick={ignoreDetection}
                  >
                    Bỏ qua
                  </Button>
                  <Button onClick={explainMore} className="bg-teal-500 text-zinc-950 hover:bg-teal-400">
                    Giải thích thêm
                  </Button>
                </div>
              </div>
            ) : null}

            <div className="rounded-2xl border border-white/10 bg-zinc-900/55 p-4">
              <div className="mb-2 flex items-center gap-2 text-sm text-zinc-300">
                <Mic className="size-4 text-teal-300" />
                LLM Insight
              </div>

              {isListeningVoice && !llmInsight ? (
                <div className="flex items-center gap-2 text-sm text-sky-200">
                  <Loader2 className="size-4 animate-spin" /> Đang tải phản hồi...
                </div>
              ) : null}

              {llmInsight ? (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="max-h-64 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-zinc-100"
                >
                  {llmInsight}
                </motion.p>
              ) : null}

              {!llmInsight && !isListeningVoice ? (
                <p className="text-sm text-zinc-500">Chưa có nội dung phân tích.</p>
              ) : null}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
