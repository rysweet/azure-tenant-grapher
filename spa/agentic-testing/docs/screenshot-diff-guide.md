# Screenshot Diff Visualization Guide

This guide explains how to use the advanced screenshot diff functionality implemented in the agentic testing system.

## Overview

The screenshot diff system provides comprehensive image comparison capabilities with:
- Multiple diff algorithms (pixel-by-pixel, perceptual, structural)
- Customizable color coding for visual differences
- Support for different image sizes
- Batch processing capabilities
- Detailed similarity scoring
- Advanced reporting features

## Quick Start

```typescript
import { createScreenshotManager } from './src/utils/screenshot';

const screenshotManager = createScreenshotManager({
  baseDir: './screenshots',
  strategy: 'by-scenario'
});

// Basic comparison
const result = await screenshotManager.compareScreenshots(
  './baseline.png',
  './actual.png'
);

console.log(`Similarity: ${result.similarityPercentage}%`);
console.log(`Match: ${result.matches}`);
```

## Diff Algorithms

### 1. Pixel-by-Pixel (`pixel-by-pixel`)
- **Best for:** Exact pixel-level comparisons
- **Use case:** UI regression testing, pixel-perfect layouts
- **Features:** High precision, antialiasing detection

```typescript
const result = await screenshotManager.compareScreenshots(
  baseline,
  actual,
  {
    algorithm: 'pixel-by-pixel',
    threshold: 0.05, // 5% difference threshold
    includeAA: true  // Include antialiasing detection
  }
);
```

### 2. Perceptual (`perceptual`)
- **Best for:** Human-visible differences
- **Use case:** Content validation, visual quality assessment
- **Features:** Luminance-based comparison, color perception

```typescript
const result = await screenshotManager.compareScreenshots(
  baseline,
  actual,
  {
    algorithm: 'perceptual',
    threshold: 0.1
  }
);
```

### 3. Structural (`structural`)
- **Best for:** Layout and shape changes
- **Use case:** Component structure validation, edge detection
- **Features:** Edge detection, shape analysis

```typescript
const result = await screenshotManager.compareScreenshots(
  baseline,
  actual,
  {
    algorithm: 'structural',
    threshold: 0.15
  }
);
```

## Color Coding Options

Customize the visual diff colors to match your needs:

```typescript
const result = await screenshotManager.compareScreenshots(
  baseline,
  actual,
  {
    colorOptions: {
      removedColor: [255, 0, 0],    // Red for removed pixels
      addedColor: [0, 255, 0],      // Green for added pixels  
      changedColor: [255, 255, 0],  // Yellow for changed pixels
      alpha: 200                    // Transparency (0-255)
    }
  }
);
```

## Advanced Diff Images

Create enhanced diff visualizations:

```typescript
// Create side-by-side comparison
const diffPath = await screenshotManager.createDiff(
  baseline,
  actual,
  './output/diff.png',
  {
    algorithm: 'pixel-by-pixel',
    showSideBySide: true,  // Shows baseline | actual | diff
    colorOptions: {
      removedColor: [220, 20, 60],   // Crimson
      addedColor: [34, 139, 34],     // Forest green
      changedColor: [255, 165, 0]    // Orange
    }
  }
);
```

## Batch Processing

Process multiple screenshot comparisons:

```typescript
const results = await screenshotManager.batchCompareScreenshots([
  {
    name: 'Homepage',
    baseline: './screenshots/home_baseline.png',
    actual: './screenshots/home_actual.png',
    options: { algorithm: 'perceptual', threshold: 0.05 }
  },
  {
    name: 'Login',
    baseline: './screenshots/login_baseline.png', 
    actual: './screenshots/login_actual.png',
    options: { algorithm: 'pixel-by-pixel', threshold: 0.02 }
  }
]);

// Generate report
const reportPath = await screenshotManager.generateComparisonReport(
  results,
  './reports/comparison_report.json'
);
```

## Multi-Algorithm Scoring

Get comprehensive similarity scores using multiple algorithms:

