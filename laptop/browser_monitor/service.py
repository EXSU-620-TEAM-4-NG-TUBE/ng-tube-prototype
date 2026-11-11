"""Local REST backend for the EXSU620 bench dashboard. Windows + pyserial."""
import argparse
import json
import math
import queue
import secrets
import sqlite3
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import serial
from serial.tools import list_ports
from monitor_rules import Alarm, Audio, SampleGate, visible_result, countdown_text
from phone_notifications import PhoneNotifications, TOPIC

ROOT = Path(__file__).resolve().parent
VERSION = 'browser_service_v2_all_results'

def utc():
    return datetime.now(timezone.utc).isoformat()

class Engine:
    def __init__(self, folder=None, connector=None, enumerate_ports=None, audio=None, phone=None):
        self.folder = Path(folder or ROOT/'bench_logs')
        self.connector = connector or serial.Serial
        self.enumerate_ports = enumerate_ports or list_ports.comports
        self.audio, self.phone = audio or Audio(), phone or PhoneNotifications()
        self.alarm, self.samples = Alarm(), SampleGate()
        self.commands = queue.Queue()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.snapshot = {'state':'READY','result':'Ready — enter session details','ph':'—','connected':False}
        self.events = []
        self.run_id = uuid.uuid4().hex
        self.operator = self.session = None
        self.notifications_enabled = False
        self.recipients = {}
        self.deliveries = {}
        self.port = None
        self.port_name = 'COM7'
        self.device_serial = None
        self.pending = b''
        self.reading = None
        self.last_rx = self.last_sync = self.retry_at = 0
        self.device_elapsed = None
        self.connection_error = None
        self.connected_once = False
        self.last_sound = self.last_transition = None
        self.reminder = 0
        self.trace = []
        self.prepared = {}
        self.notification_status = 'Not enabled'
        self.db = self.logfile = None

    def open_audit(self):
        self.folder.mkdir(parents=True,exist_ok=True)
        self.db = sqlite3.connect(self.folder/'bench.sqlite3')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, received_utc TEXT, run_id TEXT, operator TEXT, sample TEXT, kind TEXT, payload TEXT)')
        self.logfile = (self.folder/(self.run_id+'.jsonl')).open('a',encoding='utf-8')

    def save(self,kind,payload):
        label=self.samples.labels.get(payload.get('sample_id'),self.session) if isinstance(payload,dict) else self.session
        event=dict(received_utc=utc(),run_id=self.run_id,operator=self.operator,sample=label,kind=kind,payload=payload)
        self.logfile.write(json.dumps(event)+'\n');self.logfile.flush()
        self.db.execute('INSERT INTO events (received_utc,run_id,operator,sample,kind,payload) VALUES (?,?,?,?,?,?)',
            (event['received_utc'],self.run_id,self.operator,label,kind,json.dumps(payload)))
        self.db.commit()
        with self.lock:
            self.events.append(event)
            self.events=self.events[-200:]

    def disconnect(self,error):
        if self.port:
            try:self.port.close()
            except serial.SerialException:pass
        if self.samples.requested:
            self.save('SAMPLE_INTERRUPTED',{'sample_id':self.samples.requested,'error':error})
        self.port=None;self.pending=b'';self.reading=None;self.device_elapsed=None
        self.samples.requested=None;self.samples.confirmed=False;self.prepared.clear()
        self.audio.stop();self.last_sound=None
        if error != self.connection_error:self.save('LINK_ERROR',{'error':error})
        self.connection_error=error

    def write(self,payload):
        if self.port is None:raise ValueError('Pico is not connected. Wait for automatic reconnection.')
        raw=(json.dumps(payload)+'\n').encode('ascii')
        try:
            if self.port.write(raw)!=len(raw):raise serial.SerialException('Incomplete USB write')
        except serial.SerialException as exc:
            self.disconnect(str(exc));raise ValueError('USB disconnected; reconnect and retry.') from exc

    def new_sample(self,label,baseline=None,known=False,details=None):
        if not self.operator:raise ValueError('Enter operator and session details first.')
        label=str(label).strip()
        if not 1<=len(label)<=100:raise ValueError('Use a sample label of 1–100 characters.')
        if not self.port or time.monotonic()-self.last_rx>5:raise ValueError('Wait for a live Pico connection.')
        sample_id=uuid.uuid4().hex
        self.write(dict(command='NEW_SAMPLE',sample_id=sample_id,known_buffer_changed=known,baseline_ph=baseline))
        self.samples.request(sample_id,label,time.monotonic())
        self.alarm.muted_until=0;self.audio.stop();self.trace=[]
        self.save('NEW_SAMPLE_REQUEST',dict(sample_id=sample_id,label=label,baseline_ph=baseline,
            known_buffer_changed=known,buffer_details=details,critical_latched=self.alarm.latched))
        return {'sample_id':sample_id,'label':label}

    def acknowledge(self,source='BROWSER_BUTTON',event=None):
        self.alarm.acknowledge(time.monotonic());self.audio.stop()
        self.save('ACK',dict(sample_id=(event or {}).get('sample_id',self.samples.requested),source=source,
            device_event=event,mute_seconds=120,critical_latched=self.alarm.latched))

    def consent(self, recipient):
        recipient = str(recipient).strip()
        if not 1 <= len(recipient) <= 40:
            raise ValueError('Enter recipient initials or a nickname (1–40 characters).')
        key = recipient.casefold()
        if key not in self.recipients:
            record = dict(recipient_id=uuid.uuid4().hex, recipient=recipient,
                          consent_utc=utc(), topic=TOPIC, recorded_by=self.operator,
                          consent_text='I agree to receive prototype bench test notifications on my subscribed phone for this session.')
            self.recipients[key] = record
            self.save('PHONE_RECIPIENT_CONSENT', record)
        self.notifications_enabled = True
        return self.recipients[key]

    def track_notification(self, event):
        if event:
            self.deliveries[event['sample_id']] = dict(event, server_status='QUEUED',
                recipients=[dict(r) for r in self.recipients.values()], confirmations=[])
            self.save('PHONE_NOTIFICATION_QUEUED', self.deliveries[event['sample_id']])

    def act(self,action,data):
        if action=='session':
            if self.operator:raise ValueError('Session already started. Restart the service to change operator.')
            operator=str(data.get('operator','')).strip();session=str(data.get('label','')).strip()
            if not 1<=len(operator)<=40 or not 1<=len(session)<=100:raise ValueError('Enter operator initials and session label.')
            self.operator,self.session=operator,session
            self.notifications_enabled=data.get('phone_consent') is True
            self.save('RUN_START',dict(version=VERSION,port=self.port_name,bench_only=True))
            if self.notifications_enabled:
                self.consent(operator)
            self.notification_status='Enabled' if self.notifications_enabled else 'Not enabled'
            return {'run_id':self.run_id}
        if not self.operator:raise ValueError('Start a session first.')
        if action=='notifications/consent':
            if data.get('agreed') is not True:
                raise ValueError('The recipient must agree before consent is recorded.')
            return self.consent(data.get('recipient',''))
        if action=='notifications/receipt':
            delivery = self.deliveries.get(data.get('sample_id'))
            if not delivery:
                raise ValueError('Select a notification sent during this session.')
            recipient = next((r for r in delivery['recipients'] if r['recipient_id']==data.get('recipient_id')), None)
            if not recipient:
                raise ValueError('This recipient was not registered when this notification was sent. Send a new test.')
            if data.get('observed') is not True:
                raise ValueError('Check the notification on the phone and confirm its sample ID first.')
            existing = next((r for r in delivery['confirmations'] if r['recipient_id']==recipient['recipient_id']), None)
            if existing:return existing
            evidence = str(data.get('evidence_note','')).strip()
            if len(evidence)>300:raise ValueError('Evidence note must be at most 300 characters.')
            record = dict(sample_id=delivery['sample_id'], recipient_id=recipient['recipient_id'],
                recipient=recipient['recipient'], consent_utc=recipient['consent_utc'],
                confirmed_utc=utc(), recorded_by=self.operator, confirmation_method='MANUAL_PHONE_OBSERVATION',
                phone_delivery_confirmed=True, server_status=delivery['server_status'],
                ntfy_message_id=delivery.get('ntfy_message_id'), evidence_note=evidence)
            delivery['confirmations'].append(record)
            self.save('PHONE_RECEIPT_CONFIRMED',record)
            return record
        if action=='samples/new':return self.new_sample(data.get('label',''))
        if action=='ack':self.acknowledge();return {'acknowledged':True}
        if action=='notifications/test':
            if not self.notifications_enabled:raise ValueError('Phone notifications were not enabled for this session.')
            event=self.phone.submit('phone-test-'+uuid.uuid4().hex,'NORMAL','Connection test — no measurement','not applicable',test=True)
            self.track_notification(event)
            return {'queued':True}
        if action=='calibration/time':
            current=self.reading or {}
            if current.get('calibrated_at_unix') is not None:raise ValueError('Calibration already has a completion timestamp.')
            value=str(data.get('completed_utc','')).replace('Z','+00:00')
            try:dt=datetime.fromisoformat(value)
            except ValueError:raise ValueError('Enter a valid UTC completion date and time.')
            if dt.tzinfo is None:raise ValueError('Completion time must include UTC timezone.')
            stamp=int(dt.timestamp());now=int(time.time())
            if not 1700000000<=stamp<=now:raise ValueError('Calibration completion time must not be in the future.')
            cal_id=current.get('calibration_id')
            if not cal_id or current.get('calibration_load_error'):raise ValueError('Pico has not loaded a usable calibration record.')
            self.write(dict(command='REGISTER_CAL_TIME',unix_time=now,calibrated_at_unix=stamp,calibration_id=cal_id))
            self.save('CALIBRATION_TIME_REQUEST',dict(calibration_id=cal_id,calibrated_at_unix=stamp))
            return {'requested':True}
        if action=='probe-response/prepare':
            r=self.reading or {}
            if (not self.samples.matches(r) or r.get('reason')!='VALID' or r.get('settled') is not True
                    or r.get('calibration_valid') is not True or time.monotonic()-self.last_rx>5):
                raise ValueError('Measure a known baseline buffer first and wait for a valid result. Leave the test running.')
            baseline=r.get('pH_estimate')
            if not isinstance(baseline,(int,float)) or not 0<=baseline<=14:raise ValueError('Baseline is unavailable.')
            token=uuid.uuid4().hex
            self.prepared={token:dict(baseline=baseline,sample_id=r['sample_id'],created=time.monotonic())}
            return {'token':token,'baseline_ph':baseline}
        if action=='probe-response/start':
            entry=self.prepared.get(data.get('token'))
            if not entry or time.monotonic()-entry['created']>120:raise ValueError('Baseline confirmation expired; prepare the response check again.')
            try:source=float(data['source_ph']);target=float(data['target_ph'])
            except (ValueError,TypeError,KeyError):raise ValueError('Enter both known buffer pH values.')
            if not 0<=source<=14 or not 0<=target<=14 or abs(source-target)<=.4:
                raise ValueError('Use known buffers between pH 0 and 14 separated by more than 0.40 pH.')
            if data.get('transfer_confirmed') is not True:raise ValueError('Confirm the probe was transferred to the second buffer.')
            result=self.new_sample(f'Probe response {source:g} to {target:g}',entry['baseline'],True,
                dict(source_nominal_ph=source,target_nominal_ph=target,baseline_sample_id=entry['sample_id']))
            self.prepared.clear();return result
        raise ValueError('Unknown API action')

    def consume(self,item):
        if not isinstance(item,dict):raise ValueError('Expected a JSON object')
        if item.get('event_type'):
            if item['event_type']=='ACK_PRESS':self.acknowledge('PHYSICAL_BUTTON',item)
            else:self.save(item['event_type'],item)
            return
        required=('state','reason','elapsed_ms','pH_estimate','settled','calibration_valid','verdict')
        if any(k not in item for k in required) or item['state'] not in ('NORMAL','ADVISORY','CRITICAL','TECHNICAL'):
            raise ValueError('Missing/invalid reading fields')
        if type(item['elapsed_ms']) is not int:raise ValueError('Invalid elapsed time')
        ph=item['pH_estimate']
        if ph is not None and (type(ph) not in (int,float) or not math.isfinite(ph)):raise ValueError('Invalid pH value')
        if item.get('sample_elapsed_ms') is not None and type(item['sample_elapsed_ms']) is not int:raise ValueError('Invalid sample time')
        if self.device_elapsed is not None and item['elapsed_ms']<self.device_elapsed:
            if self.samples.requested:self.save('SAMPLE_INTERRUPTED',dict(sample_id=self.samples.requested,error='DEVICE_RESTART'))
            self.samples.requested=None;self.samples.confirmed=False;self.prepared.clear();self.last_sync=0;self.audio.stop()
        self.device_elapsed=item['elapsed_ms'];self.reading=item;self.last_rx=time.monotonic()
        self.save('READING',item)
        if self.samples.matches(item):
            if not self.samples.confirmed:
                self.samples.confirmed=True
                self.save('NEW_SAMPLE_CONFIRMED',dict(sample_id=self.samples.requested,device_elapsed_ms=item['elapsed_ms']))
            if (item.get('sample_elapsed_ms') or 0)>=21000:self.alarm.update(item)
            if ph is not None:
                self.trace.append({'ms':item.get('sample_elapsed_ms'),'ph':ph})
                self.trace=self.trace[-180:]
        elif item['state']=='CRITICAL' and (item.get('sample_elapsed_ms') or 0)>=21000:self.alarm.update(item)

    def serial_tick(self):
        now=time.monotonic()
        if not self.operator:return
        if self.port is None and now>=self.retry_at:
            self.retry_at=now+2
            target=self.port_name
            if self.device_serial:
                found=[p.device for p in self.enumerate_ports() if p.serial_number==self.device_serial]
                target=found[0] if len(found)==1 else None
            if target:
                try:
                    self.port=self.connector(target,115200,timeout=.02,write_timeout=.5)
                    info=next((p for p in self.enumerate_ports() if p.device==target),None)
                    if info and info.serial_number:self.device_serial=info.serial_number
                    self.port_name=target;self.last_rx=now;self.last_sync=0;self.connection_error=None
                    self.pending=b'';self.connected_once=True
                    self.save('LINK_CONNECTED',dict(port=target,device_serial=self.device_serial))
                except serial.SerialException as exc:self.disconnect(str(exc))
        if not self.port:return
        try:
            if now-self.last_sync>=60:
                self.write(dict(command='TIME_SYNC',unix_time=int(time.time())));self.last_sync=now
            self.pending+=self.port.read(max(1,min(self.port.in_waiting,4096)))
        except (serial.SerialException,ValueError) as exc:self.disconnect(str(exc));return
        if len(self.pending)>65536:
            self.save('PARSE_ERROR',{'error':'Oversized serial buffer'});self.pending=b''
        while b'\n' in self.pending:
            line,self.pending=self.pending.split(b'\n',1)
            text=line.decode('utf-8',errors='replace').strip()
            if not text:continue
            try:
                if text.startswith('{'):self.consume(json.loads(text))
                else:self.save('DEVICE_TEXT',text)
            except (ValueError,TypeError,KeyError) as exc:self.save('PARSE_ERROR',dict(error=str(exc),text=text))
        if time.monotonic()-self.last_rx>5:self.disconnect('No device heartbeat; reconnecting')

    def publish(self):
        now=time.monotonic();connected=self.port is not None and now-self.last_rx<=5
        current=self.reading if connected and self.samples.matches(self.reading) else None
        state,text,ph=visible_result(current,self.samples.requested,connected,self.alarm.latched)
        if not self.operator:state,text,ph='READY','Ready — enter session details','—'
        elif state=='RECONNECTING' and not self.connected_once:text='Connecting to Pico — no result'
        transition=(state,(current or {}).get('reason'),self.alarm.latched,self.alarm.acknowledged)
        if self.operator and transition!=self.last_transition:
            self.save('ALARM_TRANSITION',dict(state=state,reason=(current or {}).get('reason'),
                sample_id=self.samples.requested,critical_latched=self.alarm.latched,acknowledged=self.alarm.acknowledged))
            self.last_transition=transition
        muted=state in ('READY','MEASURING','STOPPED','RECONNECTING') or now<self.alarm.muted_until
        audible='MUTED' if muted else state
        if audible!=self.last_sound:
            self.audio.stop()
            if not muted:self.audio.play(state);self.reminder=now+120
            self.last_sound=audible
        elif not muted and state!='NORMAL' and now>=self.reminder:
            self.audio.play(state);self.reminder=now+120
        if (self.notifications_enabled and current and (current.get('sample_elapsed_ms') or 0)>=21000
                and state in ('NORMAL','ADVISORY','CRITICAL','TECHNICAL')
                  and current.get('reason') not in ('MEASURING','NO_SAMPLE','SAMPLE_STOPPED')):
            event=self.phone.submit(self.samples.requested,state,text,ph,reason=current.get('reason'))
            if event:self.track_notification(event);self.notification_status='Sending result…'
        for kind,payload in self.phone.drain():
            self.save(kind,payload)
            delivery=self.deliveries.get(payload.get('sample_id'))
            if delivery is not None:
                delivery.update(payload)
                delivery['server_status']='ACCEPTED' if kind=='PHONE_NOTIFICATION_ACCEPTED' else 'FAILED_OR_UNCONFIRMED'
            self.notification_status=('ntfy accepted message; check phone' if kind=='PHONE_NOTIFICATION_ACCEPTED'
                else 'Notification failed: '+payload.get('error','unknown'))
        reading=self.reading or {}
        view=dict(version=VERSION,run_id=self.run_id,session_started=bool(self.operator),operator=self.operator,
            state=state,result=text,ph=ph,countdown=countdown_text(state,current,now,self.last_rx),connected=connected,
            input=reading.get('input_source','waiting for sensor'),sample_id=self.samples.requested,
            sample_label=self.samples.labels.get(self.samples.requested,'Not selected'),reading=reading,
            critical_latched=self.alarm.latched,acknowledged=self.alarm.acknowledged,
            mute_remaining_s=max(0,int(self.alarm.muted_until-now)),notification_status=self.notification_status,
            notifications_enabled=self.notifications_enabled,topic=TOPIC,trace=self.trace[:],
            recipients=list(self.recipients.values()), deliveries=list(self.deliveries.values()),
            calibration_time_needed=bool(connected and reading.get('calibration_id') and
                reading.get('calibrated_at_unix') is None and not reading.get('calibration_load_error')),
            current_utc=utc(),connection_error=self.connection_error,port=self.port_name,
            log_folder=str(self.folder),bench_only=True)
        with self.lock:self.snapshot=view

    def run(self):
        try:
            self.open_audit()
            while not self.stop_event.is_set():
                for _ in range(8):
                    try:action,data,event,reply,cancel=self.commands.get_nowait()
                    except queue.Empty:break
                    if cancel.is_set():event.set();continue
                    try:reply['result']=self.act(action,data)
                    except (ValueError,TypeError) as exc:reply['error']=str(exc)
                    finally:event.set()
                self.serial_tick();self.publish();self.stop_event.wait(.02)
        except Exception as exc:
            with self.lock:self.snapshot.update(state='TECHNICAL',result='Service error — no current verdict',ph='—',fatal_error=str(exc),connected=False)
        finally:
            self.audio.stop()
            if self.port:self.port.close()
            if self.db:
                for kind,payload in self.phone.drain():self.save(kind,payload)
                for pending in self.phone.pending:self.save('PHONE_NOTIFICATION_UNCONFIRMED_AT_CLOSE',{'sample_id':pending})
                if self.operator:self.save('RUN_STOP',{'reason':'Service stopped'})
                self.db.close();self.logfile.close()

    def request(self,action,data):
        event=threading.Event();reply={};cancel=threading.Event()
        self.commands.put((action,data,event,reply,cancel))
        if not event.wait(5):cancel.set();raise ValueError('Service did not respond; check the service window.')
        if 'error' in reply:raise ValueError(reply['error'])
        return reply.get('result',{})

