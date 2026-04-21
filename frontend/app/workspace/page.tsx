'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { motion as framMotion } from 'framer-motion';
import {
  AlertTriangle,
  Bot,
  CircleX,
  FileVideo,
  Mic,
  MicOff,
  Play,
  Square,
  UploadCloud,
  Zap,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { API_BASE } from '@/lib/ws-client';
import { useAnalysis } from '@/context/AnalysisContext';
import { useVoiceControl } from '@/hooks/use-voice-control';

import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import { Radio, Wifi } from 'lucide-react';

import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import MuiButton from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import LinearProgress from '@mui/material/LinearProgress';
import { styled } from '@mui/material/styles';

const MotionBox = framMotion(Box);

// ── Styled video container ───────────────────────────────────────────────────

const VideoContainer = styled(Box)(() => ({
  position: 'relative',
  aspectRatio: '16 / 9',
  width: '100%',
  overflow: 'hidden',
  borderRadius: '16px',
  border: '1px solid rgba(255,255,255,0.08)',
  backgroundColor: '#0D1117',
}));

const BboxOverlay = styled(MotionBox)(() => ({
  position: 'absolute',
  border: '2px solid #F59E0B',
  backgroundColor: 'rgba(245,158,11,0.1)',
  borderRadius: '4px',
}));

// ── Status dot with pulse animation ─────────────────────────────────────────

function StatusDot({ color }: { color: string }) {
  return (
    <Box
      sx={{
        width: 8,
        height: 8,
        borderRadius: '50%',
        backgroundColor: color,
        boxShadow: `0 0 0 3px ${color}33`,
        animation: color === '#4CAF50' ? 'pulse 2s infinite' : 'none',
        '@keyframes pulse': {
          '0%, 100%': { boxShadow: `0 0 0 3px ${color}33` },
          '50%': { boxShadow: `0 0 0 7px ${color}11` },
        },
      }}
    />
  );
}

// ── Live stream input zone ───────────────────────────────────────────────────

interface LiveInputZoneProps {
  value: string;
  onChange: (v: string) => void;
  onConnect: () => void;
  isConnecting: boolean;
}

function LiveInputZone({ value, onChange, onConnect, isConnecting }: LiveInputZoneProps) {
  return (
    <Box
      sx={{
        aspectRatio: '16 / 9',
        width: '100%',
        borderRadius: '16px',
        border: '2px dashed #C8D8D6',
        backgroundColor: '#FAFCFB',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2.5,
        px: { xs: 3, md: 8 },
      }}
    >
      <Box sx={{ width: 56, height: 56, borderRadius: '16px', backgroundColor: 'rgba(0,96,100,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#006064' }}>
        <Wifi size={28} />
      </Box>
      <Box sx={{ width: '100%', maxWidth: 420, textAlign: 'center' }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.primary', mb: 0.5 }}>
          Kết nối nguồn video trực tiếp
        </Typography>
        <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 2 }}>
          Nhập địa chỉ RTSP hoặc đường dẫn thiết bị V4L2
        </Typography>
        <TextField
          fullWidth
          size="small"
          placeholder="rtsp://192.168.1.x:554/stream  hoặc  /dev/video0"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && value.trim()) onConnect(); }}
          sx={{ mb: 1.5, '& .MuiOutlinedInput-root': { borderRadius: '10px' } }}
        />
        <MuiButton
          variant="contained"
          fullWidth
          disabled={!value.trim() || isConnecting}
          onClick={onConnect}
          startIcon={isConnecting ? <CircularProgress size={14} sx={{ color: 'inherit' }} /> : <Radio size={16} />}
          sx={{ borderRadius: '10px', py: 1.25, fontWeight: 700 }}
        >
          {isConnecting ? 'Đang kết nối…' : 'Kết nối & Bắt đầu'}
        </MuiButton>
      </Box>
    </Box>
  );
}

// ── Upload zone ─────────────────────────────────────────────────────────────

interface UploadZoneProps {
  onFileSelected: (file: File) => void;
}

