"""
Tests for Tenant Reset Feature (Issue #627).

This test suite provides comprehensive coverage for the tenant reset functionality,
ensuring that all security controls, confirmation flows, and deletion logic work correctly.

Test Organization:
- test_atg_sp_preservation.py: ATG Service Principal preservation (8 tests)
- test_confirmation_flow.py: 5-stage confirmation flow (6 tests)
- test_scope_calculation.py: Scope calculation for all levels (8 tests)
- test_security_controls.py: All 10 security controls (10+ tests)
- test_deletion_logic.py: Deletion execution and error handling (6 tests)
- conftest.py: Shared fixtures and mocks

Total Coverage: ~50-60 comprehensive test cases

All tests are FAILING by design (TDD methodology) until implementation is complete.
"""

__all__ = [
    "test_atg_sp_preservation",
    "test_confirmation_flow",
    "test_deletion_logic",
    "test_scope_calculation",
    "test_security_controls",
]
