# Exception Handling Refactor Plan

## Objective
Refactor the codebase to eliminate uncaught exceptions, improve error handling, and follow best practices for exception management, logging, and maintainability.

---

## Prioritization
1. **Critical: Uncaught and Generic Exceptions**
   - Replace all `raise Exception(...)` and generic `raise` statements with custom exception classes (preferably from `src/exceptions.py`).
   - Move long error messages into exception classes or use concise messages.
   - Use `raise from` to preserve exception chaining.

2. **High: Logging and Broad Excepts**
   - Replace all `logger.error(..., exc_info=True)` with `logger.exception(...)` for full tracebacks.
   - Ensure every `except Exception` block logs the exception using `logger.exception`.
   - Remove or refactor useless or empty `try/except` blocks.
   - Never ignore exceptions without at least logging them.

3. **Medium: Try/Except Structure and Clarity**
   - Move code that should only run if no exception occurred into an `else` block after `try/except`.
   - Abstract complex or repeated raise logic into helper functions.
   - Refactor exception raising to use inner functions where flagged.

4. **Low: Linting and Documentation**
   - Run static analysis tools (pyright, tryceratops) after each refactor step.
   - Add or update docstrings to clarify exception behavior.
   - Ensure all exception classes are documented and used consistently.

---

## Step-by-Step Plan

### 1. Audit and Replace Generic Exceptions
- [ ] Search for all `raise Exception` and replace with custom exceptions.
- [ ] Refactor long error messages into exception classes.
- [ ] Use `raise from` for exception chaining where appropriate.

### 2. Improve Logging
- [ ] Replace all `.error(..., exc_info=True)` with `.exception(...)`.
- [ ] Ensure all `except Exception` blocks log the exception.
- [ ] Remove or refactor any `try/except` that does not handle or log.

### 3. Refactor Try/Except Blocks
- [ ] Move post-try logic to `else` blocks where flagged.
- [ ] Abstract repeated raise logic into helper functions.
- [ ] Refactor as needed for clarity and maintainability.

### 4. Test and Validate
- [ ] Run all tests after each major refactor.
- [ ] Use `tryceratops` and `pyright` to confirm all issues are resolved.
- [ ] Document any remaining exceptions and update developer docs.

---

## References
- [tryceratops documentation](https://tryceratops.github.io/)
- [Python Exception Best Practices](https://docs.python.org/3/tutorial/errors.html)
- [Project `src/exceptions.py` for custom exception hierarchy]

---

## Notes
- Prioritize files with the most violations and those in the main execution path.
- Refactor incrementally and commit after each logical change.
- Review exception handling in both `src/` and `scripts/` directories.
- Ensure all new code follows these practices.