function UploadZone({ onFileSelected }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const file = files[0];
      if (!file.type.startsWith('video/')) return;
      onFileSelected(file);
    },
    [onFileSelected],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => setIsDragging(false), []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  return (
    <Box
      onClick={() => inputRef.current?.click()}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      sx={{
        aspectRatio: '16 / 9',
        width: '100%',
        borderRadius: '16px',
        border: `2px dashed ${isDragging ? '#006064' : '#C8D8D6'}`,
        backgroundColor: isDragging ? 'rgba(0,96,100,0.05)' : '#FAFCFB',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        '&:hover': {
          borderColor: '#006064',
          backgroundColor: 'rgba(0,96,100,0.04)',
        },
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        style={{ display: 'none' }}
        onChange={(e) => handleFiles(e.target.files)}
      />
      <Box
        sx={{
          width: 64,
          height: 64,
          borderRadius: '16px',
          backgroundColor: isDragging ? 'rgba(0,96,100,0.12)' : 'rgba(0,96,100,0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#006064',
          transition: 'background-color 0.2s',
        }}
      >
        <UploadCloud size={30} />
      </Box>
      <Box sx={{ textAlign: 'center' }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.primary', mb: 0.5 }}>
          {isDragging ? 'Thả file vào đây' : 'Tải video lên để phân tích'}
        </Typography>
        <Typography variant="caption" color="textSecondary">
          Kéo thả hoặc nhấp để chọn · MP4, MOV, AVI, MKV
        </Typography>
      </Box>
    </Box>
  );
}

// ── Uploading progress state ─────────────────────────────────────────────────

function UploadingProgress({ fileName, progress }: { fileName: string; progress: number }) {
  return (
    <Box
      sx={{
        aspectRatio: '16 / 9',
        width: '100%',
        borderRadius: '16px',
        backgroundColor: '#0D1117',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 3,
        px: 6,
      }}
    >
      <CircularProgress
        size={52}
        thickness={3}
        sx={{ color: '#00838F' }}
      />
      <Box sx={{ width: '100%', maxWidth: 320, textAlign: 'center' }}>
        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', mb: 1.5, display: 'block' }}>
          Đang tải · {fileName}
        </Typography>
        <LinearProgress
          variant="determinate"
          value={progress}
          sx={{
            height: 4,
            borderRadius: 2,
            backgroundColor: 'rgba(255,255,255,0.1)',
            '& .MuiLinearProgress-bar': { backgroundColor: '#00838F', borderRadius: 2 },
          }}
        />
        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.4)', mt: 1, display: 'block' }}>
          {progress}%
        </Typography>
      </Box>
    </Box>
  );
}

// ── Live stream connected panel ──────────────────────────────────────────────

function LiveStreamPanel({ source, pipelineState }: { source: string; pipelineState: string }) {
  const isActive = pipelineState === 'PLAYING' || pipelineState === 'PAUSED_WAITING_INPUT' || pipelineState === 'PROCESSING_LLM';
  return (
    <Box sx={{ aspectRatio: '16 / 9', width: '100%', borderRadius: '16px', backgroundColor: '#0D1117', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2, position: 'relative', overflow: 'hidden' }}>
      {/* subtle grid bg */}
      <Box sx={{ position: 'absolute', inset: 0, backgroundImage: 'radial-gradient(circle, rgba(0,96,100,0.08) 1px, transparent 1px)', backgroundSize: '28px 28px', pointerEvents: 'none' }} />
      <Box sx={{ position: 'absolute', top: 12, left: 12, display: 'flex', alignItems: 'center', gap: 0.75, px: 1.25, py: 0.4, borderRadius: '6px', backgroundColor: isActive ? 'rgba(220,38,38,0.85)' : 'rgba(100,100,100,0.6)', backdropFilter: 'blur(6px)' }}>
        <Box sx={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: '#fff', animation: isActive ? 'pulse 1.5s infinite' : 'none', '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.35 } } }} />
        <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#fff', letterSpacing: '0.06em' }}>{isActive ? 'LIVE' : 'OFFLINE'}</Typography>
      </Box>
      <Radio size={36} color="rgba(0,132,143,0.5)" />
      <Box sx={{ textAlign: 'center', zIndex: 1 }}>
        <Typography sx={{ fontSize: '0.8rem', fontWeight: 600, color: 'rgba(255,255,255,0.55)', mb: 0.5 }}>
          {isActive ? 'Đang phân tích luồng trực tiếp' : 'Chưa kết nối'}
        </Typography>
        <Typography sx={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.3)', fontFamily: 'monospace', maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {source}
        </Typography>
      </Box>
    </Box>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function Workspace() {
  const {
    isPlaying,
    isConnected,
    pipelineState,
    currentDetection,
    isListeningVoice,
    llmInsight,
    startMockAnalysis,
    ignoreDetection,
    explainMore,
    confirmDetection,
    uploadAndConnect,
    connectLive,
    resetAnalysis,
  } = useAnalysis();

  // Source mode
  const [sourceMode, setSourceMode] = useState<'file' | 'live'>('file');
  const [liveSource, setLiveSource] = useState('');
  const [isLiveConnecting, setIsLiveConnecting] = useState(false);

  // Local video state (object URL for <video> preview)
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [transcriptLog, setTranscriptLog] = useState<{ text: string; ts: number }[]>([]);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const [backendReachable, setBackendReachable] = useState<boolean | null>(null);
  const prevBackendReachable = useRef<boolean | null>(null);
  const [backendJustCameBack, setBackendJustCameBack] = useState(false);

  // Health check on mount and every 10s when not connected
  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
        const ok = res.ok;
        // Detect offline → online transition
        if (ok && prevBackendReachable.current === false) {
          setBackendJustCameBack(true);
        }
        prevBackendReachable.current = ok;
        setBackendReachable(ok);
      } catch {
        prevBackendReachable.current = false;
        setBackendReachable(false);
        setBackendJustCameBack(false);
      }
    };
    check();
    const id = setInterval(() => { if (!isConnected) check(); }, 10000);
    return () => clearInterval(id);
  }, [isConnected]);

  // Seek video to detection frame so bbox aligns with what's on screen
  useEffect(() => {
    if (currentDetection && videoRef.current) {
      videoRef.current.currentTime = currentDetection.timestamp;
    }
  }, [currentDetection]);

  // Auto-pause / resume local video preview in sync with pipeline state
  useEffect(() => {
    if (!videoRef.current || !videoUrl) return;
    if (pipelineState === 'PAUSED_WAITING_INPUT' || pipelineState === 'PROCESSING_LLM') {
      videoRef.current.pause();
    } else if (pipelineState === 'PLAYING') {
      videoRef.current.play().catch(() => {});
    }
  }, [pipelineState, videoUrl]);

  // Ref so onIntent callback always reads current state without stale closure
  const pipelineStateRef = useRef(pipelineState);
  pipelineStateRef.current = pipelineState;

  const { isListening: isVoiceListening, audioLevel, supported: voiceSupported, micError, startListening, stopListening } =
    useVoiceControl({
      onIntent: useCallback((intent: import('@/hooks/use-voice-control').VoiceIntent, transcript: string) => {
        console.log("[Workspace] onIntent:", { intent, transcript, pipelineState: pipelineStateRef.current });
        if (transcript) {
          setTranscriptLog(prev => [...prev, { text: transcript, ts: Date.now() }]);
          transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
        // Only act on commands when the pipeline is waiting for a response
        if (pipelineStateRef.current !== 'PAUSED_WAITING_INPUT') {
          console.log("[Workspace] Ignoring intent — pipelineState not PAUSED_WAITING_INPUT");
          return;
        }
        if (intent === 'BO_QUA') ignoreDetection();
        else if (intent === 'GIAI_THICH') explainMore();
        else if (intent === 'XAC_NHAN') confirmDetection();
      }, [ignoreDetection, explainMore, confirmDetection]),
    });

  // Auto-activate mic when pipeline pauses on a detection (hands-free workflow)
  useEffect(() => {
    if (pipelineState === 'PAUSED_WAITING_INPUT' && voiceSupported && !isVoiceListening) {
      startListening();
    }
  }, [pipelineState, voiceSupported, isVoiceListening, startListening]);

  /** Upload to backend + connect WebSocket, keep local preview URL. */
  const handleFileSelected = useCallback(async (file: File) => {
    setVideoFile(file);
    setIsUploading(true);
    setUploadProgress(0);

    // Local preview immediately — no waiting for server
    const localUrl = URL.createObjectURL(file);
    setVideoUrl(localUrl);

    try {
      await uploadAndConnect(file, setUploadProgress);
      // Pipeline is now running on the server — play the local preview too
      videoRef.current?.play().catch(() => {/* autoplay blocked — user can click play manually */});
      // Start voice immediately so mic is active before first detection
      if (voiceSupported) startListening();
    } catch (err) {
      console.warn("[workspace] backend offline, using mock pipeline:", err);
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  }, [uploadAndConnect, voiceSupported, startListening]);

  const handleLiveConnect = useCallback(async () => {
    if (!liveSource.trim()) return;
    setIsLiveConnecting(true);
    try {
      await connectLive(liveSource.trim());
      if (voiceSupported) startListening();
    } catch (err) {
      console.warn('[workspace] live connect failed:', err);
    } finally {
      setIsLiveConnecting(false);
    }
  }, [liveSource, connectLive, voiceSupported, startListening]);

  const handleStop = useCallback(() => {
    stopListening();
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
    }
    setTranscriptLog([]);
    resetAnalysis();
  }, [stopListening, resetAnalysis]);

  const handleRemoveVideo = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.pause();
    }
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    setVideoFile(null);
    setVideoUrl(null);
    setIsUploading(false);
    setTranscriptLog([]);
    resetAnalysis();
  }, [videoUrl, resetAnalysis]);

  // ── Status badge config ────────────────────────────────────────────────────

  const statusConfig =
    pipelineState === 'PLAYING'
      ? { text: isConnected ? 'Đang phân tích (Live)' : 'Đang phân tích', color: '#4CAF50', bg: 'rgba(46,125,50,0.1)', textColor: '#2E7D32' }
      : pipelineState === 'PAUSED_WAITING_INPUT'
        ? { text: 'AI phát hiện bất thường', color: '#F59E0B', bg: 'rgba(245,158,11,0.12)', textColor: '#D97706' }
        : pipelineState === 'PROCESSING_LLM'
          ? { text: 'Đang phân tích LLM', color: '#0277BD', bg: 'rgba(2,119,189,0.1)', textColor: '#0277BD' }
          : pipelineState === 'EOS_SUMMARY'
            ? { text: 'Hoàn tất', color: '#2E7D32', bg: 'rgba(46,125,50,0.08)', textColor: '#2E7D32' }
            : videoUrl
              ? { text: isConnected ? 'Đã kết nối BE' : 'Video đã tải', color: '#006064', bg: 'rgba(0,96,100,0.1)', textColor: '#006064' }
              : { text: 'Chờ video', color: '#9AA5B1', bg: 'rgba(154,165,177,0.1)', textColor: '#4A5568' };

  return (
    <Box sx={{ minHeight: 'calc(100vh - 130px)', py: 3, px: { xs: 1.5, lg: 3 }, backgroundColor: 'background.default' }}>
      <Box sx={{ maxWidth: '1440px', mx: 'auto' }}>

        {/* Page header */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="h3" sx={{ fontSize: '1.375rem', fontWeight: 700, color: 'text.primary', mb: 0.5 }}>
            Workspace phân tích
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Tải video nội soi lên, theo dõi luồng và tương tác với trợ lý AI theo thời gian thực.
          </Typography>
        </Box>

        {/* Backend offline banner */}
        {backendReachable === false && (
          <Box sx={{ mb: 2, px: 2, py: 1.25, borderRadius: '12px', backgroundColor: 'rgba(211,47,47,0.08)', border: '1px solid rgba(211,47,47,0.3)', display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <AlertTriangle size={16} color="#D32F2F" />
            <Typography sx={{ fontSize: '0.85rem', color: '#D32F2F', fontWeight: 500, flex: 1 }}>
              Backend offline ({(process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8001')}). Đang chờ kết nối lại…
            </Typography>
          </Box>
        )}

        {/* Backend came back online — offer to reconnect without page reload */}
        {backendJustCameBack && !isConnected && videoFile && (
          <Box sx={{ mb: 2, px: 2, py: 1.25, borderRadius: '12px', backgroundColor: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.35)', display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <AlertTriangle size={16} color="#D97706" />
            <Typography sx={{ fontSize: '0.85rem', color: '#92400E', fontWeight: 500, flex: 1 }}>
              Backend đã khởi động lại — session cũ bị mất.
            </Typography>
            <MuiButton
              size="small"
              variant="contained"
              onClick={async () => {
                setBackendJustCameBack(false);
                resetAnalysis();
                setTranscriptLog([]);
                if (videoUrl) URL.revokeObjectURL(videoUrl);
                setVideoUrl(null);
                await handleFileSelected(videoFile);
              }}
              sx={{ borderRadius: '8px', backgroundColor: '#D97706', fontWeight: 700, fontSize: '0.8rem', whiteSpace: 'nowrap', '&:hover': { backgroundColor: '#B45309' } }}
            >
              Phân tích lại
            </MuiButton>
            <MuiButton
              size="small"
              onClick={() => setBackendJustCameBack(false)}
              sx={{ borderRadius: '8px', color: '#92400E', fontWeight: 600, fontSize: '0.8rem', whiteSpace: 'nowrap' }}
            >
              Bỏ qua
            </MuiButton>
          </Box>
        )}

        <Grid container spacing={3}>

          {/* ── Video Panel ────────────────────────────────────────────────── */}
          <Grid size={{ xs: 12, lg: 8 }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, height: '100%' }}>
            <Box
              sx={{
                backgroundColor: 'background.paper',
                borderRadius: '20px',
                border: '1px solid #E2EAE8',
                boxShadow: '0 2px 12px rgba(13,27,42,0.06)',
                overflow: 'hidden',
              }}
            >
              {/* Panel header */}
              <Box sx={{ px: 2.5, py: 1.5, borderBottom: '1px solid #E2EAE8', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap' }}>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.25 }}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 700, color: 'text.primary' }}>
                      Luồng video nội soi
                    </Typography>
                    <ToggleButtonGroup
                      value={sourceMode}
                      exclusive
                      size="small"
                      onChange={(_, v) => { if (v && v !== sourceMode) { resetAnalysis(); setVideoFile(null); setVideoUrl(null); setSourceMode(v); } }}
                      sx={{ '& .MuiToggleButton-root': { py: 0.3, px: 1.25, fontSize: '0.72rem', fontWeight: 600, textTransform: 'none', borderRadius: '6px !important', border: '1px solid #E2EAE8 !important', '&.Mui-selected': { backgroundColor: 'rgba(0,96,100,0.1)', color: '#006064' } } }}
                    >
                      <ToggleButton value="file"><FileVideo size={12} style={{ marginRight: 4 }} />Tải video</ToggleButton>
                      <ToggleButton value="live"><Wifi size={12} style={{ marginRight: 4 }} />Trực tiếp</ToggleButton>
                    </ToggleButtonGroup>
                  </Box>
                  {sourceMode === 'file' ? (
                    videoFile ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                        <FileVideo size={12} color="#006064" />
                        <Typography variant="caption" sx={{ color: '#006064', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 260 }}>
                          {videoFile.name}
                        </Typography>
                        <Typography variant="caption" color="textDisabled">
                          · {(videoFile.size / 1024 / 1024).toFixed(1)} MB
                        </Typography>
                      </Box>
                    ) : (
                      <Typography variant="caption" color="textSecondary">Chọn file video để bắt đầu phân tích</Typography>
                    )
                  ) : (
                    <Typography variant="caption" color="textSecondary">
                      {isConnected ? `Đang kết nối: ${liveSource}` : 'Nhập địa chỉ RTSP hoặc thiết bị V4L2'}
                    </Typography>
                  )}
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                  {videoUrl && (
                    <MuiButton
                      size="small"
                      onClick={handleRemoveVideo}
                      startIcon={<CircleX size={14} />}
                      sx={{ color: 'text.secondary', fontWeight: 600, fontSize: '0.8rem', textTransform: 'none', borderRadius: '8px', '&:hover': { color: '#DC2626', backgroundColor: 'rgba(220,38,38,0.06)' } }}
                    >
                      Xóa
                    </MuiButton>
                  )}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1.5, py: 0.5, borderRadius: '20px', backgroundColor: statusConfig.bg, flexShrink: 0 }}>
                    <StatusDot color={statusConfig.color} />
                    <Typography variant="caption" sx={{ fontWeight: 600, color: statusConfig.textColor, whiteSpace: 'nowrap' }}>
                      {statusConfig.text}
                    </Typography>
                  </Box>
                </Box>
              </Box>

              {/* Video content area */}
              <Box sx={{ p: 1.5 }}>
                {sourceMode === 'live' && !isConnected ? (
                  <LiveInputZone value={liveSource} onChange={setLiveSource} onConnect={handleLiveConnect} isConnecting={isLiveConnecting} />
                ) : sourceMode === 'live' && isConnected ? (
                  <VideoContainer>
                    <LiveStreamPanel source={liveSource} pipelineState={pipelineState} />
                    {/* Detection overlays reuse same logic */}
                    {pipelineState === 'PAUSED_WAITING_INPUT' && currentDetection && (
                      <Box sx={{ position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 4, px: 2, py: 1.25, backdropFilter: 'blur(14px)', backgroundColor: 'rgba(13,17,23,0.82)', borderTop: '1px solid rgba(245,158,11,0.25)', display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flex: 1, minWidth: 0 }}>
                          <AlertTriangle size={14} color="#F59E0B" />
                          <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: '#FCD34D', whiteSpace: 'nowrap' }}>{currentDetection.label}</Typography>
                          <Typography sx={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.55)' }}>{(currentDetection.confidence * 100).toFixed(0)}%</Typography>
                        </Box>
                        {voiceSupported && (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: isVoiceListening ? '#4FC3F7' : 'rgba(255,255,255,0.35)' }}>
                            {isVoiceListening ? <Mic size={14} /> : <MicOff size={14} />}
                            {isVoiceListening && (
                              <Typography sx={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.45)', maxWidth: 140 }}>đang nghe…</Typography>
                            )}
                          </Box>
                        )}
                        <MuiButton size="small" variant="outlined" onClick={explainMore} sx={{ borderRadius: '7px', borderColor: 'rgba(255,255,255,0.2)', color: '#fff', fontWeight: 600, fontSize: '0.75rem', py: 0.4, px: 1.25, whiteSpace: 'nowrap', '&:hover': { borderColor: '#0277BD', color: '#4FC3F7' } }}>Giải thích</MuiButton>
                        <MuiButton size="small" variant="contained" onClick={ignoreDetection} sx={{ borderRadius: '7px', backgroundColor: 'rgba(245,158,11,0.85)', color: '#000', fontWeight: 700, fontSize: '0.75rem', py: 0.4, px: 1.25, whiteSpace: 'nowrap', '&:hover': { backgroundColor: '#F59E0B' } }}>Bỏ qua</MuiButton>
                      </Box>
                    )}
                  </VideoContainer>
                ) : isUploading ? (
                  <UploadingProgress fileName={videoFile?.name ?? ''} progress={uploadProgress} />
                ) : videoUrl ? (
                  /* Real video player with detection overlay */
                  <VideoContainer>
                    <video
                      ref={videoRef}
                      src={videoUrl}
                      controls
                      style={{
                        position: 'absolute',
                        inset: 0,
                        width: '100%',
                        height: '100%',
                        objectFit: 'contain',
                        zIndex: 1,
                      }}
                    />
                    {/* Detection action bar — shown when pipeline is paused */}
                    {pipelineState === 'PAUSED_WAITING_INPUT' && currentDetection && (
                      <Box
                        sx={{
                          position: 'absolute',
                          bottom: 0,
                          left: 0,
                          right: 0,
                          zIndex: 4,
                          px: 2,
                          py: 1.25,
                          backdropFilter: 'blur(14px)',
                          backgroundColor: 'rgba(13,17,23,0.82)',
                          borderTop: '1px solid rgba(245,158,11,0.25)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1.5,
                        }}
                      >
                        {/* Detection label */}
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flex: 1, minWidth: 0 }}>
                          <AlertTriangle size={14} color="#F59E0B" />
                          <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: '#FCD34D', whiteSpace: 'nowrap' }}>
                            {currentDetection.label}
                          </Typography>
                          <Typography sx={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.55)' }}>
                            {(currentDetection.confidence * 100).toFixed(0)}%
                          </Typography>
                        </Box>
                        {/* Mic status indicator */}
                        {voiceSupported && (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: isVoiceListening ? '#4FC3F7' : 'rgba(255,255,255,0.35)' }}>
                            {isVoiceListening
                              ? <Mic size={14} />
                              : <MicOff size={14} />
                            }
                            {isVoiceListening && (
                              <Typography sx={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.45)', maxWidth: 140 }}>đang nghe…</Typography>
                            )}
                          </Box>
                        )}
                        {/* Action buttons — change after LLM explained */}
                        {llmInsight ? (
                          <>
                            <MuiButton size="small" variant="contained" onClick={confirmDetection}
                              sx={{ borderRadius: '7px', backgroundColor: 'rgba(34,197,94,0.85)', color: '#000', fontWeight: 700, fontSize: '0.75rem', py: 0.4, px: 1.25, whiteSpace: 'nowrap', '&:hover': { backgroundColor: '#16A34A' } }}>
                              Xác nhận
                            </MuiButton>
                            <MuiButton size="small" variant="outlined" onClick={ignoreDetection}
                              sx={{ borderRadius: '7px', borderColor: 'rgba(255,255,255,0.2)', color: '#fff', fontWeight: 600, fontSize: '0.75rem', py: 0.4, px: 1.25, whiteSpace: 'nowrap', '&:hover': { borderColor: '#EF4444', color: '#FCA5A5' } }}>
                              Bỏ qua
                            </MuiButton>
                          </>
                        ) : (
                          <>
                            <MuiButton size="small" variant="outlined" onClick={explainMore}
                              sx={{ borderRadius: '7px', borderColor: 'rgba(255,255,255,0.2)', color: '#fff', fontWeight: 600, fontSize: '0.75rem', py: 0.4, px: 1.25, whiteSpace: 'nowrap', '&:hover': { borderColor: '#0277BD', color: '#4FC3F7' } }}>
                              Giải thích
                            </MuiButton>
                            <MuiButton size="small" variant="contained" onClick={ignoreDetection}
                              sx={{ borderRadius: '7px', backgroundColor: 'rgba(245,158,11,0.85)', color: '#000', fontWeight: 700, fontSize: '0.75rem', py: 0.4, px: 1.25, whiteSpace: 'nowrap', '&:hover': { backgroundColor: '#F59E0B' } }}>
                              Bỏ qua
                            </MuiButton>
                          </>
                        )}
                      </Box>
                    )}

                    {/* AI bbox overlay on top of video */}
                    {currentDetection && (
                      <BboxOverlay
                        initial={{ opacity: 0, scale: 0.94 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.2 }}
                        sx={{
                          zIndex: 2,
                          left: `${currentDetection.bbox.x}%`,
                          top: `${currentDetection.bbox.y}%`,
                          width: `${currentDetection.bbox.width}%`,
                          height: `${currentDetection.bbox.height}%`,
                        }}
                      >
                        <Box
                          sx={{
                            position: 'absolute',
                            top: -36,
                            left: 0,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 0.75,
                            px: 1.25,
                            py: 0.5,
                            borderRadius: '8px',
                            backdropFilter: 'blur(12px)',
                            backgroundColor: 'rgba(0,0,0,0.55)',
                            border: '1px solid rgba(245,158,11,0.4)',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          <Zap size={11} color="#F59E0B" />
                          <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: '#FCD34D' }}>
                            {currentDetection.label}
                          </Typography>
                          <Box sx={{ width: '1px', height: 12, backgroundColor: 'rgba(255,255,255,0.2)' }} />
                          <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: 'rgba(255,255,255,0.7)' }}>
                            {(currentDetection.confidence * 100).toFixed(0)}%
                          </Typography>
                        </Box>
                      </BboxOverlay>
                    )}
                  </VideoContainer>
                ) : (
                  /* Upload zone — no video yet */
                  <UploadZone onFileSelected={handleFileSelected} />
                )}
              </Box>
            </Box>

            {/* ── Voice / Whisper Transcript Panel ──────────────────────────── */}
            <Box
              sx={{
                backgroundColor: 'background.paper',
                borderRadius: '16px',
                border: '1px solid #E2EAE8',
                boxShadow: '0 2px 12px rgba(13,27,42,0.06)',
                overflow: 'hidden',
              }}
            >
              <Box sx={{ px: 2.5, py: 1.25, borderBottom: '1px solid #E2EAE8', display: 'flex', flexDirection: 'column', gap: 1, backgroundColor: '#F8FAFB' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                  <Box sx={{ width: 28, height: 28, borderRadius: '8px', backgroundColor: isVoiceListening ? 'rgba(2,119,189,0.12)' : 'rgba(154,165,177,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: isVoiceListening ? '#0277BD' : '#9AA5B1', transition: 'all 0.2s' }}>
                    {isVoiceListening ? <Mic size={14} /> : <MicOff size={14} />}
                  </Box>
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.primary', display: 'block' }}>
                      Voice Transcript
                    </Typography>
                    <Typography variant="caption" sx={{ color: micError ? '#EF4444' : 'text.secondary', fontSize: '0.7rem' }}>
                      {micError
                        ? `Lỗi mic: ${micError}`
                        : isVoiceListening
                          ? 'Đang nghe…'
                          : !voiceSupported
                            ? 'Trình duyệt không hỗ trợ SpeechRecognition'
                            : 'Bấm "Bắt đầu AI" để kích hoạt mic'}
                    </Typography>
                  </Box>
                </Box>
                {/* Audio level meter — single bar showing RMS amplitude */}
                <Box sx={{ height: 4, borderRadius: 2, backgroundColor: 'rgba(0,0,0,0.07)', overflow: 'hidden' }}>
                  <Box sx={{
                    height: '100%',
                    borderRadius: 2,
                    width: `${audioLevel * 100}%`,
                    backgroundColor: audioLevel > 0.6 ? '#EF4444' : audioLevel > 0.25 ? '#22C55E' : '#9AA5B1',
                    transition: 'width 80ms linear, background-color 150ms',
                  }} />
                </Box>
              </Box>
              <Box sx={{ p: 2, maxHeight: 130, overflowY: 'auto' }}>
                {transcriptLog.length === 0 ? (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'text.disabled', py: 1 }}>
                    <MicOff size={14} />
                    <Typography variant="caption">
                      Chưa có transcript. Nói &quot;bỏ qua&quot; hoặc &quot;giải thích&quot; khi AI dừng.
                    </Typography>
                  </Box>
                ) : (
                  transcriptLog.map((entry, i) => (
                    <Box key={i} sx={{ display: 'flex', alignItems: 'baseline', gap: 1.5, mb: 0.75, '&:last-child': { mb: 0 } }}>
                      <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', fontFamily: 'monospace', flexShrink: 0 }}>
                        {new Date(entry.ts).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </Typography>
                      <Box sx={{ width: 4, height: 4, borderRadius: '50%', backgroundColor: '#0277BD', flexShrink: 0, mt: 0.5 }} />
                      <Typography sx={{ fontSize: '0.8rem', color: 'text.primary', lineHeight: 1.5 }}>
                        {entry.text}
                      </Typography>
                    </Box>
                  ))
                )}
                <div ref={transcriptEndRef} />
              </Box>
            </Box>

            </Box>
          </Grid>

          {/* ── Control Panel ───────────────────────────────────────────────── */}
          <Grid size={{ xs: 12, lg: 4 }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5, height: '100%' }}>

              {/* Upload / Playback controls */}
              <Box
                sx={{
                  backgroundColor: 'background.paper',
                  borderRadius: '16px',
                  border: '1px solid #E2EAE8',
                  boxShadow: '0 2px 12px rgba(13,27,42,0.06)',
                  p: 2.5,
                }}
              >
                <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', letterSpacing: '0.05em', textTransform: 'uppercase', mb: 2, display: 'block' }}>
                  {videoUrl ? 'Điều khiển phân tích' : 'Tải video lên'}
                </Typography>

                {!videoUrl ? (
                  /* Upload CTA when no video */
                  <MuiButton
                    variant="outlined"
                    fullWidth
                    startIcon={<UploadCloud size={18} />}
                    onClick={() => {
                      // trigger the hidden file input inside UploadZone by dispatching a click to the panel
                      const input = document.createElement('input');
                      input.type = 'file';
                      input.accept = 'video/*';
                      input.onchange = (e) => {
                        const files = (e.target as HTMLInputElement).files;
                        if (files?.[0]) handleFileSelected(files[0]);
                      };
                      input.click();
                    }}
                    sx={{
                      borderRadius: '10px',
                      py: 1.5,
                      fontWeight: 700,
                      borderColor: '#006064',
                      color: '#006064',
                      '&:hover': { backgroundColor: 'rgba(0,96,100,0.06)', borderColor: '#004044' },
                    }}
                  >
                    Chọn file video
                  </MuiButton>
                ) : (
                  /* Playback controls after upload */
                  <Box sx={{ display: 'flex', gap: 1.5 }}>
                    <MuiButton
                      variant="contained"
                      fullWidth
                      disabled={isUploading || isPlaying || pipelineState === 'EOS_SUMMARY'}
                      onClick={() => {
                        startMockAnalysis();
                        videoRef.current?.play().catch(() => {});
                        console.log("[Workspace] Bắt đầu AI clicked, voiceSupported:", voiceSupported, "isVoiceListening:", isVoiceListening);
                        if (voiceSupported) startListening();
                      }}
                      startIcon={<Play size={17} />}
                      sx={{ borderRadius: '10px', py: 1.25, fontWeight: 700, fontSize: '0.875rem' }}
                    >
                      {pipelineState === 'EOS_SUMMARY' ? 'Hoàn tất' : isPlaying ? 'Đang phân tích…' : 'Bắt đầu AI'}
                    </MuiButton>
                    <MuiButton
                      variant="outlined"
                      fullWidth
                      disabled={!isPlaying && pipelineState === 'IDLE'}
                      onClick={handleStop}
                      startIcon={<Square size={17} />}
                      sx={{
                        borderRadius: '10px',
                        py: 1.25,
                        fontWeight: 700,
                        fontSize: '0.875rem',
                        borderColor: '#E2EAE8',
                        color: 'text.secondary',
                        '&:hover': { borderColor: '#006064', color: 'primary.main', backgroundColor: 'rgba(0,96,100,0.04)' },
                      }}
                    >
                      Dừng hẳn
                    </MuiButton>
                  </Box>
                )}
              </Box>

              {/* AI Detection Alert */}
              {currentDetection && (
                <MotionBox
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  sx={{
                    backgroundColor: 'rgba(245,158,11,0.06)',
                    borderRadius: '16px',
                    border: '1px solid rgba(245,158,11,0.25)',
                    p: 2.5,
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
                    <Box sx={{ width: 36, height: 36, borderRadius: '10px', backgroundColor: 'rgba(245,158,11,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#D97706', flexShrink: 0 }}>
                      <AlertTriangle size={18} />
                    </Box>
                    <Box>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#92400E' }}>
                        AI phát hiện bất thường
                      </Typography>
                      <Typography variant="caption" sx={{ color: '#B45309' }}>
                        {currentDetection.label} · Độ tin cậy {(currentDetection.confidence * 100).toFixed(0)}%
                      </Typography>
                    </Box>
                  </Box>
                  <Box sx={{ display: 'flex', gap: 1.25 }}>
                    {llmInsight ? (
                      <>
                        <MuiButton variant="outlined" fullWidth size="small" onClick={ignoreDetection}
                          sx={{ borderRadius: '8px', borderColor: 'rgba(245,158,11,0.35)', color: '#B45309', fontWeight: 600, py: 1, '&:hover': { backgroundColor: 'rgba(245,158,11,0.08)', borderColor: '#D97706' } }}>
                          Bỏ qua
                        </MuiButton>
                        <MuiButton variant="contained" fullWidth size="small" onClick={confirmDetection}
                          sx={{ borderRadius: '8px', backgroundColor: '#16A34A', fontWeight: 600, py: 1, boxShadow: '0 4px 12px rgba(22,163,74,0.3)', '&:hover': { backgroundColor: '#15803D' } }}>
                          Xác nhận
                        </MuiButton>
                      </>
                    ) : (
                      <>
                        <MuiButton variant="outlined" fullWidth size="small" onClick={ignoreDetection}
                          sx={{ borderRadius: '8px', borderColor: 'rgba(245,158,11,0.35)', color: '#B45309', fontWeight: 600, py: 1, '&:hover': { backgroundColor: 'rgba(245,158,11,0.08)', borderColor: '#D97706' } }}>
                          Bỏ qua
                        </MuiButton>
                        <MuiButton variant="contained" fullWidth size="small" onClick={explainMore}
                          sx={{ borderRadius: '8px', backgroundColor: '#D97706', fontWeight: 600, py: 1, boxShadow: '0 4px 12px rgba(217,119,6,0.3)', '&:hover': { backgroundColor: '#B45309' } }}>
                          Giải thích thêm
                        </MuiButton>
                      </>
                    )}
                  </Box>
                </MotionBox>
              )}

              {/* LLM Smart Log */}
              <Box
                sx={{
                  backgroundColor: 'background.paper',
                  borderRadius: '16px',
                  border: '1px solid #E2EAE8',
                  boxShadow: '0 2px 12px rgba(13,27,42,0.06)',
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                  minHeight: 200,
                }}
              >
                <Box sx={{ px: 2.5, py: 2, borderBottom: '1px solid #E2EAE8', display: 'flex', alignItems: 'center', gap: 1.5, backgroundColor: '#F8FAFB' }}>
                  <Box sx={{ width: 30, height: 30, borderRadius: '8px', backgroundColor: 'rgba(0,96,100,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'primary.main' }}>
                    <Bot size={16} />
                  </Box>
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.primary', display: 'block' }}>
                      LLM Smart Log
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
                      Phân tích ngữ nghĩa theo thời gian thực
                    </Typography>
                  </Box>
                  {isListeningVoice && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: '#0277BD' }}>
                      <CircularProgress size={12} thickness={5} sx={{ color: '#0277BD' }} />
                      <Typography variant="caption" sx={{ fontWeight: 600, color: '#0277BD', fontSize: '0.7rem' }}>
                        Đang phân tích
                      </Typography>
                    </Box>
                  )}
                </Box>

                <Box sx={{ p: 2.5, flex: 1, overflowY: 'auto' }}>
                  {isListeningVoice && !llmInsight ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                      <CircularProgress size={16} thickness={5} sx={{ color: '#0277BD' }} />
                      <Typography variant="caption" sx={{ color: '#0277BD', fontWeight: 500 }}>
                        Đang tải phân tích từ LLM...
                      </Typography>
                    </Box>
                  ) : llmInsight ? (
                    <MotionBox initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }}>
                      <Box sx={{
                        backgroundColor: 'rgba(0,96,100,0.05)',
                        borderRadius: '12px',
                        borderLeft: '3px solid #006064',
                        p: 2,
                        '& p': { margin: '0 0 8px', fontSize: '0.875rem', lineHeight: 1.75, color: 'text.primary' },
                        '& p:last-child': { marginBottom: 0 },
                        '& strong': { fontWeight: 700, color: '#004D40' },
                        '& ul, & ol': { paddingLeft: '1.25rem', margin: '4px 0 8px' },
                        '& li': { fontSize: '0.875rem', lineHeight: 1.7, color: 'text.primary', marginBottom: '2px' },
                      }}>
                        <ReactMarkdown>{llmInsight}</ReactMarkdown>
                      </Box>
                    </MotionBox>
                  ) : (
                    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', py: 4, gap: 1.5, color: 'text.disabled' }}>
                      <MicOff size={28} />
                      <Typography variant="caption" sx={{ textAlign: 'center', maxWidth: 180 }}>
                        Chưa có phân tích. Nhấn &quot;Giải thích thêm&quot; để kích hoạt.
                      </Typography>
                    </Box>
                  )}
                </Box>
              </Box>
            </Box>
          </Grid>
        </Grid>
      </Box>
    </Box>
  );
}
