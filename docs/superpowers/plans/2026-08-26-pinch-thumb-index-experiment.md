# Pinch, Thumb, Index, and Sending Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated RP-Hand experiment that expands thumb/index travel, adds smooth pinch assistance, and exposes an independent Electron sending switch without changing emergency-stop recovery.

**Architecture:** Keep geometry, mapping, runtime state, and renderer responsibilities separate. `gesture_recognizer.py` produces a continuous pinch feature, `gesture_mapping.py` converts calibrated features into joint targets, `main.py` only wires those values together, and Electron reflects the existing `sending` state through the existing `toggle_pause` bridge command.

**Tech Stack:** Python 3.12, MediaPipe, NumPy, pytest, Electron 44, Node test runner, PyInstaller, electron-builder/NSIS.

---

## File Structure

- Modify `config.yaml`: store experimental thumb/index closed endpoints and opt-in pinch-assist targets.
- Modify `gesture_recognizer.py`: calculate and smooth `pinch_strength` independently of gesture labels.
- Modify `gesture_mapping.py`: apply optional source-level pinch targets after normal input calibration.
- Modify `main.py`: pass pinch configuration and the observed strength into the mapper.
- Modify `tests/test_gesture_mapping.py`: cover hardware endpoint samples and assist isolation.
- Create `tests/test_pinch_strength.py`: cover the pure fingertip-distance feature.
- Modify `tests/test_main_electron_bridge.py`: preserve the runtime integration contract after the mapper signature changes.
- Modify `electron/renderer/index.html`: add an accessible sending switch.
- Modify `electron/renderer/app.js`: synchronize the switch with Python state and the Space shortcut.
- Modify `electron/renderer/styles.css`: share switch styling and keep controls at least 44 pixels high.
- Modify `electron/renderer/layout.cjs`: reserve height for four control rows.
- Modify `electron/test/controls.test.cjs`: cover markup, state synchronization, and command behavior.
- Modify `electron/test/layout.test.cjs`: cover the four-row panel.
- Modify `electron/package.json` and `electron/package-lock.json`: identify the experimental installer as `0.3.0-beta.1`.

### Task 1: Calibrate Thumb and Index Closed Endpoints

**Files:**
- Modify: `tests/test_gesture_mapping.py`
- Modify: `config.yaml`

- [ ] **Step 1: Write the failing hardware endpoint test**

Add this test to `tests/test_gesture_mapping.py`:

```python
def test_real_hardware_thumb_and_index_closed_samples_reach_full_travel():
    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    mapper = GestureMapper(
        config["hand"]["joints"],
        config["presets"],
        config["hand"]["input_calibration"],
    )
    sample = {
        "thumb": 0.446,
        "thumb_spread": 0.1617,
        "index": 0.672,
        "middle": 0.2607,
        "ring": 0.1893,
        "pinky": 0.2296,
    }

    positions = mapper.map_mirror(sample)

    assert positions[0] == pytest.approx(10000.0)
    assert positions[2] == pytest.approx(10000.0)
    assert positions[1] == pytest.approx(0.0)
    assert positions[3:] == pytest.approx([0.0, 0.0, 0.0])
```

- [ ] **Step 2: Run the test and verify the expected failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_gesture_mapping.py::test_real_hardware_thumb_and_index_closed_samples_reach_full_travel -v
```

Expected: FAIL because `config.yaml` still treats `closed` as `1.0`, producing roughly `3025` for the thumb and `5581` for the index.

- [ ] **Step 3: Add only the two confirmed closed endpoints**

Change the corresponding entries in `config.yaml`:

```yaml
input_calibration:
  thumb:        { open: 0.2057, closed: 0.446 }
  thumb_spread: { open: 0.1617 }
  index:        { open: 0.2576, closed: 0.672 }
  middle:       { open: 0.2607 }
  ring:         { open: 0.1893 }
  pinky:        { open: 0.2296 }
