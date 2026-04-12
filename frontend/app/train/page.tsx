import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';

export default function TrainPage() {
  return (
    <Box sx={{ minHeight: 'calc(100vh - 130px)', py: 4, px: { xs: 2, lg: 4 } }}>
      <Container maxWidth="lg">
        <Typography variant="h4" component="h1" sx={{ fontWeight: 600, mb: 2 }}>
          Train Model
        </Typography>
        <Typography variant="body1" color="textSecondary">
          Here you can configure and start a new LLaVA fine‑tuning job.
        </Typography>
        {/* TODO: add form components */}
      </Container>
    </Box>
  );
}
