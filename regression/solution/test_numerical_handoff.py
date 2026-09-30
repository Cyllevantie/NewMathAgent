"""Regression tests for fixed-function bracketing and lossless case reuse."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
# 本文件测的是**某一题的解答代码**（`code/core.py`、`robustness_2d.py` 与
#   `code/outputs/*.json`），不是框架本身 —— 所以它**不在** `regression/` 的自动发现范围内
#   （见同目录 README.md）。要跑得先把那一轮的 `code/` 放回项目根。
#   缺产物时明确跳过而不是抛 traceback：这里的断言（如 -14.58984375、'graded_z120_coarse'）
#   是那一题专属的，换一题会**静默测着无关的东西** —— 所以宁可跳过也不要假绿。
_CODE = ROOT / 'code'
_SKIP_REASON = (f"需要那一题的 code/ 产物：{_CODE}（把该轮的 code/ 放回项目根再跑）。"
                "本文件的断言是某题专属的，换一题不能测 —— 见 regression/solution/README.md。")
# 这一行不能少：不把 code/ 挂上 sys.path，下面两个 import 必然失败，
#    于是整份测试**永远**走跳过分支 —— 看起来"干净"，实际一次也没跑过。
sys.path.insert(0, str(_CODE))
try:
    import core
    import robustness_2d as R
except ImportError:
    core = R = None

skip_without_code = unittest.skipUnless(core is not None, _SKIP_REASON)

class Decay:
    def step(self, C, T, dt, t_new):
        return C/(1+dt), T.copy(), True, 1, 0., 0.

def cross():
    return dict(t_prev=0., t_new=1., C_prev=np.array([1.]), T_prev=np.array([0.]),
                C_new=np.array([.5]), T_new=np.array([0.]))

@skip_without_code
class BracketTests(unittest.TestCase):
    def test_fixed_evaluation_brackets_root(self):
        c = cross()
        b = core.bisect_crossing(Decay(), c, tol=1e-6, threshold=.6,
                                 dt_fn=lambda t: 1., max_dt=None)
        lo, hi = b['bracket']
        self.assertLessEqual(lo, 2/3)
        self.assertGreaterEqual(hi, 2/3)
        self.assertLessEqual(hi-lo, 1e-6)
        self.assertAlmostEqual(b['state'][0][0], 1/(1+b['t_dry']))
        self.assertEqual(c['C_prev'][0], 1.)
    def test_recomputes_right_endpoint_even_if_already_narrow(self):
        c = cross()
        c['t_new'] = .2
        with self.assertRaises(ValueError):
            core.bisect_crossing(Decay(), c, tol=1., threshold=.6,
                                 dt_fn=lambda t: 1., max_dt=None)
    def test_rejects_nonfinite_and_bad_left(self):
        for value in (float('nan'), .5):
            c = cross(); c['C_prev'][0] = value
            with self.assertRaises(ValueError):
                core.bisect_crossing(Decay(), c, threshold=.6)
    def test_step_cap_is_part_of_evaluation(self):
        c = cross()
        b = core.bisect_crossing(Decay(), c, tol=1e-6, threshold=.6,
                                 dt_fn=lambda t: 1., max_dt=.25)
        for t, sign in zip(b['bracket'], (True, False)):
            C, _, _ = core.advance_from(Decay(), 0., (c['C_prev'],c['T_prev']),
                                        t, dt_fn=lambda t: 1., max_dt=.25)
            self.assertEqual(bool(C.max() > .6), sign)
    def test_nonconvergence_propagates(self):
        class Bad(Decay):
            def step(self, *args):
                a=list(super().step(*args)); a[2]=False; return tuple(a)
        with self.assertRaises(RuntimeError):
            core.bisect_crossing(Bad(), cross(), threshold=.6)

@skip_without_code
class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.doc=json.loads((ROOT/'code/outputs/robustness_2d.json').read_text(encoding='utf-8'))
    def load(self, doc):
        p = ROOT / 'regression' / 'reuse_fixture.json'
        try:
            p.write_text(json.dumps(doc),encoding='utf-8')
            return R._load_reused_cases(p)[0]
        finally:
            p.unlink(missing_ok=True)
    def test_current_preserves_six_cases_exactly(self):
        self.assertEqual(self.load(self.doc), self.doc['cases'])
    def test_loaded_cases_reach_closure(self):
        b=R.closure_block(self.load(self.doc))
        self.assertAlmostEqual(b['baseline']['delta_t_dry_s'], -14.58984375)
    def test_legacy_migration(self):
        legacy=json.loads((ROOT/'code/outputs/robustness_2d.prev.json').read_text(encoding='utf-8'))
        result=self.load(legacy)
        self.assertEqual([c['tag'] for c in result],
                         ['graded_z120_coarse','graded_z240_coarse','graded_z120_fine'])
        for a,b in zip(legacy['cases']+legacy['cases_fine_time'],result):
            self.assertEqual(a['one_d'],b['one_d']); self.assertEqual(a['two_d'],b['two_d'])
    def test_duplicate_labels_rejected(self):
        self.doc['cases'].append(copy.deepcopy(self.doc['cases'][0]))
        with self.assertRaises(ValueError): self.load(self.doc)
        with self.assertRaises(ValueError): R.closure_block(self.doc['cases'])
    def test_ambiguous_format_rejected(self):
        del self.doc['cases'][0]['dt_schedule']
        with self.assertRaises(ValueError): self.load(self.doc)
    def test_new_case_wins_merge(self):
        old=[{'tag':'a','delta_t_dry_s':1.}]
        new=[{'tag':'a','delta_t_dry_s':2.},{'tag':'b','delta_t_dry_s':3.}]
        self.assertEqual(R.merge_cases(old,new),new)
    def test_nan_difference_rejected(self):
        self.doc['cases'][2]['delta_t_dry_s']=float('nan')
        with self.assertRaises(ValueError): R.closure_block(self.doc['cases'])
    def test_main_rejects_old_root_results_before_running(self):
        with patch.object(R, 'load_all', side_effect=AssertionError('must fail before solving')):
            with self.assertRaises(ValueError):
                R.main(reuse_cases=ROOT/'code/outputs/robustness_2d.json', closure=True)
    def test_main_uses_fresh_closure_result(self):
        cases=copy.deepcopy(self.doc['cases'])
        for c in cases: c['root_evaluation']=core.BISECT_VERSION
        new=copy.deepcopy(cases[3]); new['delta_t_dry_s']=-12.; new['delta_t_dry_h']=-.0033
        src=ROOT/'code/outputs/robustness_2d.json'
        # Only expensive numerical diagnostics are stubbed; execute real main + merge + summary.
        stubs={name:(lambda *a, **k: {}) for name in
               ('validation','dt_convergence','mesh_adequacy','dt_sensitivity')}
        stubs.update(load_all=lambda:(None,None), _load_reused_cases=lambda p:(cases,src),
                     run_closure=lambda:[new])
        with patch.multiple(R, **stubs), patch.object(Path, 'write_text', return_value=0):
            out=R.main(reuse_cases=src,closure=True)
        self.assertEqual(out['convergence_closure']['runs'][new['tag']]['delta_t_dry_s'],-12.)

if __name__=='__main__': unittest.main(verbosity=2)
