"""Inspect outgoing requests with a fake provider; sends no real notification."""
import unittest
from phone_notifications import PhoneNotifications

class NotificationMessages(unittest.TestCase):
    def test_titles_body_priority_and_duplicate_suppression(self):
        requests=[]
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b'{"id":"fake-message"}'
        def opener(request,timeout):
            requests.append(request);return Response()
        phone=PhoneNotifications(opener=opener)
        cases=[('NORMAL','VALID','Normal'),('ADVISORY','VALID','Advisory'),
               ('CRITICAL','VALID','Critical'),('TECHNICAL','NOT_SETTLED','not settled'),
               ('TECHNICAL','UNABLE_TO_SETTLE','unable to settle'),
               ('TECHNICAL','DRIFT_FAILURE','drifting'),('TECHNICAL','STUCK_FAILURE','stuck'),
               ('TECHNICAL','SIGNAL_OUT_OF_RANGE','out of range'),
               ('TECHNICAL','CALIBRATION_INVALID','calibration'),
               ('TECHNICAL','MISSING_TIMED_READINGS','missing'),('TECHNICAL','INVALID_VALUE','invalid')]
        for i,(state,reason,title) in enumerate(cases):
            sid=str(i); result=state+'/'+reason
            event=phone.submit(sid,state,result,'4.0',reason=reason)
            self.assertEqual(event['reason'],reason)
            kind,payload=phone.events.get(timeout=2)
            phone.pending.discard(sid)
            self.assertEqual(kind,'PHONE_NOTIFICATION_ACCEPTED')
            request=requests[-1]
            self.assertEqual(request.get_header('Priority'),'4')
            self.assertIn(title,request.get_header('Title'))
            self.assertIn(result,request.data.decode('utf-8'))
            self.assertIn('Reason: '+reason,request.data.decode('utf-8'))
            self.assertFalse(payload['phone_delivery_confirmed'])
            self.assertIsNone(phone.submit(sid,state,result,'4.0',reason=reason))
        self.assertEqual(len(requests),len(cases))

if __name__=='__main__':unittest.main()
