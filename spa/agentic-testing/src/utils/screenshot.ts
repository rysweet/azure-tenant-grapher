/**
 * Screenshot utilities for Playwright-based testing
 * Handles capture, comparison, organization, and management of screenshots
 */

import { Page, Browser, BrowserContext, Locator } from 'playwright';
import * as fs from 'fs/promises';
import * as path from 'path';
import * as crypto from 'crypto';
import * as Jimp from 'jimp';
import * as pixelmatch from 'pixelmatch';

/**
 * Screenshot options interface
 */
export interface ScreenshotOptions {
  /** Output file path (if not provided, auto-generated) */
  path?: string;
  /** Screenshot type */
  type?: 'png' | 'jpeg';
  /** JPEG quality (0-100, only for JPEG) */
  quality?: number;
  /** Whether to capture full page */
  fullPage?: boolean;
  /** Specific clip area */
  clip?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  /** Animation handling */
  animations?: 'disabled' | 'allow';
  /** Mask specific elements */
  mask?: Locator[];
  /** Omit background (transparent) */
  omitBackground?: boolean;
  /** Timeout in milliseconds */
  timeout?: number;
}

/**
 * Screenshot metadata interface
 */
export interface ScreenshotMetadata {
  /** File path */
  filePath: string;
  /** Filename */
  fileName: string;
  /** Timestamp when captured */
  timestamp: Date;
  /** Test scenario ID */
  scenarioId?: string;
  /** Test step index */
  stepIndex?: number;
  /** Screenshot description */
  description?: string;
  /** Page URL when captured */
  url?: string;
  /** Viewport size */
  viewport?: { width: number; height: number };
  /** File size in bytes */
  fileSize?: number;
  /** Additional tags */
  tags?: string[];
  /** Hash for deduplication */
  hash?: string;
}

/**
 * Diff algorithm options
 */
export type DiffAlgorithm = 'pixel-by-pixel' | 'perceptual' | 'structural';

/**
 * Diff color coding options
 */
export interface DiffColorOptions {
  /** Color for removed pixels (default: red) */
  removedColor?: [number, number, number];
  /** Color for added pixels (default: green) */
  addedColor?: [number, number, number];
  /** Color for changed pixels (default: yellow) */
  changedColor?: [number, number, number];
  /** Alpha value for diff overlay (0-255, default: 255) */
  alpha?: number;
}

/**
 * Screenshot comparison options
 */
export interface ComparisonOptions {
  /** Similarity threshold (0-1, default: 0.1) */
  threshold?: number;
  /** Diff algorithm to use */
  algorithm?: DiffAlgorithm;
  /** Whether to include antialiasing detection */
  includeAA?: boolean;
  /** Color options for diff visualization */
  colorOptions?: DiffColorOptions;
  /** Whether to create a diff image */
  createDiffImage?: boolean;
}

/**
 * Screenshot comparison result
 */
export interface ComparisonResult {
  /** Whether screenshots match within threshold */
  matches: boolean;
  /** Difference percentage (0-100) */
  differencePercentage: number;
  /** Similarity percentage (0-100) */
  similarityPercentage: number;
  /** Path to difference image */
  diffImagePath?: string;
  /** Comparison metadata */
  metadata: {
    baselineImage: string;
    actualImage: string;
    threshold: number;
    algorithm: DiffAlgorithm;
    pixelCount: number;
    differentPixels: number;
    baselineSize: { width: number; height: number };
    actualSize: { width: number; height: number };
    resized: boolean;
  };
}

/**
 * Screenshot organization options
 */
export interface OrganizationOptions {
  /** Base directory for screenshots */
  baseDir: string;
  /** Organization strategy */
  strategy: 'flat' | 'by-date' | 'by-scenario' | 'by-run';
  /** Run ID for organization */
  runId?: string;
  /** Whether to include timestamps in filenames */
  includeTimestamp: boolean;
  /** Maximum number of screenshots per directory */
  maxPerDirectory?: number;
}

/**
 * Default screenshot options
 */
const DEFAULT_OPTIONS: ScreenshotOptions = {
  type: 'png',
  fullPage: false,
  animations: 'disabled',
  timeout: 30000
};

/**
 * Default organization options
 */
const DEFAULT_ORGANIZATION: OrganizationOptions = {
  baseDir: './screenshots',
  strategy: 'by-scenario',
  includeTimestamp: true
};