def make_server(engine,port=8765):
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,code,body,content_type='application/json'):
            data=json.dumps(body,allow_nan=False).encode() if content_type=='application/json' else body
            self.send_response(code);self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
            self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
        def valid_host(self):
            if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
                self.send(403,{'error':'Local host only'});return False
            return True
        def do_GET(self):
            if not self.valid_host():return
            path=urlsplit(self.path).path
            if path in ('/','/index.html'):
                self.send(200,(ROOT/'index.html').read_bytes(),'text/html; charset=utf-8')
            elif path in ('/dashboard.js','/styles.css'):
                self.send(200,(ROOT/path[1:]).read_bytes(),'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8')
            elif path=='/api/status':
                with engine.lock:status=dict(engine.snapshot)
                status['csrf_token']=token;self.send(200,status)
            elif path=='/api/events':
                with engine.lock:events=engine.events[-100:]
                self.send(200,{'events':events})
            elif path=='/api/health':self.send(200,{'service':VERSION,'bench_only':True})
            else:self.send(404,{'error':'Not found'})
        def do_POST(self):
            if not self.valid_host():return
            if self.headers.get('X-CSRF-Token')!=token:
                self.send(403,{'error':'Refresh the dashboard before issuing commands'});return
            origin=self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
                self.send(403,{'error':'Origin not allowed'});return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=8192:raise ValueError('Invalid request length')
                data=json.loads(self.rfile.read(size))
                if not isinstance(data,dict):raise ValueError('Expected JSON object')
                path=urlsplit(self.path).path
                if not path.startswith('/api/'):raise ValueError('Unknown API route')
                self.send(200,engine.request(path[5:],data))
            except (ValueError,UnicodeError) as exc:self.send(400,{'error':str(exc)})
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    engine=Engine();server=make_server(engine,args.port)
    worker=threading.Thread(target=engine.run,daemon=True);worker.start()
    url=f'http://127.0.0.1:{server.server_port}'
    print('EXSU620 browser monitor:',url,'\nClose Thonny and the old desktop monitor.\nKeep this service window open. Ctrl+C stops the service.',flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:pass
    finally:engine.stop_event.set();server.server_close();worker.join(3)

if __name__=='__main__':main()
