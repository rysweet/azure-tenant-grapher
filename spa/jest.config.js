module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/tests', '<rootDir>/main', '<rootDir>/backend', '<rootDir>/renderer'],
  testMatch: ['**/__tests__/**/*.(ts|tsx)', '**/?(*.)+(spec|test).(ts|tsx)'],
  testEnvironmentOptions: {
    customExportConditions: ['node', 'node-addons'],
  },
  transform: {
    '^.+\\.(ts|tsx)$': ['ts-jest', {
      tsconfig: {
        jsx: 'react',
        esModuleInterop: true,
        allowSyntheticDefaultImports: true,
      },
    }],
  },
  collectCoverageFrom: [
    'main/**/*.ts',
    'backend/**/*.ts',
    'renderer/src/**/*.{ts,tsx}',
    '!main/**/*.d.ts',
    '!main/**/*.test.ts',
    '!backend/**/*.d.ts',
    '!backend/**/*.test.ts',
    '!renderer/src/**/*.d.ts',
    '!renderer/src/main.tsx',
    '!renderer/src/vite-env.d.ts',
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/renderer/src/$1',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },
  // Don't use setup file for backend tests (they don't need jsdom)
  setupFilesAfterEnv: [],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx'],
  // Use different test environments based on test location
  projects: [
    {
      displayName: 'backend',
      testMatch: ['<rootDir>/backend/**/*.test.ts'],
      testEnvironment: 'node',
      preset: 'ts-jest',
      transform: {
        '^.+\\.ts$': ['ts-jest', {
          tsconfig: {
            esModuleInterop: true,
            allowSyntheticDefaultImports: true,
          },
        }],
      },
    },
    {
      displayName: 'frontend',
      testMatch: ['<rootDir>/renderer/**/*.test.{ts,tsx}', '<rootDir>/main/**/*.test.ts', '<rootDir>/tests/**/*.test.{ts,tsx}'],
      testEnvironment: 'jsdom',
      preset: 'ts-jest',
      setupFilesAfterEnv: ['<rootDir>/tests/setupTests.ts'],
      transform: {
        '^.+\\.(ts|tsx)$': ['ts-jest', {
          tsconfig: {
            jsx: 'react',
            esModuleInterop: true,
            allowSyntheticDefaultImports: true,
          },
        }],
      },
      moduleNameMapper: {
        '^@/(.*)$': '<rootDir>/renderer/src/$1',
        '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
      },
    },
  ],
};