/**
 * Screenshot manager class
 */
export class ScreenshotManager {
  private organizationOptions: OrganizationOptions;
  private metadata: Map<string, ScreenshotMetadata> = new Map();
  private runId: string;

  constructor(options: Partial<OrganizationOptions> = {}) {
    this.organizationOptions = { ...DEFAULT_ORGANIZATION, ...options };
    this.runId = options.runId || this.generateRunId();
  }

  /**
   * Capture a screenshot of the page
   */
  async capturePageScreenshot(
    page: Page,
    options: ScreenshotOptions & { scenarioId?: string; stepIndex?: number; description?: string } = {}
  ): Promise<ScreenshotMetadata> {
    const finalOptions = { ...DEFAULT_OPTIONS, ...options };

    // Generate file path if not provided
    if (!finalOptions.path) {
      finalOptions.path = this.generateFilePath('page', options.scenarioId, options.stepIndex);
    }

    // Ensure directory exists
    await this.ensureDirectoryExists(path.dirname(finalOptions.path));

    // Capture screenshot
    const buffer = await page.screenshot(finalOptions);
    await fs.writeFile(finalOptions.path, buffer);

    // Get page metadata
    const url = page.url();
    const viewport = page.viewportSize();

    // Create metadata
    const metadata: ScreenshotMetadata = {
      filePath: finalOptions.path,
      fileName: path.basename(finalOptions.path),
      timestamp: new Date(),
      scenarioId: options.scenarioId,
      stepIndex: options.stepIndex,
      description: options.description,
      url,
      viewport: viewport || undefined,
      fileSize: buffer.length,
      hash: this.calculateHash(buffer),
      tags: ['page']
    };

    // Store metadata
    this.metadata.set(finalOptions.path, metadata);

    return metadata;
  }

  /**
   * Capture a screenshot of a specific element
   */
  async captureElementScreenshot(
    element: Locator,
    options: ScreenshotOptions & { scenarioId?: string; stepIndex?: number; description?: string } = {}
  ): Promise<ScreenshotMetadata> {
    const finalOptions = { ...DEFAULT_OPTIONS, ...options };

    // Generate file path if not provided
    if (!finalOptions.path) {
      finalOptions.path = this.generateFilePath('element', options.scenarioId, options.stepIndex);
    }

    // Ensure directory exists
    await this.ensureDirectoryExists(path.dirname(finalOptions.path));

    // Capture screenshot
    const buffer = await element.screenshot(finalOptions);
    await fs.writeFile(finalOptions.path, buffer);

    // Get page metadata
    const page = element.page();
    const url = page.url();
    const viewport = page.viewportSize();

    // Create metadata
    const metadata: ScreenshotMetadata = {
      filePath: finalOptions.path,
      fileName: path.basename(finalOptions.path),
      timestamp: new Date(),
      scenarioId: options.scenarioId,
      stepIndex: options.stepIndex,
      description: options.description,
      url,
      viewport: viewport || undefined,
      fileSize: buffer.length,
      hash: this.calculateHash(buffer),
      tags: ['element']
    };

    // Store metadata
    this.metadata.set(finalOptions.path, metadata);

    return metadata;
  }

  /**
   * Capture multiple screenshots in sequence
   */
  async captureSequence(
    page: Page,
    count: number,
    interval: number,
    options: ScreenshotOptions & { scenarioId?: string; description?: string } = {}
  ): Promise<ScreenshotMetadata[]> {
    const screenshots: ScreenshotMetadata[] = [];

    for (let i = 0; i < count; i++) {
      const sequenceOptions = {
        ...options,
        description: `${options.description || 'Sequence'} - ${i + 1}/${count}`,
        path: this.generateFilePath(`sequence_${i + 1}`, options.scenarioId)
      };

      const metadata = await this.capturePageScreenshot(page, sequenceOptions);
      screenshots.push(metadata);

      if (i < count - 1) {
        await this.sleep(interval);
      }
    }

    return screenshots;
  }

