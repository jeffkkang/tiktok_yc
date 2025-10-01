const express = require('express');
const { GoogleAuth } = require('google-auth-library');
const axios = require('axios');

const app = express();
const port = process.env.PORT || 8080;

// Environment variables
const ANALYZER_URL = process.env.ANALYZER_URL;
const ANALYZER_AUDIENCE = process.env.ANALYZER_AUDIENCE || ANALYZER_URL;
const APP_TOKEN = process.env.APP_TOKEN;

if (!ANALYZER_URL || !APP_TOKEN) {
  console.error('Missing required environment variables: ANALYZER_URL, APP_TOKEN');
  process.exit(1);
}

// Middleware
app.use(express.json());

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'tiktok-analyzer-proxy' });
});

// Token verification middleware
const verifyToken = (req, res, next) => {
  const authHeader = req.headers.authorization;
  
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing or invalid authorization header' });
  }
  
  const token = authHeader.substring(7);
  if (token !== APP_TOKEN) {
    return res.status(403).json({ error: 'Invalid token' });
  }
  
  next();
};

// Metadata-only endpoint (optimized)
app.post('/metadata-only', verifyToken, async (req, res) => {
  const startTime = Date.now();
  const requestId = Math.random().toString(36).substring(7);
  
  console.log(`[${requestId}] Metadata-only request started`, { 
    url: req.body.url
  });

  try {
    // Initialize Google Auth
    const auth = new GoogleAuth();
    const client = await auth.getIdTokenClient(ANALYZER_AUDIENCE);
    
    // Call the metadata-only endpoint on analyzer
    const response = await client.request({
      url: `${ANALYZER_URL}/metadata-only`,
      method: 'POST',
      data: {
        url: req.body.url,
        comments: false
      }
    });

    const duration = Date.now() - startTime;
    
    console.log(`[${requestId}] Metadata-only request completed`, {
      url: req.body.url,
      duration: `${duration}ms`,
      filesCount: response.data.files?.length || 0
    });

    return res.json(response.data);

  } catch (error) {
    const duration = Date.now() - startTime;
    console.error(`[${requestId}] Metadata-only request failed`, {
      url: req.body.url,
      duration: `${duration}ms`,
      error: error.message
    });

    if (error.response) {
      return res.status(error.response.status).json({
        error: 'Analyzer error',
        message: error.response.data?.detail || error.message
      });
    }

    return res.status(500).json({
      error: 'Internal server error',
      message: error.message
    });
  }
});

// Comments-only endpoint (optimized)
app.post('/comments-only', verifyToken, async (req, res) => {
  const startTime = Date.now();
  const requestId = Math.random().toString(36).substring(7);
  
  console.log(`[${requestId}] Comments-only request started`, { 
    url: req.body.url
  });

  try {
    // Initialize Google Auth
    const auth = new GoogleAuth();
    const client = await auth.getIdTokenClient(ANALYZER_AUDIENCE);
    
    // Call the comments-only endpoint on analyzer
    const response = await client.request({
      url: `${ANALYZER_URL}/comments-only`,
      method: 'POST',
      data: {
        url: req.body.url,
        comments: true
      }
    });

    const duration = Date.now() - startTime;
    
    console.log(`[${requestId}] Comments-only request completed`, {
      url: req.body.url,
      duration: `${duration}ms`,
      filesCount: response.data.files?.length || 0
    });

    return res.json(response.data);

  } catch (error) {
    const duration = Date.now() - startTime;
    console.error(`[${requestId}] Comments-only request failed`, {
      url: req.body.url,
      duration: `${duration}ms`,
      error: error.message
    });

    if (error.response) {
      return res.status(error.response.status).json({
        error: 'Analyzer error',
        message: error.response.data?.detail || error.message
      });
    }

    return res.status(500).json({
      error: 'Internal server error',
      message: error.message
    });
  }
});

// Video-only endpoint (optimized)
app.post('/video-only', verifyToken, async (req, res) => {
  const startTime = Date.now();
  const requestId = Math.random().toString(36).substring(7);
  
  console.log(`[${requestId}] Video-only request started`, { 
    url: req.body.url
  });

  try {
    // Initialize Google Auth
    const auth = new GoogleAuth();
    const client = await auth.getIdTokenClient(ANALYZER_AUDIENCE);
    
    // Call the video-only endpoint on analyzer
    const response = await client.request({
      url: `${ANALYZER_URL}/video-only`,
      method: 'POST',
      data: {
        url: req.body.url,
        comments: false
      }
    });

    const duration = Date.now() - startTime;
    
    console.log(`[${requestId}] Video-only request completed`, {
      url: req.body.url,
      duration: `${duration}ms`,
      filesCount: response.data.files?.length || 0
    });

    return res.json(response.data);

  } catch (error) {
    const duration = Date.now() - startTime;
    console.error(`[${requestId}] Video-only request failed`, {
      url: req.body.url,
      duration: `${duration}ms`,
      error: error.message
    });

    if (error.response) {
      return res.status(error.response.status).json({
        error: 'Analyzer error',
        message: error.response.data?.detail || error.message
      });
    }

    return res.status(500).json({
      error: 'Internal server error',
      message: error.message
    });
  }
});

