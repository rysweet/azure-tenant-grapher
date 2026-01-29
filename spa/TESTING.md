# Dual Authentication Testing Strategy

This document describes the comprehensive TDD test suite for the dual-account Azure authentication feature.

## Testing Pyramid

Following the testing pyramid principle:

- **60% Unit Tests** - Fast, isolated component tests with mocks
- **30% Integration Tests** - Multiple components working together
- **10% E2E Tests** - Complete user workflows

## Test Coverage Summary

### Backend Tests (Unit - 60%)

#### 1. TokenStorageService (`spa/backend/src/services/__tests__/token-storage.service.test.ts`)
- **Token Encryption** (8 tests)
  - AES-256-GCM encryption
  - Decryption correctness
  - Wrong key detection
  - Corrupted data handling
- **Token Storage** (3 tests)
  - File-based storage for both tenants
  - Write failure handling
- **Token Retrieval** (5 tests)
  - Decrypt and return tokens
  - Missing file handling
  - Corrupted file handling
  - Permission errors
- **Token Validation** (4 tests)
  - Tenant ID matching (SECURITY CRITICAL)
  - Expiration checking
  - Refresh need detection
- **Token Clearing** (4 tests)
  - Individual tenant clearing
  - All tenants clearing
  - Missing file during clear
- **Edge Cases** (3 tests)
  - Empty tokens
  - Very long tokens
  - Special characters

**Total: 27 tests**

#### 2. DualAuthService (`spa/backend/src/services/__tests__/dual-auth.service.test.ts`)
- **Device Code Flow - Start** (5 tests)
  - Start flow for both tenants
  - Invalid tenant validation
  - Azure AD error handling
- **Device Code Flow - Polling** (4 tests)
  - Success, pending, expired states
  - Tenant ID validation (SECURITY CRITICAL)
- **Token Refresh** (4 tests)
  - Auto-refresh expiring tokens
  - Skip refresh for valid tokens
  - No token error handling
  - Refresh failure handling
- **Auto-Refresh Timer** (3 tests)
  - Timer start/stop
  - Both tenants refreshed
- **Sign Out** (3 tests)
  - Individual tenant sign out
  - All tenants sign out
- **Authentication Status** (3 tests)
  - Authenticated status
  - Not authenticated status
  - Expired token status
- **Security - Tenant Validation** (3 tests)
  - Tenant ID validation (CRITICAL)
  - Cross-tenant prevention (SECURITY CRITICAL)
- **Edge Cases** (2 tests)
  - Concurrent refresh requests
  - Network timeout

**Total: 27 tests**

#### 3. Auth Routes (`spa/backend/src/routes/__tests__/auth.routes.test.ts`)
- **POST /api/auth/device-code/start** (6 tests)
  - Both tenant types
  - Input validation
  - CSRF protection
- **GET /api/auth/device-code/status** (4 tests)
  - Success, pending, timeout states
  - Parameter validation
- **POST /api/auth/signout** (4 tests)
  - Individual/all tenant sign out
  - CSRF protection
- **GET /api/auth/token** (4 tests)
  - Token retrieval
  - Unauthorized handling
  - Parameter validation
- **Security - Rate Limiting** (1 test)
  - Rate limit enforcement
- **Security - Input Sanitization** (2 tests)
  - XSS prevention
  - SQL injection prevention
- **Error Handling** (2 tests)
  - Internal errors
  - Malformed JSON
- **Edge Cases** (3 tests)
  - Empty/long tenant IDs
  - Concurrent requests

**Total: 26 tests**

### Frontend Tests (Unit - 60%)

#### 4. AuthContext (`spa/renderer/src/context/__tests__/AuthContext.test.tsx`)
- **Initial State** (2 tests)
  - Unauthenticated state
  - Check existing tokens on mount
- **Device Code Flow** (5 tests)
  - Start flow
  - Polling
  - State update on success
  - Stop polling on success
  - Timeout handling
- **Auto-Refresh** (3 tests)
  - Timer start
  - Token refresh before expiry
  - Stop on sign out
