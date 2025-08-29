import { useApp } from '../context/AppContext';

export const useBackgroundOperations = () => {
  const { dispatch } = useApp();

  const addBackgroundOperation = (operation: {
    id: string;
    type: string;
    name: string;
    pid?: number;
  }) => {
    dispatch({
      type: 'ADD_BACKGROUND_OPERATION',
      payload: {
        ...operation,
        status: 'running',
        startTime: new Date(),
      },
    });
  };

  const updateBackgroundOperation = (id: string, updates: {
    status?: 'running' | 'completed' | 'error';
    pid?: number;
  }) => {
    dispatch({
      type: 'UPDATE_BACKGROUND_OPERATION',
      payload: { id, updates },
    });
  };

  const removeBackgroundOperation = (id: string) => {
    dispatch({
      type: 'REMOVE_BACKGROUND_OPERATION',
      payload: id,
    });
  };

  return {
    addBackgroundOperation,
    updateBackgroundOperation,
    removeBackgroundOperation,
  };
};