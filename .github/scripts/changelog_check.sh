#!/usr/bin/env bash
set -euo pipefail


if [[ -z "${REPO:-}" || -z "${BASE:-}" || -z "${HEAD:-}" ]]; then
    echo "❌ ERROR: Missing required environment variables (REPO, BASE, HEAD)."
    exit 1
fi

GH_TOKEN="${GH_TOKEN:-}"

echo "Checking CHANGELOG.md..."
echo "Base SHA: $BASE"
echo "Head SHA: $HEAD"

gh api "repos/$REPO/contents/CHANGELOG.md?ref=$BASE" --jq '.content' | base64 -d > base.md
gh api "repos/$REPO/contents/CHANGELOG.md?ref=$HEAD" --jq '.content' | base64 -d > head.md


extract_unreleased() {
  awk '
    BEGIN { in_unrel=0 }
    /^## \[Unreleased\]/ { in_unrel=1; next }
    /^## \[/ && in_unrel==1 { exit }
    in_unrel==1 { print }
  ' "$1"
}

extract_released() {
  awk '
    BEGIN { seen_unrel=0 }
    /^## \[Unreleased\]/ { seen_unrel=1; next }
    seen_unrel==1 { print }
  ' "$1"
}

echo `ls`
echo `cat base.md`
echo `cat head.md`
echo "extracting"

extract_unreleased base.md > base_unrel.txt
echo "extracting base"
extract_unreleased head.md > head_unrel.txt
echo "extracting head"

extract_released base.md > base_rel.txt
echo "extracting base"
echo `cat base_rel.txt`
extract_released head.md > head_rel.txt
echo "extracting head"
echo `cat head_rel.txt`

diff -u base_unrel.txt head_unrel.txt 

DIFF_UNREL=$(diff -u base_unrel.txt head_unrel.txt || true)
echo "$DIFF_UNREL"
DIFF_REL=$(diff -u base_rel.txt head_rel.txt || true)
echo "$DIFF_REL"


ADDED_TO_UNREL=$(echo "$DIFF_UNREL" | grep -E '^\+' | grep -v '^\+\+\+' || true)

echo "$ADDED_TO_UNREL"

if [[ -z "$ADDED_TO_UNREL" ]]; then
    echo "❌ FAIL: No additions detected in the [Unreleased] section."
    exit 1
fi


ADDED_TO_RELEASED=$(echo "$DIFF_REL" | grep -E '^\+' | grep -v '^\+\+\+' || true)

if [[ -n "$ADDED_TO_RELEASED" ]]; then
    echo "❌ FAIL: Additions detected in released sections (past versions)."
    echo "---- DIFF ----"
    echo "$DIFF_REL"
    exit 1
fi

DELETED_UNREL=$(echo "$DIFF_UNREL" | grep -E '^-' | grep -v '^---' || true)
DELETED_REL=$(echo "$DIFF_REL" | grep -E '^-' | grep -v '^---' || true)

if [[ -n "$DELETED_UNREL" ]] || [[ -n "$DELETED_REL" ]]; then
    echo "⚠️ WARNING: Deletions detected in CHANGELOG.md. Please verify they are intentional."

    if [[ -n "$DELETED_UNREL" ]]; then
        echo "--- Deleted in Unreleased section ---"
        echo "$DELETED_UNREL"
    fi

    if [[ -n "$DELETED_REL" ]]; then
        echo "--- Deleted in Released sections ---"
        echo "$DELETED_REL"
    fi
fi

echo "✅ PASS: CHANGELOG validation successful."
echo "Unreleased contains additions, and released sections contain no additions."
