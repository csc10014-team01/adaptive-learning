"""Post-extraction grading core. Internal interface pending the team's API contract.

No database access, model call, numeric question score or mastery update.
Unrecognized prose is never accepted merely because its numbers match.
"""
from __future__ import annotations
import hashlib
import json
import re
import time
import unicodedata
from collections.abc import Mapping


def normalize(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFC', text).casefold().replace('×','*').replace('−','-').split())


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def grade_answer(student_steps, *, question_snapshot, reference_answer, rubric,
                 skill_catalog, expected_exam_version=None, allow_demo=False):
    """Map extracted steps against author-approved statement variants.

    Input steps: [{"step": positive_int, "description": nonempty_text}].
    reference_answer.methods[].checkpoints[].variants contain complete approved
    statements, including known incorrect statements with explicit causes.
    This bounded verifier does not infer the correctness of unseen paraphrases.
    Step numbers identify submitted steps, not positions in a reference method.
    """
    started=time.perf_counter()
    base={'grading_status':'NEEDS_REVIEW','requires_teacher':True,
          'overall_result':'UNCERTAIN','final_answer_correct':None,
          'observed_level':None,'step_results':[],'errors':[],
          'missing_steps':[],'teacher_comment':None,'reason_codes':[],
          'review_reason':None,'mapping':[],'interface_version':'internal-w07-0.1'}

    def finish(reason=None, message=None):
        if reason:
            base['reason_codes']=list(dict.fromkeys([*base['reason_codes'],reason]))
            base['review_reason']=message or reason
        base['elapsed_seconds']=time.perf_counter()-started
        return base

    if not all(isinstance(x,Mapping) for x in (question_snapshot,reference_answer,rubric)):
        return finish('INVALID_INPUT','Snapshot, reference and rubric must be objects.')
    q=question_snapshot;r=reference_answer
    qid=q.get('question_id');version=q.get('exam_version')
    base.update(question_id=qid,exam_version=version,rubric_version=rubric.get('rubric_version'),
                demo_only=q.get('approval_provenance')=='synthetic_demo')
    if not qid or not version or q.get('approved') is not True:
        return finish('UNAPPROVED_SNAPSHOT','Require an explicitly approved exam snapshot.')
    if base['demo_only'] and not allow_demo:
        return finish('DEMO_REFERENCE_NOT_ALLOWED','Synthetic approval is only usable with allow_demo=True.')
    if (expected_exam_version is not None and expected_exam_version!=version) or any(
        x.get('question_id')!=qid or x.get('exam_version')!=version for x in (r,rubric)):
        return finish('VERSION_MISMATCH','Question, reference and rubric must belong to the same exam version.')
    if not isinstance(q.get('content'),str) or r.get('question_content_sha256')!=content_hash(q['content']):
        return finish('REFERENCE_CONTENT_MISMATCH','Reference does not bind to the actual question text.')
    if r.get('verification_status')!='verified' or not r.get('correct_answer'):
        return finish('REFERENCE_UNVERIFIED','Reference is missing, conflicting or not verified.')
    if not rubric.get('rubric_version') or not isinstance(rubric.get('levels_by_result'),Mapping):
        return finish('MISSING_RUBRIC','Require explicit categorical result-to-level rules.')
    if not isinstance(student_steps,list) or not student_steps:
        return finish('INSUFFICIENT_STUDENT_DATA','No extracted student steps.')
    ids=[]
    for s in student_steps:
        if not isinstance(s,Mapping) or type(s.get('step')) is not int or s['step']<1 or not isinstance(s.get('description'),str) or not s['description'].strip() or len(s['description'])>16000:
            return finish('INVALID_STUDENT_STEP','Each step needs a positive integer ID and a description.')
        ids.append(s['step'])
    if len(ids)!=len(set(ids)):
        return finish('DUPLICATE_STEP_ID','Student step IDs must be unique.')
    for s in student_steps:
        base['step_results'].append({'step':s['step'],'result':'UNCERTAIN','feedback':'Chưa ánh xạ được bước này.','source_quote':s['description']})
    try:
        catalog=set(skill_catalog)
        if not catalog or not catalog<={f'A{i:03}' for i in range(1,10)}:raise ValueError('Unknown skills')
        methods=r.get('methods',[])
        if not methods:return finish('UNSUPPORTED_REFERENCE','No verified mapping methods.')
        candidates=[]
        for method in methods:
            cps=method['checkpoints'];cpids=[cp['id'] for cp in cps]
            if len(cpids)!=len(set(cpids)) or not cps:raise ValueError('Duplicate/empty checkpoints')
            seen=set();variant_index={}
            for cp in cps:
                if not set(cp.get('depends_on',[]))<=seen:raise ValueError('Missing/forward dependency')
                seen.add(cp['id'])
                for v in cp['variants']:
                    if v['result'] not in ('CORRECT','INCORRECT','DEPENDENT'):raise ValueError('Unsupported result')
                    if not isinstance(v.get('statement'),str) or not v['statement'].strip():raise ValueError('Empty statement')
                    if not set(v.get('error_skill_ids',[]))<=catalog:raise ValueError('Unknown error skill')
                    variant_index.setdefault(normalize(v['statement']),[]).append((cp,v))
            matches=[];ambiguous=False
            for s in student_steps:
                found=variant_index.get(normalize(s['description']),[])
                if len(found)>1:ambiguous=True
                matches.append(found[0] if len(found)==1 else None)
            covered={cp['id'] for m in matches if m for cp,v in [m]}
            # A checkpoint must not be credited twice by duplicating a submitted step.
            matched_ids=[m[0]['id'] for m in matches if m]
            if len(matched_ids)!=len(set(matched_ids)):ambiguous=True
            missing=[cp['id'] for cp in cps if cp.get('required',True) and cp['id'] not in covered]
            candidates.append((sum(m is not None for m in matches),method,matches,missing,ambiguous))
        best=max(x[0] for x in candidates)
        choices=[x for x in candidates if x[0]==best]
        # Different complete methods tying ambiguously are not resolved arbitrarily.
        if len(choices)>1:return finish('AMBIGUOUS_MAPPING','Multiple reference methods have equal mapping support.')
        _,method,matches,missing,ambiguous=choices[0]
        if ambiguous:return finish('AMBIGUOUS_MAPPING','Repeated/ambiguous checkpoint correspondence.')
        base['missing_steps']=missing
        cp_to_student={m[0]['id']:s['step'] for s,m in zip(student_steps,matches) if m}
        results={};unknown=False
        for index,(s,m) in enumerate(zip(student_steps,matches)):
            if m is None:unknown=True;continue
            cp,v=m;status=v['result'];dependencies=cp.get('depends_on',[])
            results[cp['id']]=status
            base['mapping'].append({'student_step':s['step'],'reference_method':method['id'],'checkpoint_id':cp['id']})
            step_result='INCORRECT' if status in ('INCORRECT','DEPENDENT') else 'CORRECT'
            base['step_results'][index].update(result=step_result,feedback=v['feedback'])
            if status=='INCORRECT':
                base['errors'].append({'step':s['step'],'error_type':v.get('error_type','VERIFIED_ERROR'),
                    'skill_ids':v.get('error_skill_ids',[]),'description':v['feedback'],'evidence':s['description'],'cause_steps':[]})
            elif status=='DEPENDENT':
                causes=[cp_to_student[d] for d in dependencies if d in cp_to_student]
                base['errors'].append({'step':s['step'],'error_type':'DEPENDENT_ERROR','skill_ids':[],
                    'description':v['feedback'],'evidence':s['description'],'cause_steps':causes})
        if unknown or missing:
            return finish('UNMAPPED_STUDENT_STEP' if unknown else 'INCOMPLETE_MAPPING',
                          'Unknown/different method or missing evidence; teacher must verify. Missing checkpoint is not proof of a skill error.')
        for cp,v in [m for m in matches if m]:
            if v['result']=='DEPENDENT' and not any(results.get(d) in ('INCORRECT','DEPENDENT') for d in cp.get('depends_on',[])):
                return finish('UNRESOLVED_DEPENDENCY','Dependent error has no mapped incorrect cause.')
        finals=[v['final_answer_correct'] for cp,v in [m for m in matches if m] if 'final_answer_correct' in v]
        if not finals or any(type(f) is not bool for f in finals) or len(set(finals))!=1:
            return finish('FINAL_ANSWER_UNVERIFIED','Need a consistent verified final-answer observation.')
        overall='INCORRECT' if base['errors'] or finals[0] is False else 'CORRECT'
        level=rubric['levels_by_result'].get(overall)
        if level is None:return finish('RUBRIC_LEVEL_UNDEFINED','No explicit rubric mapping for this result.')
        base.update(grading_status='AI_GRADED',requires_teacher=False,overall_result=overall,
                    final_answer_correct=finals[0],observed_level=level,review_reason=None,
                    grader='post_extraction_verified_statement_mapper')
        return finish()
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        return finish('INVALID_REFERENCE_SPEC',str(exc))
