---

description: "Task list template for feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Include fixture-driven and contract-focused validation for each shippable
story.

**Organization**: Tasks are grouped by user story so each increment can be delivered,
validated, and reviewed independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

## Required Early Phases

- Compliance inventory MUST occur before downstream feature expansion.
- Source registry updates MUST happen before adding new provider behavior.
- Contract and regression tests MUST be updated before declaring a story complete.
