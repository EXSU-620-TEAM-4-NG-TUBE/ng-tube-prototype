"""EXSU620 bench monitor: laptop-only latch/ACK; requires pyserial.
Physical button stops the sample. Laptop ACK remains silence-only.
"""
import json
import sqlite3
import threading
import time
import uuid
import winsound
import tkinter as tk
from tkinter import simpledialog, messagebox
from datetime import datetime, timezone
from pathlib import Path
import serial
from serial.tools import list_ports
from phone_notifications import PhoneNotifications

PORT = 'COM8'
MUTE_SECONDS = 120
STALE_SECONDS = 5


RESULT_TEXT = {
    'NORMAL': 'Normal/ Gastric; safe to feed',
    'ADVISORY': 'Advisory/ Escalate; read new sample',
    'CRITICAL': 'Critical/ Not gastric; DO NOT FEED',
    'DRIFT_FAILURE': 'Technical/Drifting; REPEAT',
    'STUCK_FAILURE': 'Technical/Stuck; REPEAT',
    'UNABLE_TO_SETTLE': 'Technical/Unable to settle pH; REPEAT',
    'SIGNAL_OUT_OF_RANGE': 'Technical/pH out of range; REPLUG the cable.',
    'MISSING_TIMED_READINGS': 'Technical/Missing readings; REPEAT',
    'CALIBRATION_INVALID': 'Technical/Calibration unavailable or expired',
    'INVALID_VALUE': 'Technical/Invalid pH; REPEAT',
}

def visible_result(current, requested, connected, latched=False):
    if not connected:
        return 'RECONNECTING', 'Connection lost — reconnect USB', '—'
    if not requested:
        return 'READY', 'Ready — start a new sample', '—'
    if current and current.get('reason') == 'SAMPLE_STOPPED':
        return 'STOPPED', 'Test stopped — select NEW SAMPLE', '—'
    if not current or (current.get('sample_elapsed_ms') or 0) < 21000:
        return 'MEASURING', 'Measuring', '—'
    reason = current.get('reason')
    state = current.get('state', 'TECHNICAL')
    valid = (reason == 'VALID' and current.get('calibration_valid') is True
             and current.get('settled') is True and state in ('NORMAL','ADVISORY','CRITICAL'))
    ph = current.get('pH_estimate')
    if ph is None and current.get('sample_stopped'):
        ph = (current.get('last_measurement') or {}).get('pH_estimate')
    ph_text = format(ph, '.1f') if isinstance(ph, (int,float)) and 0 <= ph <= 14 else '—'
    if valid:
        if current.get('verdict') == 'PROBE_RESPONSE_DETECTED':
            return 'NORMAL', 'Probe response detected — check complete', ph_text
        if latched and state != 'CRITICAL':
            return 'CRITICAL', 'Previous critical alarm — ACKNOWLEDGE', ph_text
        return state, RESULT_TEXT[state], ph_text
    return 'TECHNICAL', RESULT_TEXT.get(reason, 'Technical/Unable to settle pH; REPEAT'), ph_text

