import json
import tempfile
import unittest
from pathlib import Path

from lib.result_contract.core import build, export, validate, audit, pointer
from lib.visualization.evidence import write_json


class ResultContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'input.txt').write_text('fixture')
        (self.root/'solver.py').write_text('# fixture producer')
        self.put('problem.json', dict(c=[2, 3], lower=[0, 0], upper=[10, 10],
             integer_indices=[0], constraints=[dict(id='capacity', a=[1, 1], sense='le', rhs=5)]))
        self.put('solution.json', dict(x=[2, 3], objective=13))
        self.put('results/metric-spec.json', dict(schema_version=1, problem_id='test', run_id='1',
             inputs=['input.txt'], scripts=['solver.py'], metrics=[dict(id='profit', label='Profit',
             unit='yuan', scenario='feasible', source='solution.json', pointer='/objective', precision=2)]))
        self.put('results/validation-spec.json', dict(schema_version=1, kind='linear', inputs=['input.txt', 'solution.json'],
             problem='problem.json', solution='solution.json', checks_required=['objective', 'constraint.capacity']))

    def put(self, path, value):
        write_json(self.root/path, value)

    def ready(self):
        build(self.root)
        export(self.root)
        validate(self.root)

    def test_verified_and_rendered(self):
        self.ready()
        self.assertEqual(audit(self.root, rendered=True), [])

    def test_feasible_but_wrong_objective_fails(self):
        self.put('solution.json', dict(x=[2, 3], objective=14))
        self.ready()
        self.assertTrue(audit(self.root))

    def test_constraint_failure_is_not_solver_success(self):
        self.put('solution.json', dict(x=[3, 3], objective=15))
        self.ready()
        self.assertTrue(audit(self.root))

    def test_source_change_invalidates_receipt(self):
        self.ready()
        self.put('solution.json', dict(x=[1, 3], objective=11))
        self.assertTrue(audit(self.root))

    def test_forged_linear_checks_recomputed(self):
        self.ready()
        path = self.root/'results/validation.json'
        data = json.loads(path.read_text())
        data['checks'][0]['evidence'] = 'fabricated'
        self.put('results/validation.json', data)
        self.assertTrue(audit(self.root))

    def test_rendered_change_detected(self):
        self.ready()
        (self.root/'paper/result-values.tex').write_text('wrong')
        self.assertTrue(audit(self.root, rendered=True))

    def test_array_pointer_rejects_negative_index(self):
        with self.assertRaises(ValueError): pointer([1, 2], '/-1')

    def test_web_gate_rejects_missing_registry(self):
        from regression.test_workflow import load_server
        server = load_server(self.root)
        self.put('config/result_contract.json', {'schema_version': 1})
        stage = next(s for s in server.STAGES if s['id'] == 'audit')
        decision = server._gate_decision(stage)
        self.assertEqual(decision['reason'], 'result_contract_failed')
        self.assertEqual(decision['target'], 'code')

    def test_web_gate_passes_contract_then_reads_verdict(self):
        from regression.test_workflow import load_server
        server = load_server(self.root)
        self.put('config/result_contract.json', {'schema_version': 1})
        self.ready()
        stage = next(s for s in server.STAGES if s['id'] == 'audit')
        (server.REPORTS/stage['report']).write_text('整题门禁裁决：PASS', encoding='utf-8')
        self.assertEqual(server._gate_decision(stage)['status'], 'PASS')


class DensePlotTests(unittest.TestCase):
    def test_facets_keep_rows_values_and_common_scale(self):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        from lib.visualization.dense import faceted_heatmap
        values = np.arange(54*7).reshape(54, 7)
        fig = faceted_heatmap(values, [str(i) for i in range(54)], list('abcdefg'), colorbar_label='value')
        self.addCleanup(plt.close, fig)
        plots = [ax for ax in fig.axes if ax.images]
        np.testing.assert_array_equal(np.concatenate([ax.images[0].get_array() for ax in plots]), values)
        self.assertEqual(len({id(ax.images[0].norm) for ax in plots}), 1)

    def test_dense_alignment_hint(self):
        from lib.publication.checks import formula_hints
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'paper').mkdir()
            (root/'paper/main.tex').write_text(r'a &\le b, & c &\le d', encoding='utf-8')
            self.assertTrue(formula_hints(root))

    def test_formula_review_must_match_source_and_pdf(self):
        from lib.publication.checks import formula_hints, formula_review_issues
        from lib.visualization.evidence import sha
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'paper').mkdir()
            path = root/'paper/main.tex'
            path.write_text(r'a &\le b, & c &\le d', encoding='utf-8')
            hints = formula_hints(root)
            self.assertTrue(formula_review_issues(root, hints, 'pdfhash'))
            items = [dict(h, source_sha256=sha(path), decision='retain', reason='fixture explanation', page=1) for h in hints]
            write_json(root/'paper/formula-review.json', dict(pdf_sha256='pdfhash', items=items))
            self.assertEqual(formula_review_issues(root, hints, 'pdfhash'), [])
            self.assertTrue(formula_review_issues(root, hints, 'newpdf'))
            path.write_text('changed', encoding='utf-8')
            self.assertTrue(formula_review_issues(root, hints, 'pdfhash'))
