"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowRight,
  Brain,
  Gauge,
  MessageSquareText,
  Play,
  ShieldAlert,
  Timer,
  UploadCloud,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAnalysis } from "@/context/AnalysisContext";

const stats = [
  {
    title: "Số ca hôm nay",
    value: "24",
    hint: "+4 so với hôm qua",
    icon: Gauge,
  },
  {
    title: "Tổng bất thường",
    value: "17",
    hint: "3 cần theo dõi sát",
    icon: ShieldAlert,
  },
  {
    title: "Thời gian TB",
    value: "01:32",
    hint: "Mỗi video",
    icon: Timer,
  },
];

const workflowFeatures = [
  {
    title: "Phân tích Real-time",
    description: "Xử lý video tốc độ cao, nhận diện tổn thương ngay lập tức.",
    icon: Activity,
  },
  {
    title: "Smart Ignore & Memory",
    description: "Tự động ghi nhớ các điểm đã bỏ qua, không cảnh báo lặp lại.",
    icon: Brain,
  },
  {
    title: "Trợ lý Y khoa LLM",
    description: "Tự động sinh phân loại y khoa và checklist hành động cho bác sĩ.",
    icon: MessageSquareText,
  },
];

const recentSessions = [
  {
    videoId: "VID-2026-0412",
    dateTime: "02/04/2026 08:45",
    findings: 3,
    status: "Hoàn tất",
  },
  {
    videoId: "VID-2026-0413",
    dateTime: "02/04/2026 09:20",
    findings: 1,
    status: "Tạm dừng",
  },
  {
    videoId: "VID-2026-0414",
    dateTime: "02/04/2026 10:10",
    findings: 2,
    status: "Hoàn tất",
  },
  {
    videoId: "VID-2026-0415",
    dateTime: "02/04/2026 11:05",
    findings: 4,
    status: "Hoàn tất",
  },
];

export default function Home() {
  const { isPlaying, startMockAnalysis } = useAnalysis();

  return (
    <div className="relative min-h-[calc(100vh-130px)] overflow-hidden px-5 py-10 lg:px-8">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_15%_10%,rgba(20,184,166,0.18),transparent_38%),radial-gradient(circle_at_85%_0%,rgba(16,185,129,0.13),transparent_30%)]" />

      <div className="mx-auto w-full max-w-[1440px] space-y-8">
        <motion.section
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="glass-card relative overflow-hidden rounded-3xl p-6 lg:p-8"
        >
          <div className="pointer-events-none absolute -top-24 left-1/2 h-64 w-64 -translate-x-1/2 rounded-full bg-teal-900/20 blur-3xl" />

          <div className="relative max-w-3xl">
            <Badge className="mb-4 border-teal-400/30 bg-teal-500/15 text-teal-200" variant="outline">
              Frontend-First Mock System
            </Badge>
            <h1 className="text-balance text-3xl font-bold leading-snug tracking-normal bg-gradient-to-r from-zinc-100 to-zinc-500 bg-clip-text text-transparent lg:text-5xl">
              Hệ thống Phân tích Nội soi Thông minh
            </h1>
            <p className="mt-3 max-w-2xl leading-relaxed text-zinc-400">
              Bộ khung UI/UX cho phòng khám: mô phỏng luồng AI phát hiện tổn thương, tạm dừng video,
              và sinh giải thích LLM theo thời gian thực.
            </p>
          </div>

          <div className="mt-7 flex flex-wrap gap-3">
            <Button
              size="lg"
              className="bg-teal-500 text-zinc-950 transition-colors hover:bg-teal-400"
              onClick={startMockAnalysis}
            >
              <Play className="mr-2" />
              {isPlaying ? "Đang phân tích..." : "Bắt đầu phân tích"}
            </Button>
            <Button asChild size="lg" variant="outline" className="border-white/20 bg-zinc-900/50">
              <Link href="/workspace">
                <UploadCloud className="mr-2" />
                Tải video lên
              </Link>
            </Button>
            <Button asChild size="lg" variant="ghost">
              <Link href="/report">
                Xem báo cáo <ArrowRight className="ml-2" />
              </Link>
            </Button>
          </div>
        </motion.section>

        <section className="grid gap-4 md:grid-cols-3">
          {stats.map((item, idx) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: idx * 0.1 }}
            >
              <Card className="glass-card rounded-2xl">
                <CardHeader>
                  <CardDescription className="text-zinc-300">{item.title}</CardDescription>
                  <CardTitle className="flex items-center justify-between text-zinc-100">
                    <span className="text-4xl font-extrabold tracking-tight">{item.value}</span>
                    <span className="rounded-xl border border-white/10 bg-zinc-900/60 p-2 text-teal-300">
                      <item.icon className="size-5" />
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-zinc-400">{item.hint}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </section>

        <section className="space-y-4">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-zinc-100">Luồng tính năng nổi bật</h2>
            <p className="mt-1 text-sm text-zinc-400">Ba bước chính trong quy trình AI phân tích nội soi.</p>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            {workflowFeatures.map((feature, idx) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: idx * 0.08 }}
              >
                <Card className="glass-card rounded-2xl">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-3 text-zinc-100">
                      <span className="rounded-xl border border-white/10 bg-zinc-900/60 p-2 text-teal-300">
                        <feature.icon className="size-5" />
                      </span>
                      {feature.title}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm leading-relaxed text-zinc-300">{feature.description}</p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </section>

        <section className="space-y-4">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-zinc-100">Các ca phân tích gần đây</h2>
            <p className="mt-1 text-sm text-zinc-400">Tổng hợp nhanh các video mới nhất và trạng thái xử lý.</p>
          </div>

          <Card className="glass-card rounded-2xl">
            <CardContent className="pt-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID Video</TableHead>
                    <TableHead>Ngày giờ</TableHead>
                    <TableHead>Tổn thương phát hiện</TableHead>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead className="text-right">Hành động</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentSessions.map((session) => {
                    const isDone = session.status === "Hoàn tất";

                    return (
                      <TableRow key={session.videoId}>
                        <TableCell className="font-medium text-zinc-100">{session.videoId}</TableCell>
                        <TableCell className="text-zinc-300">{session.dateTime}</TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className="border-teal-400/30 bg-teal-500/15 text-teal-200"
                          >
                            {session.findings} tổn thương
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={
                              isDone
                                ? "border-emerald-400/30 bg-emerald-500/15 text-emerald-200"
                                : "border-amber-400/30 bg-amber-500/15 text-amber-100"
                            }
                          >
                            {session.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" className="border border-white/10 bg-zinc-900/40 hover:bg-zinc-800/70">
                            Xem chi tiết
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
