"""Run post-extraction demo only; no Qwen or network calls."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src.ai.answer_grading import grade_answer
if __name__=='__main__':
    cases=json.loads((ROOT/'tests/fixtures/grading/demo_inputs.json').read_text(encoding='utf-8'))
    gold=json.loads((ROOT/'tests/fixtures/grading/gold.json').read_text(encoding='utf-8'))
    results=[]
    for c in cases:
        r=grade_answer(**c,skill_catalog=[f'A{i:03}' for i in range(1,10)],expected_exam_version='DEMO_APPROVED_V1',allow_demo=True)
        r['matches_demo_gold']=r['overall_result']==gold[r['question_id']]
        results.append(r)
        print(r['question_id'],r['overall_result'],r['reason_codes'],f"{r['elapsed_seconds']:.6f}s",'gold=',r['matches_demo_gold'])
    out=ROOT/'eval/results/grading/demo_results.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Output:',out)
