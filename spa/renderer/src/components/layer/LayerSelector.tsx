import React, { useState } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
  Tooltip,
  Chip,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Add as AddIcon,
  Layers as LayersIcon,
  CheckCircle as ActiveIcon,
} from '@mui/icons-material';
import { useLayer } from '../../context/LayerContext';

interface LayerSelectorProps {
  compact?: boolean;
  showCreateButton?: boolean;
  showRefreshButton?: boolean;
  onChange?: (layerId: string) => void;
}

const LayerSelector: React.FC<LayerSelectorProps> = ({
  compact = false,
  showCreateButton = true,
  showRefreshButton = true,
  onChange,
}) => {
  const { state, setActiveLayer, refreshLayers } = useLayer();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleLayerChange = async (event: any) => {
    const layerId = event.target.value as string;

    try {
      await setActiveLayer(layerId);
      if (onChange) {
        onChange(layerId);
      }
    } catch (error) {
      console.error('Failed to change layer:', error);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await refreshLayers();
    } finally {
      setIsRefreshing(false);
    }
  };

  // Get the selected layer ID (prefer selected, fallback to active)
  const selectedLayerId = state.selectedLayer?.layer_id || state.activeLayer?.layer_id || '';

  // Format layer display name
  const formatLayerName = (layer: any) => {
    const parts = [layer.name];
    if (layer.is_baseline) {
      parts.push('(Baseline)');
    }
    if (layer.node_count > 0) {
      parts.push(`- ${layer.node_count.toLocaleString()} nodes`);
    }
    return parts.join(' ');
  };

  // Compact mode - minimal selector for header
  if (compact) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 200 }}>
        <LayersIcon sx={{ fontSize: 20, color: 'text.secondary' }} />
        <FormControl size="small" fullWidth>
          <Select
            value={selectedLayerId}
            onChange={handleLayerChange}
            displayEmpty
            disabled={state.isLoading}
            sx={{
              minWidth: 150,
              fontSize: '0.875rem',
              '& .MuiSelect-select': {
                py: 0.5,
              },
            }}
          >
            {state.layers.length === 0 ? (
              <MenuItem value="" disabled>
                No layers available
              </MenuItem>
            ) : (
              state.layers.map((layer) => (
                <MenuItem key={layer.layer_id} value={layer.layer_id}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {layer.is_active && (
                      <ActiveIcon sx={{ fontSize: 16, color: 'success.main' }} />
                    )}
                    <Typography variant="body2">{layer.name}</Typography>
                    {layer.is_baseline && (
                      <Chip label="Baseline" size="small" sx={{ height: 16, fontSize: '0.625rem' }} />
                    )}
                  </Box>
                </MenuItem>
              ))
            )}
          </Select>
        </FormControl>

        {showRefreshButton && (
          <Tooltip title="Refresh layers">
            <IconButton size="small" onClick={handleRefresh} disabled={isRefreshing}>
              {isRefreshing ? <CircularProgress size={18} /> : <RefreshIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
        )}
      </Box>
    );
  }

  // Full mode - detailed selector for main content
  return (
    <Box sx={{ width: '100%' }}>
      {state.error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {state.error}
        </Alert>
      )}

      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
        <FormControl fullWidth>
          <InputLabel id="layer-selector-label">Active Layer</InputLabel>
          <Select
            labelId="layer-selector-label"
            value={selectedLayerId}
            label="Active Layer"
            onChange={handleLayerChange}
            disabled={state.isLoading}
            startAdornment={
              state.selectedLayer?.is_active ? (
                <ActiveIcon sx={{ ml: 1, color: 'success.main', fontSize: 20 }} />
              ) : null
            }
          >
            {state.layers.length === 0 ? (
              <MenuItem value="" disabled>
                <em>No layers available - create one to get started</em>
              </MenuItem>
            ) : (
              state.layers.map((layer) => (
                <MenuItem key={layer.layer_id} value={layer.layer_id}>
                  <Box sx={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body1" sx={{ fontWeight: layer.is_active ? 600 : 400 }}>
                        {layer.name}
                      </Typography>
                      {layer.is_active && (
                        <Chip
                          label="Active"
                          size="small"
                          color="success"
                          icon={<ActiveIcon />}
                        />
                      )}
                      {layer.is_baseline && (
                        <Chip label="Baseline" size="small" color="primary" />
                      )}
                      {layer.is_locked && (
                        <Chip label="Locked" size="small" color="error" />
                      )}
                    </Box>

                    <Typography variant="caption" color="text.secondary">
                      {layer.layer_id} • {layer.layer_type} • {layer.node_count.toLocaleString()} nodes
                    </Typography>

                    {layer.description && (
                      <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                        {layer.description.length > 60
                          ? `${layer.description.substring(0, 60)}...`
                          : layer.description}
                      </Typography>
                    )}
                  </Box>
                </MenuItem>
              ))
            )}
          </Select>
        </FormControl>

        <Box sx={{ display: 'flex', gap: 1, pt: 1 }}>
          {showRefreshButton && (
            <Tooltip title="Refresh layers">
              <IconButton onClick={handleRefresh} disabled={isRefreshing}>
                {isRefreshing ? <CircularProgress size={24} /> : <RefreshIcon />}
              </IconButton>
            </Tooltip>
          )}

          {showCreateButton && (
            <Tooltip title="Create new layer">
              <IconButton color="primary">
                <AddIcon />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </Box>

      {/* Layer Info */}
      {state.selectedLayer && (
        <Box sx={{ mt: 2, p: 2, bgcolor: 'background.paper', borderRadius: 1, border: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle2" gutterBottom>
            Selected Layer Details
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 1, fontSize: '0.875rem' }}>
            <Typography variant="body2" color="text.secondary">
              ID:
            </Typography>
            <Typography variant="body2">{state.selectedLayer.layer_id}</Typography>

            <Typography variant="body2" color="text.secondary">
              Type:
            </Typography>
            <Typography variant="body2">{state.selectedLayer.layer_type}</Typography>

            <Typography variant="body2" color="text.secondary">
              Created:
            </Typography>
            <Typography variant="body2">
              {new Date(state.selectedLayer.created_at).toLocaleString()}
            </Typography>

            <Typography variant="body2" color="text.secondary">
              Resources:
            </Typography>
            <Typography variant="body2">
              {state.selectedLayer.node_count.toLocaleString()} nodes •{' '}
              {state.selectedLayer.relationship_count.toLocaleString()} relationships
            </Typography>

            {state.selectedLayer.parent_layer_id && (
              <>
                <Typography variant="body2" color="text.secondary">
                  Parent:
                </Typography>
                <Typography variant="body2">{state.selectedLayer.parent_layer_id}</Typography>
              </>
            )}
          </Box>
        </Box>
      )}

      {/* Loading indicator */}
      {state.isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
          <CircularProgress size={24} />
        </Box>
      )}
    </Box>
  );
};

export default LayerSelector;