```

- [ ] **Step 4: Run mapping tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_gesture_mapping.py -v
```

Expected: all mapping tests PASS, including the existing six-channel open-hand sample.

- [ ] **Step 5: Commit the endpoint experiment**

```powershell
git add -- config.yaml tests/test_gesture_mapping.py
git commit -m "experiment(mapping): 校准拇指和食指闭合端"
```

### Task 2: Produce a Continuous Pinch Strength Feature

**Files:**
- Create: `tests/test_pinch_strength.py`
- Modify: `gesture_recognizer.py`

- [ ] **Step 1: Write failing pure-geometry tests**

Create `tests/test_pinch_strength.py`:

```python
import numpy as np
import pytest

from gesture_recognizer import _compute_pinch_strength


def _landmarks_with_normalized_pinch_distance(distance: float) -> np.ndarray:
    landmarks = np.zeros((21, 3), dtype=np.float32)
    landmarks[0] = [0.0, 0.0, 0.0]
    landmarks[9] = [1.0, 0.0, 0.0]
    landmarks[4] = [0.0, 0.0, 0.0]
    landmarks[8] = [distance, 0.0, 0.0]
    return landmarks


@pytest.mark.parametrize(
    ("distance", "expected"),
    [(0.50, 0.0), (0.45, 0.0), (0.30, 0.5), (0.15, 1.0), (0.05, 1.0)],
)
def test_pinch_strength_maps_tip_distance_to_a_bounded_continuous_value(
    distance: float,
    expected: float,
):
    landmarks = _landmarks_with_normalized_pinch_distance(distance)

    assert _compute_pinch_strength(landmarks) == pytest.approx(expected)


def test_pinch_strength_increases_monotonically_as_fingertips_approach():
    distances = [0.45, 0.35, 0.25, 0.15]
    strengths = [
        _compute_pinch_strength(_landmarks_with_normalized_pinch_distance(value))
        for value in distances
    ]

    assert strengths == sorted(strengths)
```

- [ ] **Step 2: Run the tests and verify import failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pinch_strength.py -v
```

Expected: collection ERROR because `_compute_pinch_strength` does not exist.

- [ ] **Step 3: Implement the pure feature and expose it on observations**

Add a pure helper near `_angle_deg` in `gesture_recognizer.py`:

```python
def _compute_pinch_strength(
    lm: np.ndarray,
    contact_distance: float = 0.15,
    release_distance: float = 0.45,
) -> float:
    """Return 0 when fingertips are apart and 1 near thumb-index contact."""

    palm_scale = np.linalg.norm(lm[0] - lm[9]) + 1e-6
    normalized_distance = np.linalg.norm(lm[4] - lm[8]) / palm_scale
    strength = (
        release_distance - normalized_distance
    ) / (release_distance - contact_distance)
    return float(np.clip(strength, 0.0, 1.0))
```

Add the field to `HandObservation`:

```python
pinch_strength: float = 0.0
```

Initialize and reset a smoothed value with the other recognizer state:

```python
self._smooth_pinch_strength = 0.0
```

After computing `thumb_spread`, smooth and expose the feature:

```python
raw_pinch_strength = _compute_pinch_strength(geometry_lm)
self._smooth_pinch_strength = (
    self._alpha * raw_pinch_strength
    + (1 - self._alpha) * self._smooth_pinch_strength
)
obs.pinch_strength = self._smooth_pinch_strength
```

- [ ] **Step 4: Run the focused and recognizer-adjacent tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pinch_strength.py tests/test_geometry_diagnostics.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit the continuous feature**

```powershell
git add -- gesture_recognizer.py tests/test_pinch_strength.py
git commit -m "experiment(geometry): 增加连续捏合强度特征"
```

### Task 3: Apply Opt-In Progressive Pinch Assistance

**Files:**
- Modify: `tests/test_gesture_mapping.py`
- Modify: `tests/test_main_electron_bridge.py`
- Modify: `gesture_mapping.py`
- Modify: `main.py`
- Modify: `config.yaml`

- [ ] **Step 1: Write failing mapper tests for isolation and continuity**

Add to `tests/test_gesture_mapping.py`:

```python
PINCH_JOINTS = [
    {"name": "thumb_bend", "src": "thumb", "range": [0, 10000]},
    {"name": "thumb_rotate", "src": "thumb_spread", "range": [0, 10000]},
    {"name": "index_finger", "src": "index", "range": [0, 10000]},
    {"name": "middle_finger", "src": "middle", "range": [0, 10000]},
]

