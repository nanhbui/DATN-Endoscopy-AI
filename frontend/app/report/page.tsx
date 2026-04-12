'use client';

import { motion as framMotion } from 'framer-motion';
import { CheckCircle2, Download, FileText, MapPin, ScanSearch, Sparkles } from 'lucide-react';
import { useAnalysis } from '@/context/AnalysisContext';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import MuiButton from '@mui/material/Button';

const MotionBox = framMotion(Box);

const SEVERITY_THRESHOLDS = { high: 0.8, medium: 0.6 } as const;

function getSeverity(confidence: number) {
  if (confidence >= SEVERITY_THRESHOLDS.high)
    return { label: 'Nghiêm trọng', color: '#DC2626', bg: 'rgba(220,38,38,0.08)' };
  if (confidence >= SEVERITY_THRESHOLDS.medium)
    return { label: 'Trung bình', color: '#D97706', bg: 'rgba(245,158,11,0.1)' };
  return { label: 'Nhẹ', color: '#2E7D32', bg: 'rgba(46,125,50,0.1)' };
}

export default function ReportPage() {
  const { detections, llmInsight } = useAnalysis();

  if (detections.length === 0) {
    return (
      <Box sx={{ minHeight: 'calc(100vh - 130px)', py: 5, px: { xs: 2, lg: 4 }, backgroundColor: 'background.default', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Box sx={{ textAlign: 'center', maxWidth: 360 }}>
          <ScanSearch size={48} color="#C8D8D6" style={{ marginBottom: 16 }} />
          <Typography variant="h3" sx={{ fontSize: '1.25rem', fontWeight: 700, color: 'text.primary', mb: 1 }}>
            Chưa có dữ liệu báo cáo
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Hoàn tất một phiên phân tích trong Workspace để xem báo cáo tổng kết.
          </Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box sx={{ minHeight: 'calc(100vh - 130px)', py: 5, px: { xs: 2, lg: 4 }, backgroundColor: 'background.default' }}>
      <Container maxWidth="lg" sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>

        {/* ── Header ── */}
        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, alignItems: { md: 'flex-start' }, justifyContent: 'space-between', gap: 2 }}>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1, px: 1.5, py: 0.4, borderRadius: '6px', backgroundColor: 'rgba(0,96,100,0.1)', width: 'fit-content' }}>
              <FileText size={12} color="#006064" />
              <Typography variant="caption" sx={{ fontWeight: 700, color: '#006064', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                Báo cáo tổng kết
              </Typography>
            </Box>
            <Typography variant="h3" sx={{ fontSize: '1.5rem', fontWeight: 800, color: 'text.primary', mb: 0.5 }}>
              Phiên nội soi
            </Typography>
            <Typography variant="body2" color="textSecondary">
              {detections.length} tổn thương được ghi nhận · Nguồn: GStreamer + YOLO pipeline
            </Typography>
          </Box>

          <Dialog>
            <DialogTrigger asChild>
              <MuiButton variant="contained" startIcon={<Download size={18} />} sx={{ borderRadius: '10px', px: 3, py: 1.25, fontWeight: 700, whiteSpace: 'nowrap', flexShrink: 0 }}>
                Xuất báo cáo PDF
              </MuiButton>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Xuất báo cáo PDF</DialogTitle>
                <DialogDescription>Chức năng xuất file sẽ được kết nối sau.</DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <MuiButton variant="outlined" sx={{ borderRadius: '8px' }}>Đóng</MuiButton>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </Box>

        {/* ── Detection Cards ── */}
        <Grid container spacing={2.5}>
          {detections.map((det, idx) => {
            const sev = getSeverity(det.confidence);
            return (
              <Grid size={{ xs: 12, md: 4 }} key={`${det.label}-${idx}`}>
                <MotionBox
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: idx * 0.08 }}
                  sx={{
                    height: '100%',
                    backgroundColor: 'background.paper',
                    borderRadius: '18px',
                    border: '1px solid #E2EAE8',
                    boxShadow: '0 2px 12px rgba(13,27,42,0.06)',
                    overflow: 'hidden',
                    display: 'flex',
                    flexDirection: 'column',
                    transition: 'box-shadow 0.2s, transform 0.2s',
                    '&:hover': { boxShadow: '0 8px 28px rgba(13,27,42,0.1)', transform: 'translateY(-2px)' },
                  }}
                >
                  {/* Thumbnail or gradient placeholder */}
                  <Box sx={{ height: 100, backgroundColor: '#0D1117', position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {det.frame_b64 ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={`data:image/jpeg;base64,${det.frame_b64}`} alt="detection frame" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    ) : (
                      <ScanSearch size={28} color="rgba(255,255,255,0.15)" />
                    )}
                    <Box sx={{ position: 'absolute', top: 10, right: 10, display: 'flex', alignItems: 'center', gap: 0.5, px: 1.25, py: 0.4, borderRadius: '6px', backgroundColor: 'rgba(255,255,255,0.85)', backdropFilter: 'blur(8px)' }}>
                      <Sparkles size={11} color="#006064" />
                      <Typography variant="caption" sx={{ fontWeight: 700, color: '#006064', fontSize: '0.68rem' }}>AI Flag</Typography>
                    </Box>
                    <Box sx={{ position: 'absolute', bottom: 10, left: 10, px: 1.5, py: 0.5, borderRadius: '8px', backgroundColor: sev.bg, border: `1px solid ${sev.color}30` }}>
                      <Typography variant="caption" sx={{ fontWeight: 700, color: sev.color, fontSize: '0.7rem' }}>{sev.label}</Typography>
                    </Box>
                  </Box>

                  {/* Body */}
                  <Box sx={{ p: 2.5, flex: 1, display: 'flex', flexDirection: 'column' }}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 800, color: 'text.primary', mb: 0.5, fontSize: '1rem' }}>
                      {det.label}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.5 }}>
                      <MapPin size={12} color="#006064" />
                      <Typography variant="caption" sx={{ color: '#006064', fontWeight: 600 }}>{det.anatomicalLocation}</Typography>
                    </Box>
                    <Typography variant="caption" sx={{ color: 'text.disabled', fontFamily: 'monospace', mb: 2, display: 'block' }}>
                      {det.timestamp.toFixed(1)}s · conf {(det.confidence * 100).toFixed(0)}%
                    </Typography>

                    {/* LLM insight if available for this detection */}
                    {llmInsight && idx === 0 && (
                      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                        {llmInsight.split('\n').filter(Boolean).slice(0, 3).map((line) => (
                          <Box key={line} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                            <CheckCircle2 size={14} color="#2E7D32" style={{ marginTop: 1, flexShrink: 0 }} />
                            <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.55 }}>
                              {line.replace(/^\*+\s*/, '')}
                            </Typography>
                          </Box>
                        ))}
                      </Box>
                    )}
                  </Box>
                </MotionBox>
              </Grid>
            );
          })}
        </Grid>

        {/* ── Summary Table ── */}
        <Box>
          <Typography variant="h3" sx={{ fontSize: '1.25rem', fontWeight: 700, color: 'text.primary', mb: 2.5 }}>
            Bảng tổng hợp phát hiện
          </Typography>
          <Box sx={{ backgroundColor: 'background.paper', borderRadius: '16px', border: '1px solid #E2EAE8', boxShadow: '0 2px 12px rgba(13,27,42,0.06)', overflow: 'hidden' }}>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr 2fr 1fr', px: 3, py: 1.5, backgroundColor: '#F8FAFB', borderBottom: '1px solid #E2EAE8' }}>
              {['Thời điểm', 'Vị trí giải phẫu', 'Chẩn đoán AI', 'Độ tin cậy'].map((h) => (
                <Typography key={h} variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', letterSpacing: '0.04em', textTransform: 'uppercase' }}>{h}</Typography>
              ))}
            </Box>

            {detections.map((det, idx) => (
              <Box
                key={`row-${idx}`}
                sx={{
                  display: 'grid', gridTemplateColumns: '1fr 1.5fr 2fr 1fr',
                  px: 3, py: 1.875, alignItems: 'center',
                  borderBottom: idx < detections.length - 1 ? '1px solid #F0F4F3' : 'none',
                  '&:hover': { backgroundColor: '#F8FAFB' },
                }}
              >
                <Typography variant="body2" sx={{ fontFamily: 'monospace', color: 'text.secondary', fontWeight: 500 }}>
                  {det.timestamp.toFixed(1)}s
                </Typography>
                <Typography variant="body2" color="textSecondary">{det.anatomicalLocation}</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ScanSearch size={15} color="#006064" />
                  <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>{det.label}</Typography>
                </Box>
                <Box sx={{ display: 'inline-flex', alignItems: 'center', px: 1.25, py: 0.4, borderRadius: '6px', backgroundColor: 'rgba(46,125,50,0.08)', width: 'fit-content' }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, color: '#2E7D32' }}>
                    {(det.confidence * 100).toFixed(0)}%
                  </Typography>
                </Box>
              </Box>
            ))}

            <Box sx={{ px: 3, py: 2, borderTop: '1px solid #E2EAE8', backgroundColor: '#F8FAFB', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="caption" color="textSecondary">
                {detections.length} bản ghi từ pipeline
              </Typography>
            </Box>
          </Box>
        </Box>
      </Container>
    </Box>
  );
}