```typescript
const score = await screenshotManager.calculateSimilarityScore(
  baseline,
  actual,
  {
    weights: { 
      pixel: 0.4,      // 40% weight for pixel comparison
      perceptual: 0.4, // 40% weight for perceptual comparison  
      structural: 0.2  // 20% weight for structural comparison
    }
  }
);

console.log(`Overall Similarity: ${score.overall}%`);
console.log(`Breakdown - Pixel: ${score.pixel}%, Perceptual: ${score.perceptual}%, Structural: ${score.structural}%`);
```

## Handling Different Image Sizes

The system automatically handles images of different sizes:

- Images are resized to match the larger dimensions
- Aspect ratios are preserved
- The `resized` flag indicates if resizing occurred

```typescript
const result = await screenshotManager.compareScreenshots(baseline, actual);

if (result.metadata.resized) {
  console.log('Images were resized for comparison');
  console.log('Baseline:', result.metadata.baselineSize);
  console.log('Actual:', result.metadata.actualSize);
}
```

## Integration with Playwright

Use with Playwright test scenarios:

```typescript
import { test, expect } from '@playwright/test';
import { createScreenshotManager } from './utils/screenshot';

test('visual regression test', async ({ page }) => {
  const screenshotManager = createScreenshotManager();
  
  await page.goto('/dashboard');
  
  // Capture current screenshot
  const current = await screenshotManager.capturePageScreenshot(page, {
    scenarioId: 'dashboard-test'
  });
  
  // Compare with baseline
  const result = await screenshotManager.compareScreenshots(
    './baselines/dashboard.png',
    current.filePath,
    {
      algorithm: 'perceptual',
      threshold: 0.05
    }
  );
  
  expect(result.matches).toBeTruthy();
});
```

## Configuration Options

### Comparison Options
```typescript
interface ComparisonOptions {
  threshold?: number;        // Similarity threshold (0-1)
  algorithm?: DiffAlgorithm; // 'pixel-by-pixel' | 'perceptual' | 'structural'
  includeAA?: boolean;       // Include antialiasing detection
  colorOptions?: DiffColorOptions;
  createDiffImage?: boolean; // Generate diff image
}
```

### Color Options
```typescript
interface DiffColorOptions {
  removedColor?: [number, number, number]; // RGB for removed pixels
  addedColor?: [number, number, number];   // RGB for added pixels
  changedColor?: [number, number, number]; // RGB for changed pixels
  alpha?: number;                          // Alpha value (0-255)
}
```

## Best Practices

1. **Choose the right algorithm:**
   - Use `pixel-by-pixel` for exact UI regression testing
   - Use `perceptual` for content and visual quality validation
   - Use `structural` for layout and component structure testing

2. **Set appropriate thresholds:**
   - Lower thresholds (0.01-0.05) for strict comparisons
   - Higher thresholds (0.1-0.2) for more flexible comparisons

3. **Use batch processing for efficiency:**
   - Process multiple screenshots in a single operation
   - Generate comprehensive reports

4. **Leverage side-by-side diffs:**
   - Enable `showSideBySide` for detailed visual analysis
   - Useful for debugging and manual review

5. **Customize colors for clarity:**
   - Use high-contrast colors for better visibility
   - Adjust alpha values for overlay transparency

## Troubleshooting

**Images not loading:**
- Ensure image paths are correct and accessible
- Check file permissions and formats (PNG/JPEG supported)

**High false positives:**
- Increase threshold values
- Use `perceptual` algorithm instead of `pixel-by-pixel`
- Enable antialiasing detection with `includeAA: true`

**Performance issues:**
- Disable diff image creation for batch operations: `createDiffImage: false`
- Use appropriate algorithms (structural is fastest, pixel-by-pixel is slowest)
- Process images asynchronously in batches

## Report Format

Generated reports include:

```json
{
  "runId": "run_2025-01-01T12-00-00_abc123",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "summary": {
    "totalComparisons": 3,
    "passed": 2,
    "failed": 1,
    "averageSimilarity": 87.5
  },
  "results": [
    {
      "name": "Homepage",
      "matches": true,
      "similarity": 95.2,
      "difference": 4.8,
      "algorithm": "perceptual",
      "diffImagePath": "/path/to/diff.png",
      "resized": false,
      "pixelCount": 1920000,
      "differentPixels": 92160
    }
  ]
}
```

This comprehensive screenshot diff system provides all the tools needed for robust visual testing and comparison in your Playwright-based test automation.