- **Sign Out** (2 tests)
  - Individual sign out
  - All tenants sign out
- **Feature Gates** (3 tests)
  - Scanning enabled (source only)
  - Deployment enabled (both tenants)
  - All disabled (no auth)
- **Error Handling** (2 tests)
  - API errors
  - Polling errors
- **Edge Cases** (2 tests)
  - Concurrent sign-in requests
  - Timer cleanup on unmount

**Total: 19 tests**

#### 5. AuthTab (`spa/renderer/src/components/__tests__/AuthTab.test.tsx`)
- **Rendering** (4 tests)
  - Tenant cards
  - Tenant IDs
  - Sign In/Out buttons
- **Status Indicators** (4 tests)
  - Authenticated/Not authenticated
  - Token expiration
  - Expiry warning
- **User Interactions** (4 tests)
  - Sign In/Out clicks
  - Modal open/close
- **Feature Gates Display** (3 tests)
  - Scanning/Deployment enabled states
- **Loading States** (2 tests)
  - Disabled buttons
  - Spinner display
- **Error Handling** (2 tests)
  - Error message display
  - Retry after error
- **Accessibility** (3 tests)
  - Accessible labels
  - Button labels
  - Keyboard navigation

**Total: 22 tests**

#### 6. AuthLoginModal (`spa/renderer/src/components/__tests__/AuthLoginModal.test.tsx`)
- **Rendering** (4 tests)
  - Modal open/close
  - Device code display
  - Verification URL link
  - QR code
- **Instructions** (2 tests)
  - Step-by-step instructions
  - Code highlighting
- **Expiration Timer** (4 tests)
  - Time remaining display
  - Countdown updates
  - Warning display
  - Auto-close on expiry
- **Copy to Clipboard** (3 tests)
  - Copy button
  - Clipboard write
  - "Copied!" feedback
- **Auto-Close on Success** (3 tests)
  - Auto-close trigger
  - Success message
  - Delayed close
- **User Interactions** (3 tests)
  - Cancel button
  - Backdrop click
  - Escape key
- **Different Tenant Types** (2 tests)
  - Source tenant title
  - Target tenant title
- **Error Handling** (2 tests)
  - Error display
  - Retry button
- **Accessibility** (3 tests)
  - Modal title
  - Button labels
  - Focus trap
  - Screen reader announcements
- **Edge Cases** (2 tests)
  - Missing device code
  - Timer cleanup

**Total: 28 tests**

### Python CLI Tests (Unit - 60%)

#### 7. Azure Discovery Service Token Auth (`src/services/__tests__/test_azure_discovery_service_token.py`)
- **Environment Token Usage** (3 tests)
  - Use AZURE_ACCESS_TOKEN when provided
  - Fallback to DefaultAzureCredential
  - Token validation
- **Security** (6 tests)
  - Token validation before use (SECURITY)
  - Token length validation
  - Environment cleanup (SECURITY)
  - No token logging (SECURITY CRITICAL)
  - Tenant ID validation (SECURITY CRITICAL)
  - Prevent cross-tenant usage (SECURITY CRITICAL)
- **Error Handling** (2 tests)
  - Expired token handling
  - Invalid token handling
- **Priority & Support** (3 tests)
  - Token priority over default credential
  - Source tenant support
  - Target tenant support
- **Custom Credential** (1 test)
  - Token credential wrapper
- **Edge Cases** (3 tests)
  - Token refresh warning
  - Concurrent scans
  - Case sensitivity

**Total: 18 tests**

### Integration Tests (30%)

#### 8. Dual Auth Flow Integration (`tests/integration/test_dual_auth_flow.test.ts`)
- **Complete Flow** (1 test)
  - Start → Poll → Store → Retrieve (end-to-end)
- **Dual Tenant Flow** (1 test)
  - Authenticate both tenants independently
- **Encryption Integration** (1 test)
  - Encrypt → Store → Retrieve → Decrypt
- **Sign Out Integration** (1 test)
  - Clear from storage and API