  /**
   * Capture before/after comparison screenshots
   */
  async captureComparison(
    page: Page,
    action: () => Promise<void>,
    options: ScreenshotOptions & { scenarioId?: string; stepIndex?: number; description?: string } = {}
  ): Promise<{ before: ScreenshotMetadata; after: ScreenshotMetadata }> {
    // Capture before
    const beforeOptions = {
      ...options,
      description: `${options.description || 'Comparison'} - Before`,
      path: this.generateFilePath('before', options.scenarioId, options.stepIndex)
    };
    const before = await this.capturePageScreenshot(page, beforeOptions);

    // Perform action
    await action();

    // Capture after
    const afterOptions = {
      ...options,
      description: `${options.description || 'Comparison'} - After`,
      path: this.generateFilePath('after', options.scenarioId, options.stepIndex)
    };
    const after = await this.capturePageScreenshot(page, afterOptions);

    return { before, after };
  }

  /**
   * Compare two screenshots with advanced pixel-level comparison
   */
  async compareScreenshots(
    baselineImage: string,
    actualImage: string,
    options: ComparisonOptions = {}
  ): Promise<ComparisonResult> {
    const {
      threshold = 0.1,
      algorithm = 'pixel-by-pixel',
      includeAA = false,
      createDiffImage = true,
      colorOptions = {}
    } = options;

    try {
      // Load both images using Jimp
      const [baseline, actual] = await Promise.all([
        Jimp.read(baselineImage),
        Jimp.read(actualImage)
      ]);

      const baselineSize = { width: baseline.getWidth(), height: baseline.getHeight() };
      const actualSize = { width: actual.getWidth(), height: actual.getHeight() };

      // Handle different image sizes by resizing to match
      let resized = false;
      if (baselineSize.width !== actualSize.width || baselineSize.height !== actualSize.height) {
        const maxWidth = Math.max(baselineSize.width, actualSize.width);
        const maxHeight = Math.max(baselineSize.height, actualSize.height);

        baseline.resize(maxWidth, maxHeight);
        actual.resize(maxWidth, maxHeight);
        resized = true;
      }

      const width = baseline.getWidth();
      const height = baseline.getHeight();
      const pixelCount = width * height;

      // Convert images to RGBA buffers for pixelmatch
      const baselineBuffer = new Uint8ClampedArray(baseline.bitmap.data);
      const actualBuffer = new Uint8ClampedArray(actual.bitmap.data);
      const diffBuffer = new Uint8ClampedArray(width * height * 4);

      // Configure pixelmatch options based on algorithm
      const pixelmatchOptions = {
        threshold: algorithm === 'perceptual' ? 0.2 : 0.1,
        includeAA,
        alpha: colorOptions.alpha || 1.0,
        aaColor: [255, 255, 0], // Yellow for antialiasing differences
        diffColor: colorOptions.changedColor || [255, 0, 255], // Magenta for differences
        diffColorAlt: colorOptions.addedColor || [0, 255, 0] // Green for additions
      };

      // Perform pixel comparison
      const differentPixels = pixelmatch(
        baselineBuffer,
        actualBuffer,
        diffBuffer,
        width,
        height,
        pixelmatchOptions
      );

      const differencePercentage = (differentPixels / pixelCount) * 100;
      const similarityPercentage = 100 - differencePercentage;
      const matches = differencePercentage <= (threshold * 100);

      let diffImagePath: string | undefined;

      if (createDiffImage && differentPixels > 0) {
        // Create enhanced diff image with color coding
        diffImagePath = await this.createDiff(
          baselineImage,
          actualImage,
          path.join(path.dirname(baselineImage), `diff_${Date.now()}.png`),
          {
            algorithm,
            colorOptions,
            includeAA
          }
        );
      }

      return {
        matches,
        differencePercentage: Math.round(differencePercentage * 100) / 100,
        similarityPercentage: Math.round(similarityPercentage * 100) / 100,
        diffImagePath,
        metadata: {
          baselineImage,
          actualImage,
          threshold,
          algorithm,
          pixelCount,
          differentPixels,
          baselineSize,
          actualSize,
          resized
        }
      };

    } catch (error) {
      throw new Error(`Screenshot comparison failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Create a visual difference image with color coding
   * @deprecated Use createDiff instead for more advanced functionality
   */
  async createDifferenceImage(
    baselineImage: string,
    actualImage: string,
    outputPath: string
  ): Promise<string> {
    return this.createDiff(baselineImage, actualImage, outputPath);
  }

  /**
   * Create an advanced visual difference image with multiple diff algorithms
   * and customizable color coding
   */
  async createDiff(
    baselineImage: string,
    actualImage: string,
    outputPath: string,
    options: {
      algorithm?: DiffAlgorithm;
      colorOptions?: DiffColorOptions;
      includeAA?: boolean;
      showSideBySide?: boolean;
    } = {}
  ): Promise<string> {
    const {
      algorithm = 'pixel-by-pixel',
      colorOptions = {},
      includeAA = false,
      showSideBySide = false
    } = options;

    try {
      // Load both images
      const [baseline, actual] = await Promise.all([
        Jimp.read(baselineImage),
        Jimp.read(actualImage)
      ]);

      const baselineWidth = baseline.getWidth();
      const baselineHeight = baseline.getHeight();
      const actualWidth = actual.getWidth();
      const actualHeight = actual.getHeight();

      // Handle different sizes by resizing to the larger dimensions
      const targetWidth = Math.max(baselineWidth, actualWidth);
      const targetHeight = Math.max(baselineHeight, actualHeight);

      if (baselineWidth !== targetWidth || baselineHeight !== targetHeight) {
        baseline.resize(targetWidth, targetHeight);
      }
      if (actualWidth !== targetWidth || actualHeight !== targetHeight) {
        actual.resize(targetWidth, targetHeight);
      }

      // Create diff image based on algorithm
      let diffImage: Jimp;

      if (algorithm === 'structural') {
        diffImage = await this.createStructuralDiff(baseline, actual, colorOptions);
      } else if (algorithm === 'perceptual') {
        diffImage = await this.createPerceptualDiff(baseline, actual, colorOptions);
      } else {
        diffImage = await this.createPixelDiff(baseline, actual, colorOptions, includeAA);
      }

      // Create side-by-side comparison if requested
      if (showSideBySide) {
        const sideBySideWidth = targetWidth * 3; // baseline + actual + diff
        const sideBySideImage = new Jimp(sideBySideWidth, targetHeight, '#FFFFFF');

        // Composite images side by side
        sideBySideImage.composite(baseline, 0, 0);
        sideBySideImage.composite(actual, targetWidth, 0);
        sideBySideImage.composite(diffImage, targetWidth * 2, 0);

        // Add labels
        const font = await Jimp.loadFont(Jimp.FONT_SANS_16_BLACK);
        sideBySideImage.print(font, 10, 10, 'Baseline');
        sideBySideImage.print(font, targetWidth + 10, 10, 'Actual');
        sideBySideImage.print(font, targetWidth * 2 + 10, 10, 'Diff');

        diffImage = sideBySideImage;
      }

      // Ensure output directory exists
      await this.ensureDirectoryExists(path.dirname(outputPath));

      // Save the diff image
      await diffImage.writeAsync(outputPath);

      return outputPath;

    } catch (error) {
      throw new Error(`Failed to create diff image: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Create pixel-by-pixel difference image
   */
  private async createPixelDiff(
    baseline: Jimp,
    actual: Jimp,
    colorOptions: DiffColorOptions,
    includeAA: boolean
  ): Promise<Jimp> {
    const width = baseline.getWidth();
    const height = baseline.getHeight();

    const {
      removedColor = [255, 0, 0], // Red for removed
      addedColor = [0, 255, 0],   // Green for added
      changedColor = [255, 255, 0], // Yellow for changed
      alpha = 255
    } = colorOptions;

    // Convert to RGBA buffers
    const baselineBuffer = new Uint8ClampedArray(baseline.bitmap.data);
    const actualBuffer = new Uint8ClampedArray(actual.bitmap.data);
    const diffBuffer = new Uint8ClampedArray(width * height * 4);

    // Use pixelmatch for accurate pixel comparison
    const differentPixels = pixelmatch(
      baselineBuffer,
      actualBuffer,
      diffBuffer,
      width,
      height,
      {
        threshold: 0.1,
        includeAA,
        alpha: 1.0,
        diffColor: changedColor,
        diffColorAlt: addedColor
      }
    );

    // Create enhanced diff image with custom color coding
    const diffImage = new Jimp(width, height);

    for (let i = 0; i < width * height; i++) {
      const pixelIndex = i * 4;
      const baselinePixel = [
        baselineBuffer[pixelIndex],
        baselineBuffer[pixelIndex + 1],
        baselineBuffer[pixelIndex + 2],
        baselineBuffer[pixelIndex + 3]
      ];
      const actualPixel = [
        actualBuffer[pixelIndex],
        actualBuffer[pixelIndex + 1],
        actualBuffer[pixelIndex + 2],
        actualBuffer[pixelIndex + 3]
      ];
      const diffPixel = [
        diffBuffer[pixelIndex],
        diffBuffer[pixelIndex + 1],
        diffBuffer[pixelIndex + 2],
        diffBuffer[pixelIndex + 3]
      ];

      let finalColor: [number, number, number, number];

      if (diffPixel[0] > 0 || diffPixel[1] > 0 || diffPixel[2] > 0) {
        // Pixel has difference
        const baselineGray = (baselinePixel[0] + baselinePixel[1] + baselinePixel[2]) / 3;
        const actualGray = (actualPixel[0] + actualPixel[1] + actualPixel[2]) / 3;

        if (baselineGray > actualGray + 10) {
          // Pixel was removed/darkened
          finalColor = [...removedColor, alpha];
        } else if (actualGray > baselineGray + 10) {
          // Pixel was added/brightened
          finalColor = [...addedColor, alpha];
        } else {
          // Pixel was changed
          finalColor = [...changedColor, alpha];
        }
      } else {
        // No difference, use actual pixel with reduced opacity
        finalColor = [actualPixel[0], actualPixel[1], actualPixel[2], 128];
      }

      const x = i % width;
      const y = Math.floor(i / width);
      const color = Jimp.rgbaToInt(finalColor[0], finalColor[1], finalColor[2], finalColor[3]);
      diffImage.setPixelColor(color, x, y);
    }

    return diffImage;
  }

  /**
   * Create perceptual difference image (focuses on human-visible differences)
   */
  private async createPerceptualDiff(
    baseline: Jimp,
    actual: Jimp,
    colorOptions: DiffColorOptions
  ): Promise<Jimp> {
    const width = baseline.getWidth();
    const height = baseline.getHeight();
    const diffImage = new Jimp(width, height);

    const {
      removedColor = [255, 0, 0],
      addedColor = [0, 255, 0],
      changedColor = [255, 255, 0],
      alpha = 255
    } = colorOptions;

    // Perceptual comparison using luminance
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const baselineColor = Jimp.intToRGBA(baseline.getPixelColor(x, y));
        const actualColor = Jimp.intToRGBA(actual.getPixelColor(x, y));

        // Calculate perceptual luminance
        const baselineLum = 0.299 * baselineColor.r + 0.587 * baselineColor.g + 0.114 * baselineColor.b;
        const actualLum = 0.299 * actualColor.r + 0.587 * actualColor.g + 0.114 * actualColor.b;

        const lumDiff = Math.abs(baselineLum - actualLum);

        // Calculate color difference
        const colorDiff = Math.sqrt(
          Math.pow(baselineColor.r - actualColor.r, 2) +
          Math.pow(baselineColor.g - actualColor.g, 2) +
          Math.pow(baselineColor.b - actualColor.b, 2)
        );

        let finalColor: [number, number, number, number];

        if (lumDiff > 20 || colorDiff > 30) {
          if (baselineLum > actualLum) {
            finalColor = [...removedColor, alpha];
          } else if (actualLum > baselineLum) {
            finalColor = [...addedColor, alpha];
          } else {
            finalColor = [...changedColor, alpha];
          }
        } else {
          // No significant perceptual difference
          finalColor = [actualColor.r, actualColor.g, actualColor.b, 128];
        }

        const color = Jimp.rgbaToInt(finalColor[0], finalColor[1], finalColor[2], finalColor[3]);
        diffImage.setPixelColor(color, x, y);
      }
    }

    return diffImage;
  }

  /**
   * Create structural difference image (focuses on edges and shapes)
   */
  private async createStructuralDiff(
    baseline: Jimp,
    actual: Jimp,
    colorOptions: DiffColorOptions
  ): Promise<Jimp> {
    const width = baseline.getWidth();
    const height = baseline.getHeight();

    const {
      removedColor = [255, 0, 0],
      addedColor = [0, 255, 0],
      changedColor = [255, 255, 0],
      alpha = 255
    } = colorOptions;

    // Apply edge detection (simple Sobel filter)
    const baselineEdges = this.detectEdges(baseline);
    const actualEdges = this.detectEdges(actual);

    const diffImage = new Jimp(width, height);

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const baselineEdge = baselineEdges.getPixelColor(x, y);
        const actualEdge = actualEdges.getPixelColor(x, y);

        const baselineGray = Jimp.intToRGBA(baselineEdge);
        const actualGray = Jimp.intToRGBA(actualEdge);

        const edgeDiff = Math.abs(baselineGray.r - actualGray.r);

        let finalColor: [number, number, number, number];

        if (edgeDiff > 50) {
          if (baselineGray.r > actualGray.r) {
            finalColor = [...removedColor, alpha];
          } else {
            finalColor = [...addedColor, alpha];
          }
        } else {
          // Get original pixel for no-difference areas
          const originalColor = Jimp.intToRGBA(actual.getPixelColor(x, y));
          finalColor = [originalColor.r, originalColor.g, originalColor.b, 128];
        }

        const color = Jimp.rgbaToInt(finalColor[0], finalColor[1], finalColor[2], finalColor[3]);
        diffImage.setPixelColor(color, x, y);
      }
    }

