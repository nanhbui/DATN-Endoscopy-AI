"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Download, MapPinned, ScanSearch } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAnalysis } from "@/context/AnalysisContext";

const reportItems = [
  {
    id: 1,
    label: "Viêm loét",
    location: "Dạ dày - thân vị",
    coordinate: "x:29 y:34 w:23 h:19",
    checklist: [
      "Bờ viền tổn thương không đều",
      "Vùng sung huyết xung quanh",
      "Khuyến nghị đánh giá H. pylori",
    ],
  },
  {
    id: 2,
    label: "Xung huyết niêm mạc",
    location: "Hang vị",
    coordinate: "x:40 y:42 w:20 h:16",
    checklist: [
      "Mức độ xung huyết trung bình",
      "Cần đối chiếu bệnh sử thuốc NSAID",
      "Hẹn nội soi tái khám nếu triệu chứng tồn tại",
    ],
  },
  {
    id: 3,
    label: "Nốt trợt niêm mạc",
    location: "Hành tá tràng",
    coordinate: "x:58 y:36 w:18 h:14",
    checklist: [
      "Tổn thương nông, ranh giới rõ",
      "Theo dõi tiến triển sau 2-4 tuần",
      "Cân nhắc tối ưu phác đồ bảo vệ niêm mạc",
    ],
  },
];

export default function ReportPage() {
  const { detections } = useAnalysis();

  return (
    <div className="min-h-[calc(100vh-130px)] px-5 py-8 lg:px-8">
      <div className="mx-auto w-full max-w-[1440px] space-y-5">
        <Card className="glass-card rounded-3xl">
          <CardHeader className="flex flex-col gap-3 border-b border-white/10 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <Badge variant="outline" className="mb-2 border-teal-400/30 bg-teal-500/15 text-teal-200">
                Báo cáo tổng kết
              </Badge>
              <CardTitle className="text-zinc-100">Phiên nội soi hôm nay</CardTitle>
              <CardDescription className="text-zinc-400">
                Tổng hợp hình ảnh tổn thương, tọa độ và checklist gợi ý từ LLM.
              </CardDescription>
            </div>

            <Dialog>
              <DialogTrigger asChild>
                <Button className="bg-teal-500 text-zinc-950 hover:bg-teal-400">
                  <Download className="mr-2" /> Xuất báo cáo PDF
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Xuất báo cáo PDF</DialogTitle>
                  <DialogDescription>
                    Chức năng xuất file đang ở chế độ giao diện mẫu. Logic tạo PDF sẽ được kết nối API sau.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button variant="outline" className="border-white/20 bg-zinc-900/50">
                    Đóng
                  </Button>
                  <Button className="bg-teal-500 text-zinc-950 hover:bg-teal-400">Xác nhận</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </CardHeader>
        </Card>

        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 lg:auto-rows-max">
          {reportItems.map((item, idx) => (
            <motion.article
              key={item.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: idx * 0.08 }}
              className={`glass-card rounded-2xl p-4 ${idx === 0 ? "md:col-span-2 lg:col-span-2 lg:row-span-2" : ""}`}
            >
              <div className="mb-3 h-24 rounded-xl border border-white/10 bg-[radial-gradient(circle_at_30%_30%,rgba(161,161,170,0.2),rgba(24,24,27,0.9))] lg:h-28" />
              <div className="mb-2 flex items-center justify-between">
                <p className="font-semibold text-zinc-100">{item.label}</p>
                <Badge variant="outline" className="border-amber-400/30 bg-amber-500/15 text-amber-100">
                  AI Flag
                </Badge>
              </div>
              <p className="text-xs text-zinc-300">{item.location}</p>
              <p className="mt-1 text-xs text-zinc-400">{item.coordinate}</p>
              <ul className="mt-3 space-y-1">
                {item.checklist.map((point) => (
                  <li key={point} className="flex items-start gap-2 text-xs text-zinc-200">
                    <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-teal-300" />
                    {point}
                  </li>
                ))}
              </ul>
            </motion.article>
          ))}
        </section>

        <Card className="glass-card rounded-3xl">
          <CardHeader>
            <CardTitle className="text-zinc-100">Bảng tổng hợp phát hiện</CardTitle>
            <CardDescription className="text-zinc-400">
              Dữ liệu đến từ AnalysisContext (mock), sẵn sàng thay bằng API thật.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Thời điểm</TableHead>
                  <TableHead>Vị trí giải phẫu</TableHead>
                  <TableHead>Chẩn đoán AI</TableHead>
                  <TableHead>Độ tin cậy</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(detections.length ? detections : reportItems).map((item, idx) => {
                  const hasRuntimeData = "timestamp" in item;
                  return (
                    <TableRow key={`${item.label}-${idx}`}>
                      <TableCell className="text-zinc-300">
                        {hasRuntimeData ? `${item.timestamp.toFixed(1)}s` : `Frame ${idx + 1}`}
                      </TableCell>
                      <TableCell className="text-zinc-200">
                        {hasRuntimeData ? item.anatomicalLocation : item.location}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2 text-zinc-100">
                          <ScanSearch className="size-4 text-teal-300" />
                          {item.label}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2 text-zinc-200">
                          <MapPinned className="size-4 text-zinc-400" />
                          {hasRuntimeData ? `${(item.confidence * 100).toFixed(0)}%` : "91%"}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
