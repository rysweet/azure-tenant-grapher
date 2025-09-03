/**
 * Screenshot Diff Visualization Demo
 * 
 * This example demonstrates the comprehensive screenshot diff functionality
 * with multiple algorithms, color coding, and batch processing capabilities.
 */

import { ScreenshotManager, createScreenshotManager } from '../src/utils/screenshot';

async function demonstrateScreenshotDiff() {
  console.log('🔍 Screenshot Diff Visualization Demo\n');

  // Create a screenshot manager
  const screenshotManager = createScreenshotManager({
    baseDir: './screenshots',
    strategy: 'by-scenario',
    includeTimestamp: true
  });

  // Example: Compare two screenshots with different algorithms
  const baselineImagePath = './screenshots/baseline.png';
  const actualImagePath = './screenshots/actual.png';

  try {
    console.log('1. Pixel-by-pixel comparison with custom colors:');
    const pixelResult = await screenshotManager.compareScreenshots(
      baselineImagePath,
      actualImagePath,
      {
        algorithm: 'pixel-by-pixel',
        threshold: 0.05, // 5% difference threshold
        includeAA: true,
        colorOptions: {
          removedColor: [255, 0, 0],    // Red for removed pixels
          addedColor: [0, 255, 0],      // Green for added pixels
          changedColor: [255, 255, 0],  // Yellow for changed pixels
          alpha: 200                    // Semi-transparent overlay
        }
      }
    );

    console.log(`   - Similarity: ${pixelResult.similarityPercentage}%`);
    console.log(`   - Difference: ${pixelResult.differencePercentage}%`);
    console.log(`   - Match: ${pixelResult.matches ? 'Yes' : 'No'}`);
    console.log(`   - Diff Image: ${pixelResult.diffImagePath}\n`);

    console.log('2. Perceptual comparison (human vision-focused):');
    const perceptualResult = await screenshotManager.compareScreenshots(
      baselineImagePath,
      actualImagePath,
      {
        algorithm: 'perceptual',
        threshold: 0.1,
        createDiffImage: true
      }
    );

    console.log(`   - Similarity: ${perceptualResult.similarityPercentage}%`);
    console.log(`   - Algorithm: ${perceptualResult.metadata.algorithm}\n`);

    console.log('3. Structural comparison (edges and shapes):');
    const structuralResult = await screenshotManager.compareScreenshots(
      baselineImagePath,
      actualImagePath,
      {
        algorithm: 'structural',
        threshold: 0.15
      }
    );

    console.log(`   - Similarity: ${structuralResult.similarityPercentage}%\n`);

    console.log('4. Multi-algorithm similarity score:');
    const similarityScore = await screenshotManager.calculateSimilarityScore(
      baselineImagePath,
      actualImagePath,
      {
        weights: { pixel: 0.5, perceptual: 0.3, structural: 0.2 }
      }
    );

    console.log(`   - Overall Score: ${similarityScore.overall}%`);
    console.log(`   - Pixel Score: ${similarityScore.pixel}%`);
    console.log(`   - Perceptual Score: ${similarityScore.perceptual}%`);
    console.log(`   - Structural Score: ${similarityScore.structural}%\n`);

    console.log('5. Advanced diff image with side-by-side comparison:');
    const diffImagePath = await screenshotManager.createDiff(
      baselineImagePath,
      actualImagePath,
      './screenshots/advanced_diff.png',
      {
        algorithm: 'pixel-by-pixel',
        showSideBySide: true,
        colorOptions: {
          removedColor: [220, 20, 60],   // Crimson for removed
          addedColor: [34, 139, 34],     // Forest green for added
          changedColor: [255, 165, 0],   // Orange for changed
          alpha: 180
        }
      }
    );

    console.log(`   - Created: ${diffImagePath}\n`);

    console.log('6. Batch comparison example:');
    const batchResults = await screenshotManager.batchCompareScreenshots([
      {
        name: 'Homepage',
        baseline: './screenshots/homepage_baseline.png',
        actual: './screenshots/homepage_actual.png',
        options: { algorithm: 'perceptual', threshold: 0.05 }
      },
      {
        name: 'Login Page',
        baseline: './screenshots/login_baseline.png',
        actual: './screenshots/login_actual.png',
        options: { algorithm: 'pixel-by-pixel', threshold: 0.02 }
      },
      {
        name: 'Dashboard',
        baseline: './screenshots/dashboard_baseline.png',
        actual: './screenshots/dashboard_actual.png',
        options: { algorithm: 'structural', threshold: 0.1 }
      }
    ]);

    console.log('   Batch Results:');
    batchResults.forEach(result => {
      console.log(`   - ${result.name}: ${result.matches ? 'PASS' : 'FAIL'} (${result.similarityPercentage}%)`);
    });

    console.log('\n7. Generate comprehensive report:');
    const reportPath = await screenshotManager.generateComparisonReport(
      batchResults,
      './screenshots/comparison_report.json'
    );

    console.log(`   - Report saved: ${reportPath}\n`);

  } catch (error) {
    console.error('Error during screenshot comparison:', error instanceof Error ? error.message : String(error));
  }

  console.log('✅ Demo completed! Key features showcased:');
  console.log('   • Multiple diff algorithms (pixel, perceptual, structural)');
  console.log('   • Customizable color coding for visual diffs');
  console.log('   • Support for different image sizes');
  console.log('   • Batch processing capabilities');
  console.log('   • Comprehensive similarity scoring');
  console.log('   • Side-by-side diff visualization');
  console.log('   • Detailed reporting and metadata');
}

// Run the demo if this file is executed directly
if (require.main === module) {
  demonstrateScreenshotDiff().catch(console.error);
}

export { demonstrateScreenshotDiff };