    return diffImage;
  }

  /**
   * Simple edge detection using Sobel filter
   */
  private detectEdges(image: Jimp): Jimp {
    const width = image.getWidth();
    const height = image.getHeight();
    const edges = image.clone().greyscale();

    const sobelX = [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]];
    const sobelY = [[-1, -2, -1], [0, 0, 0], [1, 2, 1]];

    for (let y = 1; y < height - 1; y++) {
      for (let x = 1; x < width - 1; x++) {
        let gx = 0, gy = 0;

        for (let ky = -1; ky <= 1; ky++) {
          for (let kx = -1; kx <= 1; kx++) {
            const pixel = Jimp.intToRGBA(image.getPixelColor(x + kx, y + ky));
            const gray = pixel.r; // Already greyscale

            gx += gray * sobelX[ky + 1][kx + 1];
            gy += gray * sobelY[ky + 1][kx + 1];
          }
        }

        const magnitude = Math.sqrt(gx * gx + gy * gy);
        const clampedMagnitude = Math.min(255, magnitude);

        const color = Jimp.rgbaToInt(clampedMagnitude, clampedMagnitude, clampedMagnitude, 255);
        edges.setPixelColor(color, x, y);
      }
    }

    return edges;
  }

  /**
   * Get all screenshots for a scenario
   */
  getScreenshotsByScenario(scenarioId: string): ScreenshotMetadata[] {
    return Array.from(this.metadata.values()).filter(
      meta => meta.scenarioId === scenarioId
    );
  }

  /**
   * Get all screenshots for a specific step
   */
  getScreenshotsByStep(scenarioId: string, stepIndex: number): ScreenshotMetadata[] {
    return Array.from(this.metadata.values()).filter(
      meta => meta.scenarioId === scenarioId && meta.stepIndex === stepIndex
    );
  }

  /**
   * Clean up old screenshots
   */
  async cleanupOldScreenshots(maxAge: number = 7 * 24 * 60 * 60 * 1000): Promise<number> {
    const now = Date.now();
    let deletedCount = 0;

    for (const [filePath, metadata] of this.metadata.entries()) {
      const age = now - metadata.timestamp.getTime();

      if (age > maxAge) {
        try {
          await fs.unlink(filePath);
          this.metadata.delete(filePath);
          deletedCount++;
        } catch (error) {
          console.warn(`Failed to delete old screenshot ${filePath}:`, error instanceof Error ? error.message : String(error));
        }
      }
    }

    return deletedCount;
  }

  /**
   * Archive screenshots for a completed run
   */
  async archiveRun(archivePath?: string): Promise<string> {
    const finalArchivePath = archivePath || path.join(
      this.organizationOptions.baseDir,
      'archives',
      `${this.runId}.tar.gz`
    );

    // Ensure archive directory exists
    await this.ensureDirectoryExists(path.dirname(finalArchivePath));

    // Create archive (simplified implementation)
    // In a real implementation, you would use a library like tar-stream
    const runScreenshots = Array.from(this.metadata.values());
    const manifest = {
      runId: this.runId,
      timestamp: new Date(),
      screenshots: runScreenshots,
      totalCount: runScreenshots.length
    };

    await fs.writeFile(
      finalArchivePath.replace('.tar.gz', '.json'),
      JSON.stringify(manifest, null, 2)
    );

    return finalArchivePath;
  }

  /**
   * Generate a unique filename
   */
  private generateFilePath(type: string, scenarioId?: string, stepIndex?: number): string {
    const timestamp = this.organizationOptions.includeTimestamp
      ? new Date().toISOString().replace(/[:.]/g, '-').split('.')[0]
      : '';

    let fileName = type;

    if (scenarioId) {
      fileName += `_${this.sanitizeFilename(scenarioId)}`;
    }

    if (stepIndex !== undefined) {
      fileName += `_step${stepIndex + 1}`;
    }

    if (timestamp) {
      fileName += `_${timestamp}`;
    }

    fileName += '.png';

    return path.join(this.getDirectoryPath(scenarioId), fileName);
  }

  /**
   * Get directory path based on organization strategy
   */
  private getDirectoryPath(scenarioId?: string): string {
    const baseDir = this.organizationOptions.baseDir;

    switch (this.organizationOptions.strategy) {
      case 'flat':
        return baseDir;

      case 'by-date':
        const date = new Date().toISOString().split('T')[0];
        return path.join(baseDir, date);

      case 'by-scenario':
        if (scenarioId) {
          return path.join(baseDir, this.sanitizeFilename(scenarioId));
        }
        return path.join(baseDir, 'unassigned');

      case 'by-run':
        return path.join(baseDir, this.runId);

      default:
        return baseDir;
    }
  }

  /**
   * Sanitize filename for filesystem compatibility
   */
  private sanitizeFilename(filename: string): string {
    return filename
      .replace(/[^a-z0-9]/gi, '_')
      .replace(/_+/g, '_')
      .replace(/^_|_$/g, '')
      .toLowerCase();
  }

  /**
   * Generate unique run ID
   */
  private generateRunId(): string {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('.')[0];
    const random = Math.random().toString(36).substring(2, 8);
    return `run_${timestamp}_${random}`;
  }

  /**
   * Calculate hash for file deduplication
   */
  private calculateHash(buffer: Buffer): string {
    return crypto.createHash('md5').update(buffer).digest('hex');
  }

  /**
   * Ensure directory exists
   */
  private async ensureDirectoryExists(dirPath: string): Promise<void> {
    try {
      await fs.access(dirPath);
    } catch {
      await fs.mkdir(dirPath, { recursive: true });
    }
  }

  /**
   * Sleep utility
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Export metadata to JSON
   */
  async exportMetadata(filePath?: string): Promise<string> {
    const finalFilePath = filePath || path.join(
      this.organizationOptions.baseDir,
      `${this.runId}_metadata.json`
    );

    const metadataArray = Array.from(this.metadata.values());
    const exportData = {
      runId: this.runId,
      exportTimestamp: new Date(),
      totalScreenshots: metadataArray.length,
      screenshots: metadataArray
    };

    await fs.writeFile(finalFilePath, JSON.stringify(exportData, null, 2));
    return finalFilePath;
  }

  /**
   * Batch compare multiple screenshot pairs
   */
  async batchCompareScreenshots(
    comparisons: Array<{
      baseline: string;
      actual: string;
      name: string;
      options?: ComparisonOptions;
    }>
  ): Promise<Array<ComparisonResult & { name: string }>> {
    const results: Array<ComparisonResult & { name: string }> = [];

    for (const comparison of comparisons) {
      try {
        const result = await this.compareScreenshots(
          comparison.baseline,
          comparison.actual,
          comparison.options
        );
        results.push({ ...result, name: comparison.name });
      } catch (error) {
        // Add failed comparison with error details
        results.push({
          name: comparison.name,
          matches: false,
          differencePercentage: 100,
          similarityPercentage: 0,
          metadata: {
            baselineImage: comparison.baseline,
            actualImage: comparison.actual,
            threshold: comparison.options?.threshold || 0.1,
            algorithm: comparison.options?.algorithm || 'pixel-by-pixel',
            pixelCount: 0,
            differentPixels: 0,
            baselineSize: { width: 0, height: 0 },
            actualSize: { width: 0, height: 0 },
            resized: false
          }
        });
      }
    }

    return results;
  }

  /**
   * Calculate similarity score using multiple algorithms
   */
  async calculateSimilarityScore(
    baseline: string,
    actual: string,
    options: {
      weights?: { pixel: number; perceptual: number; structural: number };
    } = {}
  ): Promise<{
    overall: number;
    pixel: number;
    perceptual: number;
    structural: number;
  }> {
    const { weights = { pixel: 0.4, perceptual: 0.4, structural: 0.2 } } = options;

    const [pixelResult, perceptualResult, structuralResult] = await Promise.all([
      this.compareScreenshots(baseline, actual, {
        algorithm: 'pixel-by-pixel',
        createDiffImage: false
      }),
      this.compareScreenshots(baseline, actual, {
        algorithm: 'perceptual',
        createDiffImage: false
      }),
      this.compareScreenshots(baseline, actual, {
        algorithm: 'structural',
        createDiffImage: false
      })
    ]);

    const overall =
      pixelResult.similarityPercentage * weights.pixel +
      perceptualResult.similarityPercentage * weights.perceptual +
      structuralResult.similarityPercentage * weights.structural;

    return {
      overall: Math.round(overall * 100) / 100,
      pixel: pixelResult.similarityPercentage,
      perceptual: perceptualResult.similarityPercentage,
      structural: structuralResult.similarityPercentage
    };
  }

  /**
   * Generate comparison report
   */
  async generateComparisonReport(
    results: Array<ComparisonResult & { name: string }>,
    outputPath?: string
  ): Promise<string> {
    const reportPath = outputPath || path.join(
      this.organizationOptions.baseDir,
      `comparison_report_${this.runId}.json`
    );

    const report = {
      runId: this.runId,
      timestamp: new Date(),
      summary: {
        totalComparisons: results.length,
        passed: results.filter(r => r.matches).length,
        failed: results.filter(r => !r.matches).length,
        averageSimilarity: results.reduce((sum, r) => sum + r.similarityPercentage, 0) / results.length
      },
      results: results.map(result => ({
        name: result.name,
        matches: result.matches,
        similarity: result.similarityPercentage,
        difference: result.differencePercentage,
        algorithm: result.metadata.algorithm,
        diffImagePath: result.diffImagePath,
        resized: result.metadata.resized,
        pixelCount: result.metadata.pixelCount,
        differentPixels: result.metadata.differentPixels
      }))
    };

    await this.ensureDirectoryExists(path.dirname(reportPath));
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2));
    return reportPath;
  }

  /**
   * Get run statistics
   */
  getRunStatistics() {
    const screenshots = Array.from(this.metadata.values());
    const byScenario = screenshots.reduce((acc, meta) => {
      if (meta.scenarioId) {
        acc[meta.scenarioId] = (acc[meta.scenarioId] || 0) + 1;
      }
      return acc;
    }, {} as Record<string, number>);

    const totalSize = screenshots.reduce((sum, meta) => sum + (meta.fileSize || 0), 0);

    return {
      runId: this.runId,
      totalScreenshots: screenshots.length,
      byScenario,
      totalSizeBytes: totalSize,
      totalSizeMB: Math.round(totalSize / (1024 * 1024) * 100) / 100,
      oldestScreenshot: screenshots.length > 0 ? Math.min(...screenshots.map(s => s.timestamp.getTime())) : null,
      newestScreenshot: screenshots.length > 0 ? Math.max(...screenshots.map(s => s.timestamp.getTime())) : null
    };
  }
}

/**
 * Create a screenshot manager instance
 */
export function createScreenshotManager(options?: Partial<OrganizationOptions>): ScreenshotManager {
  return new ScreenshotManager(options);
}

/**
 * Convenience function for quick page screenshot
 */
export async function capturePageScreenshot(
  page: Page,
  filePath: string,
  options?: ScreenshotOptions
): Promise<void> {
  const finalOptions = { ...DEFAULT_OPTIONS, ...options, path: filePath };
  await page.screenshot(finalOptions);
}

/**
 * Convenience function for quick element screenshot
 */
export async function captureElementScreenshot(
  element: Locator,
  filePath: string,
  options?: ScreenshotOptions
): Promise<void> {
  const finalOptions = { ...DEFAULT_OPTIONS, ...options, path: filePath };
  await element.screenshot(finalOptions);
}