PINCH_ASSIST = {
    "enabled": True,
    "targets": {"thumb": 0.8, "thumb_spread": 0.6, "index": 0.85},
}


def test_pinch_assist_progressively_enhances_only_configured_sources():
    mapper = GestureMapper(PINCH_JOINTS, {}, {}, PINCH_ASSIST)
    inputs = {"thumb": 0.0, "thumb_spread": 0.0, "index": 0.0, "middle": 0.2}

    half = mapper.map_mirror(inputs, pinch_strength=0.5)
    full = mapper.map_mirror(inputs, pinch_strength=1.0)

    assert half == pytest.approx([4000, 3000, 4250, 2000])
    assert full == pytest.approx([8000, 6000, 8500, 2000])


def test_disabled_pinch_assist_preserves_plain_continuous_mapping():
    mapper = GestureMapper(
        PINCH_JOINTS,
        {},
        {},
        {"enabled": False, "targets": PINCH_ASSIST["targets"]},
    )
    inputs = {"thumb": 0.1, "thumb_spread": 0.2, "index": 0.3, "middle": 0.4}

    assert mapper.map_mirror(inputs, pinch_strength=1.0) == pytest.approx(
        [1000, 2000, 3000, 4000]
    )
```

- [ ] **Step 2: Run the tests and verify constructor/signature failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_gesture_mapping.py -v
```

Expected: FAIL because `GestureMapper` does not accept pinch configuration or `pinch_strength`.

- [ ] **Step 3: Implement source-level assist after calibration**

Extend the constructor in `gesture_mapping.py`:

```python
def __init__(
    self,
    joint_cfg: List[dict],
    presets: Dict[str, List[float]],
    input_calibration: Optional[Dict[str, dict]] = None,
    pinch_assist: Optional[Dict[str, object]] = None,
):
    self._pinch_assist = pinch_assist or {}
    targets = self._pinch_assist.get("targets", {})
    for src, target in targets.items():
        value = float(target)
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{src} 的捏合辅助目标必须在 0 到 1 之间")
```

Add this helper:

```python
def _apply_pinch_assist(
    self,
    values: Dict[str, float],
    pinch_strength: float,
) -> Dict[str, float]:
    assisted = dict(values)
    if not self._pinch_assist.get("enabled", False):
        return assisted
    strength = min(max(float(pinch_strength), 0.0), 1.0)
    for src, target in self._pinch_assist.get("targets", {}).items():
        assisted[src] = max(assisted.get(src, 0.0), float(target) * strength)
    return assisted
```

Change `map_mirror` to calibrate first and then apply the helper:

```python
def map_mirror(
    self,
    curls: Dict[str, float],
    pinch_strength: float = 0.0,
) -> List[float]:
    calibrated = self.calibrate_inputs(curls)
    calibrated = self._apply_pinch_assist(calibrated, pinch_strength)
    out = []
    for joint in self._joints:
        low, high = joint["range"]
        src = joint.get("src")
        curl = calibrated.get(src, 0.0) if src else 0.0
        out.append(low + (high - low) * curl)
    return out
```

- [ ] **Step 4: Wire the feature through config and runtime**

Add to `config.yaml` under `hand`:

