'use client';

import { motion as framMotion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Microscope } from 'lucide-react';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import { styled } from '@mui/material/styles';

const HeroSection = styled(Box)(({ theme }) => ({
  minHeight: '60vh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
  color: theme.palette.common.white,
  marginBottom: theme.spacing(6),
  position: 'relative',
  overflow: 'hidden',
}));

const HeroContent = styled(Box)(({ theme }) => ({
  textAlign: 'center',
  maxWidth: 800,
  zIndex: 1,
}));

const MotionBox = framMotion(HeroContent);

export default function Hero() {
  return (
    <HeroSection>
      <MotionBox
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
      >
        <Box sx={{ mb: 3, display: 'flex', justifyContent: 'center' }}>
          <Microscope size={80} />
        </Box>
        <Typography
          variant="h1"
          component="h1"
          sx={{
            fontSize: { xs: '2rem', sm: '2.5rem', md: '3rem' },
            fontWeight: 700,
            mb: 2,
          }}
        >
          Nội soi Y tế Thông minh
        </Typography>
        <Typography
          variant="body1"
          sx={{
            fontSize: { xs: '0.95rem', md: '1.1rem' },
            mb: 4,
            maxWidth: 600,
            mx: 'auto',
            lineHeight: 1.6,
          }}
        >
          Nền tảng AI hỗ trợ phân tích video nội soi, phát hiện bất thường và cung cấp giải thích chi tiết.
        </Typography>
        <Button
          variant="contained"
          size="large"
          sx={{
            backgroundColor: '#fff',
            color: 'primary.main',
            fontWeight: 600,
            '&:hover': {
              backgroundColor: '#f0f0f0',
            },
          }}
          onClick={() => {
            /* start analysis */
          }}
        >
          Bắt đầu Phân tích
        </Button>
      </MotionBox>
    </HeroSection>
  );
}
