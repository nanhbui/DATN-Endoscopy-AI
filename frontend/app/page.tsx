'use client';

import Link from 'next/link';
import { motion as framMotion } from 'framer-motion';
import {
  Activity,
  ArrowRight,
  Brain,
  ChevronRight,
  Gauge,
  MessageSquareText,
  Play,
  ShieldAlert,
  Timer,
  TrendingUp,
  UploadCloud,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useAnalysis } from '@/context/AnalysisContext';

import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import Chip from '@mui/material/Chip';
import MuiButton from '@mui/material/Button';

const stats = [
  {
    title: 'Số ca hôm nay',
    value: '24',
    delta: '+4 so với hôm qua',
    trend: 'up',
    icon: Gauge,
    iconBg: 'rgba(2,119,189,0.1)',
    iconColor: '#0277BD',
  },
  {
    title: 'Tổng bất thường',
    value: '17',
    delta: '3 cần theo dõi sát',
    trend: 'warn',
    icon: ShieldAlert,
    iconBg: 'rgba(245,158,11,0.12)',
    iconColor: '#D97706',
  },
  {
    title: 'Thời gian TB',
    value: '01:32',
    delta: 'Mỗi video phân tích',
    trend: 'neutral',
    icon: Timer,
    iconBg: 'rgba(0,96,100,0.1)',
    iconColor: '#006064',
  },
];

const workflowFeatures = [
  {
    title: 'Phân tích Real-time',
    description: 'Xử lý video tốc độ cao, nhận diện tổn thương ngay lập tức với độ chính xác cao.',
    icon: Activity,
    color: '#0277BD',
    bg: 'rgba(2,119,189,0.08)',
  },
  {
    title: 'Smart Ignore & Memory',
    description: 'Tự động ghi nhớ các điểm đã bỏ qua, không cảnh báo lặp lại trong cùng phiên.',
    icon: Brain,
    color: '#006064',
    bg: 'rgba(0,96,100,0.08)',
  },
  {
    title: 'Trợ lý Y khoa LLM',
    description: 'Tự động sinh phân loại y khoa và checklist hành động phù hợp cho bác sĩ lâm sàng.',
    icon: MessageSquareText,
    color: '#2E7D32',
    bg: 'rgba(46,125,50,0.08)',
  },
];

const recentSessions = [
  { videoId: 'VID-2026-0412', dateTime: '02/04/2026 08:45', findings: 3, status: 'Hoàn tất' },
  { videoId: 'VID-2026-0413', dateTime: '02/04/2026 09:20', findings: 1, status: 'Tạm dừng' },
  { videoId: 'VID-2026-0414', dateTime: '02/04/2026 10:10', findings: 2, status: 'Hoàn tất' },
  { videoId: 'VID-2026-0415', dateTime: '02/04/2026 11:05', findings: 4, status: 'Hoàn tất' },
];

const MotionBox = framMotion(Box);