```yaml
pinch_assist:
  enabled: true
  targets:
    thumb: 0.80
    thumb_spread: 0.60
    index: 0.85
```

Pass it into `GestureMapper` in `main.py`:

```python
mapper = GestureMapper(
    cfg["hand"]["joints"],
    cfg.get("presets", {}),
    cfg["hand"].get("input_calibration", {}),
    cfg["hand"].get("pinch_assist", {}),
)
```

Pass the observed feature only in mirror mode:

```python
positions = mapper.map_mirror(
    vals,
    pinch_strength=obs.pinch_strength,
)
```

Update the test doubles in `tests/test_main_electron_bridge.py`:

```python
class Observation:
    pinch_strength = 0.0

class Mapper:
    def map_mirror(self, _values, pinch_strength=0.0):
        return [5000.0]
```

- [ ] **Step 5: Run mapping and runtime integration tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_gesture_mapping.py tests/test_pinch_strength.py tests/test_main_electron_bridge.py -v
```

Expected: all tests PASS, and existing emergency recovery assertions remain unchanged.

- [ ] **Step 6: Commit the opt-in assist**

```powershell
git add -- config.yaml gesture_mapping.py main.py tests/test_gesture_mapping.py tests/test_main_electron_bridge.py
git commit -m "experiment(mapping): 增加渐进式捏合辅助"
```

### Task 4: Add an Independent Electron Sending Switch

**Files:**
- Modify: `electron/test/controls.test.cjs`
- Modify: `electron/test/layout.test.cjs`
- Modify: `electron/renderer/index.html`
- Modify: `electron/renderer/app.js`
- Modify: `electron/renderer/styles.css`
- Modify: `electron/renderer/layout.cjs`

- [ ] **Step 1: Write failing renderer contract tests**

Add to `electron/test/controls.test.cjs`:

```javascript
test('exposes an independent sending switch synchronized with runtime state', () => {
  assert.match(html, /id="sending-toggle"/);
  assert.match(html, /id="sending-toggle"[\s\S]*?role="switch"/);
  assert.match(appJs, /pendingSending/);
  assert.match(appJs, /state\.sending/);
  assert.match(appJs, /sendCommand\('toggle_pause'\)/);
});

test('uses the same sending toggle for the button and Space shortcut', () => {
  assert.match(appJs, /sendingToggle\.addEventListener\('click', toggleSending\)/);
  assert.match(appJs, /event\.code === 'Space'[\s\S]*?toggleSending\(\)/);
});
```

Change the minimum-height contract:

```javascript
assert.match(css, /#sending-toggle[\s\S]*?min-height:\s*44px/);
```

Change the final layout test in `electron/test/layout.test.cjs`:

```javascript
test('reserves enough height for all four control rows', () => {
  const layout = computeLayout(1280, 720, 1280, 720);
  assert.equal(layout.controls.height >= 204, true);
});
```

- [ ] **Step 2: Run Electron tests and verify the missing-control failures**

Run:

```powershell
cd electron
npm test
```

Expected: FAIL because `sending-toggle`, `pendingSending`, and four-row layout do not exist.

- [ ] **Step 3: Add accessible sending switch markup**

Insert after the recognition row in `electron/renderer/index.html`:

```html
<div class="control-row">
  <span id="sending-label">指令发送</span>
  <button
    id="sending-toggle"
    type="button"
    role="switch"
    aria-labelledby="sending-label"
    aria-checked="true"
  ><span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span></button>
</div>
```

- [ ] **Step 4: Synchronize button, Space shortcut, and backend state**

In `electron/renderer/app.js`, add:

```javascript
const sendingToggle = document.getElementById('sending-toggle');
let pendingSending = null;

function toggleSending() {
  if (sendingToggle.disabled) return;
  pendingSending = sendingToggle.getAttribute('aria-checked') !== 'true';
  sendingToggle.setAttribute('aria-checked', pendingSending ? 'true' : 'false');
  window.rpHand.sendCommand('toggle_pause');
}
```

In `applyRuntimeState`, synchronize and disable it with the other controls:

```javascript
sendingToggle.disabled = stopped;
if (pendingSending === state.sending) pendingSending = null;
if (pendingSending === null) {
  sendingToggle.setAttribute('aria-checked', state.sending ? 'true' : 'false');
}
```

Register the click handler and replace the existing Space command with `toggleSending()`:

```javascript
sendingToggle.addEventListener('click', toggleSending);

if (event.code === 'Space') {
  event.preventDefault();
  toggleSending();
}
```

Disable it in `onProcessState` with the other controls.

- [ ] **Step 5: Share switch styling and reserve panel height**

In `electron/renderer/styles.css`, extend the existing selectors rather than duplicating rules:

```css
#detection-toggle,
#sending-toggle {
  display: grid;
  place-items: center;
  width: 56px;
  min-height: 44px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}

