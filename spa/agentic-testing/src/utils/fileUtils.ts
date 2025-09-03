/**
 * File system utilities for test artifact management
 * Handles directory creation, cleanup, archiving, and file operations
 */

import fs from 'fs/promises';
import path from 'path';
import crypto from 'crypto';
import { glob } from 'glob';

/**
 * File operation error class
 */
export class FileOperationError extends Error {
  constructor(message: string, public operation: string, public filePath?: string) {
    super(message);
    this.name = 'FileOperationError';
  }
}

/**
 * File metadata interface
 */
export interface FileMetadata {
  /** File path */
  filePath: string;
  /** File name */
  fileName: string;
  /** File size in bytes */
  size: number;
  /** Creation time */
  createdAt: Date;
  /** Last modification time */
  modifiedAt: Date;
  /** File extension */
  extension: string;
  /** MIME type (if determinable) */
  mimeType?: string;
  /** File hash for integrity checking */
  hash?: string;
  /** Whether file is directory */
  isDirectory: boolean;
  /** File permissions */
  permissions?: string;
}

/**
 * Directory cleanup options
 */
export interface CleanupOptions {
  /** Maximum age of files to keep in milliseconds */
  maxAge?: number;
  /** File patterns to include in cleanup (glob patterns) */
  includePatterns?: string[];
  /** File patterns to exclude from cleanup */
  excludePatterns?: string[];
  /** Whether to remove empty directories after cleanup */
  removeEmptyDirs?: boolean;
  /** Dry run mode - don't actually delete anything */
  dryRun?: boolean;
  /** Maximum number of files to delete */
  maxFiles?: number;
}

/**
 * Archive options
 */
export interface ArchiveOptions {
  /** Archive format */
  format: 'zip' | 'tar' | 'tar.gz';
  /** Compression level (0-9 for gzip) */
  compressionLevel?: number;
  /** Whether to include directory structure */
  preservePaths?: boolean;
  /** Files to exclude from archive */
  exclude?: string[];
  /** Base directory for relative paths */
  baseDir?: string;
}

/**
 * Directory synchronization options
 */
export interface SyncOptions {
  /** Whether to delete files in destination not in source */
  deleteExtra?: boolean;
  /** Whether to preserve timestamps */
  preserveTimestamps?: boolean;
  /** Files to exclude from sync */
  exclude?: string[];
  /** Whether to use checksums for comparison */
  useChecksum?: boolean;
}

/**
 * File system utility class
 */
export class FileUtils {
  /**
   * Ensure a directory exists, creating it if necessary
   */
  static async ensureDirectory(dirPath: string): Promise<void> {
    try {
      const stats = await fs.stat(dirPath);
      if (!stats.isDirectory()) {
        throw new FileOperationError(
          `Path exists but is not a directory: ${dirPath}`,
          'ensureDirectory',
          dirPath
        );
      }
    } catch (error) {
      if (error.code === 'ENOENT') {
        try {
          await fs.mkdir(dirPath, { recursive: true });
        } catch (mkdirError) {
          throw new FileOperationError(
            `Failed to create directory: ${mkdirError.message}`,
            'ensureDirectory',
            dirPath
          );
        }
      } else if (!(error instanceof FileOperationError)) {
        throw new FileOperationError(
          `Failed to check directory: ${error.message}`,
          'ensureDirectory',
          dirPath
        );
      } else {
        throw error;
      }
    }
  }

  /**
   * Read a JSON file and parse it
   */
  static async readJsonFile<T = any>(filePath: string): Promise<T> {
    try {
      const content = await fs.readFile(filePath, 'utf-8');
      return JSON.parse(content) as T;
    } catch (error) {
      throw new FileOperationError(
        `Failed to read JSON file: ${error.message}`,
        'readJsonFile',
        filePath
      );
    }
  }

  /**
   * Write an object to a JSON file
   */
  static async writeJsonFile(filePath: string, data: any, pretty: boolean = true): Promise<void> {
    try {
      await this.ensureDirectory(path.dirname(filePath));
      const content = pretty ? JSON.stringify(data, null, 2) : JSON.stringify(data);
      await fs.writeFile(filePath, content, 'utf-8');
    } catch (error) {
      throw new FileOperationError(
        `Failed to write JSON file: ${error.message}`,
        'writeJsonFile',
        filePath
      );
    }
  }

  /**
   * Append content to a file
   */
  static async appendToFile(filePath: string, content: string): Promise<void> {
    try {
      await this.ensureDirectory(path.dirname(filePath));
      await fs.appendFile(filePath, content);
    } catch (error) {
      throw new FileOperationError(
        `Failed to append to file: ${error.message}`,
        'appendToFile',
        filePath
      );
    }
  }

