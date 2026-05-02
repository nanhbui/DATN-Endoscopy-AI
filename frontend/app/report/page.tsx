'use client';

import { useState } from 'react';
import { motion as framMotion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AlertTriangle, CheckCircle2, CircleX, Clock, Download, FileText, MapPin, ScanSearch, Sparkles, Trash2, X, Zap } from 'lucide-react';
import { useAnalysis, type Detection, type DetectionStatus } from '@/context/AnalysisContext';

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
import MuiDialog from '@mui/material/Dialog';
import MuiDialogContent from '@mui/material/DialogContent';
import Chip from '@mui/material/Chip';
import { PipelineMetricsSection } from '@/components/pipeline-metrics-section';

const MotionBox = framMotion(Box);

const SEVERITY_THRESHOLDS = { high: 0.8, medium: 0.6 } as const;

function getSeverity(confidence: number) {
  if (confidence >= SEVERITY_THRESHOLDS.high)
    return { label: 'Nghiêm trọng', color: '#DC2626', bg: 'rgba(220,38,38,0.1)', light: 'rgba(220,38,38,0.06)' };
  if (confidence >= SEVERITY_THRESHOLDS.medium)
    return { label: 'Trung bình', color: '#D97706', bg: 'rgba(245,158,11,0.12)', light: 'rgba(245,158,11,0.06)' };
  return { label: 'Nhẹ', color: '#059669', bg: 'rgba(5,150,105,0.1)', light: 'rgba(5,150,105,0.05)' };
}