#detection-toggle[aria-checked="true"] .switch-track,
#sending-toggle[aria-checked="true"] .switch-track {
  background: #1769e0;
}

#detection-toggle[aria-checked="true"] .switch-thumb,
#sending-toggle[aria-checked="true"] .switch-thumb {
  transform: translateX(20px);
}
```

Include `#sending-toggle` in focus, disabled, and narrow-container selectors.

In `electron/renderer/layout.cjs`, replace the control height calculation with:

```javascript
const controlsHeight = Math.max(204, 220 * scale);
```

- [ ] **Step 6: Run Electron tests**

Run:

```powershell
cd electron
npm test
```

Expected: all Electron tests PASS.

- [ ] **Step 7: Commit the sending control**

```powershell
git add -- electron/renderer/index.html electron/renderer/app.js electron/renderer/styles.css electron/renderer/layout.cjs electron/test/controls.test.cjs electron/test/layout.test.cjs
git commit -m "feat(electron): 增加独立的指令发送开关"
```

### Task 5: Verify, Version, and Package the Experiment

**Files:**
- Modify: `electron/package.json`
- Modify: `electron/package-lock.json`

- [ ] **Step 1: Run the complete Python suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests PASS with no real SDK connection or hardware motion.

- [ ] **Step 2: Run the complete Electron suite**

Run:

```powershell
cd electron
npm test
```

Expected: all tests PASS.

- [ ] **Step 3: Assign an unmistakable experimental version**

Run from `electron`:

```powershell
npm version 0.3.0-beta.1 --no-git-tag-version
```

Expected: `package.json` and `package-lock.json` both contain `0.3.0-beta.1`.

- [ ] **Step 4: Commit the experimental version**

```powershell
git add -- electron/package.json electron/package-lock.json
git commit -m "chore(electron): 标记捏合映射实验版本"
```

- [ ] **Step 5: Build the complete Windows installer**

Run from `electron`:

```powershell
npm run dist:win
```

Expected: exit code `0` and a new installer at `electron/dist/RP-Hand Setup 0.3.0-beta.1.exe`.

- [ ] **Step 6: Verify artifact metadata and repository state**

Run:

```powershell
Get-Item -LiteralPath '.\dist\RP-Hand Setup 0.3.0-beta.1.exe' | Select-Object FullName,Length,LastWriteTime
Get-FileHash -LiteralPath '.\dist\RP-Hand Setup 0.3.0-beta.1.exe' -Algorithm SHA256
git -C .. status --short --branch
```

Expected: the installer exists with a fresh timestamp and nonzero size; Git shows the experiment branch with no uncommitted source changes.

- [ ] **Step 7: Hand off the guarded real-hardware checklist**

Report the installer path and SHA-256. Ask the operator to test in this exact order: sending off visual inspection, open/close endpoint check, other-finger regression check, slow pinch approach/release, sending switch/Space synchronization, and emergency stop/recovery. Do not claim hardware behavior is fixed until that checklist passes on the real hand.
