# FROID Internationalization — Phase 1

## Scope

Phase 1 introduces the technical language foundation for:

- `pt-BR` — production baseline;
- `en-US` — controlled validation;
- `fr-FR` — controlled validation;
- `es-ES` — controlled validation.

The Spanish locale is deliberately explicit. Additional variants such as
`es-US` and `es-MX` require their own language and clinical validation cohorts.

## Session language contract

Every new session keeps four independent locale fields:

- `patient_ui_locale`: patient-facing interface language;
- `spoken_language`: language expected in the original audio;
- `analysis_language`: semantic-analysis language;
- `report_locale`: language used for generated summaries and reports.

The original transcript must never be overwritten by a translation. A future
translated transcript must be stored as a derived record with model, language,
timestamp, and provenance.

## Current implementation status

- Session locale allowlist and normalization: implemented.
- OpenAI transcription language hint: implemented.
- Single authoritative STT pipeline per professional/patient track: implemented.
- Server-authoritative session locale retrieval across authorized devices: implemented.
- Content-free transcription telemetry and report p50/p95 quality summary: implemented.
- Server-owned language-specific transcription prompt: implemented.
- Summary output locale: implemented.
- Invite and report language provenance: implemented.
- Locale-aware word segmentation through `Intl.Segmenter`: implemented.
- Patient critical entry/room copy: localized for Phase 1.
- Professional, summary, longitudinal and report dashboard core navigation: localized for Phase 1.
- FROID Explica controls and generated-response locale: localized for Phase 1.
- Human-reviewed legal and clinical translation: pending.
- Clinical thresholds and population calibration: pending validation.

No international locale may be described as clinically validated until its
validation gate is approved.

## Validation dataset requirements

Each record used for calibration must include the locale, capture modality,
device/browser class, signal quality, age band, sex where lawfully available,
and accent/region when voluntarily declared. Raw identifiers must not enter the
anonymous Data-FROID cohort.

### Speech-to-text

- WER for alphabetic Phase 1 languages;
- recall and precision for critical clinical vocabulary;
- empty, truncated, duplicated, and delayed segment rates;
- p50 and p95 latency;
- number/date/medication/name accuracy;
- code-switching and negation accuracy.

The deterministic batch evaluator is available at
`froid-server/tools/evaluate_language_validation.py`. It accepts UTF-8 JSONL
records containing `locale`, `reference`, `hypothesis`, `critical_terms`,
`latency_ms`, `status`, and optional `subgroups`, and produces a versioned JSON
report without modifying the source batch.

### Acoustic reliability

- valid voiced duration and signal-to-noise ratio;
- clipping, packet loss, and missing-window rate;
- test-retest ICC and coefficient of variation;
- device and browser bias through Bland-Altman analysis;
- stability of F0, jitter proxy, shimmer proxy, MFCC, spectral, and subharmonic measures;
- remote, presential, and patient-mobile equivalence analysis.

### Clinical and semantic validation

- sensitivity, specificity, PPV, NPV, and likelihood ratios where an endpoint is defined;
- ROC-AUC, Brier score, calibration intercept, and calibration slope;
- agreement between two independent native clinical reviewers;
- summary faithfulness, omission, unsupported-statement, and cultural-appropriateness rates;
- external validation separated by professional or institution;
- predefined subgroup performance-gap assessment, capped at 10% only after the exact denominator and absolute/relative rule are registered.

Sample sizes must be determined by a statistical power calculation after the
endpoint, prevalence, and acceptable confidence interval are fixed. Development
and external-validation cohorts must remain separate.

## Release gates

1. Engineering gate: supported audio, deterministic locale propagation, no silent fallback to another language.
2. Data-quality gate: invalid audio is marked insufficient rather than interpreted.
3. Native-review gate: two independent reviewers plus adjudication.
4. Clinical-validation gate: registered endpoints and external validation.
5. Legal/infrastructure gate: country-specific contracts and provider chain approved.
6. Controlled rollout: tenant feature flag, monitoring, and rollback.

International languages remain controlled-validation features until every
applicable gate is complete.
