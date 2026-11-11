"""Local API/engine regression checks; no physical USB or network notification."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "software" / "browser_monitor"))

from service import Engine, make_server

class Audio:
    def stop(self):pass
    def play(self,state):pass
class Phone:
    pending=set()
    def drain(self):return []
    def submit(self,*a,**k):return None
class RecordingPhone(Phone):
    def __init__(self):self.calls=[];self.seen=set()
    def submit(self,sample_id,state,result,ph,**kw):
        if sample_id in self.seen:return None
        self.seen.add(sample_id);self.calls.append((sample_id,state,result,ph,kw))
        return dict(sample_id=sample_id,state=state,result=result,reason=kw.get('reason'))
class Port:
    def __init__(self):self.writes=[]
    def write(self,b):self.writes.append(json.loads(b));return len(b)
    def close(self):pass

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.e=Engine(folder=self.tmp.name,audio=Audio(),phone=Phone())
        self.e.open_audit()
    def tearDown(self):
        self.e.db.close();self.e.logfile.close();self.tmp.cleanup()
    def reading(self,ms,**updates):
        r=dict(state='NORMAL',reason='VALID',elapsed_ms=ms+1000,sample_elapsed_ms=ms,
          sample_id=self.e.samples.requested,pH_estimate=4.0,settled=True,calibration_valid=True,verdict='GASTRIC_RANGE')
        r.update(updates);self.e.consume(r);self.e.publish()
    def test_sample_lifecycle(self):
        self.e.publish();self.assertEqual(self.e.snapshot['state'],'READY')
        self.e.act('session',dict(operator='TEST',label='mock'))
        self.e.port=Port();self.e.last_rx=time.monotonic()
        self.e.act('samples/new',{'label':'buffer 4'})
        self.reading(20000);self.assertEqual(self.e.snapshot['state'],'MEASURING');self.assertEqual(self.e.snapshot['ph'],chr(0x2014))
        self.reading(21000);self.assertEqual(self.e.snapshot['state'],'NORMAL')
        self.reading(22000,state='CRITICAL',pH_estimate=7,verdict='DO_NOT_FEED')
        self.assertTrue(self.e.alarm.latched)
        self.e.act('ack',{});self.assertTrue(self.e.alarm.acknowledged)
        self.reading(23000,state='TECHNICAL',reason='SAMPLE_STOPPED',pH_estimate=None,verdict=None,settled=False)
        self.assertEqual(self.e.snapshot['state'],'STOPPED')
        self.e.disconnect('test unplug');self.e.publish()
        self.assertIsNone(self.e.samples.requested);self.assertEqual(self.e.snapshot['ph'],chr(0x2014))
        self.e.port=Port();self.e.last_rx=time.monotonic();self.e.publish()
        self.assertEqual(self.e.snapshot['state'],'READY')
        self.e.act('samples/new',{'label':'new buffer'})
        self.assertFalse(self.e.port.writes[-1]['known_buffer_changed'])
    def test_response_and_audit(self):
        self.e.act('session',dict(operator='TEST',label='mock',phone_consent=True))
        self.e.port=Port();self.e.last_rx=time.monotonic();self.e.act('samples/new',{'label':'baseline'})
        self.reading(21000)
        prepared=self.e.act('probe-response/prepare',{})
        self.e.act('probe-response/start',dict(token=prepared['token'],source_ph=4,target_ph=7,transfer_confirmed=True))
        self.assertTrue(self.e.port.writes[-1]['known_buffer_changed'])
        self.assertEqual(self.e.port.writes[-1]['baseline_ph'],4)
        self.assertTrue(any(x['kind']=='PHONE_RECIPIENT_CONSENT' for x in self.e.events))
        self.assertGreater(self.e.db.execute('select count(*) from events').fetchone()[0],0)

    def test_advisory_not_overridden_by_previous_critical(self):
        self.e.act('session',dict(operator='TEST',label='latch display'))
        self.e.port=Port();self.e.last_rx=time.monotonic()
        self.e.act('samples/new',{'label':'critical'})
        self.reading(21000,state='CRITICAL',pH_estimate=7,verdict='DO_NOT_FEED')
        self.assertTrue(self.e.alarm.latched)
        self.e.act('samples/new',{'label':'advisory'})
        self.reading(21000,elapsed_ms=50000,state='ADVISORY',pH_estimate=5.8,verdict='ESCALATE')
        self.assertEqual(self.e.snapshot['state'],'ADVISORY')
        self.assertEqual(self.e.snapshot['result'],'Advisory/escalate; REPEAT with new sample')
        self.assertTrue(self.e.snapshot['critical_latched'])
        self.e.act('ack',{});self.e.publish()
        self.assertEqual(self.e.snapshot['state'],'ADVISORY')
        self.assertTrue(self.e.snapshot['acknowledged'])
    def test_http(self):
        self.e.publish();server=make_server(self.e,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(server.server_port)
        try:
            for path in ('/','/styles.css','/dashboard.js','/api/health','/api/events'):
                with urlopen(url+path) as r:self.assertEqual(r.status,200)
            with urlopen(url+'/api/status') as r:token=json.load(r)['csrf_token']
            with self.assertRaises(HTTPError) as caught:urlopen(Request(url+'/api/ack',data=b'{}'))
            self.assertEqual(caught.exception.code,403)
            # Handler dispatch is isolated from SQLite's owning thread here.
            self.e.request=lambda action,data:{'action':action,'received':data}
            with urlopen(Request(url+'/api/samples/new',data=b'{"label":"test"}',headers={'X-CSRF-Token':token})) as r:
                self.assertEqual(json.load(r)['action'],'samples/new')
        finally:server.shutdown();server.server_close();thread.join()

    def test_consent_and_receipt(self):
        self.e.act('session',dict(operator='TEST',label='consent test'))
        with self.assertRaises(ValueError):
            self.e.act('notifications/consent',dict(recipient='SL',agreed=False))
        r=self.e.act('notifications/consent',dict(recipient='SL',agreed=True))
        self.assertTrue(r['consent_utc'])
        self.e.track_notification(dict(sample_id='test-1',test_notification=True))
        self.assertEqual(self.e.deliveries['test-1']['confirmations'],[])
        later=self.e.act('notifications/consent',dict(recipient='SP',agreed=True))
        with self.assertRaises(ValueError):
            self.e.act('notifications/receipt',dict(sample_id='test-1',recipient_id=later['recipient_id'],observed=True))
        with self.assertRaises(ValueError):
            self.e.act('notifications/receipt',dict(sample_id='test-1',recipient_id=r['recipient_id'],observed=False))
        data=dict(sample_id='test-1',recipient_id=r['recipient_id'],observed=True,evidence_note='screenshot.png')
        first=self.e.act('notifications/receipt',data)
        self.assertEqual(first,self.e.act('notifications/receipt',data))
        self.assertEqual(len(self.e.deliveries['test-1']['confirmations']),1)
        self.assertEqual(first['confirmation_method'],'MANUAL_PHONE_OBSERVATION')
        self.assertEqual(self.e.db.execute("select count(*) from events where kind='PHONE_RECEIPT_CONFIRMED'").fetchone()[0],1)

    def test_notifications_cover_every_completed_outcome(self):
        phone=RecordingPhone();self.e.phone=phone
        self.e.act('session',dict(operator='TEST',label='all outcomes',phone_consent=True))
        self.e.port=Port();self.e.last_rx=time.monotonic()
        cases=[('NORMAL','VALID','Normal/'),('ADVISORY','VALID','Advisory/'),
               ('CRITICAL','VALID','Critical/'),('TECHNICAL','UNABLE_TO_SETTLE','Unable to settle'),
               ('TECHNICAL','NOT_SETTLED','Unable to settle'),('TECHNICAL','DRIFT_FAILURE','Drifting'),
               ('TECHNICAL','STUCK_FAILURE','Stuck'),('TECHNICAL','SIGNAL_OUT_OF_RANGE','out of range'),
               ('TECHNICAL','CALIBRATION_INVALID','Calibration'),('TECHNICAL','MISSING_TIMED_READINGS','Missing'),
               ('TECHNICAL','INVALID_VALUE','Invalid')]
        for i,(state,reason,word) in enumerate(cases):
            self.e.act('samples/new',{'label':reason})
            self.reading(20000,state=state,reason=reason,elapsed_ms=i*30000+20000)
            self.assertEqual(len(phone.calls),i)
            self.reading(21000,state=state,reason=reason,elapsed_ms=i*30000+21000,settled=state!='TECHNICAL',verdict=None if state=='TECHNICAL' else 'TEST')
            self.e.publish();self.e.publish()
            self.assertEqual(len(phone.calls),i+1)
            self.assertEqual(phone.calls[-1][1],state)
            self.assertIn(word,phone.calls[-1][2])
            self.assertEqual(phone.calls[-1][4]['reason'],reason)
        self.e.act('samples/new',{'label':'stopped'})
        self.reading(22000,elapsed_ms=400000,state='TECHNICAL',reason='SAMPLE_STOPPED',settled=False,verdict=None)
        self.assertEqual(len(phone.calls),len(cases))
        self.e.notifications_enabled=False
        self.e.act('samples/new',{'label':'no consent'})
        self.reading(21000,elapsed_ms=430000)
        self.assertEqual(len(phone.calls),len(cases))

if __name__=='__main__':unittest.main()
