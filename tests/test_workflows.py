import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from atelier.fixtures import CASES, demo_map, demo_scenario, demo_assessment
from atelier.schemas import Problem, MAP, ASSESSMENT, validate, validate_map
from atelier.service import Service
from atelier.store import Store


class FakeGemini:
    def __init__(self):
        self.calls = []
        self.answers = []

    def generate(self, instruction, data, schema):
        self.calls.append((instruction, deepcopy(data), schema))
        if not self.answers:
            raise AssertionError('Unexpected provider call')
        return deepcopy(self.answers.pop(0))


class Workflows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'test.sqlite3')
        self.provider = FakeGemini()
        self.service = Service(self.store, self.provider, 'gemini')
        self.service.seed()
        self.key = CASES[0]['id']

    def checked_case(self):
        demo = Service(self.store, mode='demo')
        case = self.store.get('cases', self.key)
        case = demo.counterfactual(self.key, {'version': case['version'], 'change': '전달 목적을 행사 안내로 바꾼다면?'})
        case = demo.review(self.key, {'version': case['version'], 'verdict': 'confirmed', 'reviewer': '테스트 검토자', 'note': '전달 목적에서는 실제 관람 거리의 정보 가독성이 우선입니다.'})
        return demo.approve(self.key, {'version': case['version'], 'confirmed': True})

    def scenario(self, index=0):
        scenario = demo_scenario(CASES[0], 0, 'context')
        scenario['brief'] += f' 새로운 상황 {index}.'
        return scenario

    def assessment(self, score=3):
        result = demo_assessment()
        for d in result['dimensions']:
            d['score'] = score
            d['evidence'] = '관람 거리와 날짜의 가독성을 먼저 확인합니다.' if score else ''
        return result

    def submit(self, session, score=3):
        self.provider.answers.append(self.assessment(score))
        return self.service.assess(session['id'], {'version': session['version'], 'option_id': 'b',
            'reasoning': '관람 거리와 날짜의 가독성을 먼저 확인합니다. 제목을 키우는 방법과 정보를 분리하는 방법을 비교해서 읽기 쉬운 대안을 선택합니다.', 'confidence': 90})

    def test_seed_is_idempotent_and_all_quotes_are_grounded(self):
        self.service.seed()
        self.assertEqual(len(self.store.list('cases')), 3)
        for case in self.store.list('cases'):
            validate_map(case['map'], case['source'])
            self.assertEqual(case['status'], 'draft')

    def test_approval_requires_counterfactual_expert_review_and_attestation(self):
        with self.assertRaisesRegex(Problem, '반례'):
            self.service.approve(self.key, {'version': 1, 'confirmed': True})
        with self.assertRaisesRegex(Problem, '검토'):
            self.service.start({'case_id': self.key})
        case = self.checked_case()
        self.assertEqual(case['status'], 'approved')
        self.assertEqual(case['approval']['reviewer'], '테스트 검토자')
        self.assertIn('knowledge_approved', [x['kind'] for x in self.store.list('events')])

    def test_revise_verdict_cannot_be_approved(self):
        case = self.checked_case()
        case = self.service.review(self.key, {'version': case['version'], 'verdict': 'revise', 'reviewer': '실제 검토자', 'note': '조건이 부족하므로 관람 기록을 추가해 지도 수정이 필요합니다.'})
        with self.assertRaises(Problem):
            self.service.approve(self.key, {'version': case['version'], 'confirmed': True})

    def test_model_quotes_cannot_be_fabricated(self):
        document = demo_map(CASES[0])
        document['nodes'][0]['evidence']['quote'] = '원문에 없는 인용'
        with self.assertRaisesRegex(Problem, '인용'):
            validate_map(document, CASES[0]['source'])
        document['nodes'][0]['evidence'] = {'quote':'가짜 관찰','provenance':'ai_inference'}
        with self.assertRaisesRegex(Problem, 'AI 해석'):
            validate_map(document, CASES[0]['source'])

    def test_map_edges_and_dimensions_are_validated(self):
        doc = demo_map(CASES[0])
        doc['edges'][0]['target']='unknown'
        with self.assertRaisesRegex(Problem, '연결'):
            validate_map(doc, CASES[0]['source'])
        doc = demo_map(CASES[0])
        doc['rubric'][0]['dimension'] = doc['rubric'][1]['dimension']
        with self.assertRaisesRegex(Problem, '중복'):
            validate_map(doc, CASES[0]['source'])
        doc = demo_map(CASES[0])
        doc['nodes'].append(deepcopy(doc['nodes'][0]))
        with self.assertRaisesRegex(Problem, '중복'):
            validate_map(doc, CASES[0]['source'])

    def test_extraction_provider_error_never_creates_fake_case(self):
        self.provider.answers.append({'title':'malformed'})
        with self.assertRaises(Problem):
            self.service.extract({'source': CASES[0]['source'], 'domain': '디자인'})
        self.assertEqual(len(self.store.list('cases')), 3)

    def test_interview_reextract_invalidates_approval_and_keeps_original(self):
        case=self.checked_case()
        self.provider.answers.append(demo_map(CASES[0]))
        case=self.service.interview(self.key, {'version': case['version'], 'question_id':'q1', 'answer':'다른 대안으로 인물 크기를 줄였지만 날짜와 제목의 관계가 흐려졌습니다.'})
        self.assertEqual(case['revision'], 2)
        self.assertEqual(case['status'], 'draft')
        self.assertIsNone(case['approval'])
        self.assertIsNone(case['counterfactual'])
        self.assertEqual(case['original_source'], CASES[0]['source'])
        self.assertEqual(len(case['interviews']), 1)

    def test_version_conflict_does_not_overwrite_review(self):
        self.checked_case()
        with self.assertRaises(Problem) as cm:
            self.service.review(self.key, {'version':1, 'verdict':'confirmed','note':'충분히 확인한 적용 범위 기록입니다.','reviewer':'다른 검토자'})
        self.assertEqual(cm.exception.status,409)
        self.assertEqual(self.store.get('cases',self.key)['approval']['reviewer'],'테스트 검토자')

    def test_training_hides_answers_and_unopened_hints(self):
        self.checked_case()
        self.provider.answers.append(self.scenario())
        session=self.service.start({'case_id':self.key})
        self.assertNotIn('map_snapshot',session)
        self.assertNotIn('expert_notes',session['scenario'])
        self.assertNotIn('criteria',session['scenario'])
        self.assertEqual(session['scenario']['hints'],[])
        again=self.service.start({'case_id':self.key})
        self.assertEqual(again['id'],session['id'])
        self.assertEqual(len(self.provider.calls),1)
        session=self.service.hint(session['id'],{'version':session['version']})
        self.assertEqual(len(session['scenario']['hints']),1)
        self.assertEqual(self.store.get('sessions',session['id'])['hints_used'],1)

    def test_invalid_option_and_confidence_are_rejected_before_model_call(self):
        self.checked_case()
        self.provider.answers.append(self.scenario())
        session=self.service.start({'case_id':self.key})
        values={'version':1,'option_id':'forged','reasoning':'실제 단서와 다른 대안을 충분히 비교한 답안입니다.','confidence':50}
        with self.assertRaises(Problem):
            self.service.assess(session['id'],values)
        values.update(option_id='b',confidence=True)
        with self.assertRaises(Problem):
            self.service.assess(session['id'],values)
        self.assertEqual(len(self.provider.calls),1)

    def test_assessment_requires_exact_answer_evidence(self):
        self.checked_case()
        self.provider.answers.append(self.scenario())
        session=self.service.start({'case_id':self.key})
        result=self.assessment()
        result['dimensions'][0]['evidence']='답안에 없는 인용'
        self.provider.answers.append(result)
        with self.assertRaisesRegex(Problem,'근거 인용'):
            self.service.assess(session['id'],{'version':1,'option_id':'b','reasoning':'관람 거리와 날짜의 가독성을 먼저 확인합니다. 다른 대안도 비교합니다.','confidence':50})
        self.assertIsNone(self.store.get('sessions',session['id'])['assessment'])

    def test_two_distinct_unassisted_trials_advance_one_stage(self):
        self.checked_case()
        for index in range(2):
            self.provider.answers.append(self.scenario(index))
            session=self.service.start({'case_id':self.key})
            self.submit(session)
            self.assertEqual(self.service.plan(self.key)['level'],0 if index==0 else 1)
        self.assertEqual(self.service.plan(self.key)['averages']['context'],3)

    def test_assisted_trials_do_not_advance_and_cannot_submit_twice(self):
        self.checked_case()
        for index in range(2):
            self.provider.answers.append(self.scenario(index))
            session=self.service.start({'case_id':self.key})
            session=self.service.hint(session['id'],{'version':session['version']})
            session=self.submit(session,4)
        self.assertEqual(self.service.plan(self.key)['level'],0)
        with self.assertRaisesRegex(Problem,'이미 제출'):
            self.service.assess(session['id'],{'version':session['version']})

    def test_counterfactual_revokes_approval_and_blocks_active_session(self):
        self.checked_case()
        self.provider.answers.append(self.scenario())
        session=self.service.start({'case_id':self.key})
        case=self.store.get('cases',self.key)
        demo=Service(self.store,mode='demo')
        demo.counterfactual(self.key,{'version':case['version'],'change':'새롭게 바뀐 매체 조건입니다.'})
        with self.assertRaisesRegex(Problem,'승인'):
            self.service.hint(session['id'],{'version':session['version']})

    def test_demo_never_invents_scores_or_claims_provider_call(self):
        self.checked_case()
        demo=Service(self.store,mode='demo')
        session=demo.start({'case_id':self.key})
        session=demo.assess(session['id'],{'version':session['version'],'option_id':'b','reasoning':'어떠한 답안이든 데모에서는 숙련도를 실제로 평가하지 않습니다.','confidence':100})
        self.assertEqual(session['origin'],'demo')
        self.assertEqual(demo.plan(self.key)['attempts'],0)
        self.assertEqual(demo.plan(self.key)['level'],0)
        self.assertFalse(self.provider.calls)

    def test_reapproval_requires_new_session_and_old_hints_stay_blocked(self):
        self.checked_case()
        self.provider.answers.append(self.scenario())
        old=self.service.start({'case_id':self.key})
        approved=self.checked_case()
        self.assertNotEqual(approved['approval']['id'],old['case_approval'])
        with self.assertRaises(Problem):
            self.service.hint(old['id'],{'version':old['version']})
        self.provider.answers.append(self.scenario(1))
        new=self.service.start({'case_id':self.key})
        self.assertNotEqual(old['id'],new['id'])
        self.assertEqual(new['case_approval'],approved['approval']['id'])

    def test_new_map_revision_keeps_history_but_resets_learning_evidence(self):
        case=self.checked_case()
        for index in range(2):
            self.provider.answers.append(self.scenario(index))
            self.submit(self.service.start({'case_id':self.key}))
        self.assertEqual(self.service.plan(self.key)['level'],1)
        self.provider.answers.append(demo_map(CASES[0]))
        case=self.service.interview(self.key,{'version':case['version'],'question_id':'q1','answer':'추가로 실제 출력 거리에서 날짜의 가독성을 확인했습니다.'})
        self.assertEqual(self.service.plan(self.key)['attempts'],0)
        self.assertEqual(self.service.plan(self.key)['level'],0)
        self.assertEqual(len(self.store.list('sessions')),2)

    def test_hint_budget_is_enforced_and_independent_level_has_no_hints(self):
        self.checked_case()
        self.provider.answers.append(self.scenario())
        session=self.service.start({'case_id':self.key})
        for _ in range(3):session=self.service.hint(session['id'],{'version':session['version']})
        with self.assertRaisesRegex(Problem,'힌트'):
            self.service.hint(session['id'],{'version':session['version']})
        self.submit(session)
        for index in range(4):
            self.provider.answers.append(self.scenario(index+1))
            self.submit(self.service.start({'case_id':self.key}))
        self.assertEqual(self.service.plan(self.key)['level'],2)
        self.provider.answers.append(self.scenario(8))
        session=self.service.start({'case_id':self.key})
        self.assertEqual(session['hint_budget'],0)
        with self.assertRaises(Problem):self.service.hint(session['id'],{'version':session['version']})

    def test_runtime_survives_reopening_store(self):
        approved=self.checked_case()
        reopened=Store(self.store.path)
        self.assertEqual(reopened.get('cases',self.key)['approval'],approved['approval'])
        self.assertEqual(len(reopened.list('events')),6)

    def test_schema_rejects_booleans_as_score_and_extra_fields(self):
        result=self.assessment()
        result['dimensions'][0]['score']=True
        with self.assertRaises(Problem):validate(result,ASSESSMENT)
        result=self.assessment()
        result['secret']='untrusted'
        with self.assertRaises(Problem):validate(result,ASSESSMENT)


if __name__=='__main__':unittest.main()
