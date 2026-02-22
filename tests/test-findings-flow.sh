#!/usr/bin/env bash
# Integration test: findings write → read → synthesis timeline
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HELPER="$SCRIPT_DIR/scripts/findings-helper.sh"
TMPDIR=$(mktemp -d /tmp/findings-test-XXXXXX)
FINDINGS="$TMPDIR/peer-findings.jsonl"
PASS=0
FAIL=0

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "  PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc"
    echo "    expected: $expected"
    echo "    actual:   $actual"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Test 1: Empty file read ==="
result=$(bash "$HELPER" read "$TMPDIR/nonexistent.jsonl")
assert_eq "empty read returns []" "[]" "$result"

echo "=== Test 2: Write blocking finding ==="
bash "$HELPER" write "$FINDINGS" "blocking" "fd-correctness" "api-conflict" \
  "POST /api/agents already exists with incompatible semantics" \
  "internal/http/handlers.go:34"
count=$(jq -s 'length' "$FINDINGS")
assert_eq "one line written" "1" "$count"

echo "=== Test 3: Write notable finding ==="
bash "$HELPER" write "$FINDINGS" "notable" "fd-safety" "auth-bypass" \
  "No authentication on admin endpoints" \
  "internal/http/router.go:89" "internal/http/middleware.go:12"
count=$(jq -s 'length' "$FINDINGS")
assert_eq "two lines total" "2" "$count"

echo "=== Test 4: Read all findings ==="
all=$(bash "$HELPER" read "$FINDINGS")
all_count=$(echo "$all" | jq 'length')
assert_eq "read all returns 2" "2" "$all_count"

echo "=== Test 5: Read blocking only ==="
blocking=$(bash "$HELPER" read "$FINDINGS" blocking)
blocking_count=$(echo "$blocking" | jq 'length')
assert_eq "read blocking returns 1" "1" "$blocking_count"

echo "=== Test 6: Read notable only ==="
notable=$(bash "$HELPER" read "$FINDINGS" notable)
notable_count=$(echo "$notable" | jq 'length')
assert_eq "read notable returns 1" "1" "$notable_count"

echo "=== Test 7: Schema validation ==="
first=$(jq -s '.[0]' "$FINDINGS")
has_severity=$(echo "$first" | jq 'has("severity")')
has_agent=$(echo "$first" | jq 'has("agent")')
has_category=$(echo "$first" | jq 'has("category")')
has_summary=$(echo "$first" | jq 'has("summary")')
has_refs=$(echo "$first" | jq 'has("file_refs")')
has_ts=$(echo "$first" | jq 'has("timestamp")')
assert_eq "has severity" "true" "$has_severity"
assert_eq "has agent" "true" "$has_agent"
assert_eq "has category" "true" "$has_category"
assert_eq "has summary" "true" "$has_summary"
assert_eq "has file_refs" "true" "$has_refs"
assert_eq "has timestamp" "true" "$has_ts"

echo "=== Test 8: file_refs is array ==="
refs_type=$(echo "$first" | jq '.file_refs | type')
assert_eq "file_refs is array" '"array"' "$refs_type"

echo "=== Test 9: Multiple file_refs ==="
second=$(jq -s '.[1]' "$FINDINGS")
refs_count=$(echo "$second" | jq '.file_refs | length')
assert_eq "second finding has 2 refs" "2" "$refs_count"

echo "=== Test 10: Concurrent append simulation ==="
for i in {1..5}; do
  bash "$HELPER" write "$FINDINGS" "notable" "fd-agent-$i" "test-$i" "Concurrent finding $i" &
done
wait
total=$(grep -c '^{' "$FINDINGS")
assert_eq "7 total findings after concurrent writes" "7" "$total"
invalid=$(grep -v '^{' "$FINDINGS" | grep -v '^$' | wc -l || true)
assert_eq "no corrupted lines" "0" "$invalid"

# Cleanup
rm -rf "$TMPDIR"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