function fmtTs(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m} phút ${String(s).padStart(2, '0')} giây` : `${s} giây`;
}

const STATUS_CFG: Record<DetectionStatus, { label: string; color: string; bg: string; icon: React.ReactNode }> = {
  confirmed: { label: 'Xác nhận',     color: '#059669', bg: 'rgba(5,150,105,0.1)',   icon: <CheckCircle2 size={11} /> },
  analyzed:  { label: 'Đã phân tích', color: '#0277BD', bg: 'rgba(2,119,189,0.1)',   icon: <Sparkles size={11} /> },
  ignored:   { label: 'Bỏ qua',       color: '#9AA5B1', bg: 'rgba(154,165,177,0.1)', icon: <CircleX size={11} /> },
  detected:  { label: 'Phát hiện',    color: '#D97706', bg: 'rgba(245,158,11,0.1)',   icon: <AlertTriangle size={11} /> },
};

function ConfidenceRing({ pct, color }: { pct: number; color: string }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  return (
    <Box sx={{ position: 'relative', width: 72, height: 72, flexShrink: 0 }}>
      <svg width="72" height="72" style={{ transform: 'rotate(-90deg)' }}>
        <circle cx="36" cy="36" r={r} fill="none" stroke="rgba(0,0,0,0.07)" strokeWidth="5" />
        <circle
          cx="36" cy="36" r={r} fill="none"
          stroke={color} strokeWidth="5"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 0.6s ease' }}
        />
      </svg>
      <Box sx={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <Typography sx={{ fontSize: '1rem', fontWeight: 800, color, lineHeight: 1 }}>{pct.toFixed(0)}</Typography>
        <Typography sx={{ fontSize: '0.58rem', fontWeight: 600, color: 'text.disabled', letterSpacing: '0.04em' }}>%</Typography>
      </Box>
    </Box>
  );
}

function DetectionModal({
  det,
  onClose,
  onDelete,
}: {
  det: Detection;
  onClose: () => void;
  onDelete: () => void;
}) {
  const sev = getSeverity(det.confidence);
  const pct = det.confidence * 100;

  return (
    <MuiDialog
      open
      onClose={onClose}
      maxWidth={false}
      fullWidth
      slotProps={{ paper: { sx: { borderRadius: '24px', overflow: 'hidden', width: '90vw', maxWidth: 1080, maxHeight: '85vh' } } }}
    >
      <MuiDialogContent sx={{ p: 0 }}>
        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, minHeight: 520 }}>

          {/* ── Left: frame image ─────────────────────────────────────────── */}
          <Box sx={{ flex: '0 0 52%', backgroundColor: '#0A0F16', position: 'relative', minHeight: { xs: 240, md: 'auto' } }}>
            {det.frame_b64 ? (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`data:image/jpeg;base64,${det.frame_b64}`}
                  alt="detection frame"
                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                />
                {/* Bounding box */}
                <Box sx={{
                  position: 'absolute',
                  left: `${det.bbox.x}%`, top: `${det.bbox.y}%`,
                  width: `${det.bbox.width}%`, height: `${det.bbox.height}%`,
                  border: '2px solid #F59E0B',
                  borderRadius: '4px',
                  boxShadow: '0 0 0 1px rgba(0,0,0,0.6), inset 0 0 0 1px rgba(245,158,11,0.3)',
                  pointerEvents: 'none',
                }} />
                {/* Bbox label */}
                <Box sx={{
                  position: 'absolute',
                  left: `${det.bbox.x}%`, top: `calc(${det.bbox.y}% - 28px)`,
                  display: 'flex', alignItems: 'center', gap: 0.5,
                  px: 1, py: 0.35, borderRadius: '6px',
                  backgroundColor: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)',
                  border: '1px solid rgba(245,158,11,0.4)',
                  pointerEvents: 'none',
                }}>
                  <Zap size={10} color="#F59E0B" />
                  <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#FCD34D', whiteSpace: 'nowrap' }}>
                    {det.label}
                  </Typography>
                </Box>
              </>
            ) : (
              /* Empty state — no frame captured */
              <Box sx={{
                height: '100%', minHeight: 280, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 1.5,
                background: 'radial-gradient(ellipse at 50% 40%, rgba(0,96,100,0.12) 0%, transparent 70%)',
              }}>
                <Box sx={{ width: 72, height: 72, borderRadius: '50%', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <ScanSearch size={32} color="rgba(255,255,255,0.2)" />
                </Box>
                <Typography sx={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.25)', fontWeight: 500 }}>
                  Không có khung hình
                </Typography>
              </Box>
            )}

            {/* Bottom gradient + severity badge */}
            <Box sx={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 80, background: 'linear-gradient(to top, rgba(0,0,0,0.75) 0%, transparent 100%)', pointerEvents: 'none' }} />
            <Box sx={{ position: 'absolute', bottom: 14, left: 14, display: 'flex', alignItems: 'center', gap: 0.75, px: 1.5, py: 0.6, borderRadius: '8px', backgroundColor: sev.bg, border: `1px solid ${sev.color}35`, backdropFilter: 'blur(10px)' }}>
              <Box sx={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: sev.color }} />
              <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: sev.color }}>{sev.label}</Typography>
            </Box>

            {/* AI badge */}
            <Box sx={{ position: 'absolute', top: 14, left: 14, display: 'flex', alignItems: 'center', gap: 0.5, px: 1.25, py: 0.45, borderRadius: '6px', backgroundColor: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(10px)', border: '1px solid rgba(255,255,255,0.1)' }}>
              <Sparkles size={10} color="#00BCD4" />
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: '#80DEEA', letterSpacing: '0.06em', textTransform: 'uppercase' }}>AI Detection</Typography>
            </Box>
          </Box>

          {/* ── Right: details panel ──────────────────────────────────────── */}
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: 'background.paper' }}>

            {/* Header strip */}
            <Box sx={{ px: 3, pt: 2.5, pb: 2, borderBottom: '1px solid #EEF2F0', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, color: '#006064', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                    Kết quả phát hiện
                  </Typography>
                  {(() => { const sc = STATUS_CFG[det.status ?? 'detected']; return (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4, px: 1, py: 0.25, borderRadius: '6px', backgroundColor: sc.bg }}>
                      <Box sx={{ color: sc.color, display: 'flex' }}>{sc.icon}</Box>
                      <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: sc.color }}>{sc.label}</Typography>
                    </Box>
                  ); })()}
                </Box>
                <Typography sx={{ fontSize: '1.3rem', fontWeight: 800, color: 'text.primary', lineHeight: 1.25, wordBreak: 'break-word' }}>
                  {det.label}
                </Typography>
              </Box>
              <Box component="button" onClick={onClose} sx={{ background: 'none', border: 'none', cursor: 'pointer', p: 0.75, borderRadius: '8px', flexShrink: 0, transition: 'background 0.15s', '&:hover': { backgroundColor: '#F0F4F3' } }}>
                <X size={17} color="#9AA5B1" />
              </Box>
            </Box>

            {/* Scrollable body */}
            <Box sx={{ flex: 1, overflowY: 'auto', px: 3, py: 2.5, display: 'flex', flexDirection: 'column', gap: 2.5 }}>

              {/* Meta tags row */}
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                <Chip
                  icon={<MapPin size={12} />}
                  label={det.anatomicalLocation}
                  size="small"
                  sx={{ backgroundColor: 'rgba(0,96,100,0.08)', color: '#006064', fontWeight: 600, fontSize: '0.78rem', '& .MuiChip-icon': { color: '#006064' }, borderRadius: '8px', height: 28 }}
                />
                <Chip
                  icon={<Clock size={12} />}
                  label={fmtTs(det.timestamp)}
                  size="small"
                  sx={{ backgroundColor: 'rgba(0,0,0,0.04)', color: 'text.secondary', fontWeight: 500, fontSize: '0.78rem', fontFamily: 'monospace', '& .MuiChip-icon': { color: 'text.disabled' }, borderRadius: '8px', height: 28 }}
                />
              </Box>

              {/* Confidence section */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5, p: 2, borderRadius: '14px', backgroundColor: sev.light, border: `1px solid ${sev.color}18` }}>
                <ConfidenceRing pct={pct} color={sev.color} />
                <Box>
                  <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em', mb: 0.5 }}>
                    Độ tin cậy
                  </Typography>
                  <Typography sx={{ fontSize: '0.92rem', fontWeight: 700, color: sev.color }}>
                    {pct.toFixed(0)}% — {sev.label}
                  </Typography>
                  <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled', mt: 0.25 }}>
                    Phát hiện tại {fmtTs(det.timestamp)}
                  </Typography>
                </Box>
              </Box>

              {/* LLM Insight */}
              {det.llmInsight ? (
                <Box>
                  <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.07em', mb: 1.25 }}>
                    Phân tích AI
                  </Typography>
                  <Box sx={{
                    fontSize: '0.875rem', lineHeight: 1.75, color: 'text.primary',
                    '& p': { margin: '0 0 8px' },
                    '& p:last-child': { marginBottom: 0 },
                    '& strong': { fontWeight: 700, color: '#004D40' },
                    '& p:has(strong:first-of-type)': {
                      borderLeft: '3px solid #00897B',
                      pl: 1.25, mb: 0.75,
                      backgroundColor: 'rgba(0,137,123,0.04)',
                      borderRadius: '0 6px 6px 0',
                    },
                    '& ul, & ol': { pl: '1.1rem', margin: '4px 0 8px' },
                    '& li': { mb: '3px', listStyleType: 'none', pl: 0 },
                    '& li input[type="checkbox"]': { mr: '7px', accentColor: '#006064', width: 13, height: 13, verticalAlign: 'middle' },
                    '& h1, & h2, & h3': { fontSize: '0.88rem', fontWeight: 700, color: '#004D40', margin: '8px 0 3px' },
                    '& code': { backgroundColor: 'rgba(0,96,100,0.08)', borderRadius: '4px', padding: '1px 5px', fontSize: '0.8rem' },
                  }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{det.llmInsight}</ReactMarkdown>
                  </Box>
                </Box>
              ) : (
                <Box sx={{ py: 2, textAlign: 'center', color: 'text.disabled' }}>
                  <Typography sx={{ fontSize: '0.82rem' }}>Chưa có phân tích LLM cho tổn thương này</Typography>
                </Box>
              )}
            </Box>

            {/* Footer actions */}
            <Box sx={{ px: 3, py: 2, borderTop: '1px solid #EEF2F0', display: 'flex', gap: 1.5 }}>
              <MuiButton
                variant="outlined"
                startIcon={<Trash2 size={14} />}
                onClick={onDelete}
                sx={{ borderRadius: '10px', fontWeight: 700, borderColor: 'rgba(220,38,38,0.3)', color: '#DC2626', px: 2.5, '&:hover': { backgroundColor: 'rgba(220,38,38,0.06)', borderColor: '#DC2626' } }}
              >
                Xóa
              </MuiButton>
              <MuiButton
                fullWidth
                variant="contained"
                onClick={onClose}
                sx={{ borderRadius: '10px', fontWeight: 700, backgroundColor: '#006064', '&:hover': { backgroundColor: '#004D51' } }}
              >
                Đóng
              </MuiButton>
            </Box>
          </Box>
        </Box>
      </MuiDialogContent>
    </MuiDialog>
  );
}

export default function ReportPage() {
  const { detections, removeDetection } = useAnalysis();
  const [selected, setSelected] = useState<Detection | null>(null);

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
            const sc = STATUS_CFG[det.status ?? 'detected'];
            return (
              <Grid size={{ xs: 12, md: 4 }} key={`${det.label}-${idx}`}>
                <MotionBox
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: idx * 0.08 }}
                  onClick={() => setSelected(det)}
                  sx={{
                    height: '100%',
                    backgroundColor: 'background.paper',
                    borderRadius: '18px',
                    border: '1px solid #E2EAE8',
                    boxShadow: '0 2px 12px rgba(13,27,42,0.06)',
                    overflow: 'hidden',
                    display: 'flex',
                    flexDirection: 'column',
                    cursor: 'pointer',
                    opacity: det.status === 'ignored' ? 0.72 : 1,
                    transition: 'box-shadow 0.2s, transform 0.2s, opacity 0.2s',
                    '&:hover': { boxShadow: '0 8px 28px rgba(13,27,42,0.1)', transform: 'translateY(-2px)', opacity: 1 },
                  }}
                >
                  {/* Thumbnail */}
                  <Box sx={{ height: 110, backgroundColor: '#0D1117', position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {det.frame_b64 ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={`data:image/jpeg;base64,${det.frame_b64}`} alt="detection frame" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    ) : (
                      <ScanSearch size={28} color="rgba(255,255,255,0.15)" />
                    )}
                    {/* Status badge (top-right) */}
                    <Box sx={{ position: 'absolute', top: 9, right: 9, display: 'flex', alignItems: 'center', gap: 0.4, px: 1.1, py: 0.35, borderRadius: '6px', backgroundColor: sc.bg, backdropFilter: 'blur(8px)', border: `1px solid ${sc.color}25` }}>
                      <Box sx={{ color: sc.color, display: 'flex' }}>{sc.icon}</Box>
                      <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: sc.color }}>{sc.label}</Typography>
                    </Box>
                    {/* Severity (bottom-left) */}
                    <Box sx={{ position: 'absolute', bottom: 9, left: 9, px: 1.25, py: 0.4, borderRadius: '7px', backgroundColor: sev.bg, border: `1px solid ${sev.color}30`, backdropFilter: 'blur(8px)' }}>
                      <Typography sx={{ fontSize: '0.67rem', fontWeight: 700, color: sev.color }}>{sev.label}</Typography>
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
                      {fmtTs(det.timestamp)} · {(det.confidence * 100).toFixed(0)}%
                    </Typography>

                    {det.llmInsight ? (
                      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                        {det.llmInsight.split('\n').filter(Boolean).slice(0, 2).map((line) => (
                          <Box key={line} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                            <CheckCircle2 size={13} color="#2E7D32" style={{ marginTop: 1, flexShrink: 0 }} />
                            <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.55 }}>
                              {line.replace(/^\*+\s*/, '')}
                            </Typography>
                          </Box>
                        ))}
                        {det.llmInsight.split('\n').filter(Boolean).length > 2 && (
                          <Typography variant="caption" sx={{ color: '#006064', fontWeight: 600 }}>Xem thêm…</Typography>
                        )}
                      </Box>
                    ) : det.status === 'ignored' ? (
                      <Typography variant="caption" sx={{ color: 'text.disabled', fontStyle: 'italic' }}>Đã bỏ qua — không có phân tích</Typography>
                    ) : null}
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
            <Box sx={{ display: 'grid', gridTemplateColumns: '1.2fr 1.4fr 2fr 0.9fr 1fr', px: 3, py: 1.5, backgroundColor: '#F8FAFB', borderBottom: '1px solid #E2EAE8' }}>
              {['Thời điểm', 'Vị trí', 'Chẩn đoán AI', 'Độ tin cậy', 'Trạng thái'].map((h) => (
                <Typography key={h} variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', letterSpacing: '0.04em', textTransform: 'uppercase' }}>{h}</Typography>
              ))}
            </Box>

            {detections.map((det, idx) => {
              const sc = STATUS_CFG[det.status ?? 'detected'];
              return (
                <Box
                  key={`row-${idx}`}
                  onClick={() => setSelected(det)}
                  sx={{
                    display: 'grid', gridTemplateColumns: '1.2fr 1.4fr 2fr 0.9fr 1fr',
                    px: 3, py: 1.75, alignItems: 'center',
                    borderBottom: idx < detections.length - 1 ? '1px solid #F0F4F3' : 'none',
                    cursor: 'pointer',
                    opacity: det.status === 'ignored' ? 0.65 : 1,
                    '&:hover': { backgroundColor: '#F0F9F9', opacity: 1 },
                  }}
                >
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', color: 'text.secondary', fontWeight: 500, fontSize: '0.82rem' }}>
                    {fmtTs(det.timestamp)}
                  </Typography>
                  <Typography variant="body2" color="textSecondary" sx={{ fontSize: '0.88rem' }}>{det.anatomicalLocation}</Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <ScanSearch size={14} color="#006064" />
                    <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary', fontSize: '0.9rem' }}>{det.label}</Typography>
                  </Box>
                  <Typography variant="caption" sx={{ fontWeight: 700, color: '#2E7D32', fontFamily: 'monospace' }}>
                    {(det.confidence * 100).toFixed(0)}%
                  </Typography>
                  <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, px: 1, py: 0.3, borderRadius: '6px', backgroundColor: sc.bg, width: 'fit-content' }}>
                    <Box sx={{ color: sc.color, display: 'flex' }}>{sc.icon}</Box>
                    <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: sc.color }}>{sc.label}</Typography>
                  </Box>
                </Box>
              );
            })}

            <Box sx={{ px: 3, py: 2, borderTop: '1px solid #E2EAE8', backgroundColor: '#F8FAFB', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="caption" color="textSecondary">
                {detections.length} bản ghi từ pipeline
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* ── GstShark Metrics ── */}
        <PipelineMetricsSection />

      </Container>

      {/* ── Detection Detail Modal ── */}
      {selected && (
        <DetectionModal
          det={selected}
          onClose={() => setSelected(null)}
          onDelete={() => {
            removeDetection(selected.timestamp);
            setSelected(null);
          }}
        />
      )}
    </Box>
  );
}
