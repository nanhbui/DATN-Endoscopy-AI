import Link from 'next/link';
import { Microscope } from 'lucide-react';

import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import MuiLink from '@mui/material/Link';

export default function Footer() {
  return (
    <Box
      component="footer"
      sx={{
        marginTop: 'auto',
        borderTop: '1px solid',
        borderColor: 'divider',
        backgroundColor: 'rgba(244,248,247,0.88)',
        backdropFilter: 'blur(8px)',
      }}
    >
      <Container maxWidth="lg">
        <Box
          sx={{
            display: 'flex',
            gap: 3,
            flexDirection: { xs: 'column', lg: 'row' },
            alignItems: { xs: 'flex-start', lg: 'center' },
            justifyContent: { lg: 'space-between' },
            py: 3,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, fontWeight: 500, color: 'text.secondary' }}>
            <Microscope size={16} color="currentColor" />
            <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 500 }}>
              AI Endoscopy Frontend Scaffold
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
            <MuiLink component={Link} href="/workspace" underline="none" color="inherit" sx={{ '&:hover': { color: 'text.primary' } }}>
              Workspace
            </MuiLink>
            <MuiLink component={Link} href="/report" underline="none" color="inherit" sx={{ '&:hover': { color: 'text.primary' } }}>
              Báo cáo
            </MuiLink>
          </Box>

          <Typography variant="body2" color="textSecondary">
            © 2026 Phòng khám nội soi thông minh
          </Typography>
        </Box>
      </Container>
    </Box>
  );
}
