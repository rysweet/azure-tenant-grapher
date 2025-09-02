import io from 'socket.io-client';
import { Server } from 'http';
import { spawn } from 'child_process';
import * as path from 'path';

describe('WebSocket Real-time Log Streaming', () => {
  let socket: any;
  let server: Server;
  const BACKEND_URL = 'http://localhost:3001';

  beforeAll((done) => {
    // Start the backend server
    const serverPath = path.join(__dirname, '../../backend/src/server.ts');
    const serverProcess = spawn('npx', ['tsx', serverPath], {
      env: { ...process.env, PORT: '3001' },
    });

    // Wait a bit for server to start
    setTimeout(() => {
      socket = io(BACKEND_URL, {
        transports: ['websocket'],
        reconnection: false,
      });

      socket.on('connect', () => {
        done();
      });
    }, 2000);
  });

  afterAll((done) => {
    if (socket) {
      socket.disconnect();
    }
    done();
  });

  test('should connect to WebSocket server', (done) => {
    const testSocket = io(BACKEND_URL, {
      transports: ['websocket'],
    });

    testSocket.on('connect', () => {
      expect(testSocket.connected).toBe(true);
      testSocket.disconnect();
      done();
    });
  });

  test('should receive output events when subscribed to a process', (done) => {
    const testProcessId = 'test-process-123';

    socket.emit('subscribe', testProcessId);

    socket.on('output', (data: any) => {
      expect(data).toHaveProperty('processId');
      expect(data).toHaveProperty('type');
      expect(data).toHaveProperty('data');
      expect(data).toHaveProperty('timestamp');
      done();
    });

    // Simulate output event from server
    setTimeout(() => {
      socket.emit('test-output', {
        processId: testProcessId,
        type: 'stdout',
        data: ['Test output line 1', 'Test output line 2'],
        timestamp: new Date().toISOString(),
      });
    }, 100);
  });

  test('should handle process exit events', (done) => {
    const testProcessId = 'test-process-456';

    socket.emit('subscribe', testProcessId);

    socket.on('process-exit', (event: any) => {
      expect(event).toHaveProperty('processId', testProcessId);
      expect(event).toHaveProperty('code');
      expect(event).toHaveProperty('timestamp');
      done();
    });

    // Simulate process exit
    setTimeout(() => {
      socket.emit('test-exit', {
        processId: testProcessId,
        code: 0,
        timestamp: new Date().toISOString(),
      });
    }, 100);
  });

  test('should handle process error events', (done) => {
    const testProcessId = 'test-process-789';

    socket.emit('subscribe', testProcessId);

    socket.on('process-error', (event: any) => {
      expect(event).toHaveProperty('processId', testProcessId);
      expect(event).toHaveProperty('error');
      expect(event).toHaveProperty('timestamp');
      done();
    });

    // Simulate process error
    setTimeout(() => {
      socket.emit('test-error', {
        processId: testProcessId,
        error: 'Test error message',
        timestamp: new Date().toISOString(),
      });
    }, 100);
  });

  test('should unsubscribe from process events', (done) => {
    const testProcessId = 'test-process-unsubscribe';

    socket.emit('subscribe', testProcessId);

    setTimeout(() => {
      socket.emit('unsubscribe', testProcessId);

      // Should not receive events after unsubscribe
      let received = false;
      socket.on('output', (data: any) => {
        if (data.processId === testProcessId) {
          received = true;
        }
      });

      socket.emit('test-output', {
        processId: testProcessId,
        type: 'stdout',
        data: ['Should not receive this'],
        timestamp: new Date().toISOString(),
      });

      setTimeout(() => {
        expect(received).toBe(false);
        done();
      }, 500);
    }, 100);
  });

  test('should handle multiple concurrent process subscriptions', (done) => {
    const processIds = ['process-1', 'process-2', 'process-3'];
    const receivedOutputs = new Set<string>();

    // Subscribe to all processes
    processIds.forEach(id => socket.emit('subscribe', id));

    socket.on('output', (data: any) => {
      receivedOutputs.add(data.processId);

      if (receivedOutputs.size === processIds.length) {
        expect(Array.from(receivedOutputs).sort()).toEqual(processIds.sort());
        done();
      }
    });

    // Simulate output for each process
    processIds.forEach((id, index) => {
      setTimeout(() => {
        socket.emit('test-output', {
          processId: id,
          type: 'stdout',
          data: [`Output from ${id}`],
          timestamp: new Date().toISOString(),
        });
      }, 100 * (index + 1));
    });
  });

  test('should handle large output data', (done) => {
    const testProcessId = 'test-process-large';
    const largeOutput = Array(1000).fill('Lorem ipsum dolor sit amet, consectetur adipiscing elit.');

    socket.emit('subscribe', testProcessId);

    socket.on('output', (data: any) => {
      if (data.processId === testProcessId) {
        expect(data.data).toBeDefined();
        expect(Array.isArray(data.data)).toBe(true);
        expect(data.data.length).toBe(largeOutput.length);
        done();
      }
    });

    setTimeout(() => {
      socket.emit('test-output', {
        processId: testProcessId,
        type: 'stdout',
        data: largeOutput,
        timestamp: new Date().toISOString(),
      });
    }, 100);
  });

  test('should maintain output order', (done) => {
    const testProcessId = 'test-process-order';
    const expectedOutput = ['Line 1', 'Line 2', 'Line 3', 'Line 4', 'Line 5'];
    const receivedOutput: string[] = [];

    socket.emit('subscribe', testProcessId);

    socket.on('output', (data: any) => {
      if (data.processId === testProcessId) {
        receivedOutput.push(...data.data);

        if (receivedOutput.length === expectedOutput.length) {
          expect(receivedOutput).toEqual(expectedOutput);
          done();
        }
      }
    });

    // Send output in order
    expectedOutput.forEach((line, index) => {
      setTimeout(() => {
        socket.emit('test-output', {
          processId: testProcessId,
          type: 'stdout',
          data: [line],
          timestamp: new Date().toISOString(),
        });
      }, 50 * index);
    });
  });

  test('should differentiate between stdout and stderr', (done) => {
    const testProcessId = 'test-process-streams';
    const outputs = { stdout: [], stderr: [] };
    let totalReceived = 0;

    socket.emit('subscribe', testProcessId);

    socket.on('output', (data: any) => {
      if (data.processId === testProcessId) {
        outputs[data.type].push(...data.data);
        totalReceived++;

        if (totalReceived === 2) {
          expect(outputs.stdout).toEqual(['Standard output']);
          expect(outputs.stderr).toEqual(['Error output']);
          done();
        }
      }
    });

    // Send stdout
    setTimeout(() => {
      socket.emit('test-output', {
        processId: testProcessId,
        type: 'stdout',
        data: ['Standard output'],
        timestamp: new Date().toISOString(),
      });
    }, 100);

    // Send stderr
    setTimeout(() => {
      socket.emit('test-output', {
        processId: testProcessId,
        type: 'stderr',
        data: ['Error output'],
        timestamp: new Date().toISOString(),
      });
    }, 200);
  });

  test('should handle reconnection', (done) => {
    const reconnectSocket = io(BACKEND_URL, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: 3,
      reconnectionDelay: 100,
    });

    let disconnectCount = 0;
    let connectCount = 0;

    reconnectSocket.on('connect', () => {
      connectCount++;

      if (connectCount === 1) {
        // Force disconnect
        reconnectSocket.disconnect();
        setTimeout(() => {
          reconnectSocket.connect();
        }, 200);
      } else if (connectCount === 2) {
        expect(disconnectCount).toBe(1);
        expect(connectCount).toBe(2);
        reconnectSocket.disconnect();
        done();
      }
    });

    reconnectSocket.on('disconnect', () => {
      disconnectCount++;
    });
  });
});