// Main proxy endpoint
app.post('/analyze', verifyToken, async (req, res) => {
  const startTime = Date.now();
  const requestId = Math.random().toString(36).substring(7);
  
  console.log(`[${requestId}] Proxy request started`, { 
    url: req.body.url,
    comments: req.body.comments 
  });

  try {
    // Initialize Google Auth
    const auth = new GoogleAuth();
    const client = await auth.getIdTokenClient(ANALYZER_AUDIENCE);
    
    // Forward request to analyzer with OIDC token
    const response = await client.request({
      url: `${ANALYZER_URL}/analyze`,
      method: 'POST',
      data: req.body,
      timeout: 900000, // 15 minutes
      validateStatus: () => true // Don't throw on non-2xx status
    });
    
    const duration = Date.now() - startTime;
    console.log(`[${requestId}] Proxy request completed`, {
      status: response.status,
      duration: `${duration}ms`
    });
    
    // Forward the response
    res.status(response.status).json(response.data);
    
  } catch (error) {
    const duration = Date.now() - startTime;
    console.error(`[${requestId}] Proxy request failed`, {
      error: error.message,
      duration: `${duration}ms`
    });
    
    if (error.code === 'ECONNABORTED') {
      res.status(504).json({ error: 'Gateway timeout' });
    } else if (error.response) {
      res.status(error.response.status).json(error.response.data);
    } else {
      res.status(500).json({ error: 'Internal proxy error' });
    }
  }
});

// GCS download proxy endpoint
app.get('/proxy/download', verifyToken, async (req, res) => {
  const startTime = Date.now();
  const requestId = Math.random().toString(36).substring(7);
  const { gcs, filename } = req.query;
  
  if (!gcs || !gcs.startsWith('gs://')) {
    return res.status(400).json({ error: 'Invalid gcs parameter' });
  }
  
  console.log(`[${requestId}] Download request started`, { gcs, filename });

  try {
    // Parse GCS URL: gs://bucket/path/to/file
    const gcsUrl = gcs.replace('gs://', '');
    const [bucket, ...pathParts] = gcsUrl.split('/');
    const objectPath = pathParts.join('/');
    
    if (!bucket || !objectPath) {
      return res.status(400).json({ error: 'Invalid GCS URL format' });
    }
    
    // Initialize Google Auth for GCS access
    const auth = new GoogleAuth({
      scopes: ['https://www.googleapis.com/auth/devstorage.read_only']
    });
    const authClient = await auth.getClient();
    const accessToken = await authClient.getAccessToken();
    
    // Stream from GCS using the Storage API
    const gcsApiUrl = `https://storage.googleapis.com/storage/v1/b/${bucket}/o/${encodeURIComponent(objectPath)}?alt=media`;
    
    const response = await axios({
      method: 'GET',
      url: gcsApiUrl,
      headers: {
        'Authorization': `Bearer ${accessToken.token}`
      },
      responseType: 'stream',
      timeout: 900000 // 15 minutes
    });
    
    // Set appropriate headers for download
    const downloadFilename = filename || objectPath.split('/').pop() || 'download';
    res.setHeader('Content-Type', response.headers['content-type'] || 'application/octet-stream');
    res.setHeader('Content-Disposition', `attachment; filename="${downloadFilename}"`);
    
    if (response.headers['content-length']) {
      res.setHeader('Content-Length', response.headers['content-length']);
    }
    
    // Pipe the response stream
    response.data.pipe(res);
    
    response.data.on('end', () => {
      const duration = Date.now() - startTime;
      console.log(`[${requestId}] Download completed`, {
        gcs,
        filename: downloadFilename,
        duration: `${duration}ms`
      });
    });
    
    response.data.on('error', (error) => {
      const duration = Date.now() - startTime;
      console.error(`[${requestId}] Download stream error`, {
        gcs,
        error: error.message,
        duration: `${duration}ms`
      });
      if (!res.headersSent) {
        res.status(500).json({ error: 'Stream error' });
      }
    });
    
  } catch (error) {
    const duration = Date.now() - startTime;
    console.error(`[${requestId}] Download request failed`, {
      gcs,
      error: error.message,
      duration: `${duration}ms`
    });
    
    if (!res.headersSent) {
      if (error.response) {
        res.status(error.response.status).json({ 
          error: `GCS error: ${error.response.status}` 
        });
      } else {
        res.status(500).json({ error: 'Internal download error' });
      }
    }
  }
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({ error: 'Not found' });
});

// Error handler
app.use((error, req, res, next) => {
  console.error('Unhandled error:', error);
  res.status(500).json({ error: 'Internal server error' });
});

app.listen(port, '0.0.0.0', () => {
  console.log(`TikTok Analyzer Proxy listening on port ${port}`);
  console.log(`Analyzer URL: ${ANALYZER_URL}`);
  console.log(`Analyzer Audience: ${ANALYZER_AUDIENCE}`);
});
