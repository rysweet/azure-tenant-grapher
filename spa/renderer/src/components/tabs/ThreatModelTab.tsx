import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  Grid,
  Card,
  CardContent,
  Chip,
  LinearProgress,
} from '@mui/material';
import { Security as SecurityIcon, Assessment as AssessmentIcon, GetApp as ExportIcon } from '@mui/icons-material';
import axios from 'axios';

interface ThreatResult {
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  threats: Array<{
    id: string;
    name: string;
    description: string;
    severity: string;
    mitigation: string;
  }>;
  summary: string;
}

const ThreatModelTab: React.FC = () => {
  const [tenantId, setTenantId] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [results, setResults] = useState<ThreatResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  // Load environment configuration on component mount
  useEffect(() => {
    const loadEnvConfig = async () => {
      try {
        const response = await axios.get('http://localhost:3001/api/config/env');
        const envData = response.data;
        
        // Set tenant ID from .env if available and current value is empty
        if (envData.AZURE_TENANT_ID && !tenantId) {
          setTenantId(envData.AZURE_TENANT_ID);
        }
      } catch (err) {
        console.error('Failed to load env config:', err);
        // Silently fail - user can still manually enter tenant ID
      }
    };
    
    loadEnvConfig();
  }, [tenantId]);

  const handleAnalyze = async () => {
    if (!tenantId) {
      setError('Tenant ID is required');
      return;
    }

    setError(null);
    setIsAnalyzing(true);
    setResults(null);
    setProgress(0);

    try {
      const result = await window.electronAPI.cli.execute('threat-model', ['--tenant-id', tenantId]);
      
      let outputBuffer = '';
      window.electronAPI.on('process:output', (data: any) => {
        if (data.id === result.data.id) {
          outputBuffer += data.data.join('\n');
          
          // Update progress based on output
          if (outputBuffer.includes('Analyzing')) setProgress(25);
          if (outputBuffer.includes('Identifying')) setProgress(50);
          if (outputBuffer.includes('Assessing')) setProgress(75);
          if (outputBuffer.includes('Complete')) setProgress(100);
        }
      });

      window.electronAPI.on('process:exit', (data: any) => {
        if (data.id === result.data.id) {
          setIsAnalyzing(false);
          if (data.code === 0) {
            // Parse results from output buffer
            try {
              // Look for JSON output in the buffer
              const jsonMatch = outputBuffer.match(/\{[\s\S]*"threats"[\s\S]*\}/);
              if (jsonMatch) {
                const parsedResults = JSON.parse(jsonMatch[0]);
                setResults(parsedResults);
              } else {
                // Fallback: create results from output analysis
                const threats = [];
                let threatId = 1;
                
                // Parse common threat patterns from output
                if (outputBuffer.includes('Excessive permissions') || outputBuffer.includes('broad access')) {
                  threats.push({
                    id: String(threatId++),
                    name: 'Excessive Permissions',
                    description: 'Service principals or users have overly broad access rights',
                    severity: 'high',
                    mitigation: 'Implement least privilege principle and review permissions',
                  });
                }
                
                if (outputBuffer.includes('No MFA') || outputBuffer.includes('multi-factor')) {
                  threats.push({
                    id: String(threatId++),
                    name: 'Missing Multi-Factor Authentication',
                    description: 'Accounts without MFA are vulnerable to credential attacks',
                    severity: 'high',
                    mitigation: 'Enable MFA for all privileged accounts',
                  });
                }
                
                if (outputBuffer.includes('stale') || outputBuffer.includes('unused')) {
                  threats.push({
                    id: String(threatId++),
                    name: 'Stale Resources',
                    description: 'Unused resources increase attack surface',
                    severity: 'medium',
                    mitigation: 'Remove or disable unused resources',
                  });
                }
                
                // Determine risk level based on threats found
                const highSeverityCount = threats.filter(t => t.severity === 'high').length;
                let riskLevel = 'low';
                if (highSeverityCount >= 2) riskLevel = 'high';
                else if (highSeverityCount === 1 || threats.length >= 2) riskLevel = 'medium';
                
                setResults({
                  riskLevel,
                  threats: threats.length > 0 ? threats : [{
                    id: '1',
                    name: 'No Critical Issues Found',
                    description: 'Security posture appears acceptable',
                    severity: 'low',
                    mitigation: 'Continue monitoring and regular reviews',
                  }],
                  summary: `Analysis complete. Found ${threats.length} potential security issues.`,
                });
              }
            } catch (parseError) {
              console.error('Failed to parse threat model results:', parseError);
              setError('Failed to parse analysis results');
            }
          } else {
            setError(`Analysis failed with exit code ${data.code}`);
          }
        }
      });
      
    } catch (err: any) {
      setError(err.message);
      setIsAnalyzing(false);
    }
  };

  const handleExport = async () => {
    if (!results) return;

    try {
      const filePath = await window.electronAPI.dialog.saveFile({
        defaultPath: 'threat-model-report.json',
        filters: [
          { name: 'JSON', extensions: ['json'] },
          { name: 'All Files', extensions: ['*'] }
        ]
      });

      if (filePath) {
        await window.electronAPI.file.write(filePath, JSON.stringify(results, null, 2));
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'low': return 'success';
      case 'medium': return 'warning';
      case 'high': return 'error';
      case 'critical': return 'error';
      default: return 'default';
    }
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h5" gutterBottom>
          Threat Model Analysis
        </Typography>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Tenant ID"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              disabled={isAnalyzing}
              helperText="Azure AD Tenant ID to analyze"
              required
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <Button
                variant="contained"
                color="primary"
                startIcon={<SecurityIcon />}
                onClick={handleAnalyze}
                disabled={isAnalyzing || !tenantId}
                size="large"
              >
                {isAnalyzing ? 'Analyzing...' : 'Analyze Threats'}
              </Button>
              
              {results && (
                <Button
                  variant="outlined"
                  startIcon={<ExportIcon />}
                  onClick={handleExport}
                >
                  Export Report
                </Button>
              )}
            </Box>
          </Grid>
        </Grid>

        {isAnalyzing && (
          <Box sx={{ mt: 2 }}>
            <LinearProgress variant="determinate" value={progress} />
            <Typography variant="caption" color="text.secondary">
              Analyzing security posture... {progress}%
            </Typography>
          </Box>
        )}
      </Paper>

      {results && (
        <Box sx={{ flex: 1, overflow: 'auto', px: 2 }}>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Risk Assessment
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Chip
                      label={`Overall Risk: ${results.riskLevel.toUpperCase()}`}
                      color={getRiskColor(results.riskLevel) as any}
                      size="medium"
                    />
                    <Typography variant="body2" color="text.secondary">
                      {results.summary}
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {results.threats.map((threat) => (
              <Grid item xs={12} md={6} key={threat.id}>
                <Card>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="h6">{threat.name}</Typography>
                      <Chip
                        label={threat.severity}
                        color={getRiskColor(threat.severity) as any}
                        size="small"
                      />
                    </Box>
                    <Typography variant="body2" color="text.secondary" paragraph>
                      {threat.description}
                    </Typography>
                    <Typography variant="body2">
                      <strong>Mitigation:</strong> {threat.mitigation}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}
    </Box>
  );
};

export default ThreatModelTab;