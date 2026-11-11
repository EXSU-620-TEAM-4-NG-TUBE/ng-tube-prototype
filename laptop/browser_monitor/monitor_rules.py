"""Shared bench display and alarm rules; no GUI dependencies."""
import time
import threading
import winsound

MUTE_SECONDS = 120
STALE_SECONDS = 5
RESULT_TEXT = {'NORMAL': 'Normal/ Gastric; safe to feed', 'ADVISORY': 'Advisory/escalate; REPEAT with new sample', 'CRITICAL': 'Critical/ Not gastric; DO NOT FEED', 'DRIFT_FAILURE': 'Technical/Drifting; REPEAT', 'STUCK_FAILURE': 'Technical/Stuck; REPEAT', 'UNABLE_TO_SETTLE': 'Technical/Unable to settle pH; REPEAT', 'SIGNAL_OUT_OF_RANGE': 'Technical/pH out of range; REPLUG the cable.', 'MISSING_TIMED_READINGS': 'Technical/Missing readings; REPEAT', 'CALIBRATION_INVALID': 'Technical/Calibration unavailable or expired', 'INVALID_VALUE': 'Technical/Invalid pH; REPEAT'}

def visible_result(current, requested, connected, latched=False):
    if not connected:
        return ('RECONNECTING', 'Connection lost — reconnect USB', '—')
    if not requested:
        return ('READY', 'Ready — start a new sample', '—')
    if current and current.get('reason') == 'SAMPLE_STOPPED':
        return ('STOPPED', 'Test stopped — select NEW SAMPLE', '—')
    if not current or (current.get('sample_elapsed_ms') or 0) < 21000:
        return ('MEASURING', 'Measuring', '—')
    reason = current.get('reason')
    state = current.get('state', 'TECHNICAL')
    valid = reason == 'VALID' and current.get('calibration_valid') is True and (current.get('settled') is True) and (state in ('NORMAL', 'ADVISORY', 'CRITICAL'))
    ph = current.get('pH_estimate')
    if ph is None and current.get('sample_stopped'):
        ph = (current.get('last_measurement') or {}).get('pH_estimate')
    ph_text = format(ph, '.1f') if isinstance(ph, (int, float)) and 0 <= ph <= 14 else '—'
    if valid:
        if current.get('verdict') == 'PROBE_RESPONSE_DETECTED':
            return ('NORMAL', 'Probe response detected — check complete', ph_text)
        # The main result describes this sample; historical alarms are separate.
        return (state, RESULT_TEXT[state], ph_text)
    return ('TECHNICAL', RESULT_TEXT.get(reason, 'Technical/Unable to settle pH; REPEAT'), ph_text)

def countdown_text(state, current, now, last_rx):
    if state == 'MEASURING':
        if current is None or current.get('sample_elapsed_ms') is None:
            return '21 s — waiting for device to start'
        elapsed_ms = current['sample_elapsed_ms'] + max(0, now - last_rx) * 1000
        remaining = max(0, int((21000 - elapsed_ms + 999) // 1000))
        return f'{remaining} s until result' if remaining else '0 s — waiting for result'
    if state == 'STOPPED':
        return 'Timer stopped'
    if state in ('READY', 'RECONNECTING'):
        return 'Result in 21 seconds after starting' if state == 'READY' else 'Timer paused — device disconnected'
    return '0 s — result ready'

class Alarm:

    def __init__(self):
        self.latched = False
        self.acknowledged = False
        self.muted_until = 0.0

    def update(self, reading):
        trustworthy = bool(reading and reading.get('settled') is True and (reading.get('calibration_valid') is True) and (reading.get('reason') == 'VALID') and (reading.get('state') in ('NORMAL', 'ADVISORY', 'CRITICAL')))
        if not trustworthy:
            return 'TECHNICAL'
        state = reading['state']
        if state == 'CRITICAL' and (not self.latched):
            self.latched = True
            self.acknowledged = False
            self.muted_until = 0.0
        if self.latched and self.acknowledged and (state == 'NORMAL'):
            self.latched = False
        return 'CRITICAL' if self.latched else state

    def acknowledge(self, now):
        self.acknowledged = True
        self.muted_until = now + MUTE_SECONDS

class SampleGate:
    """Do not display an old reading as a newly requested sample."""

    def __init__(self):
        self.requested = None
        self.labels = {}
        self.confirmed = False
        self.request_time = None

    def request(self, sample_id, label, now):
        self.requested = sample_id
        self.labels[sample_id] = label
        self.confirmed = False
        self.request_time = now

    def matches(self, reading):
        return bool(self.requested and reading and (reading.get('sample_id') == self.requested))

class Audio:

    def __init__(self):
        self.version = 0

    def stop(self):
        self.version += 1

    def play(self, state):
        self.stop()
        version = self.version
        count, frequency, duration = {'NORMAL': (0, 1000, 100), 'ADVISORY': (3, 800, 150), 'CRITICAL': (10, 1200, 150), 'TECHNICAL': (1, 1500, 100)}[state]

        def worker():
            try:
                for _ in range(count):
                    if self.version != version:
                        return
                    winsound.Beep(frequency, duration)
                    time.sleep(0.15)
            except RuntimeError as exc:
                print('AUDIO ERROR:', exc, flush=True)
        threading.Thread(target=worker, daemon=True).start()
