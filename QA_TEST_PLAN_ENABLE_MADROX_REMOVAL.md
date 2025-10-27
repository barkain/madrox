# QA Test Plan: Remove enable_madrox Parameter

**Date:** 2025-10-27
**QA Engineer:** Instance 5cd6ea99
**Project:** Madrox Orchestrator
**Branch:** feature/remove-enable-madrox-parameter

## Executive Summary

This test plan covers the removal of the `enable_madrox` parameter from spawn functions. After this change, Madrox tools will ALWAYS be available to spawned instances.

## Scope

### Files Requiring Test Updates

**Unit Tests (2 files):**
1. `tests/test_mcp_stdio_config.py` - 4 references
2. `tests/test_codex_mcp_config.py` - 4 references

**Integration Tests (4 files):**
3. `tests/supervision/test_supervisor_integration.py` - 1 reference + ASSERTION ⚠️
4. `tests/test_integration_verification.py` - 1 reference + ASSERTION ⚠️
5. `tests/test_mcp_tools_integration.py` - 1 reference
6. `tests/test_mcp_configuration.py` - 5 references

**E2E Tests (3 files):**
7. `tests/test_bidirectional_messaging.py` - 1 reference
8. `tests/test_network_bidirectional.py` - 2 references
9. `tests/simple_bidirectional_test.py` - 1 reference

## Test Strategy

### Phase 1: Unit Test Updates
- Remove `enable_madrox` parameter from instance definitions
- Verify MCP configuration always includes Madrox
- Update test assertions to check Madrox is always present

### Phase 2: Integration Test Updates
- Remove `enable_madrox` from spawn calls
- Update assertions that check for `enable_madrox=True`
- Verify backward compatibility

### Phase 3: E2E Test Updates
- Remove parameter from all spawn_claude calls
- Verify bidirectional messaging still works
- Verify parent-child communication unchanged

### Phase 4: Validation
- Run full test suite
- Verify all tests pass
- Document any issues found

## Critical Test Cases

### Test Case 1: Madrox Always Available (HIGH PRIORITY)
**File:** `tests/test_mcp_stdio_config.py`
**Current:** Tests with `enable_madrox=False` and `enable_madrox=True`
**Update:** Remove parameter, verify Madrox always configured
**Assertion:** Madrox server present in all spawned instances

### Test Case 2: Supervisor Spawn Assertion (CRITICAL)
**File:** `tests/supervision/test_supervisor_integration.py:89`
**Current:** `assert call_kwargs["enable_madrox"] is True`
**Update:** Remove assertion or change to verify Madrox tools available
**Risk:** High - This is an explicit assertion that will fail

### Test Case 3: Integration Verification Assertion (CRITICAL)
**File:** `tests/test_integration_verification.py:80`
**Current:** `assert call_kwargs["enable_madrox"] is True`
**Update:** Remove assertion or change to verify Madrox tools available
**Risk:** High - This is an explicit assertion that will fail

### Test Case 4: Bidirectional Messaging
**Files:** Multiple E2E tests
**Current:** All use `enable_madrox=True`
**Update:** Remove parameter
**Verification:** Bidirectional protocol still works

### Test Case 5: MCP Configuration Format
**File:** `tests/test_mcp_stdio_config.py`
**Current:** Tests different MCP formats with enable_madrox flag
**Update:** Verify Madrox always included with correct format
**Verification:** HTTP transport for Madrox always configured

## Success Criteria

✅ All test files updated to remove `enable_madrox` parameter
✅ No tests explicitly check for `enable_madrox` parameter
✅ All tests verify Madrox tools are available
✅ Full test suite passes
✅ Bidirectional messaging tests pass
✅ Supervisor integration tests pass
✅ No regressions in existing functionality

## Test Execution Plan

### Step 1: Update Unit Tests
- [ ] test_mcp_stdio_config.py
- [ ] test_codex_mcp_config.py

### Step 2: Update Integration Tests
- [ ] test_supervisor_integration.py (CRITICAL - has assertion)
- [ ] test_integration_verification.py (CRITICAL - has assertion)
- [ ] test_mcp_tools_integration.py
- [ ] test_mcp_configuration.py

### Step 3: Update E2E Tests
- [ ] test_bidirectional_messaging.py
- [ ] test_network_bidirectional.py
- [ ] simple_bidirectional_test.py

### Step 4: Validation
- [ ] Run pytest on updated files
- [ ] Run full test suite
- [ ] Verify no regressions
- [ ] Document results

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Assertion failures in integration tests | HIGH | Update assertions to check for Madrox availability instead |
| Test coverage gaps | MEDIUM | Add tests to verify Madrox always present |
| E2E test failures | MEDIUM | Verify bidirectional messaging protocol unchanged |
| Backward compatibility issues | LOW | Parameter should be ignored if still passed |

## Notes

- Two tests have explicit assertions that will fail: lines 89 and 80
- All E2E tests depend on Madrox being available for bidirectional messaging
- Tests should verify Madrox tools are ALWAYS available, not conditionally
- Need to test both Claude and Codex instance types

## Sign-off

**Prepared by:** QA Engineer Instance 5cd6ea99
**Status:** Test analysis complete, ready to execute updates
**Next Step:** Begin Phase 1 - Unit Test Updates
