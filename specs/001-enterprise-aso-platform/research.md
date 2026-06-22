# Research: Enterprise ASO Platform Foundation

## Decision: Use project-local Spec Kit artifacts

**Rationale**: The repo already vendors `spec-kit`, but there is no initialized
`.specify` workspace. Creating project-local artifacts is the smallest step that makes
the bundled workflow immediately usable in this repository.

**Alternatives considered**:
- Depend on a global `specify` installation. Rejected because it would not make the repo
  self-contained.
- Keep `spec-kit` as documentation only. Rejected because the user explicitly requested
  working `/speckit.*` artifacts.

## Decision: Keep Python for the first platform slice

**Rationale**: The existing ASO logic is already Python-based and can be wrapped behind
explicit provider and service boundaries without a risky rewrite.

**Alternatives considered**:
- Full rewrite in another language. Rejected because it slows validation of the new
  architecture and compliance model.

## Decision: Encode source policy in JSON

**Rationale**: A plain JSON source registry is easy to review, test, and gate in CI while
remaining independent of code changes.

**Alternatives considered**:
- Hardcode source rules in provider modules. Rejected because policy review becomes harder.
- Use YAML. Rejected because JSON is already sufficient and avoids adding parser concerns.

## Decision: Use evidence-backed confidence instead of absolute accuracy claims

**Rationale**: Public ASO signals are noisy and provider availability can vary by locale
and time. Confidence and warnings make the system honest and auditable.

**Alternatives considered**:
- Promise near-perfect accuracy. Rejected because it is neither testable nor defensible.

## Decision: Limit v1 to free and lawful public sources

**Rationale**: This aligns with the user's explicit constraint and reduces operational and
legal risk.

**Alternatives considered**:
- Allow optional paid APIs. Rejected for the first rollout because it complicates the
  contract and governance model.
