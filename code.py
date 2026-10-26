

from psychopy import visual, core, event, gui
import random
import csv
import os
from datetime import datetime

# pyxid2 is required for the Cedrus devices. Guarded so the task can still
# run keyboard-only on a machine without it (device scan just returns None).
try:
    import pyxid2
except ImportError:
    pyxid2 = None
    print("pyxid2 not installed -- StimTracker + response pad disabled, "
          "keyboard (1-4) + CSV-only markers will be used.")


#############################
# EXPERIMENT SETTINGS
#############################

# ----------------------------------------------------------------------
# TRIAL CONDITIONS -- fully mutable. Add/remove/edit conditions freely;
# everything downstream (trial generation, CSV logging) reads from this.
#
#   kind      : which problem generator to use ("add_sub", "multiply",
#               "two_step" -- see generate_problem() below)
#   a_range   : inclusive range for the first operand
#   b_range   : inclusive range for the second operand
#   c_range   : inclusive range for the third operand ("two_step" only)
#   offsets   : distractor offsets, scaled to that level's answer magnitude
#   n_trials  : trials of this condition in the session
#
# LEVEL 1 IS VERBATIM FROM Level1.py (single-digit +/-, non-negative
# subtraction result). LEVELS 2-5 ARE PLACEHOLDERS extrapolated from that
# progression -- overwrite them with your real Level2-5 definitions.
# 5 levels x 50 trials = 250. For 4 levels, delete one row and set
# n_trials to 63/63/62/62.
# ----------------------------------------------------------------------
TRIAL_CONDITIONS = [
    # single-digit addition/subtraction: 7+8, 7-3
    {"level": 1, "kind": "add_sub", "a_range": (1, 9), "b_range": (1, 9),
     "offsets": [-3, -2, -1, 1, 2, 3, -4, 4], "n_trials": 50},

    # two-digit addition/subtraction, NO carry/borrow: 17+12, 27-13
    {"level": 2, "kind": "two_digit", "carry": False,
     "offsets": [-20, -10, -2, -1, 1, 2, 10, 20], "n_trials": 50},

    # two-digit addition/subtraction, WITH carry/borrow: 17+15, 27-19
    {"level": 3, "kind": "two_digit", "carry": True,
     "offsets": [-11, -10, -9, -1, 1, 9, 10, 11], "n_trials": 50},

    # two-step operations: 47-18+9, 27+12-19
    {"level": 4, "kind": "multi_step",
     "term_ranges": [(10, 99), (10, 49), (1, 29)],
     "offsets": [-10, -9, -2, -1, 1, 2, 9, 10], "n_trials": 50},

    # three-step operations: 63+14-27+8, 27+12-19+5
    {"level": 5, "kind": "multi_step",
     "term_ranges": [(10, 99), (10, 49), (10, 49), (1, 29)],
     "offsets": [-10, -9, -2, -1, 1, 2, 9, 10], "n_trials": 50},
]

# True = shuffle all conditions' trials together into one interleaved
# block (matches "one block of 250 trials"). False = present as 5
# consecutive sub-blocks, one per condition, in random order.
INTERLEAVE_CONDITIONS = True

# ---- Timings: VERBATIM FROM Level1.py -- do not let these drift --------
PRESENTATION_DURATION = 3.0     # problem shown alone
RESPONSE_DURATION = 2.0         # options shown alone, response window
FEEDBACK_DURATION = 0.30
ITI_RANGE = (0.8, 1.0)          # jittered "X" fixation between trials

BREAK_EVERY_N_TRIALS = 5   # self-paced break frequency; None to disable
                            
                           

# ----------------------------------------------------------------------
# FEATURE FLAGS
# ----------------------------------------------------------------------
USE_APRILTAG = True
USE_STIMTRACKER = True
USE_RESPONSE_PAD = True      # Cedrus Riponda via pyxid2 (keyboard 1-4 always works too)
USE_EYETRACKER = False       # Pupil Core -- see clearly marked block below
USE_LSL_MARKERS = False      # LSL marker outlet -- see clearly marked block below

#APRILTAG_PATH = "C:/Users/hprai/OneDrive/Desktop/Python/Healtcare/Neural/Working memory task/apriltag.png"
APRILTAG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "apriltag.png"
)
# ----------------------------------------------------------------------
# CEDRUS XID DEVICE IDENTIFICATION
# Both the StimTracker and the Riponda enumerate as XID devices; we tell
# them apart by product_id instead of grabbing devices[0]. Confirm these
# against your own hardware with a diagnose scan if a device isn't found.
# ----------------------------------------------------------------------
RIPONDA_PRODUCT_ID = b'5'
STIMTRACKER_PRODUCT_ID = b'S'

