"""Bench-only ntfy delivery. Network work never runs on the GUI thread."""
import json
import queue
import threading
import urllib.request
from datetime import datetime, timezone

TOPIC = 'EXSU620_TEAM4_NGTUBE'
ENDPOINT = 'https://ntfy.sh/' + TOPIC

class PhoneNotifications:
    def __init__(self, opener=None):
        self.opener = opener or urllib.request.urlopen
        self.events = queue.Queue()
        self.sent_samples = set()
        self.pending = set()

    def submit(self, sample_id, state, result, ph, test=False, reason=None):
        if not sample_id or sample_id in self.sent_samples:
            return None
        self.sent_samples.add(sample_id)
        stamp = datetime.now(timezone.utc).isoformat()
        data = {'sample_id': sample_id, 'topic': TOPIC, 'queued_utc': stamp,
                'test_notification': test, 'state': state, 'reason': reason,
                'result': result, 'pH_display': ph}
        if len(self.pending) >= 16:
            self.events.put(('PHONE_NOTIFICATION_FAILED', dict(data,error='Notification queue full')))
            return data
        self.pending.add(sample_id)
        body = ('BENCH DEMONSTRATION — NOT FOR PATIENT CARE\n'
                f'Sample ID: {sample_id}\nEstimated pH: {ph}\n'
                f'Result: {result}\nReason: {reason or state}\nResult queued UTC: {stamp}')
        technical_titles = {
            'NOT_SETTLED': 'Technical - not settled; REPEAT',
            'UNABLE_TO_SETTLE': 'Technical - unable to settle pH; REPEAT',
            'DRIFT_FAILURE': 'Technical - drifting; REPEAT',
            'STUCK_FAILURE': 'Technical - stuck; REPEAT',
            'SIGNAL_OUT_OF_RANGE': 'Technical - pH out of range; REPLUG cable',
            'ADC_FAULT': 'Technical - ADC fault; REPLUG cable',
            'CALIBRATION_INVALID': 'Technical - calibration unavailable or expired',
            'MISSING_TIMED_READINGS': 'Technical - missing readings; REPEAT',
            'INVALID_VALUE': 'Technical - invalid pH; REPEAT',
        }
        title = technical_titles.get(reason, 'Technical - see result') if state == 'TECHNICAL' else {
            'NORMAL': 'Normal - sample result',
            'ADVISORY': 'Advisory - escalate; REPEAT with new sample',
            'CRITICAL': 'Critical - DO NOT FEED',
        }.get(state, 'Sample result')
        def worker():
            try:
                request = urllib.request.Request(ENDPOINT,data=body.encode('utf-8'),method='POST',
                    headers={'Title':'EXSU620 - BENCH TEST' if test else 'EXSU620 - ' + title,
                             # All completed outcomes are equally eligible for phone alerts.
                             'Priority':'4',
                             'Content-Type':'text/plain; charset=utf-8'})
                with self.opener(request,timeout=8) as response:
                    if response.status != 200:
                        raise ValueError('ntfy HTTP status '+str(response.status))
                    reply=json.loads(response.read(16384).decode('utf-8'))
                    if not isinstance(reply,dict) or not reply.get('id'):
                        raise ValueError('ntfy response did not confirm a message ID')
                self.events.put(('PHONE_NOTIFICATION_ACCEPTED', dict(data,ntfy_message_id=reply['id'],
                    accepted_utc=datetime.now(timezone.utc).isoformat(),phone_delivery_confirmed=False)))
            except Exception as exc:
                # Do not retry automatically: a timed-out request might already be delivered.
                self.events.put(('PHONE_NOTIFICATION_FAILED',dict(data,error=str(exc),
                    completed_utc=datetime.now(timezone.utc).isoformat(),phone_delivery_confirmed=False)))
        threading.Thread(target=worker,daemon=True).start()
        return data

    def drain(self):
        result=[]
        while True:
            try:
                event=self.events.get_nowait()
            except queue.Empty:
                break
            self.pending.discard(event[1]['sample_id'])
            result.append(event)
        return result
