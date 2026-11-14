import copy
import json
import unittest
from pathlib import Path
from src.ai.answer_grading import grade_answer,content_hash
ROOT=Path(__file__).resolve().parents[1]
CASES=json.loads((ROOT/'tests/fixtures/grading/demo_inputs.json').read_text(encoding='utf-8'))
def run(case,**kw):return grade_answer(**case,skill_catalog=[f'A{i:03}' for i in range(1,10)],allow_demo=True,**kw)
class Checks(unittest.TestCase):
 def test_four_demo_cases(self):
  self.assertEqual([run(c)['overall_result'] for c in CASES],['CORRECT','CORRECT','INCORRECT','UNCERTAIN'])
 def test_wrong_exam_version(self):self.assertIn('VERSION_MISMATCH',run(CASES[0],expected_exam_version='V2')['reason_codes'])
 def test_reference_changed_question(self):
  c=copy.deepcopy(CASES[0]);c['question_snapshot']['content']+=' changed'
  self.assertIn('REFERENCE_CONTENT_MISMATCH',run(c)['reason_codes'])
 def test_no_implicit_approval(self):
  c=copy.deepcopy(CASES[0]);c['question_snapshot']['approved']=False
  self.assertTrue(run(c)['requires_teacher'])
 def test_demo_refused_by_default(self):
  self.assertIn('DEMO_REFERENCE_NOT_ALLOWED',grade_answer(**CASES[0],skill_catalog=['A001'])['reason_codes'])
 def test_unseen_paraphrase_not_accepted(self):
  c=copy.deepcopy(CASES[0]);c['student_steps'][1]['description']='20 vì nhân tất cả lựa chọn.'
  r=run(c);self.assertTrue(r['requires_teacher']);self.assertEqual(r['overall_result'],'UNCERTAIN')
 def test_reordered_numbers_map_by_content(self):
  c=copy.deepcopy(CASES[0]);c['student_steps'][0]['step']=8;c['student_steps'][1]['step']=3
  self.assertEqual(run(c)['overall_result'],'CORRECT')
 def test_duplicate_ids_refused(self):
  c=copy.deepcopy(CASES[0]);c['student_steps'][1]['step']=1
  self.assertIn('DUPLICATE_STEP_ID',run(c)['reason_codes'])
 def test_partial_mapping_retains_findings(self):
  c=copy.deepcopy(CASES[2]);c['student_steps'][-1]['description']='Không rõ kết luận.'
  r=run(c);self.assertTrue(r['requires_teacher']);self.assertEqual(r['errors'][0]['skill_ids'],['A009'])
 def test_no_new_skill_for_dependent_error(self):
  r=run(CASES[2]);self.assertEqual(r['errors'][2]['skill_ids'],[]);self.assertEqual(r['errors'][2]['cause_steps'],[1,2])
 def test_missing_rubric(self):
  c=copy.deepcopy(CASES[0]);c['rubric']={}
  self.assertTrue(run(c)['requires_teacher'])
 def test_missing_final_does_not_guess(self):
  c=copy.deepcopy(CASES[0]);del c['reference_answer']['methods'][0]['checkpoints'][-1]['variants'][0]['final_answer_correct']
  self.assertIn('FINAL_ANSWER_UNVERIFIED',run(c)['reason_codes'])
 def test_skill_outside_nine_refused(self):
  c=copy.deepcopy(CASES[2]);c['reference_answer']['methods'][0]['checkpoints'][0]['variants'][0]['error_skill_ids']=['A999']
  self.assertIn('INVALID_REFERENCE_SPEC',run(c)['reason_codes'])
 def test_no_gold_argument(self):
  with self.assertRaises(TypeError):run(CASES[0],expected_result={'overall_result':'CORRECT'})
if __name__=='__main__':unittest.main()
