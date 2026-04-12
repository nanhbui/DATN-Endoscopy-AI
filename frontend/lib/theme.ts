import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#006064',
      light: '#00838F',
      dark: '#004044',
      contrastText: '#fff',
    },
    secondary: {
      main: '#0277BD',
      light: '#0288D1',
      dark: '#01579B',
      contrastText: '#fff',
    },
    success: {
      main: '#2E7D32',
      light: '#4CAF50',
      dark: '#1B5E20',
    },
    warning: {
      main: '#F59E0B',
      light: '#FCD34D',
      dark: '#D97706',
    },
    error: {
      main: '#DC2626',
      light: '#EF4444',
      dark: '#B91C1C',
    },
    info: {
      main: '#0277BD',
      light: '#0288D1',
      dark: '#01579B',
    },
    background: {
      default: '#F4F7F6',
      paper: '#FFFFFF',
    },
    text: {
      primary: '#0D1B2A',
      secondary: '#4A5568',
      disabled: '#9AA5B1',
    },
    divider: '#E2EAE8',
  },
  typography: {
    fontFamily: 'var(--font-inter), "Inter", "Segoe UI", system-ui, -apple-system, sans-serif',
    h1: { fontSize: '2.5rem', fontWeight: 700, lineHeight: 1.2 },
    h2: { fontSize: '2rem', fontWeight: 700, lineHeight: 1.3 },
    h3: { fontSize: '1.5rem', fontWeight: 600, lineHeight: 1.4 },
    h4: { fontSize: '1.25rem', fontWeight: 600, lineHeight: 1.4 },
    h5: { fontSize: '1rem', fontWeight: 600 },
    h6: { fontSize: '0.875rem', fontWeight: 600 },
    body1: { fontSize: '1rem', lineHeight: 1.6 },
    body2: { fontSize: '0.875rem', lineHeight: 1.5 },
    button: { textTransform: 'none', fontWeight: 600 },
    subtitle1: { fontSize: '1rem', fontWeight: 500, lineHeight: 1.75 },
    subtitle2: { fontSize: '0.875rem', fontWeight: 500, lineHeight: 1.57 },
    caption: { fontSize: '0.75rem', lineHeight: 1.66 },
    overline: { fontSize: '0.75rem', fontWeight: 600, lineHeight: 2.66 },
  },
  shape: { borderRadius: 12 },
  spacing: 8,
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          borderRadius: 10,
          padding: '10px 20px',
          letterSpacing: '0.01em',
        },
        contained: {
          boxShadow: '0 4px 14px rgba(0,96,100,0.25)',
          '&:hover': { boxShadow: '0 6px 20px rgba(0,96,100,0.35)' },
        },
        sizeLarge: { padding: '12px 28px', fontSize: '0.9375rem' },
        sizeSmall: { padding: '6px 14px', fontSize: '0.8125rem' },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          border: '1px solid #E2EAE8',
          boxShadow: '0 2px 12px rgba(13,27,42,0.06)',
          borderRadius: 16,
        },
      },
    },
    MuiAppBar: {
      styleOverrides: { root: { boxShadow: 'none' } },
    },
    MuiPaper: {
      styleOverrides: { root: { backgroundImage: 'none' } },
    },
    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: 10 },
      },
    },
  },
});
