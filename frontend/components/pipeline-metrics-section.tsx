'use client';

import { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { Activity } from 'lucide-react';
import { API_BASE } from '@/lib/ws-client';

interface FramerateEntry  { element: string; avg_fps: number; min_fps: number }
interface ProctimeEntry   { element: string; avg_ms: number; max_ms: number }
interface LatencyEntry    { path: string; avg_ms: number }

interface Metrics {
  enabled: boolean;
  framerate?: FramerateEntry[];
  proctime?: ProctimeEntry[];
  interlatency?: LatencyEntry[];
}

function MetricTable({ headers, rows }: { headers: string[]; rows: (string | number)[][] }) {
  return (
    <Box sx={{ borderRadius: '12px', border: '1px solid #E2EAE8', overflow: 'hidden' }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: `repeat(${headers.length}, 1fr)`, px: 2.5, py: 1.25, backgroundColor: '#F8FAFB', borderBottom: '1px solid #E2EAE8' }}>
        {headers.map(h => (
          <Typography key={h} variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            {h}
          </Typography>
        ))}
      </Box>
      {rows.map((row, i) => (
        <Box key={i} sx={{ display: 'grid', gridTemplateColumns: `repeat(${headers.length}, 1fr)`, px: 2.5, py: 1.25, borderBottom: i < rows.length - 1 ? '1px solid #F0F4F3' : 'none', '&:hover': { backgroundColor: '#F8FAFB' } }}>
          {row.map((cell, j) => (
            <Typography key={j} variant="body2" sx={{ fontFamily: j > 0 ? 'monospace' : undefined, color: j === 0 ? 'text.primary' : 'text.secondary', fontWeight: j === 0 ? 600 : 400 }}>
              {cell}
            </Typography>
          ))}
        </Box>
      ))}
    </Box>
  );
}

export function PipelineMetricsSection() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/pipeline/metrics`)
      .then(r => r.json())
      .then(setMetrics)
      .catch(() => setMetrics(null));
  }, []);

  if (!metrics || !metrics.enabled) return null;

  const hasData = (metrics.framerate?.length ?? 0) + (metrics.proctime?.length ?? 0) > 0;
  if (!hasData) return null;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2.5 }}>
        <Activity size={18} color="#006064" />
        <Typography variant="h3" sx={{ fontSize: '1.25rem', fontWeight: 700, color: 'text.primary' }}>
          GStreamer Pipeline Metrics
        </Typography>
        <Box sx={{ ml: 1, px: 1.25, py: 0.3, borderRadius: '6px', backgroundColor: 'rgba(0,96,100,0.08)' }}>
          <Typography variant="caption" sx={{ fontWeight: 700, color: '#006064' }}>GstShark</Typography>
        </Box>
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Framerate */}
        {(metrics.framerate?.length ?? 0) > 0 && (
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.25, color: 'text.primary' }}>
              Framerate theo element
            </Typography>
            <MetricTable
              headers={['Element', 'Avg FPS', 'Min FPS']}
              rows={metrics.framerate!.map(r => [r.element, r.avg_fps.toFixed(1), r.min_fps.toFixed(1)])}
            />
          </Box>
        )}

        {/* Processing time */}
        {(metrics.proctime?.length ?? 0) > 0 && (
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.25, color: 'text.primary' }}>
              Thời gian xử lý per element
            </Typography>
            <MetricTable
              headers={['Element', 'Avg (ms)', 'Max (ms)']}
              rows={metrics.proctime!.map(r => [r.element, r.avg_ms.toFixed(3), r.max_ms.toFixed(3)])}
            />
          </Box>
        )}

        {/* Interlatency */}
        {(metrics.interlatency?.length ?? 0) > 0 && (
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.25, color: 'text.primary' }}>
              Latency giữa các pad
            </Typography>
            <MetricTable
              headers={['Đường đi', 'Avg latency (ms)']}
              rows={metrics.interlatency!.map(r => [r.path, r.avg_ms.toFixed(3)])}
            />
          </Box>
        )}
      </Box>
    </Box>
  );
}