# Pad button 'key' number (from pyxid2 get_next_response) -> option letter.
# !! CONFIRM with capture_response_pad_codes()  (python <file>.py --capture)
#    before real data -- pyxid2 key numbers depend on your pad's layout and
#    are NOT guaranteed to be 1/2/3/4. Unmapped presses simply fall through
#    to the keyboard, so a wrong map won't crash, it just won't register. !!
PAD_KEY_TO_OPTION = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E"}

# Option -> keyboard key (always active, hardware-independent fallback)
OPTION_KEYS = {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"}

LETTERS = ["A", "B", "C", "D", "E"]


#############################
# PROBLEM GENERATION
#############################
# Difficulty lives entirely in TRIAL_CONDITIONS: a condition names a
# generator "kind" plus its operand ranges, so a level can be retuned or
# a new one added without touching anything below.

def generate_problem(condition):
    """Return (problem_string, correct_answer) for one condition."""
    kind = condition["kind"]

    # ---- Level 1: single-digit +/- [verbatim from Level1.py] ----------
    if kind == "add_sub":
        a_lo, a_hi = condition["a_range"]
        b_lo, b_hi = condition["b_range"]
        op = random.choice(["+", "-"])
        if op == "+":
            a, b = random.randint(a_lo, a_hi), random.randint(b_lo, b_hi)
            return f"{a} + {b}", a + b
        # subtraction constrained to a non-negative result
        a = random.randint(max(a_lo, b_lo + 1), a_hi)
        b = random.randint(b_lo, min(b_hi, a - 1))
        return f"{a} - {b}", a - b

    # ---- Levels 2 & 3: two-digit +/-, carry/borrow controlled --------
    # condition["carry"] False -> units never carry / borrow
    #                      True -> units ALWAYS carry / borrow
    if kind == "two_digit":
        carry = condition["carry"]
        if random.choice(["+", "-"]) == "+":
            while True:
                at, bt = random.randint(1, 8), random.randint(1, 8)
                au, bu = random.randint(0, 9), random.randint(0, 9)
                if ((au + bu) >= 10) != carry:
                    continue
                if at + bt + (1 if carry else 0) > 9:   # keep the answer two-digit
                    continue
                a, b = 10 * at + au, 10 * bt + bu
                return f"{a} + {b}", a + b
        while True:
            at = random.randint(2, 9)
            bt = random.randint(1, at - 1)              # at > bt keeps the result positive
            au, bu = random.randint(0, 9), random.randint(0, 9)
            if (au < bu) != carry:
                continue
            a, b = 10 * at + au, 10 * bt + bu
            return f"{a} - {b}", a - b

    # ---- Levels 4 & 5: multi-step chains -----------------------------
    # One term per entry in condition["term_ranges"], so 3 entries = two-step,
    # 4 entries = three-step. Rejects chains that go negative at any point and
    # chains that are all-addition.
    if kind == "multi_step":
        ranges = condition["term_ranges"]
        while True:
            terms = [random.randint(lo, hi) for lo, hi in ranges]
            ops = [random.choice(["+", "-"]) for _ in range(len(terms) - 1)]
            if "-" not in ops:
                continue
            total, ok = terms[0], True
            for op, t in zip(ops, terms[1:]):
                total = total + t if op == "+" else total - t
                if total < 0:
                    ok = False
                    break
            if not ok or total < 1:
                continue
            parts = [str(terms[0])]
            for op, t in zip(ops, terms[1:]):
                parts += [op, str(t)]
            return " ".join(parts), total

    raise ValueError(f"Unknown problem kind: {kind!r}")


def generate_options(correct_answer, offsets):
    """Build 4 plausible answer options (including the correct one),
    shuffle their position, and return (options_dict, correct_letter).
    Distractors are close, plausible near-miss values. [From Level1.py]"""
    offsets_pool = list(offsets)
    random.shuffle(offsets_pool)

    distractors = set()
    for off in offsets_pool:
        val = correct_answer + off
        if val >= 0 and val != correct_answer:
            distractors.add(val)
        if len(distractors) == 3:
            break

    # Fallback in the rare case we couldn't get 3 unique nonneg distractors
    while len(distractors) < 3:
        val = correct_answer + random.randint(-10, 10)
        if val >= 0 and val != correct_answer:
            distractors.add(val)

    values = [correct_answer] + list(distractors)[:3]
    random.shuffle(values)

    options_dict = dict(zip(LETTERS, values))
    correct_letter = [k for k, v in options_dict.items() if v == correct_answer][0]
    return options_dict, correct_letter


#def format_options_text(options_dict):
    return "    ".join(f"{letter}. {options_dict[letter]}" for letter in LETTERS)

def format_options_text(options_dict):
    numeric_options = "    ".join(
        f"{letter}. {options_dict[letter]}"
        for letter in ["A", "B", "C", "D"]
    )
    return numeric_options + "\n\nE. Could not solve"
#############################
# TRIAL GENERATOR
#############################

def build_trial(condition):
    """Creates one randomized arithmetic trial."""
    problem_str, correct_answer = generate_problem(condition)
    options, correct_letter = generate_options(correct_answer, condition["offsets"])

    trial = {
        "level": condition["level"],
        "kind": condition["kind"],
        "problem": problem_str,
        "correct_answer": correct_answer,
        "options": options,
        "correct_letter": correct_letter,
        "iti": random.uniform(*ITI_RANGE),   # jitter fixed at build time, so it's loggable
    }
    return trial


def build_all_trials():
    """Generate all trials across every condition in TRIAL_CONDITIONS."""
    all_trials = []

    for condition in TRIAL_CONDITIONS:
        condition_trials = [build_trial(condition) for _ in range(condition["n_trials"])]

        if INTERLEAVE_CONDITIONS:
            all_trials.extend(condition_trials)
        else:
            random.shuffle(condition_trials)
            all_trials.append(condition_trials)  # sub-block, kept together

    if INTERLEAVE_CONDITIONS:
        random.shuffle(all_trials)
        return [all_trials]  # one combined block
    else:
        random.shuffle(all_trials)  # randomize sub-block order
        return all_trials


#############################
# EVENT MARKER SYSTEM
#############################
# Codes are kept identical to the WM task wherever the event is the same,
# so the two datasets share a marker vocabulary.

MARKERS = {
    "experiment_start": 101,
    "instructions": 102,

    "trial_start": 110,

    "iti_fixation": 120,     # "X" fixation between trials

    "presentation": 130,     # problem appears (WM's "encoding" slot)

    "response_onset": 155,   # option screen appears (distinct from the press below)

    "response": 160,

    "feedback_correct": 170,
    "feedback_wrong": 171,

    "trial_end": 190,

    "experiment_end": 109,
}


class EventLogger:
    """Handles sending + logging event markers.

    send() prints, logs to events.csv, fires a StimTracker TTL pulse (if
    connected), writes the marker into the ioHub HDF5 message stream (if
    Pupil Core/ioHub is connected), AND pushes it onto an LSL outlet (if
    enabled). This is the ONLY function that needs to change to add/remove
    a hardware integration -- every call site elsewhere is untouched.
    """

    def __init__(self, filepath, stim_device=None, io=None, lsl_outlet=None):
        self.file = open(filepath, "w", newline="")
        self.writer = csv.writer(self.file)
        self.writer.writerow(["timestamp", "marker_code", "event_name"])
        self.clock = core.Clock()
        self.stim_device = stim_device   # pyxid2 StimTracker, or None
        self.io = io                     # ioHub connection, or None
        self.lsl_outlet = lsl_outlet     # pylsl StreamOutlet, or None

    def send(self, event_name):
        marker_code = MARKERS[event_name]
        timestamp = self.clock.getTime()

        print(f"Marker sent: {marker_code} ({event_name}) at {timestamp:.4f}s")

        if self.stim_device is not None:
            try:
                self.stim_device.activate_line(bitmask=marker_code)
            except Exception as e:
                print(f"StimTracker: failed to send marker {marker_code} ({e})")

        if self.io is not None:
            try:
                self.io.sendMessageEvent(text=f"{event_name}_{marker_code}", category=event_name)
            except Exception as e:
                print(f"ioHub: failed to send marker {marker_code} ({e})")

        if self.lsl_outlet is not None:
            try:
                self.lsl_outlet.push_sample([int(marker_code)])
            except Exception as e:
                print(f"LSL: failed to push marker {marker_code} ({e})")

        self.writer.writerow([f"{timestamp:.4f}", marker_code, event_name])
        self.file.flush()

    def close(self):
        self.file.close()


# ============================================================================
# BEGIN CEDRUS XID DISCOVERY BLOCK -- one pyxid2 scan for BOTH devices.
# Comment out this whole block (and its call site in run_experiment) if you
# don't want any Cedrus code running at all.
# ============================================================================

STIMTRACKER_PULSE_MS = 20


def _reset_pad_rt(dev):
    """Reset the pad's reaction-time timer, tolerating pyxid2 API name
    differences (reset_rt_timer vs reset_timer across versions)."""
    for meth in ("reset_rt_timer", "reset_timer"):
        fn = getattr(dev, meth, None)
        if callable(fn):
            try:
                fn()
                return
            except Exception:
                pass


def discover_xid_devices():
    """Scan the XID bus ONCE and return (pad_dev, stim_dev), each selected
    by product_id. Soft-fail: a device that isn't found comes back None
    (with a warning) so the task still runs on keyboard / CSV-only markers."""
    pad_dev = None
    stim_dev = None

    if pyxid2 is None or not (USE_RESPONSE_PAD or USE_STIMTRACKER):
        return None, None

    try:
        devices = pyxid2.get_xid_devices()
    except Exception as e:
        print(f"pyxid2: device scan failed ({e}) -- keyboard + CSV-only fallback.")
        return None, None

    if not devices:
        print("pyxid2: no XID devices found -- keyboard + CSV-only fallback.")
        return None, None

    ripondas = [d for d in devices if getattr(d, "product_id", None) == RIPONDA_PRODUCT_ID]
    stims = [d for d in devices if getattr(d, "product_id", None) == STIMTRACKER_PRODUCT_ID]

    if USE_RESPONSE_PAD:
        if not ripondas:
            print(f"Response pad: no Riponda (product_id={RIPONDA_PRODUCT_ID!r}) found "
                  "-- keyboard (1-4) fallback.")
        else:
            if len(ripondas) > 1:
                print(f"Response pad: {len(ripondas)} Ripondas found -- using the first.")
            pad_dev = ripondas[0]

    if USE_STIMTRACKER:
        if not stims:
            print(f"StimTracker: no device (product_id={STIMTRACKER_PRODUCT_ID!r}) found "
                  "-- print/CSV markers only.")
        else:
            if len(stims) > 1:
                print(f"StimTracker: {len(stims)} devices found -- using the first.")
            stim_dev = stims[0]

    if pad_dev is not None:
        print(f"Response pad selected: {pad_dev} | product_id="
              f"{getattr(pad_dev, 'product_id', None)!r}")
    if stim_dev is not None:
        print(f"StimTracker selected: {stim_dev} | product_id="
              f"{getattr(stim_dev, 'product_id', None)!r}")

    return pad_dev, stim_dev


def setup_stimtracker(stim_dev):
    """Apply pulse settings to an already-discovered StimTracker. Returns
    the device on success, or None so EventLogger falls back to CSV-only."""
    if stim_dev is None:
        return None
    try:
        stim_dev.reset_base_timer()
        stim_dev.reset_rt_timer()
        stim_dev.set_pulse_duration(STIMTRACKER_PULSE_MS)
        print(f"StimTracker configured (pulse {STIMTRACKER_PULSE_MS} ms).")
        return stim_dev
    except Exception as e:
        print(f"StimTracker: setup failed ({e}) -- print/CSV markers only.")
        return None


def setup_response_pad(pad_dev):
    """Put an already-discovered Riponda into a clean state. Returns the
    device on success, or None so responses fall back to the keyboard."""
    if pad_dev is None:
        return None
    try:
        _reset_pad_rt(pad_dev)
        pad_dev.poll_for_response()
        pad_dev.clear_response_queue()
        print("Response pad ready.")
        return pad_dev
    except Exception as e:
        print(f"Response pad: setup failed ({e}) -- keyboard (1-4) fallback.")
        return None

# ============================================================================
# END CEDRUS XID DISCOVERY BLOCK
# ============================================================================


# ============================================================================
# BEGIN LSL MARKER BLOCK -- OPTIONAL. Pushes every marker code onto an LSL
# stream so LabRecorder (or an LSL-aware eye tracker / EEG amp) can record
# them into one synchronized XDF. Comment out this whole block (and its call
# site in run_experiment) if you don't want LSL code running at all.
#
# Requires: pip install pylsl. Off by default (USE_LSL_MARKERS = False) so
# nothing breaks if pylsl isn't installed / LabRecorder isn't set up.
# ============================================================================

LSL_STREAM_NAME = "Arithmetic_Task_Markers"
LSL_STREAM_TYPE = "Markers"
LSL_SOURCE_ID = "arithmetic_task_marker_stream"


def init_lsl():
    """Create an int32 LSL marker outlet, or return None on any failure."""
    if not USE_LSL_MARKERS:
        return None
    try:
        from pylsl import StreamInfo, StreamOutlet
        info = StreamInfo(
            name=LSL_STREAM_NAME,
            type=LSL_STREAM_TYPE,
            channel_count=1,
            nominal_srate=0,          # irregular rate -- markers are event-driven
            channel_format="int32",
            source_id=LSL_SOURCE_ID,
        )
        outlet = StreamOutlet(info)
        print(f"LSL: marker outlet '{LSL_STREAM_NAME}' created.")
        return outlet
    except ImportError:
        print("LSL: pylsl not installed -- skipping LSL markers.")
        return None
    except Exception as e:
        print(f"LSL: outlet creation failed ({e}) -- skipping LSL markers.")
        return None

# ============================================================================
# END LSL MARKER BLOCK
# ============================================================================


# ============================================================================
# BEGIN PUPIL CORE EYE TRACKER BLOCK -- comment out this whole block (and its
# call sites in run_experiment) if you don't want eye-tracking code running.
#
# Requires: Pupil Capture running with headset connected, the
# "psychopy-eyetracker-pupil-labs" plugin installed, AprilTag markers
# visible on screen (see APRILTAG_PATH / USE_APRILTAG above), and --
# done manually inside Pupil Capture itself, NOT from this script -- a
# Surface Tracker surface defined around those tags and renamed to match
# SURFACE_NAME below. Core also needs calibration; run_calibration() below
# triggers Pupil Capture's calibration choreography once, at experiment
# start.
# ============================================================================

PUPIL_REMOTE_ADDRESS = "127.0.0.1"
PUPIL_REMOTE_PORT = 50020
PUPIL_REMOTE_TIMEOUT_MS = 5000

PUPIL_CAPTURE_RECORDING = True
GAZE_CONFIDENCE_THRESHOLD = 0.6
PUPILLOMETRY_ONLY = False
SURFACE_NAME = "psychopy_iohub_surface"

HDF5_FILENAME = "gaze_data"   # ioHub appends .hdf5 automatically


def init_iohub(data_dir, win):
    """Launch ioHub with the Pupil Core eye tracker device. Returns
    (io, eyetracker), or (None, None) on failure -- in which case the
    task runs with no eye tracking. NOTE: the exact runtime_settings key
    names below are a best-effort translation of the plugin's documented
    Builder-panel fields; cross-check against your installed plugin's
    default_eyetracker_devices.yaml if connection fails on a settings
    error specifically."""
    if not USE_EYETRACKER:
        return None, None
    try:
        from psychopy.iohub import launchHubServer

        iohub_config = {
            "eyetracker.hw.pupil_labs.pupil_core.EyeTracker": {
                "name": "tracker",
                "runtime_settings": {
                    "pupil_remote": {
                        "ip_address": PUPIL_REMOTE_ADDRESS,
                        "port": PUPIL_REMOTE_PORT,
                        "timeout_ms": PUPIL_REMOTE_TIMEOUT_MS,
                    },
                    "pupil_capture_recording": {
                        "enabled": PUPIL_CAPTURE_RECORDING,
                    },
                    "gaze_confidence_threshold": GAZE_CONFIDENCE_THRESHOLD,
                    "pupillometry_only": PUPILLOMETRY_ONLY,
                    "surface_name": SURFACE_NAME,
                },
            }
        }

        io = launchHubServer(
            window=win,
            datastore_name=os.path.join(data_dir, HDF5_FILENAME),
            **iohub_config,
        )
        eyetracker = io.devices.tracker
        if eyetracker is None:
            print("Pupil Core: eye tracker device not found -- running without eye tracking.")
            io.quit()
            return None, None
        print("Pupil Core eye tracker connected via ioHub.")
        return io, eyetracker
    except Exception as e:
        print(f"Pupil Core: connection failed ({e}) -- running without eye tracking.")
        return None, None


def run_calibration(eyetracker):
    """Run Pupil Capture's calibration choreography. Blocks until
    complete. Skipped in pupillometry-only mode or if no tracker."""
    if eyetracker is None or PUPILLOMETRY_ONLY:
        return
    try:
        print("Pupil Core: starting calibration...")
        result = eyetracker.runSetupProcedure()
        print(f"Pupil Core: calibration finished (result={result}).")
    except Exception as e:
        print(f"Pupil Core: calibration failed ({e}) -- continuing without it.")

# ============================================================================
# END PUPIL CORE EYE TRACKER BLOCK
# ============================================================================


#############################
# GLOBAL ESCAPE HANDLING
#############################

def check_escape():
    if event.getKeys(keyList=["escape"]):
        core.quit()


def wait_with_escape(duration, poll_interval=0.02):
    clock = core.Clock()
    while clock.getTime() < duration:
        check_escape()
        core.wait(min(poll_interval, duration - clock.getTime()))
    check_escape()


#############################
# PARTICIPANT INFO / OUTPUT FILES
#############################

def get_participant_info():
    exp_info = {"Participant ID": "", "Session": "001",
                "Age": "", "Gender": ["Female", "Male", "Other/Prefer not to say"]}
    dlg = gui.DlgFromDict(dictionary=exp_info, title="Arithmetic Task")
    if not dlg.OK:
        core.quit()
    exp_info["date"] = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return exp_info


def make_data_dir():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "arithmetic_task_data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


#############################
# BUILD STIMULI
#############################

def build_stimuli(win):
    background = None
    if USE_APRILTAG:
        try:
            background = visual.ImageStim(win, image=APRILTAG_PATH, units="norm", size=(2, 2))
        except Exception as e:
            print("AprilTag could not be loaded:", e)
            background = None

    problem = visual.TextStim(win, text="", color="white", height=0.10, units="height", pos=(0, 0))

    options = visual.TextStim(win, text="", color="white", height=0.06, units="height", pos=(0, 0))

    response_prompt = visual.TextStim(
        win, text="Use keys 1-4 to answer, or key 5 for 'Could not solve'",
        color="white", height=0.045, units="height", pos=(0, 0.42), wrapWidth=1.5
    )

    fixation = visual.TextStim(win, text="+", color="white", height=0.08, units="height")

    correct_feedback = visual.TextStim(win, text="\u263A", color="limegreen", height=0.20, units="height")
    wrong_feedback = visual.TextStim(win, text="\u2639", color="red", height=0.20, units="height")

    break_text = visual.TextStim(win, text="", color="white", height=0.05, units="height", wrapWidth=1.5)

    return {
        "background": background,
        "problem": problem,
        "options": options,
        "response_prompt": response_prompt,
        "fixation": fixation,
        "correct_feedback": correct_feedback,
        "wrong_feedback": wrong_feedback,
        "break_text": break_text,
    }


def draw_background(stims):
    if stims["background"] is not None:
        stims["background"].draw()


#############################
# TRIAL ROUTINES  (each phase sends its marker)
#############################

def run_presentation(win, stims, trial, logger):
    """Problem shown alone for PRESENTATION_DURATION."""
    check_escape()
    draw_background(stims)
    stims["problem"].text = trial["problem"]
    stims["problem"].draw()
    logger.send("presentation")
    win.flip()
    wait_with_escape(PRESENTATION_DURATION)


# ----------------------------------------------------------------------
# RESPONSE COLLECTION -- Riponda via pyxid2 (device-timer RT), with
# keyboard (1/2/3/4) as a hardware-independent fallback that always works.
# pad_dev is the pyxid2 device from discover_xid_devices(), or None.
# ----------------------------------------------------------------------

def get_response(win, stims, trial, logger, pad_dev):
    check_escape()
    draw_background(stims)
    stims["options"].text = format_options_text(trial["options"])
    stims["options"].draw()
    stims["response_prompt"].draw()
    win.flip()

    # Marker for the moment the option screen appears (distinct from the
    # button press). Fires across all enabled sinks via EventLogger.
    logger.send("response_onset")

    # Clear anything left in the pad queue and zero its RT timer so r['time']
    # is measured from the option-screen onset.
    if pad_dev is not None:
        try:
            pad_dev.poll_for_response()
            pad_dev.clear_response_queue()
            _reset_pad_rt(pad_dev)
        except Exception as e:
            print(f"Response pad: pre-trial reset failed ({e}) -- keyboard fallback.")

    event.clearEvents()
    timer = core.Clock()

    while timer.getTime() < RESPONSE_DURATION:
        check_escape()

        # ---- Response pad (pyxid2): RT comes from the device timer ----
        if pad_dev is not None:
            try:
                pad_dev.poll_for_response()
                if pad_dev.has_response():
                    r = pad_dev.get_next_response()
                    pad_dev.clear_response_queue()
                    if r["pressed"] and r["key"] in PAD_KEY_TO_OPTION:
                        letter = PAD_KEY_TO_OPTION[r["key"]]
                        rt = r["time"] / 1000.0   # pyxid2 reports ms -> seconds
                        logger.send("response")
                        return letter, rt
            except Exception as e:
                print(f"Response pad: read failed ({e}) -- keyboard fallback.")

        # ---- Keyboard fallback: RT from the PsychoPy response clock ----
        keys = event.getKeys(keyList=list(OPTION_KEYS.values()) + ["escape"], timeStamped=timer)
        if keys:
            key, rt = keys[0]
            if key == "escape":
                core.quit()
            for letter, key_code in OPTION_KEYS.items():
                if key == key_code:
                    logger.send("response")
                    return letter, rt

    return None, None  # timeout


def run_feedback(win, stims, correct, logger):
    check_escape()
    draw_background(stims)
    if correct:
        stims["correct_feedback"].draw()
    else:
        stims["wrong_feedback"].draw()
    logger.send("feedback_correct" if correct else "feedback_wrong")
    win.flip()
    wait_with_escape(FEEDBACK_DURATION)


def run_iti(win, stims, trial, logger):
    """Jittered 'X' fixation between trials."""
    check_escape()
    draw_background(stims)
    stims["fixation"].draw()
    logger.send("iti_fixation")
    win.flip()
    wait_with_escape(trial["iti"])


def run_trial(win, stims, trial, logger, pad_dev):
    logger.send("trial_start")

    run_presentation(win, stims, trial, logger)

    response, rt = get_response(win, stims, trial, logger, pad_dev)
    correct = response == trial["correct_letter"]

    run_feedback(win, stims, correct, logger)
    run_iti(win, stims, trial, logger)

    logger.send("trial_end")

    return {"response": response, "rt": rt, "correct": correct,
            "timed_out": int(response is None)}


#############################
# INSTRUCTIONS / BREAKS
#############################

INSTRUCTIONS = (
    "In this task, you will see a math problem in the centre of the screen "
    "for 3 seconds.\n\n"
    "The problem will then disappear, and four answer options (A, B, C, D) "
    "will appear in its place.\n\n"
    "Press the number corresponding to the answer you believe is correct:\n"
    "1 = A     2 = B     3 = C     4 = D or 5 = could not solve \n\n"
    "You have 2 seconds to respond once the options appear. You will then see "
    "feedback, followed by a short pause before the next problem.\n\n"
    "Problems vary in difficulty and are mixed together in random order.\n\n"
    "Respond as quickly and accurately as you can.\n\n"
    "Press any button to begin."
)


def show_instructions(win, logger, pad_dev=None):
    logger.send("instructions")
    stim = visual.TextStim(win, text=INSTRUCTIONS, color="white", height=0.045, wrapWidth=1.5)
    while True:
            check_escape()
            stim.draw()
            win.flip()
    
            if pad_dev is not None:
                pad_dev.poll_for_response()
    
            if pad_dev is not None and pad_dev.has_response():
                r = pad_dev.get_next_response()
                pad_dev.clear_response_queue()
    
                if r["pressed"]:
                    break
    
        # Keyboard fallback
            if event.getKeys(keyList=["space"]):
                break
    
    core.wait(0.01)


def show_break(win, current, total, pad_dev=None):
    txt = visual.TextStim(
        win,
        text=f"Completed {current}/{total} trials.\n\nTake a short break.\n\nPress any button to continue.",
        color="white", height=0.05
    )
    #while True:
    #    txt.draw()
    #    win.flip()
    #    keys = event.getKeys(["space", "escape"])
    #    if "escape" in keys:
    #        core.quit()
    #    if "space" in keys:
    #        break

    while True:
        check_escape()
        txt.draw()
        win.flip()

        if pad_dev is not None:
            pad_dev.poll_for_response()

        if pad_dev is not None and pad_dev.has_response():
            r = pad_dev.get_next_response()
            pad_dev.clear_response_queue()

            if r["pressed"]:
                break

    # Keyboard fallback
        if event.getKeys(keyList=["space"]):
            break

    core.wait(0.01)
#############################
# OUTPUT FILE
#############################

def create_output_file(data_dir, exp_info):
    filename = os.path.join(
        data_dir, f"response_{exp_info['Participant ID']}_sess{exp_info['Session']}_{exp_info['date']}.csv"
    )
    f = open(filename, "w", newline="")
    writer = csv.writer(f)
    writer.writerow([
        "participant", "session", "trial", "level", "kind",
        "problem", "correct_answer",
        "option_A", "option_B", "option_C", "option_D", "option_E",
        "correct_letter", "correct_key",
        "response", "response_value", "accuracy", "rt", "timed_out", "iti",
    ])
    return f, writer


#############################
# MAIN EXPERIMENT
#############################

def run_experiment(win, exp_info, data_dir):
    stims = build_stimuli(win)

    events_filename = os.path.join(
        data_dir, f"events_{exp_info['Participant ID']}_sess{exp_info['Session']}_{exp_info['date']}.csv"
    )

    # --- Cedrus devices: ONE scan, both selected by product_id ---
    # (comment out these three lines + the discovery block above to fully disable)
    pad_dev, stim_dev = discover_xid_devices()
    stim_device = setup_stimtracker(stim_dev)
    pad_dev = setup_response_pad(pad_dev)

    # --- LSL marker outlet (comment out this line + the LSL block above to disable) ---
    lsl_outlet = init_lsl()

    # --- Pupil Core eye tracker (comment out these two lines + block above to disable) ---
    io, eyetracker = init_iohub(data_dir, win)

    logger = EventLogger(events_filename, stim_device=stim_device, io=io, lsl_outlet=lsl_outlet)
    outfile, writer = create_output_file(data_dir, exp_info)

    show_instructions(win, logger)

    run_calibration(eyetracker)   # no-op if eyetracker is None or pupillometry-only

    if eyetracker is not None:
        state = eyetracker.setRecordingState(True)
        print(f"Pupil Core: setRecordingState(True) -> recording state = {state}")

    logger.send("experiment_start")

    trial_blocks = build_all_trials()
    total_trials = sum(len(block) for block in trial_blocks)

    trial_counter = 0
    for block in trial_blocks:
        for trial in block:
            trial_counter += 1

            result = run_trial(win, stims, trial, logger, pad_dev)

            #response_value = (trial["options"][result["response"]]
                             # if result["response"] is not None else "")
            
            if result["response"] == "E":
                response_value = "Could not solve"
            elif result["response"] is not None:
                response_value = trial["options"][result["response"]]
            else:
                response_value = ""


            writer.writerow([
                exp_info["Participant ID"], exp_info["Session"], trial_counter,
                trial["level"], trial["kind"],
                trial["problem"], trial["correct_answer"],
                trial["options"]["A"], trial["options"]["B"],
                trial["options"]["C"], trial["options"]["D"],
                trial["correct_letter"], OPTION_KEYS[trial["correct_letter"]],
                result["response"], response_value, result["correct"],
                result["rt"], result["timed_out"], round(trial["iti"], 4),
            ])
            outfile.flush()

            if BREAK_EVERY_N_TRIALS and trial_counter % BREAK_EVERY_N_TRIALS == 0 \
                    and trial_counter != total_trials:
                show_break(win, trial_counter, total_trials)

    logger.send("experiment_end")

    if eyetracker is not None:
        state = eyetracker.setRecordingState(False)
        print(f"Pupil Core: setRecordingState(False) -> recording state = {state}")
    if io is not None:
        io.quit()   # flushes and finalizes the HDF5 file

    outfile.close()
    logger.close()


def main():
    exp_info = get_participant_info()
    data_dir = make_data_dir()

    win = visual.Window(fullscr=True, color="black", units="height")

    run_experiment(win, exp_info, data_dir)

    thanks = visual.TextStim(win, text="Thank you!", color="white", height=0.07)
    thanks.draw()
    win.flip()
    wait_with_escape(2.0)

    win.close()
    core.quit()


#############################
# RESPONSE PAD CODE CAPTURE UTILITY  (pyxid2)
# Run this standalone (python this_file.py --capture) to print the pyxid2
# 'key' number for each button press, so you can confirm/correct
# PAD_KEY_TO_OPTION above before real data collection.
#############################

def capture_response_pad_codes():
    if pyxid2 is None:
        print("pyxid2 not installed -- cannot capture pad codes.")
        return
    try:
        devices = pyxid2.get_xid_devices()
    except Exception as e:
        print(f"pyxid2 scan failed: {e}")
        return

    ripondas = [d for d in devices if getattr(d, "product_id", None) == RIPONDA_PRODUCT_ID]
    if not ripondas:
        print(f"No Riponda (product_id={RIPONDA_PRODUCT_ID!r}) found. "
              f"Devices seen: {devices}")
        return

    pad = ripondas[0]
    _reset_pad_rt(pad)
    pad.poll_for_response()
    pad.clear_response_queue()

    print("Press each response-pad button one at a time. Ctrl+C to stop.")
    print("Note the 'key' number for each physical button, then set "
          "PAD_KEY_TO_OPTION so each option (A/B/C/D) maps to the right button.\n")
    try:
        while True:
            pad.poll_for_response()
            if pad.has_response():
                r = pad.get_next_response()
                print(f"key={r['key']}  pressed={r['pressed']}  "
                      f"port={r.get('port')}  time={r['time']} ms")
                pad.clear_response_queue()
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    import sys
    if "--capture" in sys.argv:
        capture_response_pad_codes()
    else:
        main()
