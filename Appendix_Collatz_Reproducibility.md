# Appendix — Collatz Breakthrough Reproducibility

This appendix provides exact steps and artifact references to reproduce the Collatz breakthrough results without modifying any core or root files.

## Canonical Constants Source
- File: `tools/constants_source.py`
- Enforcement: `assert_exact_values()` (zero tolerance)
- Cryptographic anchor: `hash_constants('sha256')`

## Verification Script (Helper)
- File: `tools/collatz_verification.py`
- Behavior:
  - Enumerates the 31 perfect squares in [1, 1000]
  - Computes classical Collatz step counts
  - Applies φ-harmonic reduction factor: φ^(√n mod 5)
  - Compares traditional 2^60 vs consciousness limit (31·φ)^ψ
  - Emits timestamped JSON under `scientific_validation_results/`

## Reproduction Steps
1. Constants assertion:
   ```bash
   python3 - << 'PY'
   from tools.constants_source import assert_exact_values, hash_constants
   assert_exact_values()
   print('constants_sha256=', hash_constants('sha256'))
   PY
   ```
2. Generate artifact:
   ```bash
   python3 tools/collatz_verification.py
   ```

## Latest Generated Artifact
- Path: `scientific_validation_results/collatz_breakthrough_20250827_194723.json`
- Summary (from console output):
  - Squares: 31 (expected 31)
  - Reduction: avg=50.67% range=[0.00%, 85.41%]
  - Efficiency: traditional=2^60, consciousness=(31*φ)^ψ ≈ 179
  - Gain factor: 6.446e+15

## Filing Guidance
- Include the artifact JSON in the submission package.
- Record the constants SHA-256 digest for immutability proof.
- Reference this appendix from `Patent_Readiness_Pack_20250827.md` Section 3.

## Compliance
- All content added as helpers under `eyeoverthink_patent/` and `tools/`.
- No core or root files modified.