export default function Home() {
  const { isPlaying, startMockAnalysis } = useAnalysis();

  return (
    <Box sx={{ minHeight: 'calc(100vh - 130px)', py: 5, px: { xs: 2, sm: 3, lg: 4 }, backgroundColor: 'background.default' }}>
      <Container maxWidth="lg" sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>

        {/* ── Hero ── */}
        <MotionBox
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          sx={{
            borderRadius: '20px',
            overflow: 'hidden',
            position: 'relative',
            background: 'linear-gradient(135deg, #004044 0%, #006064 45%, #00838F 100%)',
            p: { xs: 3, lg: 5 },
            color: '#fff',
          }}
        >
          {/* decorative blobs */}
          <Box sx={{ position: 'absolute', top: -60, right: -60, width: 280, height: 280, borderRadius: '50%', background: 'rgba(255,255,255,0.04)', pointerEvents: 'none' }} />
          <Box sx={{ position: 'absolute', bottom: -80, right: 80, width: 200, height: 200, borderRadius: '50%', background: 'rgba(255,255,255,0.03)', pointerEvents: 'none' }} />

          <Box sx={{ position: 'relative', zIndex: 1 }}>
            <Chip
              label="Frontend-First Mock System"
              size="small"
              sx={{ mb: 2.5, backgroundColor: 'rgba(255,255,255,0.15)', color: '#fff', fontWeight: 600, fontSize: '0.7rem', letterSpacing: '0.05em' }}
            />
            <Typography
              variant="h1"
              sx={{ fontSize: { xs: '1.75rem', md: '2.5rem' }, fontWeight: 800, mb: 1.5, lineHeight: 1.25, color: '#fff' }}
            >
              Hệ thống Phân tích Nội soi Thông minh
            </Typography>
            <Typography
              sx={{ mb: 4, maxWidth: 640, lineHeight: 1.7, color: 'rgba(255,255,255,0.78)', fontSize: '0.9375rem' }}
            >
              Bộ khung UI/UX cho phòng khám: mô phỏng luồng AI phát hiện tổn thương, tạm dừng video, và sinh giải thích LLM theo thời gian thực.
            </Typography>

            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5 }}>
              <MuiButton
                variant="contained"
                size="large"
                startIcon={<Play size={18} />}
                onClick={startMockAnalysis}
                sx={{
                  backgroundColor: '#fff',
                  color: '#006064',
                  fontWeight: 700,
                  borderRadius: '10px',
                  px: 3,
                  boxShadow: '0 4px 20px rgba(0,0,0,0.25)',
                  '&:hover': { backgroundColor: '#f0fafa', boxShadow: '0 6px 24px rgba(0,0,0,0.3)' },
                }}
              >
                {isPlaying ? 'Đang phân tích...' : 'Bắt đầu phân tích'}
              </MuiButton>
              <MuiButton
                component={Link}
                href="/workspace"
                variant="outlined"
                size="large"
                startIcon={<UploadCloud size={18} />}
                sx={{
                  borderColor: 'rgba(255,255,255,0.45)',
                  color: '#fff',
                  borderRadius: '10px',
                  px: 3,
                  '&:hover': { borderColor: '#fff', backgroundColor: 'rgba(255,255,255,0.1)' },
                }}
              >
                Tải video lên
              </MuiButton>
              <MuiButton
                component={Link}
                href="/report"
                variant="text"
                size="large"
                endIcon={<ArrowRight size={16} />}
                sx={{ color: 'rgba(255,255,255,0.8)', borderRadius: '10px', px: 2, '&:hover': { color: '#fff', backgroundColor: 'rgba(255,255,255,0.08)' } }}
              >
                Xem báo cáo
              </MuiButton>
            </Box>
          </Box>
        </MotionBox>

        {/* ── Stats ── */}
        <Grid container spacing={2.5}>
          {stats.map((item, idx) => (
            <Grid item xs={12} sm={4} key={item.title}>
              <MotionBox
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: idx * 0.08 }}
                sx={{
                  backgroundColor: 'background.paper',
                  borderRadius: '16px',
                  border: '1px solid #E2EAE8',
                  boxShadow: '0 2px 12px rgba(13,27,42,0.06)',
                  p: 3,
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  gap: 2,
                  transition: 'box-shadow 0.2s',
                  '&:hover': { boxShadow: '0 6px 24px rgba(13,27,42,0.1)' },
                }}
              >
                <Box>
                  <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', mb: 0.5, display: 'block' }}>
                    {item.title}
                  </Typography>
                  <Typography sx={{ fontSize: '2rem', fontWeight: 800, color: 'text.primary', lineHeight: 1.1, mb: 0.75 }}>
                    {item.value}
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    {item.trend === 'up' && <TrendingUp size={12} color="#2E7D32" />}
                    <Typography variant="caption" sx={{ color: item.trend === 'warn' ? '#D97706' : item.trend === 'up' ? '#2E7D32' : 'text.secondary', fontWeight: 500 }}>
                      {item.delta}
                    </Typography>
                  </Box>
                </Box>
                <Box
                  sx={{
                    width: 48,
                    height: 48,
                    borderRadius: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: item.iconBg,
                    color: item.iconColor,
                    flexShrink: 0,
                  }}
                >
                  <item.icon size={22} />
                </Box>
              </MotionBox>
            </Grid>
          ))}
        </Grid>

        {/* ── Features ── */}
        <Box>
          <Box sx={{ mb: 3 }}>
            <Typography variant="h3" sx={{ fontSize: '1.375rem', fontWeight: 700, mb: 0.5, color: 'text.primary' }}>
              Luồng tính năng nổi bật
            </Typography>
            <Typography variant="body2" color="textSecondary">
              Ba bước chính trong quy trình AI phân tích nội soi.
            </Typography>
          </Box>

          <Grid container spacing={2.5}>
            {workflowFeatures.map((feature, idx) => (
              <Grid item xs={12} md={4} key={feature.title}>
                <MotionBox
                  initial={{ opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: idx * 0.08 }}
                  sx={{
                    height: '100%',
                    backgroundColor: 'background.paper',
                    borderRadius: '16px',
                    border: '1px solid #E2EAE8',
                    boxShadow: '0 2px 12px rgba(13,27,42,0.06)',
                    p: 3,
                    transition: 'box-shadow 0.2s, transform 0.2s',
                    '&:hover': { boxShadow: '0 8px 28px rgba(13,27,42,0.1)', transform: 'translateY(-2px)' },
                  }}
                >
                  <Box
                    sx={{
                      width: 44,
                      height: 44,
                      borderRadius: '12px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      backgroundColor: feature.bg,
                      color: feature.color,
                      mb: 2,
                    }}
                  >
                    <feature.icon size={22} />
                  </Box>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1, color: 'text.primary' }}>
                    {feature.title}
                  </Typography>
                  <Typography variant="body2" color="textSecondary" sx={{ lineHeight: 1.65 }}>
                    {feature.description}
                  </Typography>
                </MotionBox>
              </Grid>
            ))}
          </Grid>
        </Box>

        {/* ── Recent Sessions ── */}
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
            <Box>
              <Typography variant="h3" sx={{ fontSize: '1.375rem', fontWeight: 700, mb: 0.5, color: 'text.primary' }}>
                Các ca phân tích gần đây
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Tổng hợp nhanh các video mới nhất và trạng thái xử lý.
              </Typography>
            </Box>
            <MuiButton
              component={Link}
              href="/report"
              endIcon={<ChevronRight size={16} />}
              size="small"
              sx={{ color: 'primary.main', fontWeight: 600, textTransform: 'none' }}
            >
              Xem tất cả
            </MuiButton>
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
                gridTemplateColumns: '1.5fr 1.5fr 1fr 1fr 0.8fr',
                px: 3,
                py: 1.5,
                backgroundColor: '#F8FAFB',
                borderBottom: '1px solid #E2EAE8',
              }}
            >
              {['ID Video', 'Ngày giờ', 'Tổn thương', 'Trạng thái', ''].map((h) => (
                <Typography key={h} variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                  {h}
                </Typography>
              ))}
            </Box>

            {recentSessions.map((session, idx) => {
              const isDone = session.status === 'Hoàn tất';
              return (
                <Box
                  key={session.videoId}
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: '1.5fr 1.5fr 1fr 1fr 0.8fr',
                    px: 3,
                    py: 1.75,
                    alignItems: 'center',
                    borderBottom: idx < recentSessions.length - 1 ? '1px solid #F0F4F3' : 'none',
                    transition: 'background-color 0.15s',
                    '&:hover': { backgroundColor: '#F8FAFB' },
                  }}
                >
                  <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary', fontFamily: 'monospace' }}>
                    {session.videoId}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    {session.dateTime}
                  </Typography>
                  <Box
                    component="span"
                    sx={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      px: 1.25,
                      py: 0.4,
                      borderRadius: '6px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      width: 'fit-content',
                      backgroundColor: 'rgba(2,119,189,0.08)',
                      color: '#0277BD',
                    }}
                  >
                    {session.findings} tổn thương
                  </Box>
                  <Box
                    component="span"
                    sx={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 0.5,
                      px: 1.25,
                      py: 0.4,
                      borderRadius: '6px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      width: 'fit-content',
                      backgroundColor: isDone ? 'rgba(46,125,50,0.1)' : 'rgba(245,158,11,0.12)',
                      color: isDone ? '#2E7D32' : '#D97706',
                    }}
                  >
                    <Box sx={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'currentColor' }} />
                    {session.status}
                  </Box>
                  <MuiButton
                    size="small"
                    endIcon={<ChevronRight size={14} />}
                    component={Link}
                    href="/report"
                    sx={{ color: 'primary.main', fontWeight: 600, fontSize: '0.8rem', textTransform: 'none', justifyContent: 'flex-end', p: 0, minWidth: 0, '&:hover': { background: 'none', textDecoration: 'underline' } }}
                  >
                    Chi tiết
                  </MuiButton>
                </Box>
              );
            })}
          </Box>
        </Box>
      </Container>
    </Box>
  );
}
