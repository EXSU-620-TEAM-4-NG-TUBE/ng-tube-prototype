import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "software" / "browser_monitor"))
from phone_notifications import PhoneNotifications,ENDPOINT

calls=[]
class Response:
    status=200
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read(self,n):return json.dumps({'id':'mock123'}).encode()
def opener(request,timeout):
    calls.append(request)
    assert request.full_url==ENDPOINT and timeout==8
    return Response()
p=PhoneNotifications(opener)
assert p.submit('sample1','CRITICAL','Critical test','7.0')
assert p.submit('sample1','CRITICAL','duplicate','7.0') is None
event=p.events.get(timeout=2)
assert event[0]=='PHONE_NOTIFICATION_ACCEPTED'
assert event[1]['phone_delivery_confirmed'] is False
assert len(calls)==1
assert b'BENCH DEMONSTRATION' in calls[0].data
p.events.put(event)
assert p.drain() and not p.pending
def failed(request,timeout):raise TimeoutError('simulated offline')
p=PhoneNotifications(failed)
p.submit('sample2','NORMAL','Normal test','4.0')
event=p.events.get(timeout=2)
assert event[0]=='PHONE_NOTIFICATION_FAILED'
assert 'offline' in event[1]['error']
assert p.submit('sample2','NORMAL','duplicate','4.0') is None
print('PASS: mocked ntfy acceptance/failure, one send per sample, timeout, no false phone-delivery claim. No network used.')