  /**
   * Copy a file or directory
   */
  static async copy(source: string, destination: string, overwrite: boolean = true): Promise<void> {
    try {
      await this.ensureDirectory(path.dirname(destination));
      
      const stats = await fs.stat(source);
      
      if (stats.isDirectory()) {
        await this.copyDirectory(source, destination, overwrite);
      } else {
        if (!overwrite && await this.exists(destination)) {
          throw new FileOperationError(
            `Destination file already exists: ${destination}`,
            'copy',
            destination
          );
        }
        await fs.copyFile(source, destination);
      }
    } catch (error) {
      if (!(error instanceof FileOperationError)) {
        throw new FileOperationError(
          `Failed to copy: ${error.message}`,
          'copy',
          source
        );
      }
      throw error;
    }
  }

  /**
   * Copy a directory recursively
   */
  private static async copyDirectory(source: string, destination: string, overwrite: boolean): Promise<void> {
    await this.ensureDirectory(destination);
    
    const items = await fs.readdir(source);
    
    for (const item of items) {
      const srcPath = path.join(source, item);
      const destPath = path.join(destination, item);
      
      const stats = await fs.stat(srcPath);
      
      if (stats.isDirectory()) {
        await this.copyDirectory(srcPath, destPath, overwrite);
      } else {
        if (!overwrite && await this.exists(destPath)) {
          continue;
        }
        await fs.copyFile(srcPath, destPath);
      }
    }
  }

  /**
   * Move/rename a file or directory
   */
  static async move(source: string, destination: string): Promise<void> {
    try {
      await this.ensureDirectory(path.dirname(destination));
      await fs.rename(source, destination);
    } catch (error) {
      throw new FileOperationError(
        `Failed to move: ${error.message}`,
        'move',
        source
      );
    }
  }

  /**
   * Delete a file or directory
   */
  static async delete(filePath: string, recursive: boolean = false): Promise<void> {
    try {
      const stats = await fs.stat(filePath);
      
      if (stats.isDirectory()) {
        if (recursive) {
          await fs.rm(filePath, { recursive: true, force: true });
        } else {
          await fs.rmdir(filePath);
        }
      } else {
        await fs.unlink(filePath);
      }
    } catch (error) {
      if (error.code !== 'ENOENT') {
        throw new FileOperationError(
          `Failed to delete: ${error.message}`,
          'delete',
          filePath
        );
      }
    }
  }

