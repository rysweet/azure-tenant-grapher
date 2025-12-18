# Python 3.13 Compatibility Fix

## Problem
The azure-tenant-grapher project was incompatible with Python 3.13 due to a dependency conflict:
- The project requires `littleballoffur>=2.3.1` for graph sampling functionality
- `littleballoffur` 2.3.1 has a hard constraint of `pandas<2.0`
- `pandas` 1.5.3 (the latest version <2.0) fails to compile on Python 3.13 due to deprecated C API functions

## Solution
Modified the `littleballoffur` package locally to support pandas 2.x:

### Changes Made

1. **Modified littleballoffur setup.py** (`littleballoffur-2.3.1/setup.py`)
   - Changed `pandas<2.0` to `pandas>=1.5.0`
   - This allows pandas 2.x to be installed

2. **Updated pyproject.toml**
   - Removed `littleballoffur>=2.3.1` from dependencies (now using local modified version)
   - Changed `numpy>=1.24.0,<2.0.0` to `numpy>=1.24.0` (removed upper bound)
   - Added `pandas>=2.0.0` as an explicit dependency

3. **Installed modified littleballoffur**
   - Installed the modified version as an editable package: `pip install -e ./littleballoffur-2.3.1`

## Verification

### Tests Passed
All sampling-related tests passed successfully on Python 3.13.9:
```
tests/test_sampling_imports.py::test_littleballoffur_import PASSED
tests/test_sampling_imports.py::test_networkx_import PASSED
tests/test_sampling_imports.py::test_sampling_workflow PASSED
```

### Installed Versions
- Python: 3.13.9
- pandas: 2.3.3
- numpy: 1.26.4 (downgraded from 2.3.5 due to other dependencies)
- littleballoffur: 2.3.1 (modified)

## Compatibility
This solution maintains compatibility with both Python 3.12 and Python 3.13:
- Python 3.12: Works with both pandas 1.x and 2.x
- Python 3.13: Requires pandas 2.x (which is now supported)

## Why This Works
The `littleballoffur` package only uses pandas for basic CSV reading and DataFrame operations in its dataset reader module. These APIs are stable and compatible across pandas 1.x and 2.x versions. The original `pandas<2.0` constraint was overly conservative.

## Future Considerations
- Monitor the upstream `littleballoffur` repository for official pandas 2.x support
- Consider submitting a pull request to the upstream project with this fix
- If upstream updates, remove the local modified version and use the official package

## Installation Instructions

### For Python 3.13 Users
1. Clone the repository
2. Navigate to `azure-tenant-grapher`
3. Install the modified littleballoffur: `pip install -e ./littleballoffur-2.3.1`
4. Install the project: `uv pip install -e .`

### For Python 3.12 Users
The standard installation process works without modifications:
```bash
uv pip install -e .
```

## Files Modified
- `azure-tenant-grapher/pyproject.toml` - Updated dependency constraints
- `azure-tenant-grapher/littleballoffur-2.3.1/setup.py` - Relaxed pandas constraint
