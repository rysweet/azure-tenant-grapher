import React, { createContext, useContext, useReducer, useEffect, ReactNode } from 'react';
import axios from 'axios';

export interface Layer {
  layer_id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string | null;
  created_by: string;
  parent_layer_id: string | null;
  is_active: boolean;
  is_baseline: boolean;
  is_locked: boolean;
  tenant_id: string;
  subscription_ids: string[];
  node_count: number;
  relationship_count: number;
  layer_type: 'baseline' | 'scaled' | 'experimental' | 'snapshot';
  metadata: Record<string, any>;
  tags: string[];
}

interface LayerState {
  layers: Layer[];
  activeLayer: Layer | null;
  selectedLayer: Layer | null;
  isLoading: boolean;
  error: string | null;
  lastFetch: Date | null;
}

type LayerAction =
  | { type: 'SET_LAYERS'; payload: Layer[] }
  | { type: 'SET_ACTIVE_LAYER'; payload: Layer | null }
  | { type: 'SET_SELECTED_LAYER'; payload: Layer | null }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'ADD_LAYER'; payload: Layer }
  | { type: 'UPDATE_LAYER'; payload: Layer }
  | { type: 'REMOVE_LAYER'; payload: string }
  | { type: 'REFRESH_SUCCESS'; payload: { layers: Layer[]; activeLayer: Layer | null } };

const initialState: LayerState = {
  layers: [],
  activeLayer: null,
  selectedLayer: null,
  isLoading: false,
  error: null,
  lastFetch: null,
};

function layerReducer(state: LayerState, action: LayerAction): LayerState {
  switch (action.type) {
    case 'SET_LAYERS':
      return {
        ...state,
        layers: action.payload,
        error: null,
      };

    case 'SET_ACTIVE_LAYER':
      return {
        ...state,
        activeLayer: action.payload,
        // Auto-select active layer if no layer is selected
        selectedLayer: state.selectedLayer || action.payload,
        error: null,
      };

    case 'SET_SELECTED_LAYER':
      return {
        ...state,
        selectedLayer: action.payload,
      };

    case 'SET_LOADING':
      return {
        ...state,
        isLoading: action.payload,
      };

    case 'SET_ERROR':
      return {
        ...state,
        error: action.payload,
        isLoading: false,
      };

    case 'ADD_LAYER':
      return {
        ...state,
        layers: [...state.layers, action.payload],
        error: null,
      };

    case 'UPDATE_LAYER':
      return {
        ...state,
        layers: state.layers.map(layer =>
          layer.layer_id === action.payload.layer_id ? action.payload : layer
        ),
        activeLayer:
          state.activeLayer?.layer_id === action.payload.layer_id
            ? action.payload
            : state.activeLayer,
        selectedLayer:
          state.selectedLayer?.layer_id === action.payload.layer_id
            ? action.payload
            : state.selectedLayer,
        error: null,
      };

    case 'REMOVE_LAYER':
      return {
        ...state,
        layers: state.layers.filter(layer => layer.layer_id !== action.payload),
        activeLayer:
          state.activeLayer?.layer_id === action.payload ? null : state.activeLayer,
        selectedLayer:
          state.selectedLayer?.layer_id === action.payload ? null : state.selectedLayer,
        error: null,
      };

    case 'REFRESH_SUCCESS':
      return {
        ...state,
        layers: action.payload.layers,
        activeLayer: action.payload.activeLayer,
        selectedLayer: state.selectedLayer || action.payload.activeLayer,
        isLoading: false,
        error: null,
        lastFetch: new Date(),
      };

    default:
      return state;
  }
}

interface LayerContextValue {
  state: LayerState;
  dispatch: React.Dispatch<LayerAction>;
  refreshLayers: () => Promise<void>;
  setActiveLayer: (layerId: string) => Promise<void>;
  createLayer: (
    layerId: string,
    name: string,
    description: string,
    layerType?: string
  ) => Promise<Layer>;
  deleteLayer: (layerId: string, force?: boolean) => Promise<void>;
}

const LayerContext = createContext<LayerContextValue | undefined>(undefined);

const API_BASE_URL = 'http://localhost:3001/api';

export function LayerProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(layerReducer, initialState);

  // Fetch layers from backend
  const refreshLayers = async () => {
    dispatch({ type: 'SET_LOADING', payload: true });

    try {
      // Fetch all layers
      const layersResponse = await axios.get(`${API_BASE_URL}/layers`);
      const layers: Layer[] = layersResponse.data.layers || [];

      // Fetch active layer
      const activeResponse = await axios.get(`${API_BASE_URL}/layers/active`);
      const activeLayer: Layer | null = activeResponse.data.layer || null;

      dispatch({
        type: 'REFRESH_SUCCESS',
        payload: { layers, activeLayer },
      });
    } catch (error: any) {
      console.error('Failed to fetch layers:', error);
      dispatch({
        type: 'SET_ERROR',
        payload: error.response?.data?.error || 'Failed to fetch layers',
      });
    }
  };

  // Set active layer
  const setActiveLayer = async (layerId: string) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/layers/${layerId}/activate`);
      const updatedLayer: Layer = response.data.layer;

      // Update local state
      dispatch({ type: 'SET_ACTIVE_LAYER', payload: updatedLayer });
      dispatch({ type: 'SET_SELECTED_LAYER', payload: updatedLayer });

      // Refresh all layers to ensure consistency
      await refreshLayers();
    } catch (error: any) {
      console.error('Failed to set active layer:', error);
      dispatch({
        type: 'SET_ERROR',
        payload: error.response?.data?.error || 'Failed to set active layer',
      });
      throw error;
    }
  };

  // Create new layer
  const createLayer = async (
    layerId: string,
    name: string,
    description: string,
    layerType: string = 'experimental'
  ): Promise<Layer> => {
    try {
      const response = await axios.post(`${API_BASE_URL}/layers`, {
        layer_id: layerId,
        name,
        description,
        layer_type: layerType,
        created_by: 'ui',
      });

      const newLayer: Layer = response.data.layer;
      dispatch({ type: 'ADD_LAYER', payload: newLayer });

      return newLayer;
    } catch (error: any) {
      console.error('Failed to create layer:', error);
      dispatch({
        type: 'SET_ERROR',
        payload: error.response?.data?.error || 'Failed to create layer',
      });
      throw error;
    }
  };

  // Delete layer
  const deleteLayer = async (layerId: string, force: boolean = false) => {
    try {
      await axios.delete(`${API_BASE_URL}/layers/${layerId}`, {
        params: { force },
      });

      dispatch({ type: 'REMOVE_LAYER', payload: layerId });

      // Refresh to get updated active layer if needed
      await refreshLayers();
    } catch (error: any) {
      console.error('Failed to delete layer:', error);
      dispatch({
        type: 'SET_ERROR',
        payload: error.response?.data?.error || 'Failed to delete layer',
      });
      throw error;
    }
  };

  // Auto-fetch layers on mount
  useEffect(() => {
    refreshLayers();
  }, []);

  // Setup WebSocket listener for layer changes (optional but recommended)
  useEffect(() => {
    // Listen for layer update events from WebSocket
    // This would connect to your existing WebSocket infrastructure
    // For now, we'll rely on manual refresh
  }, []);

  return (
    <LayerContext.Provider
      value={{
        state,
        dispatch,
        refreshLayers,
        setActiveLayer,
        createLayer,
        deleteLayer,
      }}
    >
      {children}
    </LayerContext.Provider>
  );
}

export function useLayer() {
  const context = useContext(LayerContext);
  if (!context) {
    throw new Error('useLayer must be used within a LayerProvider');
  }
  return context;
}