def countdown_text(state, current, now, last_rx):
    if state == 'MEASURING':
        if current is None or current.get('sample_elapsed_ms') is None:
            return '21 s — waiting for device to start'
        elapsed_ms = current['sample_elapsed_ms'] + max(0, now-last_rx)*1000
        remaining = max(0, int((21000-elapsed_ms+999)//1000))
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
        trustworthy = bool(reading and reading.get('settled') is True
                           and reading.get('calibration_valid') is True
                           and reading.get('reason') == 'VALID'
                           and reading.get('state') in
                           ('NORMAL', 'ADVISORY', 'CRITICAL'))
        if not trustworthy:
            return 'TECHNICAL'
        state = reading['state']
        if state == 'CRITICAL' and not self.latched:
            self.latched = True
            self.acknowledged = False
            self.muted_until = 0.0
        if self.latched and self.acknowledged and state == 'NORMAL':
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
        return bool(self.requested and reading and
                    reading.get('sample_id') == self.requested)

class Audio:
    def __init__(self):
        self.version = 0

    def stop(self):
        self.version += 1

    def play(self, state):
        self.stop()
        version = self.version
        count, frequency, duration = {
            'NORMAL': (0, 1000, 100),
            'ADVISORY': (3, 800, 150),
            'CRITICAL': (10, 1200, 150),
            'TECHNICAL': (1, 1500, 100),
        }[state]

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

def main():
    operator = input('Operator initials: ').strip()
    sample = input('Session/test label: ').strip()
    if not operator or not sample:
        raise ValueError('Both labels are required.')
    folder = Path(__file__).resolve().parent / 'bench_logs'
    folder.mkdir(exist_ok=True)
    run_id = uuid.uuid4().hex
    db = sqlite3.connect(folder / 'bench.sqlite3')
    db.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY, received_utc TEXT, run_id TEXT,
        operator TEXT, sample TEXT, kind TEXT, payload TEXT)''')
    logfile = (folder / (run_id + '.jsonl')).open('a', encoding='utf-8')

    samples = SampleGate()

    def save(kind, payload):
        stamp = datetime.now(timezone.utc).isoformat()
        event_sample = samples.labels.get(payload.get('sample_id'), sample) if isinstance(payload, dict) else sample
        event = dict(received_utc=stamp, run_id=run_id, operator=operator,
                     sample=event_sample, kind=kind, payload=payload)
        logfile.write(json.dumps(event) + '\n')
        logfile.flush()
        db.execute('''INSERT INTO events
            (received_utc,run_id,operator,sample,kind,payload)
            VALUES (?,?,?,?,?,?)''',
            (stamp, run_id, operator, event_sample, kind, json.dumps(payload)))
        db.commit()

    root = tk.Tk()
    root.title('EXSU620 pH monitor — BENCH DEMONSTRATION')
    root.geometry('960x760')
    root.minsize(760, 650)
    root.configure(bg='#f3f6f8')
    tk.Label(root, text='BENCH DEMONSTRATION — not for patient feeding decisions',
             font=('Arial', 12, 'bold'), bg='#f3f6f8').pack(pady=(12,6))
    input_label = tk.Label(root, text='Input: waiting for sensor', font=('Arial', 13), bg='#f3f6f8')
    input_label.pack()
    tk.Label(root, text='ESTIMATED pH', font=('Arial',12,'bold'), bg='#f3f6f8').pack(pady=(14,0))
    ph_label = tk.Label(root, text='—', font=('Arial',54,'bold'), bg='#f3f6f8')
    ph_label.pack()
    timer_label = tk.Label(root, text='Result in 21 seconds after starting',
                          font=('Arial',20,'bold'), fg='#144d70', bg='#f3f6f8')
    timer_label.pack(pady=(0,8))
    tk.Label(root, text='VERDICT', font=('Arial',12,'bold'), bg='#f3f6f8').pack()
    display = tk.Label(root, text='Ready — start a new sample', font=('Arial',24,'bold'),
                       bg='#e5eaf0', padx=18,pady=20,wraplength=880)
    display.pack(fill='x',padx=24,pady=10)
    more = tk.Toplevel(root,bg='#e5eaf0')
    more.title('More info — bench monitor')
    more.geometry('900x520')
    more.withdraw()
    more.protocol('WM_DELETE_WINDOW', more.withdraw)
    details = tk.Label(more,text='',font=('Arial',11),justify='left',wraplength=880,bg='#e5eaf0')
    details.pack(fill='x',padx=12,pady=8)
    latch_label = tk.Label(more,text='',font=('Arial',11),bg='#e5eaf0')
    latch_label.pack(pady=3)
    timing_label = tk.Label(more,text='',font=('Arial',11),bg='#e5eaf0')
    timing_label.pack(pady=3)
    tk.Label(more,text='Physical ACK: stop sample + silence. Screen ACK: silence only.\n'
        'Thresholds: ≤5.5 gastric; >5.5–6.0 advisory; >6.0 critical. Calibration interval: seven days.',
        font=('Arial',10),bg='#e5eaf0').pack(pady=5)
    alarm, audio = Alarm(), Audio()
    phone = PhoneNotifications()
    phone_status = tk.Label(more,text='Phone notifications: configured for EXSU620_TEAM4_NGTUBE',
                           font=('Arial',10),bg='#e5eaf0',wraplength=850)
    phone_status.pack(pady=5)

    def test_phone():
        event = phone.submit('phone-test-'+uuid.uuid4().hex,'NORMAL',
            'Connection test — no sensor measurement', 'not applicable',test=True)
        if event:
            save('PHONE_NOTIFICATION_QUEUED',event)
            phone_status.config(text='Sending test notification…')
    tk.Button(more,text='SEND TEST PHONE NOTIFICATION',command=test_phone,
              font=('Arial',11)).pack(pady=4)
    reading = None
    previous_displayed_ph = None
    last_rx = time.monotonic()
    link_error = None
    last_snapshot = None
    last_audible = None
    next_reminder = 0.0
    running = True
    timestamp_prompted = set()
    last_clock_sync = 0.0
    reconnect_at = 0.0
    device_serial = None
    connected_once = False
    last_device_elapsed = None

    sample_text = tk.StringVar(value='Sample 1')
    tk.Label(root, text='Sample label — no patient identifiers').pack()
    tk.Entry(root, textvariable=sample_text, width=50, font=('Arial',16)).pack(pady=6)
    sample_status = tk.Label(root, text='Select a new sample before reading a verdict.', wraplength=740)
    sample_status.pack(pady=4)

    def new_sample(response_check=False, baseline=None, buffer_details=None):
        nonlocal link_error
        label = sample_text.get().strip()
        if not label or len(label) > 100:
            sample_status.config(text='Enter a sample label of 1–100 characters.')
            return
        if port is None or link_error is not None:
            sample_status.config(text='Waiting for automatic USB reconnection.')
            return
        alarm.muted_until = 0.0  # New samples must be audible again.
        new_id = uuid.uuid4().hex
        samples.request(new_id, label, time.monotonic())
        # Clear the visible current verdict before waiting for USB confirmation.
        display.config(text='Measuring', bg='#e5eaf0')
        ph_label.config(text='—')
        timer_label.config(text='21 s until result')
        details.config(text='New sample requested. Current verdict: WITHHELD')
        save('NEW_SAMPLE_REQUEST', {'sample_id': new_id, 'label': label,
                                   'critical_latched': alarm.latched,
                                   'known_buffer_changed': response_check, 'baseline_ph': baseline,
                                   'test_mode': 'PROBE_RESPONSE_CHECK' if response_check else 'ROUTINE_SAMPLE',
                                   'buffer_details': buffer_details,
                                   'previous_device_elapsed_ms': reading.get('elapsed_ms') if reading else None})
        try:
            command = json.dumps({'command': 'NEW_SAMPLE', 'sample_id': new_id,
                                  'known_buffer_changed': response_check, 'baseline_ph': baseline}) + '\n'
            encoded = command.encode('ascii')
            if port.write(encoded) != len(encoded):
                raise serial.SerialException('Incomplete command write')
        except serial.SerialException as exc:
            lost_connection(str(exc))

    tk.Button(root, text='NEW SAMPLE', command=new_sample,
              font=('Arial', 18, 'bold'), bg='#144d70', fg='white', padx=32, pady=12).pack(pady=7)

    def acknowledge(source='LAPTOP_BUTTON', device_event=None):
        now = time.monotonic()
        alarm.acknowledge(now)
        audio.stop()
        save('ACK', {'operator': operator, 'mute_seconds': MUTE_SECONDS,
                     'source': source, 'device_event': device_event,
                     'sample_id': device_event.get('sample_id') if device_event else samples.requested,
                     'critical_latched': alarm.latched,
                     'device_elapsed_ms': reading.get('elapsed_ms') if reading else None})

    button = tk.Button(root, text='ACKNOWLEDGE / SILENCE',
                       command=acknowledge, font=('Arial', 17, 'bold'), padx=24, pady=10)
    button.pack(pady=8)
    def toggle_more():
        if more.state() != 'withdrawn':
            more.withdraw()
        else:
            more.deiconify()
            more.lift()
    more_button = tk.Button(root,text='More info ▾',command=toggle_more,font=('Arial',12))
    more_button.pack(pady=4)

    def check_probe_response():
        # The source must be the currently measured known buffer, not an arbitrary old sample.
        if (not samples.matches(reading) or reading.get('reason') != 'VALID'
                or reading.get('settled') is not True or reading.get('calibration_valid') is not True
                or port is None or time.monotonic()-last_rx > STALE_SECONDS):
            messagebox.showinfo('Measure baseline buffer first',
                'Use NEW SAMPLE to measure a known buffer first. Wait for a valid result, '
                'then select CHECK PROBE RESPONSE while that test is still running.', parent=root)
            return
        baseline = reading.get('pH_estimate')
        if not isinstance(baseline,(int,float)) or not 0 <= baseline <= 14:
            return
        baseline_id = reading.get('sample_id')
        source_ph = simpledialog.askfloat('Baseline buffer',
            'Nominal pH of the known buffer currently holding the probe:', minvalue=0,maxvalue=14,parent=root)
        if source_ph is None:
            return
        target_ph = simpledialog.askfloat('Different reference buffer',
            'Nominal pH of the different known buffer you will move to:', minvalue=0,maxvalue=14,parent=root)
        if target_ph is None:
            return
        if abs(target_ph-source_ph) <= 0.40:
            messagebox.showinfo('Use separated buffers',
                'For this response challenge, use known buffers separated by more than 0.40 pH, '
                'for example pH 4 and pH 7.',parent=root)
            return
        if not messagebox.askokcancel('Move probe to the second buffer',
            f'Baseline recorded: {baseline:.3f} pH.\nRinse the probe and move it from the pH {source_ph:g} '
            f'buffer into the pH {target_ph:g} buffer.\nClick OK immediately after immersion to start '
            'the 21-second response check.\nThis checks response, not calibration accuracy.',parent=root):
            return
        sample_text.set(f'Probe response {source_ph:g} to {target_ph:g}')
        new_sample(True, baseline, {'source_nominal_ph':source_ph,'target_nominal_ph':target_ph,
                                   'baseline_sample_id':baseline_id})

    tk.Button(more,text='CHECK PROBE RESPONSE',command=check_probe_response,
              font=('Arial',12,'bold'),padx=12,pady=8).pack(pady=8)
    tk.Label(more,text='Use only with a deliberate move between different known buffers.\n'
             'Routine NEW SAMPLE does not test for stuck response.',bg='#e5eaf0',font=('Arial',10)).pack()

    def close():
        nonlocal running
        running = False
    root.protocol('WM_DELETE_WINDOW', close)
    port = None
    pending = b''
    print('Run:', run_id, '\nFiles:', folder, flush=True)
    save('RUN_START', {'port': PORT, 'version': 'laptop_monitor_response_v8',
                      'mute_seconds': MUTE_SECONDS, 'stale_seconds': STALE_SECONDS})
    def lost_connection(error):
        nonlocal port, pending, reading, link_error, last_audible, last_device_elapsed, previous_displayed_ph
        if port is not None:
            try:
                port.close()
            except serial.SerialException:
                pass
        port = None
        pending = b''
        reading = None
        previous_displayed_ph = None
        last_device_elapsed = None
        if samples.requested:
            save('SAMPLE_INTERRUPTED', {'sample_id':samples.requested,'error':error})
        samples.requested = None
        samples.confirmed = False
        audio.stop()
        last_audible = None
        if link_error != error:
            save('LINK_ERROR', {'error':error})
        link_error = error

    try:
        while running:
            root.update()
            for kind, payload in phone.drain():
                save(kind,payload)
                phone_status.config(text=('ntfy accepted the message — check your phone.'
                    if kind == 'PHONE_NOTIFICATION_ACCEPTED' else 'Phone notification failed: '+payload.get('error','unknown')))
            if not running:
                break
            if port is None and time.monotonic() >= reconnect_at:
                reconnect_at = time.monotonic()+2.0
                target = PORT
                if device_serial:
                    matches = [p.device for p in list_ports.comports() if p.serial_number == device_serial]
                    target = matches[0] if len(matches)==1 else None
                if target:
                    try:
                        port = serial.Serial(target,115200,timeout=0.02,write_timeout=0.5)
                        info = next((p for p in list_ports.comports() if p.device==target),None)
                        if info and info.serial_number:
                            device_serial = info.serial_number
                        pending = b''
                        link_error = None
                        last_rx = time.monotonic()
                        last_clock_sync = 0.0
                        connected_once = True
                        save('LINK_CONNECTED',{'port':target,'device_serial':device_serial})
                    except serial.SerialException as exc:
                        lost_connection(str(exc))
            if port is not None:
                try:
                    if time.monotonic() - last_clock_sync >= 60:
                        command = json.dumps({'command':'TIME_SYNC', 'unix_time':int(time.time())})+'\n'
                        if port.write(command.encode('ascii')) != len(command):
                            raise serial.SerialException('Incomplete clock write')
                        last_clock_sync = time.monotonic()
                    pending += port.read(max(1, min(port.in_waiting, 4096)))
                except serial.SerialException as exc:
                    lost_connection(str(exc))
            else:
                time.sleep(0.05)
            if len(pending) > 65536:
                save('PARSE_ERROR', {'error': 'oversized buffer'})
                pending = b''
            while b'\n' in pending:
                line, pending = pending.split(b'\n', 1)
                text = line.decode('utf-8', errors='replace').strip()
                if not text:
                    continue
                if not text.startswith('{'):
                    save('DEVICE_TEXT', text)
                    continue
                try:
                    item = json.loads(text)
                    if isinstance(item, dict) and item.get('event_type') == 'ACK_PRESS':
                        if not isinstance(item.get('press_id'), int) or not isinstance(item.get('elapsed_ms'), int):
                            raise ValueError('invalid button event')
                        acknowledge(source='PHYSICAL_BUTTON', device_event=item)
                        continue
                    if isinstance(item, dict) and item.get('event_type') in ('NEW_SAMPLE_STARTED', 'COMMAND_ERROR', 'SAMPLE_STOPPED', 'SETTLING_TIMEOUT', 'DRIFT_FAILURE', 'FIXED_WINDOW_RESULT', 'CALIBRATION_TIME_REGISTERED'):
                        save(item['event_type'], item)
                        if item['event_type'] == 'SAMPLE_STOPPED' and samples.matches(item):
                            audio.stop()
                        continue
                    required = ('state','reason','elapsed_ms','pH_estimate',
                                'settled','calibration_valid','verdict')
                    if not isinstance(item, dict) or any(k not in item for k in required):
                        raise ValueError('missing required fields')
                    if item['state'] not in ('NORMAL','ADVISORY','CRITICAL','TECHNICAL'):
                        raise ValueError('unknown state')
                except (ValueError, TypeError) as exc:
                    save('PARSE_ERROR', {'text': text, 'error': str(exc)})
                    continue
                cal_id = item.get('calibration_id')
                if (item.get('firmware_version') in ('sample_weekly_v6','sample_simple_v7','sample_response_v8')
                        and item.get('calibrated_at_unix') is None
                        and not item.get('calibration_load_error')
                        and cal_id not in timestamp_prompted):
                    timestamp_prompted.add(cal_id)
                    value = simpledialog.askstring('Record calibration completion time',
                        'Enter the ACTUAL completion date/time of calibration '+str(cal_id)+
                        ' in UTC (YYYY-MM-DD HH:MM:SS).\n'
                        'Do not enter today unless calibration was completed today.\n'
                        'Current UTC: '+datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), parent=root)
                    if value:
                        try:
                            stamp = int(datetime.strptime(value.strip(), '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp())
                            now_epoch = int(time.time())
                            if not 1700000000 <= stamp <= now_epoch:
                                raise ValueError('Completion time must not be in the future.')
                            command = json.dumps({'command':'REGISTER_CAL_TIME','unix_time':now_epoch,
                                'calibrated_at_unix':stamp,'calibration_id':cal_id})+'\n'
                            if port is None or port.write(command.encode('ascii')) != len(command):
                                raise serial.SerialException('Incomplete calibration time write')
                            save('CALIBRATION_TIME_REQUEST', {'calibration_id':cal_id,'calibrated_at_unix':stamp})
                        except (ValueError, serial.SerialException) as exc:
                            messagebox.showerror('Time not registered', str(exc), parent=root)
                if (last_device_elapsed is not None and item['elapsed_ms'] < last_device_elapsed):
                    if samples.requested:
                        save('SAMPLE_INTERRUPTED', {'sample_id':samples.requested,'error':'DEVICE_RESTART'})
                    samples.requested = None
                    samples.confirmed = False
                    last_clock_sync = 0.0
                    previous_displayed_ph = None
                    audio.stop()
                last_device_elapsed = item['elapsed_ms']
                reading = item
                last_rx = time.monotonic()
                save('READING', item)
                # Old buffered normal records must not clear a latch during a new request.
                if samples.matches(item):
                    if not samples.confirmed:
                        samples.confirmed = True
                        save('NEW_SAMPLE_CONFIRMED', {'sample_id': samples.requested,
                             'device_elapsed_ms': item['elapsed_ms']})
                    if (item.get('sample_elapsed_ms') or 0) >= 21000:
                        alarm.update(item)
                elif item['state'] == 'CRITICAL' and (item.get('sample_elapsed_ms') or 0) >= 21000:
                    alarm.update(item)
            now = time.monotonic()
            if port is not None and now-last_rx > STALE_SECONDS:
                lost_connection('No device heartbeat; reconnecting')
            stale = link_error is not None or now - last_rx > STALE_SECONDS
            current = reading if not stale and samples.matches(reading) else None
            signal_fault = bool(current and current.get('reason') == 'SIGNAL_OUT_OF_RANGE')
            missing_timed = bool(current and current.get('reason') == 'MISSING_TIMED_READINGS')
            drifting = bool(current and current.get('reason') == 'DRIFT_FAILURE')
            timed_out = bool(current and current.get('reason') == 'UNABLE_TO_SETTLE')
            stopped = bool(current and current.get('reason') == 'SAMPLE_STOPPED')
            if current and (current.get('sample_elapsed_ms') or 0) >= 21000:
                alarm.update(current)
            state, result_text, visible_ph = visible_result(current, samples.requested,
                port is not None and not stale, alarm.latched)
            if state == 'RECONNECTING' and not connected_once:
                result_text = 'Connecting to Pico — no result'
            if (current and (current.get('sample_elapsed_ms') or 0) >= 21000
                    and state in ('NORMAL','ADVISORY','CRITICAL','TECHNICAL')
                    and current.get('reason') not in ('MEASURING','NOT_SETTLED','NO_SAMPLE','SAMPLE_STOPPED')):
                event = phone.submit(samples.requested,state,result_text,visible_ph)
                if event:
                    save('PHONE_NOTIFICATION_QUEUED',event)
                    phone_status.config(text='Sending sample result to phone…')
            reason = ('LINK_ERROR' if link_error else 'LINK_STALE') if stale else (
                current['reason'] if current else (
                    'WAITING_NEW_SAMPLE' if samples.requested else 'NO_SAMPLE_SELECTED'))
            snapshot = (state, reason, alarm.latched, alarm.acknowledged)
            if snapshot != last_snapshot:
                save('ALARM_TRANSITION', dict(state=state, reason=reason,
                     critical_latched=alarm.latched, acknowledged=alarm.acknowledged,
                     sample_id=samples.requested))
                last_snapshot = snapshot
            muted = state in ('READY','MEASURING','RECONNECTING','STOPPED') or now < alarm.muted_until
            audible = state if not muted else 'MUTED'
            if audible != last_audible:
                audio.stop()
                if audible != 'MUTED':
                    audio.play(state)
                    next_reminder = now + MUTE_SECONDS
                last_audible = audible
            elif not muted and state != 'NORMAL' and now >= next_reminder:
                audio.play(state)
                next_reminder = now + MUTE_SECONDS
            color = {'NORMAL':'#bce8c8','ADVISORY':'#ffe1a0','CRITICAL':'#ffb6b6',
                     'TECHNICAL':'#b8e5ec'}.get(state,'#e5eaf0')
            display.config(text=result_text,bg=color)
            ph_label.config(text=visible_ph)
            timer_label.config(text=countdown_text(state,current,now,last_rx))
            if current and visible_ph != '—' and isinstance(current.get('pH_estimate'),(int,float)):
                previous_displayed_ph = current['pH_estimate']
            input_label.config(text='Input: '+str((reading or {}).get('input_source','waiting for sensor')))
            verdict = current['verdict'] if current and reason == 'VALID' else None
            if alarm.latched:
                verdict_text = 'WITHHELD — critical alarm remains latched'
            else:
                verdict_text = str(verdict) if verdict is not None else 'WITHHELD'
            ph_text = format(current['pH_estimate'], '.1f') if current and isinstance(current.get('pH_estimate'), (int, float)) else 'unavailable'
            source = current.get('input_source', 'UNSPECIFIED') if current else 'unavailable'
            age = str(current['elapsed_ms']) if current else 'unavailable'
            details.config(text=f'Input: {source} | Device elapsed: {age} ms\n'
                           f'Estimated pH: {ph_text} (not validated)\n'
                           f'Reason: {reason}\nCurrent verdict: {verdict_text}')
            if signal_fault:
                history = current.get('last_measurement') or {}
                fault_raw = current.get('raw')
                if fault_raw is None:
                    fault_raw = history.get('raw')
                details.config(text=(f'ADC: {fault_raw} | Allowed range: 500–45000 inclusive.\n'
                    'No verdict. Check the pH sensor cable connections with power disconnected.\n'
                    'After reconnecting, restore the bench session if needed and select NEW SAMPLE.'))
            if timed_out:
                details.config(text='No verdict. The sample did not settle by the 21-second decision.\nMeasurement stopped. Prepare the sample and click NEW SAMPLE to repeat.')
            if missing_timed:
                details.config(text='No verdict. Required timed readings were missed or late.\nClick NEW SAMPLE to repeat.')
            if drifting:
                drift = current.get('drift_check') or {}
                details.config(text=(
                    'No verdict. Measurement stopped. Click NEW SAMPLE to repeat.\n'
                    f'First-three mean: {drift.get("first_three_mean_ph")}\n'
                    f'Last-three mean: {drift.get("last_three_mean_ph")}\n'
                    f'Difference: {drift.get("difference_ph")} pH\n'
                    'Review the saved trace: gradual movement or an isolated jump.'))
            if current and current.get('reason') == 'STUCK_FAILURE':
                details.config(text='Signal remained within ±0.10 pH of the previous displayed value\nfor at least 15 seconds despite a confirmed buffer change.\nNo verdict. Repeat after checking the probe and connections.')
            if stopped:
                history = current.get('last_measurement') or {}
                details.config(text=(
                    'Test ended. No current verdict. Click NEW SAMPLE to restart.\n'
                    f'Historical last pH: {history.get("pH_estimate", "unavailable")}\n'
                    f'Historical state: {history.get("state", "unavailable")} | '
                    f'Last verdict: {history.get("verdict")}'))
            label = samples.labels.get(samples.requested, 'not selected')
            sample_status.config(text=f'Sample: {label}\nID: {samples.requested or "—"}')
            timing_label.config(text=(f'Sample elapsed: {(current or {}).get("sample_elapsed_ms")} ms | '
                f'Calibration remaining: {((reading or {}).get("calibration_remaining_ms") or 0)/3600000:.2f} hours'))
            if current:
                stuck = current.get('stuck_check') or {}
                details.config(text=details.cget('text')+'\nStuck check: '+str(stuck.get('reason','pending'))+
                    ' | Baseline pH: '+str(stuck.get('baseline_ph')))
            remaining = 'until NEW SAMPLE' if stopped else str(max(0, int(alarm.muted_until - now)))
            latch_label.config(text=f'Critical latch: {alarm.latched} | '
                               f'Acknowledged: {alarm.acknowledged} | '
                               f'Audio mute remaining: {remaining} s')
            button.config(state='normal' if state not in ('NORMAL', 'STOPPED', 'READY', 'MEASURING','RECONNECTING') else 'disabled')
    except KeyboardInterrupt:
        pass
    finally:
        audio.stop()
        for kind,payload in phone.drain():
            save(kind,payload)
        for pending_id in phone.pending:
            save('PHONE_NOTIFICATION_UNCONFIRMED_AT_CLOSE',{'sample_id':pending_id,
                'note':'Monitor closed before network completion was logged; delivery may still occur.'})
        if port is not None:
            port.close()
        save('RUN_STOP', {'reason': 'monitor closed'})
        logfile.close()
        db.close()
        root.destroy()
        print('Saved:', folder / (run_id + '.jsonl'), flush=True)

if __name__ == '__main__':
    main()