- **Token Refresh Integration** (1 test)
  - Auto-refresh expiring token
- **Error Handling** (2 tests)
  - Timeout handling
  - Corrupted file handling
- **Security** (1 test)
  - Cross-tenant prevention (SECURITY CRITICAL)
- **Concurrent Operations** (1 test)
  - Concurrent authentication attempts

**Total: 9 tests**

### E2E Tests (10%)

#### 9. Complete Authentication E2E (`tests/e2e/test_complete_authentication.spec.ts`)
- **Source Tenant Flow** (1 test)
  - Navigate → Sign In → Modal → Device Code → Auth → Success
- **Dual Tenant Flow** (1 test)
  - Authenticate both → Enable deployment
- **Sign Out** (1 test)
  - Sign out → Clear token → Disable features
- **Token Refresh** (1 test)
  - Auto-refresh expiring token
- **Python CLI Integration** (1 test)
  - Token passed to Python CLI via environment
- **Cross-Tenant Deployment** (1 test)
  - Scan with source → Deploy to target
- **Timeout Handling** (1 test)
  - Device code expiration
- **Security** (2 tests)
  - Token not in console
  - Token not in network traffic
- **Error Scenarios** (2 tests)
  - Network error
  - Invalid tenant ID

**Total: 11 tests**

## Test Execution

### Running Tests

```bash
# Backend/Frontend Unit Tests
cd spa
npm test

# Backend/Frontend Unit Tests (watch mode)
npm test -- --watch

# Python Unit Tests
cd ..
pytest src/services/__tests__/

# Integration Tests
cd spa
npm test tests/integration/

# E2E Tests (requires running backend)
npm run test:e2e

# All Tests
npm test && cd .. && pytest src/services/__tests__/ && cd spa && npm run test:e2e
```

### Test Coverage

```bash
# Generate coverage report
cd spa
npm test -- --coverage

# View coverage report
open coverage/lcov-report/index.html
```

## Expected Test Results (TDD)

**All tests will FAIL initially** because implementation is not yet complete. This is the TDD approach:

1. **Red Phase** (Current) - Tests written, all failing
2. **Green Phase** (Next) - Implement minimum code to make tests pass
3. **Refactor Phase** (Final) - Clean up code while keeping tests passing

## Security Testing Checklist

Critical security tests included:

- ✅ Token encryption/decryption
- ✅ Tenant ID validation (prevent cross-account attacks)
- ✅ CSRF token validation
- ✅ Environment variable cleanup (no tokens left in environment)
- ✅ No tokens in logs (CRITICAL)
- ✅ No tokens exposed in browser console (E2E)
- ✅ No tokens leaked in network traffic (E2E)
- ✅ Input sanitization (XSS, SQL injection)
- ✅ Rate limiting
- ✅ Token expiration checking

## Test Proportionality Analysis

**Implementation Estimate**: ~2000-2500 lines of code

**Test Lines**: ~2800 lines of test code

**Test Ratio**: ~1.2:1 (tests to implementation)

**Proportionality Check**:
- ✅ Complex business logic (auth flows) - Justifies comprehensive testing
- ✅ Security-critical code (token handling) - Requires exhaustive testing
- ✅ Multiple integration points (frontend, backend, CLI) - Needs integration tests
- ✅ Critical user workflows - Requires E2E validation

**Conclusion**: Test coverage is appropriate for the complexity and criticality of dual-account authentication.

## Test Maintenance

As implementation evolves:

1. **Keep tests in sync** with implementation changes
2. **Update mocks** when Azure SDK APIs change
3. **Add tests** for new edge cases discovered in production
4. **Remove tests** for deprecated functionality
5. **Refactor tests** to reduce duplication while maintaining coverage

## Next Steps

1. **Implement components** following test specifications
2. **Run tests frequently** (TDD cycle: Red → Green → Refactor)
3. **Fix failing tests** one at a time
4. **Add integration** between components
5. **Validate E2E flows** with real Azure tenants (manual testing)
