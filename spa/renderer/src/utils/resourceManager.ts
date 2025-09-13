/**
 * Resource Manager for preventing memory leaks and managing cleanup
 */

export class ResourceManager {
  private resources: Map<string, {
    cleanup: () => void | Promise<void>;
    type: 'timer' | 'listener' | 'subscription' | 'controller' | 'custom';
    created: number;
  }> = new Map();

  private cleanupQueue: Set<() => void | Promise<void>> = new Set();
  private isDisposed = false;

  /**
   * Register a timer for automatic cleanup
   */
  registerTimer(id: string, timerId: NodeJS.Timeout): void {
    if (this.isDisposed) {
      clearTimeout(timerId);
      return;
    }

    this.resources.set(id, {
      cleanup: () => clearTimeout(timerId),
      type: 'timer',
      created: Date.now(),
    });
  }

  /**
   * Register an interval for automatic cleanup
   */
  registerInterval(id: string, intervalId: NodeJS.Timer): void {
    if (this.isDisposed) {
      clearInterval(intervalId as any);
      return;
    }

    this.resources.set(id, {
      cleanup: () => clearInterval(intervalId as any),
      type: 'timer',
      created: Date.now(),
    });
  }

  /**
   * Register an event listener for automatic cleanup
   */
  registerListener(
    id: string,
    target: EventTarget,
    event: string,
    handler: EventListener,
    options?: boolean | AddEventListenerOptions
  ): void {
    if (this.isDisposed) return;

    target.addEventListener(event, handler, options);
    
    this.resources.set(id, {
      cleanup: () => target.removeEventListener(event, handler, options),
      type: 'listener',
      created: Date.now(),
    });
  }

  /**
   * Register an AbortController for automatic cleanup
   */
  registerAbortController(id: string, controller: AbortController): void {
    if (this.isDisposed) {
      controller.abort();
      return;
    }

    this.resources.set(id, {
      cleanup: () => {
        if (!controller.signal.aborted) {
          controller.abort();
        }
      },
      type: 'controller',
      created: Date.now(),
    });
  }

  /**
   * Register a custom cleanup function
   */
  registerCleanup(id: string, cleanup: () => void | Promise<void>): void {
    if (this.isDisposed) {
      void this.executeCleanup(cleanup);
      return;
    }

    this.resources.set(id, {
      cleanup,
      type: 'custom',
      created: Date.now(),
    });
  }

  /**
   * Add a cleanup function to be executed on dispose
   */
  addCleanupCallback(callback: () => void | Promise<void>): () => void {
    if (this.isDisposed) {
      void this.executeCleanup(callback);
      return () => {};
    }

    this.cleanupQueue.add(callback);
    
    // Return unregister function
    return () => {
      this.cleanupQueue.delete(callback);
    };
  }

  /**
   * Unregister a specific resource
   */
  unregister(id: string): void {
    const resource = this.resources.get(id);
    if (resource) {
      void this.executeCleanup(resource.cleanup);
      this.resources.delete(id);
    }
  }

  /**
   * Clean up resources older than specified age
   */
  cleanupOldResources(maxAgeMs: number): void {
    const now = Date.now();
    const toCleanup: string[] = [];

    for (const [id, resource] of this.resources.entries()) {
      if (now - resource.created > maxAgeMs) {
        toCleanup.push(id);
      }
    }

    toCleanup.forEach(id => this.unregister(id));
  }

  /**
   * Get resource statistics
   */
  getStats(): {
    totalResources: number;
    byType: Record<string, number>;
    oldestResource: number | null;
  } {
    const byType: Record<string, number> = {};
    let oldestResource: number | null = null;

    for (const resource of this.resources.values()) {
      byType[resource.type] = (byType[resource.type] || 0) + 1;
      
      if (oldestResource === null || resource.created < oldestResource) {
        oldestResource = resource.created;
      }
    }

    return {
      totalResources: this.resources.size,
      byType,
      oldestResource,
    };
  }

  /**
   * Execute a cleanup function safely
   */
  private async executeCleanup(cleanup: () => void | Promise<void>): Promise<void> {
    try {
      await cleanup();
    } catch (error) {
      // Console error removed
    }
  }

  /**
   * Dispose all resources
   */
  async dispose(): Promise<void> {
    if (this.isDisposed) return;
    
    this.isDisposed = true;

    // Execute all cleanup callbacks
    const cleanupPromises: Promise<void>[] = [];
    
    for (const callback of this.cleanupQueue) {
      cleanupPromises.push(this.executeCleanup(callback));
    }
    
    // Clean up all registered resources
    for (const resource of this.resources.values()) {
      cleanupPromises.push(this.executeCleanup(resource.cleanup));
    }

    await Promise.all(cleanupPromises);
    
    this.resources.clear();
    this.cleanupQueue.clear();
  }

  /**
   * Check if the manager has been disposed
   */
  get disposed(): boolean {
    return this.isDisposed;
  }
}

/**
 * Hook for using ResourceManager in React components
 */
export function useResourceManager(): ResourceManager {
  const managerRef = React.useRef<ResourceManager>();
  
  if (!managerRef.current) {
    managerRef.current = new ResourceManager();
  }

  React.useEffect(() => {
    const manager = managerRef.current;
    
    return () => {
      if (manager) {
        void manager.dispose();
      }
    };
  }, []);

  return managerRef.current;
}

// Import React for the hook
import * as React from 'react';