# Tasks: Enterprise ASO Platform Foundation

**Input**: Design documents from `/specs/001-enterprise-aso-platform/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: This feature includes unit and contract validation because reproducibility and
compliance are required by the constitution.

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize Speckit workspace and project scaffolding

- [x] T001 Create `.specify/` workspace files in `.specify/`
- [x] T002 Create local Speckit template overrides in `.specify/templates/`
- [x] T003 [P] Create active feature directory and core artifacts in `specs/001-enterprise-aso-platform/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Compliance and contract foundations that all stories depend on

- [x] T004 Create source registry policy in `config/source_registry.json`
- [x] T005 [P] Define typed analysis models in `src/aso_platform/models.py`
- [x] T006 [P] Implement source registry loader and policy checks in `src/aso_platform/registry.py`
- [x] T007 Create report contract schema in `specs/001-enterprise-aso-platform/contracts/analysis-report.schema.json`

**Checkpoint**: Foundation ready for story implementation

---

## Phase 3: User Story 1 - Evidence-Backed Single App Inspection (Priority: P1) MVP

**Goal**: Deliver a typed, automation-friendly inspection flow for one app

**Independent Test**: Run the new inspect CLI with a stubbed provider and confirm JSON
contract fields, evidence, warnings, and confidence.

### Tests for User Story 1

- [x] T008 [P] [US1] Add registry policy tests in `tests/unit/test_registry.py`
- [x] T009 [P] [US1] Add inspection service tests in `tests/unit/test_app_inspector.py`
- [x] T010 [P] [US1] Add CLI contract test in `tests/contract/test_cli_json.py`

### Implementation for User Story 1

- [x] T011 [P] [US1] Create provider exports in `src/aso_platform/providers/__init__.py`
- [x] T012 [P] [US1] Implement Play Store adapter in `src/aso_platform/providers/play_store.py`
- [x] T013 [US1] Implement inspection service in `src/aso_platform/services/app_inspector.py`
- [x] T014 [US1] Implement API helper in `src/aso_platform/__init__.py`
- [x] T015 [US1] Implement CLI entrypoint in `src/aso_platform/cli.py`

**Checkpoint**: User Story 1 is functional and testable independently

---

## Phase 4: User Story 2 - Compliance-Controlled Source Management (Priority: P2)

**Goal**: Enforce source policy through configuration rather than ad hoc behavior

**Independent Test**: Disable a source in the registry and verify the service refuses to
fetch it.

### Implementation for User Story 2

- [x] T016 [US2] Add compliance-disabled behavior to the inspection service in `src/aso_platform/services/app_inspector.py`
- [x] T017 [US2] Record legal and operational metadata in the registry-backed source model via `src/aso_platform/registry.py`

**Checkpoint**: Source policy can block disallowed fetch paths

---

## Phase 5: User Story 3 - Speckit-Governed Delivery Artifacts (Priority: P3)

**Goal**: Ensure future work inherits the same governance and planning rules

**Independent Test**: Resolve the active feature from `.specify/feature.json` and verify
the required files exist.

### Implementation for User Story 3

- [x] T018 [P] [US3] Create constitution and overrides in `.specify/`
- [x] T019 [P] [US3] Create spec, plan, research, and data model docs in `specs/001-enterprise-aso-platform/`
- [x] T020 [US3] Create quickstart, checklist, contract, and task artifacts in `specs/001-enterprise-aso-platform/`

**Checkpoint**: Speckit rollout artifacts exist and are aligned

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T021 [P] Add package markers in `src/__init__.py`, `tests/__init__.py`, and service/provider packages
- [x] T022 Update dependencies for test execution in `requirements.txt`
- [ ] T023 Run live-source manual validation against multiple package IDs and document findings in `reports/`
- [x] T024 Add governed keyword rank tracking provider coverage in `src/aso_platform/services/keyword_rank.py`
- [x] T025 Add richer rank tracking fixtures and fallback scenarios in `tests/unit/test_keyword_rank.py`
- [x] T026 Add full governed capability catalog in `config/capability_catalog.json`
- [x] T027 Add capability audit CLI in `src/aso_platform/capabilities.py`
- [ ] T028 Expand provider coverage for reviews, trends, and metadata scoring into the new core
- [ ] T029 Run live-source manual validation against multiple package IDs and document findings in `reports/`

---

## Dependencies & Execution Order

- Setup tasks unblock all later work.
- Foundational tasks MUST complete before story work.
- User Story 1 depends on foundational tasks.
- User Story 2 depends on the inspection service and registry loader.
- User Story 3 depends on the `.specify` workspace being in place.
- Polish tasks T023-T025 remain future work beyond the first implemented slice.

## Parallel Opportunities

- T003, T005, and T006 can run independently.
- T008-T010 can be written in parallel once the contract and models are defined.
- T018 and T019 can proceed in parallel after `.specify/` exists.

## Implementation Strategy

1. Establish Speckit governance and feature scaffolding.
2. Build the typed platform contract and source registry.
3. Deliver the single-app inspection MVP with CLI access.
4. Lock in deterministic tests and leave broader source migration for later phases.
