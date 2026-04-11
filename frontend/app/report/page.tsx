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

const reportItems = [
  {
    id: 1,
    label: 'Viêm loét',
    location: 'Dạ dày - thân vị',
    coordinate: 'x:29 y:34 w:23 h:19',
    severity: 'high',
    checklist: [
      'Bờ viền tổn thương không đều',
      'Vùng sung huyết xung quanh',
      'Khuyến nghị đánh giá H. pylori',
    ],
    gradient: 'linear-gradient(135deg, rgba(0,64,68,0.18) 0%, rgba(0,131,143,0.28) 100%)',
    accentColor: '#006064',
    accentBg: 'rgba(0,96,100,0.08)',
  },
  {
    id: 2,
    label: 'Xung huyết niêm mạc',
    location: 'Hang vị',
    coordinate: 'x:40 y:42 w:20 h:16',
    severity: 'medium',
    checklist: [
      'Mức độ xung huyết trung bình',
      'Cần đối chiếu bệnh sử thuốc NSAID',
      'Hẹn nội soi tái khám nếu triệu chứng tồn tại',
    ],
    gradient: 'linear-gradient(135deg, rgba(2,87,137,0.15) 0%, rgba(2,136,209,0.25) 100%)',
    accentColor: '#0277BD',
    accentBg: 'rgba(2,119,189,0.08)',
  },
  {
    id: 3,
    label: 'Nốt trợt niêm mạc',
    location: 'Hành tá tràng',
    coordinate: 'x:58 y:36 w:18 h:14',
    severity: 'low',
    checklist: [
      'Tổn thương nông, ranh giới rõ',
      'Theo dõi tiến triển sau 2–4 tuần',
      'Cân nhắc tối ưu phác đồ bảo vệ niêm mạc',
    ],
    gradient: 'linear-gradient(135deg, rgba(120,53,15,0.12) 0%, rgba(245,158,11,0.22) 100%)',
    accentColor: '#D97706',
    accentBg: 'rgba(245,158,11,0.08)',
  },
];

const severityMap: Record<string, { label: string; color: string; bg: string }> = {
  high: { label: 'Nghiêm trọng', color: '#DC2626', bg: 'rgba(220,38,38,0.08)' },
  medium: { label: 'Trung bình', color: '#D97706', bg: 'rgba(245,158,11,0.1)' },
  low: { label: 'Nhẹ', color: '#2E7D32', bg: 'rgba(46,125,50,0.1)' },
};

const MotionBox = framMotion(Box);