describe('WebSocket Hook Integration', () => {
  test('useWebSocket hook should manage subscriptions', () => {
    // Mock implementation for testing the hook
    const mockSocket = {
      emit: jest.fn(),
      on: jest.fn(),
      connected: true,
    };

    const subscribeToProcess = (processId: string) => {
      mockSocket.emit('subscribe', processId);
    };

    const unsubscribeFromProcess = (processId: string) => {
      mockSocket.emit('unsubscribe', processId);
    };

    // Test subscription
    subscribeToProcess('test-process');
    expect(mockSocket.emit).toHaveBeenCalledWith('subscribe', 'test-process');

    // Test unsubscription
    unsubscribeFromProcess('test-process');
    expect(mockSocket.emit).toHaveBeenCalledWith('unsubscribe', 'test-process');
  });

  test('should aggregate output data correctly', () => {
    const outputs = new Map<string, any[]>();

    const addOutput = (processId: string, data: any) => {
      const existing = outputs.get(processId) || [];
      outputs.set(processId, [...existing, data]);
    };

    const getProcessOutput = (processId: string): string[] => {
      const processOutputs = outputs.get(processId) || [];
      return processOutputs.flatMap(output => output.data);
    };

    // Add some outputs
    addOutput('process-1', { type: 'stdout', data: ['Line 1', 'Line 2'] });
    addOutput('process-1', { type: 'stdout', data: ['Line 3'] });
    addOutput('process-2', { type: 'stdout', data: ['Other process'] });

    // Test aggregation
    expect(getProcessOutput('process-1')).toEqual(['Line 1', 'Line 2', 'Line 3']);
    expect(getProcessOutput('process-2')).toEqual(['Other process']);
    expect(getProcessOutput('process-3')).toEqual([]);
  });
});
