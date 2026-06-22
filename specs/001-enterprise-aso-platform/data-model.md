# Data Model: Enterprise ASO Platform Foundation

## SourceDescriptor

- `source_id`: stable identifier for the source
- `display_name`: human-readable label
- `purpose`: what the source is used for
- `cost`: expected to be `free` for this project slice
- `auth`: expected to be `none` for this project slice
- `legal_notes`: operator-facing notes about why usage is allowed or constrained
- `compliance_status`: `approved`, `disabled`, or `review_required`
- `rate_limit`: textual throttling strategy
- `cache_ttl_minutes`: default cache TTL
- `enabled`: boolean runtime switch

## FetchPolicy

- `rate_limit`
- `cache_ttl_minutes`
- `minimal_collection`
- `fallback_behavior`

## AppDetails

- `package_id`
- `title`
- `summary`
- `description`
- `score`
- `ratings`
- `reviews`
- `installs`
- `developer`
- `category`
- `version`
- `updated`
- `histogram`
- `fetched_at`
- `from_cache`

## SourceEvidence

- `source_id`
- `display_name`
- `source_type`
- `scope`
- `fetched_at`
- `from_cache`
- `locale`
- `country`

## AnalysisScore

- `name`
- `value`
- `scale`
- `formula_version`
- `explanation`

## AnalysisWarning

- `code`
- `severity`
- `message`
- `source_id`

## ConfidenceAssessment

- `label`
- `score`
- `rationale`

## AnalysisReport

- `request_context`
- `app`
- `evidence`
- `scores`
- `insights`
- `warnings`
- `confidence`

## Relationships

- One `AnalysisReport` has one `AppDetails`.
- One `AnalysisReport` can reference many `SourceEvidence` items.
- One `AnalysisReport` can expose many `AnalysisScore` and `AnalysisWarning` records.
- One `SourceDescriptor` governs one or more provider adapters.
