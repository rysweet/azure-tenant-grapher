# Testing Workflow Rules

1. Tests must be self-contained and idempotent. They must not rely on pre-conditions or external command execution.
2. Use fixtures to manage all test dependencies.
3. Reuse existing fixture code when writing new tests.
4. Think carefully about the code or feature being tested and the acceptance criteria.
5. Structure tests to validate desired outcomes and ensure proper setup for success.
6. Start with a failing test, then iterate on the code or feature until the test passes.
7. Adapt the testing approach as the code evolves.
8. Do not skip tests unless explicitly instructed.
9. Do not use mocks in integration tests.

10. All changes to Roo Rules, mode definitions, or workflow logic must be validated by Roo Modes Changes Tester. Roo Modes Changes Tester is responsible for running and reporting on all relevant tests (unit, integration, pre-commit, and compliance) for any change to rules, modes, or workflow logic. No such change may be marked as complete until Roo Modes Changes Tester validation passes.