export default function ReportPage() {
  const { detections } = useAnalysis();

  const tableRows = detections.length
    ? detections.map((d, i) => ({
        key: `${d.label}-${i}`,
        time: `${d.timestamp.toFixed(1)}s`,
        location: d.anatomicalLocation,
        label: d.label,
        confidence: `${(d.confidence * 100).toFixed(0)}%`,
      }))
    : reportItems.map((item, i) => ({
        key: `${item.label}-${i}`,
        time: `Frame ${i + 1}`,
        location: item.location,
        label: item.label,
        confidence: '91%',
      }));

  return (
    <Box sx={{ minHeight: 'calc(100vh - 130px)', py: 5, px: { xs: 2, lg: 4 }, backgroundColor: 'background.default' }}>
      <Container maxWidth="lg" sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>

        {/* ── Page Header ── */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', md: 'row' },
            alignItems: { md: 'flex-start' },
            justifyContent: 'space-between',
            gap: 2,
          }}
        >
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Box
                sx={{
                  px: 1.5,
                  py: 0.4,
                  borderRadius: '6px',
                  backgroundColor: 'rgba(0,96,100,0.1)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 0.5,
                }}
              >
                <FileText size={12} color="#006064" />
                <Typography variant="caption" sx={{ fontWeight: 700, color: '#006064', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                  Báo cáo tổng kết
                </Typography>
              </Box>
            </Box>
            <Typography variant="h3" sx={{ fontSize: '1.5rem', fontWeight: 800, color: 'text.primary', mb: 0.5 }}>
              Phiên nội soi hôm nay
            </Typography>
            <Typography variant="body2" color="textSecondary">
              Tổng hợp hình ảnh tổn thương, tọa độ và checklist gợi ý từ LLM.
            </Typography>
          </Box>

          <Dialog>
            <DialogTrigger asChild>
              <MuiButton
                variant="contained"
                startIcon={<Download size={18} />}
                sx={{ borderRadius: '10px', px: 3, py: 1.25, fontWeight: 700, whiteSpace: 'nowrap', flexShrink: 0 }}
              >
                Xuất báo cáo PDF
              </MuiButton>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Xuất báo cáo PDF</DialogTitle>
                <DialogDescription>
                  Chức năng xuất file đang ở chế độ giao diện mẫu. Logic tạo PDF sẽ được kết nối API sau.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <MuiButton variant="outlined" sx={{ borderRadius: '8px' }}>Đóng</MuiButton>
                <MuiButton variant="contained" sx={{ borderRadius: '8px' }}>Xác nhận</MuiButton>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </Box>

        {/* ── Finding Cards ── */}
        <Grid container spacing={2.5}>
          {reportItems.map((item, idx) => {
            const sev = severityMap[item.severity];
            return (
              <Grid item xs={12} md={4} key={item.id}>
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
                  {/* Gradient preview */}
                  <Box
                    sx={{
                      height: 100,
                      background: item.gradient,
                      position: 'relative',
                      display: 'flex',
                      alignItems: 'flex-end',
                      p: 2,
                    }}
                  >
                    <Box
                      sx={{
                        position: 'absolute',
                        top: 12,
                        right: 12,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5,
                        px: 1.25,
                        py: 0.4,
                        borderRadius: '6px',
                        backgroundColor: 'rgba(255,255,255,0.85)',
                        backdropFilter: 'blur(8px)',
                      }}
                    >
                      <Sparkles size={11} color={item.accentColor} />
                      <Typography variant="caption" sx={{ fontWeight: 700, color: item.accentColor, fontSize: '0.68rem' }}>
                        AI Flag
                      </Typography>
                    </Box>
                    <Box
                      sx={{
                        px: 1.5,
                        py: 0.5,
                        borderRadius: '8px',
                        backgroundColor: sev.bg,
                        border: `1px solid ${sev.color}30`,
                      }}
                    >
                      <Typography variant="caption" sx={{ fontWeight: 700, color: sev.color, fontSize: '0.7rem' }}>
                        {sev.label}
                      </Typography>
                    </Box>
                  </Box>

                  {/* Card body */}
                  <Box sx={{ p: 2.5, flex: 1, display: 'flex', flexDirection: 'column' }}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 800, color: 'text.primary', mb: 0.5, fontSize: '1rem' }}>
                      {item.label}
                    </Typography>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.5 }}>
                      <MapPin size={12} color={item.accentColor} />
                      <Typography variant="caption" sx={{ color: item.accentColor, fontWeight: 600 }}>
                        {item.location}
                      </Typography>
                    </Box>
                    <Typography variant="caption" sx={{ color: 'text.disabled', fontFamily: 'monospace', mb: 2, display: 'block' }}>
                      {item.coordinate}
                    </Typography>

                    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
                      {item.checklist.map((point) => (
                        <Box key={point} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                          <CheckCircle2 size={14} color="#2E7D32" style={{ marginTop: 1, flexShrink: 0 }} />
                          <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.55 }}>
                            {point}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  </Box>
                </MotionBox>
              </Grid>
            );
          })}
        </Grid>

        {/* ── Summary DataTable ── */}
        <Box>
          <Box sx={{ mb: 2.5 }}>
            <Typography variant="h3" sx={{ fontSize: '1.25rem', fontWeight: 700, color: 'text.primary', mb: 0.5 }}>
              Bảng tổng hợp phát hiện
            </Typography>
            <Typography variant="body2" color="textSecondary">
              Dữ liệu từ AnalysisContext — sẵn sàng thay bằng API thật.
            </Typography>
          </Box>

          <Box
            sx={{
              backgroundColor: 'background.paper',
              borderRadius: '16px',
              border: '1px solid #E2EAE8',
              boxShadow: '0 2px 12px rgba(13,27,42,0.06)',
              overflow: 'hidden',
            }}
          >
            {/* Table header */}
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: '1fr 1.5fr 2fr 1fr',
                px: 3,
                py: 1.5,
                backgroundColor: '#F8FAFB',
                borderBottom: '1px solid #E2EAE8',
              }}
            >
              {['Thời điểm', 'Vị trí giải phẫu', 'Chẩn đoán AI', 'Độ tin cậy'].map((h) => (
                <Typography key={h} variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                  {h}
                </Typography>
              ))}
            </Box>

            {tableRows.map((row, idx) => (
              <Box
                key={row.key}
                sx={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1.5fr 2fr 1fr',
                  px: 3,
                  py: 1.875,
                  alignItems: 'center',
                  borderBottom: idx < tableRows.length - 1 ? '1px solid #F0F4F3' : 'none',
                  transition: 'background-color 0.15s',
                  '&:hover': { backgroundColor: '#F8FAFB' },
                }}
              >
                <Typography variant="body2" sx={{ fontFamily: 'monospace', color: 'text.secondary', fontWeight: 500 }}>
                  {row.time}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  {row.location}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ScanSearch size={15} color="#006064" />
                  <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                    {row.label}
                  </Typography>
                </Box>
                <Box
                  sx={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    px: 1.25,
                    py: 0.4,
                    borderRadius: '6px',
                    backgroundColor: 'rgba(46,125,50,0.08)',
                    width: 'fit-content',
                  }}
                >
                  <Typography variant="caption" sx={{ fontWeight: 700, color: '#2E7D32' }}>
                    {row.confidence}
                  </Typography>
                </Box>
              </Box>
            ))}

            {/* Table footer with export */}
            <Box
              sx={{
                px: 3,
                py: 2,
                borderTop: '1px solid #E2EAE8',
                backgroundColor: '#F8FAFB',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <Typography variant="caption" color="textSecondary">
                {tableRows.length} bản ghi · Cập nhật lần cuối: hôm nay
              </Typography>
              <Dialog>
                <DialogTrigger asChild>
                  <MuiButton
                    size="small"
                    variant="outlined"
                    startIcon={<Download size={14} />}
                    sx={{
                      borderRadius: '8px',
                      borderColor: '#E2EAE8',
                      color: 'text.secondary',
                      fontWeight: 600,
                      fontSize: '0.8rem',
                      py: 0.75,
                      '&:hover': { borderColor: '#006064', color: 'primary.main', backgroundColor: 'rgba(0,96,100,0.04)' },
                    }}
                  >
                    Xuất PDF
                  </MuiButton>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Xuất báo cáo PDF</DialogTitle>
                    <DialogDescription>
                      Chức năng xuất file đang ở chế độ giao diện mẫu. Logic tạo PDF sẽ được kết nối API sau.
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <MuiButton variant="outlined" sx={{ borderRadius: '8px' }}>Đóng</MuiButton>
                    <MuiButton variant="contained" sx={{ borderRadius: '8px' }}>Xác nhận</MuiButton>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </Box>
          </Box>
        </Box>
      </Container>
    </Box>
  );
}
