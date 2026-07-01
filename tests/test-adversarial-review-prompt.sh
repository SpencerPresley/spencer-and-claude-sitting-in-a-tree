#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT="$ROOT/plugins/adversarial-review/agents/adversarial-reviewer.md"
SKILL="$ROOT/plugins/adversarial-review/skills/adversarial-review/SKILL.md"

require_text() {
  local file="$1"
  local text="$2"
  if ! grep -Fq "$text" "$file"; then
    echo "missing expected text in ${file#$ROOT/}: $text" >&2
    exit 1
  fi
}

require_text "$SKILL" "disable-model-invocation: true"
require_text "$SKILL" "<adversarial_review_request>"
require_text "$SKILL" "<mode>"
require_text "$SKILL" "<target_label>"
require_text "$SKILL" "<collection_guidance>"
require_text "$SKILL" "<user_focus>"

require_text "$AGENT" "<role>"
require_text "$AGENT" "<operating_stance>"
require_text "$AGENT" "<attack_surface>"
require_text "$AGENT" "<review_method>"
require_text "$AGENT" "<finding_bar>"
require_text "$AGENT" "<grounding_rules>"
require_text "$AGENT" "<output_contract>"
require_text "$AGENT" "<final_check>"