  /**
   * Check if file or directory exists
   */
  static async exists(filePath: string): Promise<boolean> {
    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Get file metadata
   */
  static async getMetadata(filePath: string): Promise<FileMetadata> {
    try {
      const stats = await fs.stat(filePath);
      const fileName = path.basename(filePath);
      const extension = path.extname(fileName).toLowerCase();
      
      return {
        filePath,
        fileName,
        size: stats.size,
        createdAt: stats.birthtime,
        modifiedAt: stats.mtime,
        extension,
        isDirectory: stats.isDirectory(),
        permissions: stats.mode.toString(8).slice(-3)
      };
    } catch (error) {
      throw new FileOperationError(
        `Failed to get metadata: ${error.message}`,
        'getMetadata',
        filePath
      );
    }
  }

  /**
   * Calculate file hash
   */
  static async calculateHash(filePath: string, algorithm: string = 'md5'): Promise<string> {
    try {
      const buffer = await fs.readFile(filePath);
      return crypto.createHash(algorithm).update(buffer).digest('hex');
    } catch (error) {
      throw new FileOperationError(
        `Failed to calculate hash: ${error.message}`,
        'calculateHash',
        filePath
      );
    }
  }

  /**
   * Find files matching patterns
   */
  static async findFiles(patterns: string | string[], options?: {
    cwd?: string;
    ignore?: string[];
    absolute?: boolean;
  }): Promise<string[]> {
    try {
      const globPatterns = Array.isArray(patterns) ? patterns : [patterns];
      const results: string[] = [];
      
      for (const pattern of globPatterns) {
        const matches = await glob(pattern, {
          cwd: options?.cwd,
          ignore: options?.ignore,
          absolute: options?.absolute ?? true
        });
        results.push(...matches);
      }
      
      // Remove duplicates
      return [...new Set(results)];
    } catch (error) {
      throw new FileOperationError(
        `Failed to find files: ${error.message}`,
        'findFiles'
      );
    }
  }

  /**
   * Clean up files and directories based on criteria
   */
  static async cleanup(directory: string, options: CleanupOptions = {}): Promise<{
    deletedFiles: string[];
    deletedDirectories: string[];
    totalSize: number;
    errors: Array<{ path: string; error: string }>;
  }> {
    const result = {
      deletedFiles: [] as string[],
      deletedDirectories: [] as string[],
      totalSize: 0,
      errors: [] as Array<{ path: string; error: string }>
    };

    try {
      if (!await this.exists(directory)) {
        return result;
      }

      const files = await this.findFiles(
        options.includePatterns || ['**/*'],
        { cwd: directory, absolute: true }
      );

      let filesToDelete = files;

      // Filter by age if specified
      if (options.maxAge) {
        const cutoffTime = Date.now() - options.maxAge;
        filesToDelete = await this.filterByAge(filesToDelete, cutoffTime);
      }

      // Apply exclude patterns
      if (options.excludePatterns) {
        filesToDelete = await this.filterByPatterns(filesToDelete, options.excludePatterns, true);
      }

      // Limit number of files if specified
      if (options.maxFiles && filesToDelete.length > options.maxFiles) {
        filesToDelete = filesToDelete.slice(0, options.maxFiles);
      }

      // Delete files
      for (const filePath of filesToDelete) {
        try {
          if (options.dryRun) {
            const stats = await fs.stat(filePath);
            result.totalSize += stats.size;
            if (stats.isDirectory()) {
              result.deletedDirectories.push(filePath);
            } else {
              result.deletedFiles.push(filePath);
            }
          } else {
            const stats = await fs.stat(filePath);
            result.totalSize += stats.size;
            
            await this.delete(filePath, true);
            
            if (stats.isDirectory()) {
              result.deletedDirectories.push(filePath);
            } else {
              result.deletedFiles.push(filePath);
            }
          }
        } catch (error) {
          result.errors.push({
            path: filePath,
            error: error.message
          });
        }
      }

      // Remove empty directories if requested
      if (options.removeEmptyDirs && !options.dryRun) {
        await this.removeEmptyDirectories(directory);
      }

    } catch (error) {
      throw new FileOperationError(
        `Cleanup failed: ${error.message}`,
        'cleanup',
        directory
      );
    }

    return result;
  }

  /**
   * Create a backup of a file or directory
   */
  static async backup(source: string, backupDir?: string): Promise<string> {
    try {
      if (!backupDir) {
        backupDir = path.join(path.dirname(source), 'backups');
      }

      await this.ensureDirectory(backupDir);

      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('.')[0];
      const sourceName = path.basename(source);
      const backupName = `${sourceName}.backup.${timestamp}`;
      const backupPath = path.join(backupDir, backupName);

      await this.copy(source, backupPath);
      return backupPath;

    } catch (error) {
      throw new FileOperationError(
        `Backup failed: ${error.message}`,
        'backup',
        source
      );
    }
  }

  /**
   * Synchronize directories
   */
  static async sync(source: string, destination: string, options: SyncOptions = {}): Promise<{
    copied: string[];
    updated: string[];
    deleted: string[];
    errors: Array<{ path: string; error: string }>;
  }> {
    const result = {
      copied: [] as string[],
      updated: [] as string[],
      deleted: [] as string[],
      errors: [] as Array<{ path: string; error: string }>
    };

    try {
      await this.ensureDirectory(destination);

      // Get source files
      const sourceFiles = await this.findFiles('**/*', { cwd: source, absolute: false });
      
      // Filter by exclude patterns
      const filteredSourceFiles = options.exclude 
        ? await this.filterByPatterns(sourceFiles, options.exclude, true)
        : sourceFiles;

      // Process each source file
      for (const relativePath of filteredSourceFiles) {
        const sourcePath = path.join(source, relativePath);
        const destPath = path.join(destination, relativePath);

        try {
          if (await this.exists(destPath)) {
            // File exists, check if update needed
            const sourceStats = await fs.stat(sourcePath);
            const destStats = await fs.stat(destPath);

            let needsUpdate = false;

            if (options.useChecksum) {
              const sourceHash = await this.calculateHash(sourcePath);
              const destHash = await this.calculateHash(destPath);
              needsUpdate = sourceHash !== destHash;
            } else {
              needsUpdate = sourceStats.mtime > destStats.mtime;
            }

            if (needsUpdate) {
              await this.copy(sourcePath, destPath);
              result.updated.push(relativePath);
            }
          } else {
            // File doesn't exist, copy it
            await this.copy(sourcePath, destPath);
            result.copied.push(relativePath);
          }
        } catch (error) {
          result.errors.push({
            path: relativePath,
            error: error.message
          });
        }
      }

      // Handle deletion of extra files
      if (options.deleteExtra) {
        const destFiles = await this.findFiles('**/*', { cwd: destination, absolute: false });
        const extraFiles = destFiles.filter(f => !filteredSourceFiles.includes(f));

        for (const extraFile of extraFiles) {
          try {
            const extraPath = path.join(destination, extraFile);
            await this.delete(extraPath, true);
            result.deleted.push(extraFile);
          } catch (error) {
            result.errors.push({
              path: extraFile,
              error: error.message
            });
          }
        }
      }

    } catch (error) {
      throw new FileOperationError(
        `Sync failed: ${error.message}`,
        'sync',
        source
      );
    }

    return result;
  }

  /**
   * Get directory size recursively
   */
  static async getDirectorySize(directory: string): Promise<number> {
    let totalSize = 0;

    try {
      const files = await this.findFiles('**/*', { cwd: directory, absolute: true });
      
      for (const filePath of files) {
        try {
          const stats = await fs.stat(filePath);
          if (stats.isFile()) {
            totalSize += stats.size;
          }
        } catch {
          // Skip files that can't be accessed
        }
      }
    } catch (error) {
      throw new FileOperationError(
        `Failed to get directory size: ${error.message}`,
        'getDirectorySize',
        directory
      );
    }

    return totalSize;
  }

  /**
   * Create a temporary file
   */
  static async createTempFile(prefix: string = 'temp', suffix: string = '.tmp'): Promise<string> {
    const tempDir = process.env.TMPDIR || process.env.TMP || '/tmp';
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 8);
    const fileName = `${prefix}_${timestamp}_${random}${suffix}`;
    const tempPath = path.join(tempDir, fileName);

    try {
      await fs.writeFile(tempPath, '');
      return tempPath;
    } catch (error) {
      throw new FileOperationError(
        `Failed to create temp file: ${error.message}`,
        'createTempFile',
        tempPath
      );
    }
  }

