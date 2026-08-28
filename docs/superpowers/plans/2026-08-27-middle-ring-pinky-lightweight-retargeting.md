# Middle, Ring, and Pinky Lightweight Retargeting Plan

**Goal:** Add a reversible vector feature that improves independent middle, ring, and pinky flexion without changing thumb/index or hardware safety behavior.

**Architecture:** A pure geometry module computes normalized fingertip retraction. The recognizer exposes and smooths it, the mapper calibrates and fuses it with the existing curl, and the runtime only forwards the observation.

**Tech Stack:** Python 3.12, NumPy, MediaPipe, pytest, PyInstaller, Electron/NSIS.

## Task 1: Pure geometry (TDD)

- Add failing tests for straight, curled, scale-invariant, rotation-invariant, and degenerate finger chains.
- Implement `finger_retargeting.py` with normalized tip-retraction helpers.
- Run the focused geometry tests.

## Task 2: Observation and smoothing (TDD)

- Add failing tests that the recognizer exposes retractions and resets them when tracking is lost.
- Add `finger_retractions` to `HandObservation` and smooth the three target channels with the existing EMA factor.
- Run recognizer-adjacent tests.

## Task 3: Configurable fusion (TDD)

- Add failing mapper tests for max fusion, target-finger isolation, disabled fallback, missing-data fallback, clipping, and invalid calibration.
- Extend `GestureMapper` with optional `finger_retargeting` configuration and `finger_retractions` input.
- Add conservative per-finger calibration values to `config.yaml`.
- Wire the observation through `main.py` and update test doubles.

## Task 4: Verification and package

- Run the complete Python and Electron test suites.
- Build the Windows installer without changing the published semantic version.
- Record installer path, size, timestamp, and SHA-256.
- Hand off a guarded real-hardware A/B checklist; do not claim the movement is fixed until the operator confirms it.
