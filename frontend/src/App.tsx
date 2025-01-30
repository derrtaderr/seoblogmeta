import React, { useState } from 'react';
import {
  Container,
  TextField,
  Button,
  Paper,
  Typography,
  Box,
  CircularProgress,
  Alert,
} from '@mui/material';
import axios from 'axios';

function App() {
  const [sitemapUrl, setSitemapUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleAnalyze = async () => {
    if (!sitemapUrl) {
      setError('Please enter a sitemap URL');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await axios.post('http://localhost:8000/analyze-sitemap', {
        url: sitemapUrl
      });

      if (response.data.status === 'success') {
        setSuccess(`Successfully analyzed ${response.data.analyzed_count} blogs! Check the generated Excel file.`);
      }
    } catch (err) {
      setError('Error analyzing sitemap. Please check the URL and try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ my: 4 }}>
        <Typography variant="h3" component="h1" gutterBottom align="center">
          SEO Blog Meta Analyzer
        </Typography>
        
        <Paper elevation={3} sx={{ p: 4, mt: 4 }}>
          <Typography variant="body1" gutterBottom>
            Enter your sitemap URL below to analyze your blog content and generate SEO-optimized summaries.
          </Typography>

          <TextField
            fullWidth
            label="Sitemap URL"
            variant="outlined"
            value={sitemapUrl}
            onChange={(e) => setSitemapUrl(e.target.value)}
            sx={{ mt: 2 }}
            placeholder="https://example.com/sitemap.xml"
          />

          <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
            <Button
              variant="contained"
              color="primary"
              onClick={handleAnalyze}
              disabled={loading}
              size="large"
            >
              {loading ? (
                <>
                  <CircularProgress size={24} color="inherit" sx={{ mr: 1 }} />
                  Analyzing...
                </>
              ) : (
                'Analyze Blogs'
              )}
            </Button>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}

          {success && (
            <Alert severity="success" sx={{ mt: 2 }}>
              {success}
            </Alert>
          )}
        </Paper>
      </Box>
    </Container>
  );
}

export default App;