  /**
   * Create a temporary directory
   */
  static async createTempDirectory(prefix: string = 'temp'): Promise<string> {
    const tempDir = process.env.TMPDIR || process.env.TMP || '/tmp';
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 8);
    const dirName = `${prefix}_${timestamp}_${random}`;
    const tempPath = path.join(tempDir, dirName);

    try {
      await this.ensureDirectory(tempPath);
      return tempPath;
    } catch (error) {
      throw new FileOperationError(
        `Failed to create temp directory: ${error.message}`,
        'createTempDirectory',
        tempPath
      );
    }
  }

  /**
   * Filter files by age
   */
  private static async filterByAge(files: string[], cutoffTime: number): Promise<string[]> {
    const filtered: string[] = [];
    
    for (const filePath of files) {
      try {
        const stats = await fs.stat(filePath);
        if (stats.mtime.getTime() < cutoffTime) {
          filtered.push(filePath);
        }
      } catch {
        // Skip files that can't be accessed
      }
    }
    
    return filtered;
  }

  /**
   * Filter files by patterns
   */
  private static async filterByPatterns(files: string[], patterns: string[], exclude: boolean): Promise<string[]> {
    // This is a simplified implementation
    // In a real implementation, you'd use a proper glob matching library
    return files.filter(filePath => {
      const matches = patterns.some(pattern => {
        const regex = new RegExp(pattern.replace(/\*/g, '.*'));
        return regex.test(filePath);
      });
      return exclude ? !matches : matches;
    });
  }

  /**
   * Remove empty directories recursively
   */
  private static async removeEmptyDirectories(directory: string): Promise<void> {
    try {
      const items = await fs.readdir(directory);
      
      for (const item of items) {
        const itemPath = path.join(directory, item);
        const stats = await fs.stat(itemPath);
        
        if (stats.isDirectory()) {
          await this.removeEmptyDirectories(itemPath);
          
          // Check if directory is now empty
          const remainingItems = await fs.readdir(itemPath);
          if (remainingItems.length === 0) {
            await fs.rmdir(itemPath);
          }
        }
      }
    } catch {
      // Ignore errors when removing empty directories
    }
  }
}

/**
 * Convenience functions for common operations
 */

/**
 * Ensure directory exists
 */
export async function ensureDir(dirPath: string): Promise<void> {
  return FileUtils.ensureDirectory(dirPath);
}

/**
 * Read JSON file
 */
export async function readJson<T = any>(filePath: string): Promise<T> {
  return FileUtils.readJsonFile<T>(filePath);
}

/**
 * Write JSON file
 */
export async function writeJson(filePath: string, data: any, pretty: boolean = true): Promise<void> {
  return FileUtils.writeJsonFile(filePath, data, pretty);
}

/**
 * Check if file exists
 */
export async function exists(filePath: string): Promise<boolean> {
  return FileUtils.exists(filePath);
}

/**
 * Delete file or directory
 */
export async function remove(filePath: string, recursive: boolean = false): Promise<void> {
  return FileUtils.delete(filePath, recursive);
}

/**
 * Copy file or directory
 */
export async function copy(source: string, destination: string, overwrite: boolean = true): Promise<void> {
  return FileUtils.copy(source, destination, overwrite);
}

/**
 * Find files matching patterns
 */
export async function findFiles(patterns: string | string[], cwd?: string): Promise<string[]> {
  return FileUtils.findFiles(patterns, { cwd, absolute: true });
}