# FROID bioacoustic units

This note protects the clinical thresholds from unit drift.

## Jitter and Shimmer in the current dashboard

The current browser-side bioacoustic pipeline exposes:

- `jitter` / `jitter_proxy_index`
- `shimmer` / `shimmer_proxy_index`

These are internal normalized proxy indices. They are not physical Praat-equivalent
measurements.

Current sources:

- `jitter_proxy_index`: zero crossing rate scaled by 45, clamped to 0-1.
- `shimmer_proxy_index`: RMS envelope coefficient of variation, clamped to 0-1.

The alert threshold `0.45` is therefore an internal FROID proxy threshold. It must
not be compared directly to normative jitter percent values or shimmer dB values.

## Future physical extraction layer

If the system later implements a validated physical acoustic extractor, store the
measurements separately, for example:

- `jitter_local_percent`
- `jitter_rap_percent`
- `jitter_ppq5_percent`
- `shimmer_local_percent`
- `shimmer_db`

Only those physical fields should be compared against normative ranges from
Praat/openSMILE or peer-reviewed acoustic voice literature.

## Spectral band names

Fields such as `spectral_delta_0_4hz`, `spectral_theta_4_8hz`,
`spectral_alpha_8_12hz`, `spectral_beta_12_30hz`, and
`spectral_gamma_30_80hz` are vocal modulation bands. They do not represent EEG or
direct brain-wave measurement.

## Sub-harmonics

The nuclear autonomic sub-harmonic range implemented in the FROID live pipeline is
5-12 Hz. Adjacent bands such as 12-20 Hz and 20-40 Hz are complementary vocal
modulation features and should be described as such.
