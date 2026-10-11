import io
import json
import unittest
from urllib.error import HTTPError, URLError
from atelier.gemini import Gemini
from atelier.schemas import Problem, obj, text


class Response(io.BytesIO):
    pass


class GeminiBoundary(unittest.TestCase):
    schema=obj(answer=text(100))

    def test_header_only_key_structured_output_and_valid_json(self):
        requests=[]
        def opener(request,timeout):
            requests.append(request)
            self.assertEqual(timeout,45)
            return Response(json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"answer":"확인"}'}]}}]}).encode())
        result=Gemini('test-secret',opener=opener).generate('작업',{'source':'자료'},self.schema)
        self.assertEqual(result,{'answer':'확인'})
        request=requests[0]
        self.assertNotIn('test-secret',request.full_url)
        self.assertEqual(request.get_header('X-goog-api-key'),'test-secret')
        body=json.loads(request.data)
        self.assertEqual(body['generationConfig']['responseFormat']['text']['schema'],self.schema)
        self.assertNotIn('test-secret',request.data.decode())

    def test_transient_error_retries_only_once(self):
        calls=[]
        def opener(request,timeout):
            calls.append(1)
            raise HTTPError(request.full_url,429,'raw secret not exposed',{},None)
        with self.assertRaisesRegex(Problem,'한도') as cm:
            Gemini('test-secret',opener=opener,sleeper=lambda _:None).generate('작업',{},self.schema)
        self.assertEqual(len(calls),2)
        self.assertNotIn('secret',str(cm.exception))

    def test_authentication_errors_do_not_retry_or_leak_response(self):
        calls=[]
        def opener(request,timeout):
            calls.append(1)
            raise HTTPError(request.full_url,403,'test-secret',{},None)
        with self.assertRaisesRegex(Problem,'권한'):
            Gemini('test-secret',opener=opener).generate('작업',{},self.schema)
        self.assertEqual(len(calls),1)

    def test_truncated_or_invalid_model_json_is_rejected(self):
        for candidate in [{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'{"answer":"partial"}'}]}},
                          {'finishReason':'STOP','content':{'parts':[{'text':'not JSON'}]}},
                          {'finishReason':'STOP','content':{'parts':[{'text':'{"answer":"good","extra":1}'}]}}]:
            opener=lambda request,timeout,c=candidate:Response(json.dumps({'candidates':[c]}).encode())
            with self.assertRaises(Problem):Gemini('test',opener=opener).generate('작업',{},self.schema)

    def test_model_cannot_change_endpoint_and_key_is_required(self):
        with self.assertRaises(Problem):Gemini('test','../../other?key=secret')
        with self.assertRaises(Problem):Gemini('')

    def test_network_failure_is_actionable(self):
        def opener(request,timeout):raise URLError('sensitive failure')
        with self.assertRaisesRegex(Problem,'네트워크'):
            Gemini('test',opener=opener).generate('작업',{},self.schema)
