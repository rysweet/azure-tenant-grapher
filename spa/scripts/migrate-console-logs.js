#!/usr/bin/env node

/**
 * Migration script to replace console.* statements with logger.*
 * This script will:
 * 1. Find all TypeScript/JavaScript files
 * 2. Replace console.log/error/warn/debug with logger equivalents
 * 3. Add logger imports where needed
 */

const fs = require('fs');
const path = require('path');
const glob = require('glob');

// Configuration
const DIRECTORIES_TO_PROCESS = [
  'spa/main',
  'spa/renderer/src',
  'spa/backend/src'
];

const FILES_TO_SKIP = [
  'logger.ts',
  'logger.js',
  'logger-setup.ts',
  'logger-setup.js',
  'logger-transports.ts',
  'logger-transports.js',
  'migrate-console-logs.js'
];

const IMPORT_STATEMENTS = {
  backend: "import { createLogger } from './logger-setup';\n\nconst logger = createLogger('{{COMPONENT}}');",
  main: "import { createLogger } from './logger-setup';\n\nconst logger = createLogger('{{COMPONENT}}');",
  renderer: "import { createLogger } from '@/utils/logger';\n\nconst logger = createLogger('{{COMPONENT}}');"
};

/**
 * Determine which type of file this is based on path
 */
function getFileType(filePath) {
  if (filePath.includes('spa/backend')) return 'backend';
  if (filePath.includes('spa/main')) return 'main';
  if (filePath.includes('spa/renderer')) return 'renderer';
  return null;
}

/**
 * Extract component name from file path
 */
function getComponentName(filePath) {
  const basename = path.basename(filePath, path.extname(filePath));
  return basename.replace(/[-_]/g, '');
}

/**
 * Check if file already has logger import
 */
function hasLoggerImport(content) {
  return content.includes('createLogger') || 
         content.includes('from \'./logger\'') ||
         content.includes('from "./logger"') ||
         content.includes('logger-setup');
}

/**
 * Add logger import to file content
 */
function addLoggerImport(content, filePath) {
  const fileType = getFileType(filePath);
  if (!fileType) return content;

  const componentName = getComponentName(filePath);
  let importStatement = IMPORT_STATEMENTS[fileType].replace('{{COMPONENT}}', componentName);

  // Adjust import path based on file location
  if (fileType === 'backend' || fileType === 'main') {
    const fileDir = path.dirname(filePath);
    const setupPath = path.join(fileDir, 'logger-setup.ts');
    
    if (!fs.existsSync(setupPath)) {
      // Need to go up directories to find logger-setup
      const depth = filePath.split('/').length - filePath.split('/').indexOf('src') - 1;
      const relativePath = '../'.repeat(depth) + 'logger-setup';
      importStatement = importStatement.replace('./logger-setup', relativePath);
    }
  }

  // Find the last import statement
  const importRegex = /^import .* from .*;?$/gm;
  const imports = content.match(importRegex);
  
  if (imports && imports.length > 0) {
    const lastImport = imports[imports.length - 1];
    const lastImportIndex = content.lastIndexOf(lastImport);
    const insertPosition = lastImportIndex + lastImport.length;
    
    return content.slice(0, insertPosition) + '\n' + importStatement + '\n' + content.slice(insertPosition);
  } else {
    // No imports found, add at the beginning
    return importStatement + '\n\n' + content;
  }
}

/**
 * Replace console statements with logger
 */
function replaceConsoleStatements(content) {
  let modified = content;
  let changeCount = 0;

  // Replace console.log
  modified = modified.replace(/console\.log\(/g, () => {
    changeCount++;
    return 'logger.info(';
  });

  // Replace console.error
  modified = modified.replace(/console\.error\(/g, () => {
    changeCount++;
    return 'logger.error(';
  });

  // Replace console.warn
  modified = modified.replace(/console\.warn\(/g, () => {
    changeCount++;
    return 'logger.warn(';
  });

  // Replace console.debug
  modified = modified.replace(/console\.debug\(/g, () => {
    changeCount++;
    return 'logger.debug(';
  });

  // Replace console.info
  modified = modified.replace(/console\.info\(/g, () => {
    changeCount++;
    return 'logger.info(';
  });

  // Handle commented console.log statements
  modified = modified.replace(/\/\/\s*console\.log\(/g, () => {
    changeCount++;
    return 'logger.debug(';
  });

  return { content: modified, changeCount };
}

/**
 * Process a single file
 */
function processFile(filePath) {
  const fileName = path.basename(filePath);
  
  // Skip files in the skip list
  if (FILES_TO_SKIP.includes(fileName)) {
    return { skipped: true };
  }

  try {
    let content = fs.readFileSync(filePath, 'utf8');
    const originalContent = content;

    // Replace console statements
    const { content: modifiedContent, changeCount } = replaceConsoleStatements(content);
    
    if (changeCount === 0) {
      return { skipped: true, reason: 'No console statements found' };
    }

    content = modifiedContent;

    // Add logger import if needed and not already present
    if (!hasLoggerImport(content)) {
      content = addLoggerImport(content, filePath);
    }

    // Write back the file
    if (content !== originalContent) {
      fs.writeFileSync(filePath, content, 'utf8');
      return { success: true, changeCount };
    }

    return { skipped: true, reason: 'No changes needed' };
  } catch (error) {
    return { error: error.message };
  }
}

/**
 * Main function
 */
function main() {
  console.log('🔄 Starting console.log migration...\n');

  let totalFiles = 0;
  let modifiedFiles = 0;
  let skippedFiles = 0;
  let errorFiles = 0;
  let totalChanges = 0;

  DIRECTORIES_TO_PROCESS.forEach(dir => {
    const fullPath = path.join(process.cwd(), dir);
    
    if (!fs.existsSync(fullPath)) {
      console.log(`⚠️  Directory not found: ${dir}`);
      return;
    }

    const pattern = path.join(fullPath, '**/*.{ts,tsx,js,jsx}');
    const files = glob.sync(pattern, { ignore: ['**/node_modules/**'] });

    console.log(`📁 Processing ${files.length} files in ${dir}...`);

    files.forEach(file => {
      totalFiles++;
      const result = processFile(file);
      const relativePath = path.relative(process.cwd(), file);

      if (result.success) {
        modifiedFiles++;
        totalChanges += result.changeCount;
        console.log(`  ✅ Modified: ${relativePath} (${result.changeCount} changes)`);
      } else if (result.skipped) {
        skippedFiles++;
        if (result.reason && result.reason !== 'No console statements found') {
          console.log(`  ⏭️  Skipped: ${relativePath} - ${result.reason}`);
        }
      } else if (result.error) {
        errorFiles++;
        console.log(`  ❌ Error: ${relativePath} - ${result.error}`);
      }
    });

    console.log('');
  });

  // Summary
  console.log('📊 Migration Summary:');
  console.log(`  Total files processed: ${totalFiles}`);
  console.log(`  Files modified: ${modifiedFiles}`);
  console.log(`  Files skipped: ${skippedFiles}`);
  console.log(`  Files with errors: ${errorFiles}`);
  console.log(`  Total replacements: ${totalChanges}`);
  console.log('\n✨ Migration complete!');

  if (modifiedFiles > 0) {
    console.log('\n⚠️  Please review the changes and test your application.');
    console.log('   The logger imports have been added automatically but may need adjustment.');
  }
}

// Check if glob is installed
try {
  require('glob');
} catch (e) {
  console.error('❌ Error: glob package is required. Please install it first:');
  console.error('   npm install --save-dev glob');
  process.exit(1);
}

// Run the migration
main();