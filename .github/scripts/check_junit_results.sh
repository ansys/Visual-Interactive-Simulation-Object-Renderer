#!/usr/bin/env bash
# check_junit_results.sh — Reusable JUnit XML result checker for CI workflows.
#
# Usage:
#   check_junit_results.sh <suite_name>:<xml_path> [<suite_name>:<xml_path> ...]
#
# Environment variables:
#   MISSING_XML_MODE  What to do when an XML file is missing.
#                     "skip"  = ignore that suite (default)
#                     "error" = treat as an error (exit 2)
#                     "fail"  = treat as a failure (exit 1)
#   DETECT_ERRORS     Whether to detect <testsuite errors="N">.
#                     "true"  = detect errors, use exit codes 0/1/2/3 (default)
#                     "false" = only detect failures, use exit codes 0/1
#
# Exit codes:
#   0 = all suites passed
#   1 = at least one suite has test FAILURES (assertion failures)
#   2 = at least one suite has test ERRORS (infrastructure issues)
#   3 = both FAILURES and ERRORS detected across suites
#
# Note: Argument paths must not contain spaces.
# Note: Requires GNU grep (supports -oP).
# Note: This script is designed to work with xml with single suite per file, which is the default for pytest's junitxml output.

set -euo pipefail

# --- Guard: require GNU grep with -P support ---
if ! echo "" | grep -oP "" 2>/dev/null; then
  echo "::error::This script requires GNU grep with Perl-compatible regex (-oP). Aborting." >&2
  exit 1
fi

# --- Read environment variables with defaults ---
MISSING_XML_MODE="${MISSING_XML_MODE:-skip}"   # skip | error | fail
DETECT_ERRORS="${DETECT_ERRORS:-true}"          # true | false

# --- Validate at least one argument ---
if [ $# -eq 0 ]; then
  echo "Usage: $0 <suite_name>:<xml_path> [<suite_name>:<xml_path> ...]" >&2
  echo "Example: $0 unit:tests/artifacts/unit/unit-junit.xml smoke:tests/artifacts/smoke/reports/smoke-junit.xml" >&2
  exit 1
fi

# --- Initialize accumulators ---
any_failed=0
any_errored=0
failed_suites=""
errored_suites=""

# --- Process each suite argument ---
for arg in "$@"; do
  suite_name="${arg%%:*}"
  xml_path="${arg#*:}"

  # Handle missing XML file
  if [ ! -f "$xml_path" ]; then
    echo "⚠️  [$suite_name] JUnit XML not found: $xml_path"
    if [ "$MISSING_XML_MODE" = "skip" ]; then
      echo "    Skipping this suite."
      continue
    elif [ "$MISSING_XML_MODE" = "error" ]; then
      echo "    Treating as an error condition (MISSING_XML_MODE=error)."
      any_errored=1
      errored_suites="${errored_suites}${suite_name},"
      continue
    else
      # "fail" (default fallback)
      echo "    Treating as a failure (MISSING_XML_MODE=fail)."
      any_failed=1
      failed_suites="${failed_suites}${suite_name},"
      continue
    fi
  fi

  # Extract failure count from the <testsuite> element
  failure_count=$(grep -oP 'failures="\K[0-9]+' "$xml_path" | head -1)
  failure_count=${failure_count:-0}

  # Extract error count (only if DETECT_ERRORS=true)
  if [ "$DETECT_ERRORS" = "true" ]; then
    error_count=$(grep -oP 'errors="\K[0-9]+' "$xml_path" | head -1)
    error_count=${error_count:-0}
  else
    error_count=0
  fi

  echo "📋 [$suite_name] tests — failures=$failure_count, errors=$error_count"

  # Record failures
  if [ "$failure_count" -gt 0 ]; then
    echo "  ❌ $failure_count test failure(s) detected."
    any_failed=1
    failed_suites="${failed_suites}${suite_name},"
  fi

  # Record errors
  if [ "$error_count" -gt 0 ]; then
    echo "  ⚠️  $error_count test error(s) detected."
    any_errored=1
    errored_suites="${errored_suites}${suite_name},"
  fi
done

# --- Remove trailing commas ---
failed_suites="${failed_suites%,}"
errored_suites="${errored_suites%,}"

# --- Compute exit code and emit annotations ---
exit_code=0

if [ $any_failed -ne 0 ] && [ $any_errored -ne 0 ]; then
  echo ""
  echo "::error::Both test FAILURES and ERRORS detected."
  exit_code=3
elif [ $any_failed -ne 0 ]; then
  echo ""
  echo "::error::Test FAILURES detected."
  exit_code=1
elif [ $any_errored -ne 0 ]; then
  echo ""
  echo "::error::Test ERRORS detected (infrastructure/runtime issues)."
  exit_code=2
else
  echo ""
  echo "✅ All test suites passed."
fi

# --- Write outputs to $GITHUB_OUTPUT (guarded so the script also works locally) ---
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "exit_code=$exit_code"             >> "$GITHUB_OUTPUT"
  echo "failed_suites=$failed_suites"     >> "$GITHUB_OUTPUT"
  echo "errored_suites=$errored_suites"   >> "$GITHUB_OUTPUT"
fi

exit $exit_code
