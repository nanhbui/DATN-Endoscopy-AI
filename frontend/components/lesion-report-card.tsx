'use client';

/**
 * lesion-report-card.tsx — structured 3-section endoscopy lesion report.
 *
 * Renders the JSON returned by the backend LESION_REPORT_DONE event
 * (defined by LESION_REPORT_SCHEMA in src/backend/api/llm_prompts.py).
 *
 * Sections, exactly mirroring the prompt's required structure:
 *   1. Kỹ thuật       — phương pháp, thiết bị, thời điểm
 *   2. Mô tả tổn thương — kích thước, Paris, surface, color, margin, vascular, fluid
 *   3. Kết luận       — primary dx, severity badge, differential, recommendations,
 *                       AI confidence
 *
 * Replaces the ReactMarkdown rendering of `llmInsight` for detections that
 * have a structured `lesionReport`. The legacy markdown path stays alive for
 * older sessions and the streaming text fallback (LLM_CHUNK / LLM_DONE).
 */

import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import type { LesionReport } from '@/lib/ws-client';
import { DisclaimerFooter } from '@/components/disclaimer';

// ── Severity → visual style ──────────────────────────────────────────────────
//
// 3-level severity locked by user decision 2A: thấp / trung bình / cao.
// Colors are tuned for clinical readability — green/yellow/red is the
// universal medical triage convention; we don't reinvent it.

const SEVERITY_STYLE = {
  'thấp':        { color: '#2E7D32', bg: 'rgba(46,125,50,0.10)',  emoji: '🟢' },
  'trung bình':  { color: '#ED6C02', bg: 'rgba(237,108,2,0.10)',  emoji: '🟡' },
  'cao':         { color: '#D32F2F', bg: 'rgba(211,47,47,0.10)',  emoji: '🔴' },
} as const;

// ── Sub-components ───────────────────────────────────────────────────────────

interface SectionProps {
  title: string;
  icon: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

function Section({ title, icon, defaultOpen = true, children }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Box sx={{ borderRadius: '8px', border: '1px solid #E2EAE8', overflow: 'hidden' }}>
      <Box
        onClick={() => setOpen((v) => !v)}
        sx={{
          px: 1.5, py: 1, display: 'flex', alignItems: 'center', gap: 1,
          cursor: 'pointer', backgroundColor: '#F8FAFB',
          '&:hover': { backgroundColor: '#F0F4F3' },
        }}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: 'text.primary', flex: 1 }}>
          <span style={{ marginRight: 6 }}>{icon}</span>{title}
        </Typography>
      </Box>
      {open && <Box sx={{ px: 1.5, py: 1.25 }}>{children}</Box>}
    </Box>
  );
}

interface KeyValueProps { label: string; value: string }

function KeyValue({ label, value }: KeyValueProps) {
  return (
    <Box sx={{ display: 'flex', gap: 1, fontSize: '0.78rem', lineHeight: 1.5 }}>
      <Typography sx={{ fontSize: 'inherit', fontWeight: 600, color: 'text.secondary', minWidth: 92, flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography sx={{ fontSize: 'inherit', color: 'text.primary', flex: 1 }}>
        {value || '—'}
      </Typography>
    </Box>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export interface LesionReportCardProps {
  report: LesionReport;
}

export function LesionReportCard({ report }: LesionReportCardProps) {
  const sev = SEVERITY_STYLE[report.conclusion.severity];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
      {/* ── Header strip: severity + confidence ──────────────────────────── */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        <Chip
          label={`${sev.emoji} ${report.conclusion.severity.toUpperCase()}`}
          size="small"
          sx={{
            fontWeight: 700, fontSize: '0.72rem', height: 22,
            color: sev.color, backgroundColor: sev.bg, border: `1px solid ${sev.color}33`,
          }}
        />
        <Box sx={{ flex: 1, minWidth: 120 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
            <Typography sx={{ fontSize: '0.68rem', fontWeight: 600, color: 'text.secondary' }}>
              AI confidence
            </Typography>
            <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#006064' }}>
              {report.conclusion.ai_confidence}%
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={report.conclusion.ai_confidence}
            sx={{
              height: 4, borderRadius: 2, backgroundColor: 'rgba(0,96,100,0.1)',
              '& .MuiLinearProgress-bar': { backgroundColor: '#006064', borderRadius: 2 },
            }}
          />
        </Box>
      </Box>

      {/* ── Section 1: Kỹ thuật ──────────────────────────────────────────── */}
      <Section title="Kỹ thuật" icon="🔬" defaultOpen={false}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          <KeyValue label="Phương pháp" value={report.technique.method} />
          <KeyValue label="Thiết bị"    value={report.technique.device} />
          <KeyValue label="Thời điểm"   value={report.technique.timestamp} />
        </Box>
      </Section>

      {/* ── Section 2: Mô tả tổn thương ──────────────────────────────────── */}
      <Section title="Mô tả tổn thương" icon="📋">
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          <KeyValue label="Kích thước"  value={report.description.size_mm} />
          <KeyValue label="Phân loại Paris" value={report.description.paris_class} />
          <KeyValue label="Bề mặt"      value={report.description.surface} />
          <KeyValue label="Màu sắc"     value={report.description.color} />
          <KeyValue label="Bờ"          value={report.description.margin} />
          <KeyValue label="Mạch máu"    value={report.description.vascular} />
          <KeyValue label="Dịch / máu"  value={report.description.fluid} />
        </Box>
      </Section>

      {/* ── Section 3: Kết luận ──────────────────────────────────────────── */}
      <Section title="Kết luận" icon="🩺">
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
          {/* Primary diagnosis */}
          <Box>
            <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, color: 'text.secondary', mb: 0.25 }}>
              Chẩn đoán chính
            </Typography>
            <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, color: 'text.primary', lineHeight: 1.4 }}>
              {report.conclusion.primary_dx}
            </Typography>
          </Box>

          {/* Differential diagnoses with probability bars */}
          <Box>
            <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>
              Chẩn đoán phân biệt
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.6 }}>
              {report.conclusion.differential.map((d, i) => (
                <Box key={i}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.2 }}>
                    <Typography sx={{ fontSize: '0.75rem', color: 'text.primary', flex: 1, mr: 1 }}>
                      {d.dx}
                    </Typography>
                    <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: '#006064' }}>
                      {d.probability_pct}%
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={d.probability_pct}
                    sx={{
                      height: 3, borderRadius: 1.5, backgroundColor: 'rgba(0,96,100,0.08)',
                      '& .MuiLinearProgress-bar': { backgroundColor: i === 0 ? '#006064' : '#90A4AE', borderRadius: 1.5 },
                    }}
                  />
                </Box>
              ))}
            </Box>
          </Box>

          {/* Recommendations */}
          <Box>
            <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>
              Khuyến nghị
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 2.5, display: 'flex', flexDirection: 'column', gap: 0.4 }}>
              {report.conclusion.recommendations.map((r, i) => (
                <Box component="li" key={i} sx={{ fontSize: '0.78rem', color: 'text.primary', lineHeight: 1.5 }}>
                  {r}
                </Box>
              ))}
            </Box>
          </Box>
        </Box>
      </Section>

      {/* ── Disclaimer footer (decision 4C — banner+footer) ──────────────── */}
      <DisclaimerFooter />
    </Box>
  );
}
