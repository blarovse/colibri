"""Tests for the Jarvis PredictionAgent statistical engines."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from monday.agents.prediction_agent import (  # noqa: E402
    PredictionAgent,
    _extract_series,
    _solve_linear_system,
)


class TestSequencePrediction(unittest.TestCase):
    def setUp(self):
        self.agent = PredictionAgent()

    def test_arithmetic(self):
        r = self.agent.predict_sequence([2, 4, 6, 8])
        self.assertEqual(r['pattern'], 'arithmetic')
        self.assertEqual(r['next_value'], 10.0)

    def test_geometric(self):
        r = self.agent.predict_sequence([2, 4, 8, 16, 32])
        self.assertEqual(r['pattern'], 'geometric')
        self.assertEqual(r['next_value'], 64.0)

    def test_fibonacci(self):
        r = self.agent.predict_sequence([1, 1, 2, 3, 5, 8])
        self.assertEqual(r['pattern'], 'fibonacci_like')
        self.assertEqual(r['next_value'], 13.0)

    def test_quadratic(self):
        r = self.agent.predict_sequence([1, 4, 9, 16, 25])
        self.assertEqual(r['pattern'], 'polynomial_order_2')
        self.assertEqual(r['next_value'], 36.0)

    def test_cubic(self):
        r = self.agent.predict_sequence([1, 8, 27, 64, 125])
        self.assertEqual(r['pattern'], 'polynomial_order_3')
        self.assertEqual(r['next_value'], 216.0)

    def test_cyclic(self):
        r = self.agent.predict_sequence([3, 1, 4, 3, 1, 4])
        self.assertEqual(r['pattern'], 'cyclic')
        self.assertEqual(r['next_value'], 3.0)

    def test_linear_recurrence(self):
        # v[n] = 2*v[n-1] + v[n-2]
        r = self.agent.predict_sequence([1, 1, 3, 7, 17, 41])
        self.assertEqual(r['pattern'], 'linear_recurrence_order_2')
        self.assertEqual(r['next_value'], 99.0)

    def test_no_false_pattern(self):
        r = self.agent.predict_sequence([4, 7, 1, 9, 3])
        self.assertEqual(r['pattern'], 'none')
        self.assertLessEqual(r['confidence'], 0.55)

    def test_too_short(self):
        r = self.agent.predict_sequence([1, 2])
        self.assertIn('error', r)


class TestForecast(unittest.TestCase):
    def setUp(self):
        self.agent = PredictionAgent()

    def test_linear_series_forecast(self):
        r = self.agent.forecast_series([10, 12, 14, 16, 18, 20])
        self.assertAlmostEqual(r['next_value'], 22.0, delta=0.5)
        self.assertEqual(r['horizon'], 1)

    def test_intervals_contain_point(self):
        r = self.agent.forecast_series([5, 6, 8, 7, 9, 11, 10, 12])
        lo80, hi80 = r['interval_80']
        lo95, hi95 = r['interval_95']
        self.assertTrue(lo80 <= r['next_value'] <= hi80)
        self.assertLess(lo95, lo80)
        self.assertGreater(hi95, hi80)

    def test_multi_horizon_path(self):
        r = self.agent.forecast_series([1, 2, 3, 4, 5, 6, 7], horizon=3)
        self.assertEqual(len(r['path']), 3)
        self.assertAlmostEqual(r['next_value'], 10.0, delta=1.0)

    def test_too_short(self):
        self.assertIn('error', self.agent.forecast_series([1, 2]))


class TestDirection(unittest.TestCase):
    def setUp(self):
        self.agent = PredictionAgent()

    def test_uptrend(self):
        up = [float(x) for x in range(100, 130, 2)]
        r = self.agent.predict_direction(up, symbol='UPCO')
        self.assertEqual(r['verdict'], 'UP')
        self.assertGreater(r['probabilities']['up'], 0.5)

    def test_downtrend(self):
        down = [float(x) for x in range(130, 100, -2)]
        r = self.agent.predict_direction(down)
        self.assertEqual(r['verdict'], 'DOWN')
        self.assertGreater(r['probabilities']['down'], 0.5)

    def test_probabilities_sum_to_one(self):
        series = [float(x) for x in range(100, 130, 2)]
        p = self.agent.predict_direction(series)['probabilities']
        self.assertAlmostEqual(p['up'] + p['down'] + p['sideways'], 1.0, places=2)

    def test_disclaimer_always_present(self):
        r = self.agent.predict_direction([float(x) for x in range(100, 130, 2)])
        self.assertIn('disclaimer', r)
        self.assertIn('Not financial advice', r['disclaimer'])

    def test_signals_have_valid_range(self):
        r = self.agent.predict_direction([float(x) for x in range(100, 130, 2)])
        for s in r['signals']:
            self.assertLessEqual(abs(s['value']), 1.0)

    def test_too_short(self):
        self.assertIn('error', self.agent.predict_direction([1, 2, 3]))


class TestScenariosAndRisk(unittest.TestCase):
    def setUp(self):
        self.agent = PredictionAgent()
        # mild uptrend with noise
        self.series = [100, 101, 100.5, 102, 103, 102.5, 104, 105, 104.5, 106]

    def test_scenario_probabilities_sum_to_one(self):
        scenarios = self.agent.scenarios(self.series)['scenarios']
        total = sum(s['probability'] for s in scenarios)
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_scenario_ordering(self):
        scenarios = self.agent.scenarios(self.series)['scenarios']
        bull, base, bear = (s['target'] for s in scenarios)
        self.assertGreater(bull, base)
        self.assertGreater(base, bear)

    def test_risk_metrics(self):
        r = self.agent.assess_risk(self.series, symbol='TEST')
        self.assertGreaterEqual(r['volatility_per_period'], 0)
        self.assertLessEqual(r['max_drawdown_pct'], 0)  # drawdown is non-positive
        self.assertIn(r['risk_label'], ('low', 'medium', 'high', 'extreme'))
        self.assertIn(r['volatility_regime'], ('stable', 'expanding', 'contracting'))
        self.assertIn('disclaimer', r)

    def test_risk_short_series_warning(self):
        r = self.agent.assess_risk([1, 2, 3, 4, 5])
        self.assertIn('warnings', r)

    def test_market_brief(self):
        r = self.agent.analyze_market(self.series, symbol='TEST')
        self.assertEqual(r['kind'], 'market_brief')
        self.assertEqual(len(r['scenarios']), 3)
        self.assertIn('direction', r)
        self.assertIn('risk', r)


class TestEventProbability(unittest.TestCase):
    def setUp(self):
        self.agent = PredictionAgent()

    def test_frequency_laplace(self):
        r = self.agent.event_probability(successes=7, trials=10)
        self.assertAlmostEqual(r['probability'], 8 / 12, places=4)
        lo, hi = r['interval_95']
        self.assertLess(lo, r['probability'])
        self.assertGreater(hi, r['probability'])

    def test_evidence_for_raises_probability(self):
        base = self.agent.event_probability(base_rate=0.3)
        boosted = self.agent.event_probability(
            base_rate=0.3, evidence=[{'direction': 'for', 'strength': 0.8}])
        self.assertGreater(boosted['probability'], base['probability'])

    def test_evidence_against_lowers_probability(self):
        cut = self.agent.event_probability(
            base_rate=0.6, evidence=[{'direction': 'against', 'strength': 0.8}])
        self.assertLess(cut['probability'], 0.6)

    def test_bounds(self):
        extreme = self.agent.event_probability(
            base_rate=0.99, evidence=[{'direction': 'for', 'strength': 1.0}])
        self.assertLessEqual(extreme['probability'], 0.99)

    def test_invalid_frequency(self):
        self.assertIn('error', self.agent.event_probability(successes=11, trials=10))

    def test_reasoning_steps_recorded(self):
        r = self.agent.event_probability(
            base_rate=0.5, evidence=[{'direction': 'for', 'strength': 0.5}])
        self.assertTrue(any('FOR' in s or 'base rate' in s for s in r['reasoning']))


class TestHelpers(unittest.TestCase):
    def test_extract_series(self):
        self.assertEqual(_extract_series('prices 1, 2, 3'), [1.0, 2.0, 3.0])
        self.assertEqual(_extract_series('only 1 and 2'), [])

    def test_solve_linear_system(self):
        x = _solve_linear_system([[2.0, 1.0], [1.0, 3.0]], [3.0, 5.0])
        self.assertAlmostEqual(x[0], 0.8, places=9)
        self.assertAlmostEqual(x[1], 1.4, places=9)

    def test_solve_singular_returns_none(self):
        self.assertIsNone(_solve_linear_system([[1, 1], [1, 1]], [1, 2]))


class TestAgentInterface(unittest.TestCase):
    def setUp(self):
        self.agent = PredictionAgent()

    def _request(self, objective, spec):
        from monday.core.base_agent import AgentRequest
        return AgentRequest(
            task_id='t1', parent_task_id=None, agent_type='prediction',
            objective=objective, inputs={'specification': spec},
        )

    def test_capabilities_advertised(self):
        for cap in ('prediction', 'forecasting', 'market_analysis',
                    'risk_assessment'):
            self.assertTrue(self.agent.can_handle(cap))

    def test_execute_sequence(self):
        response = self.agent.execute(self._request(
            'predict the next number in 2 4 8 16', {}))
        self.assertTrue(response.success)
        self.assertEqual(response.output['next_value'], 32.0)

    def test_execute_direction_with_entities(self):
        spec = {'entities': {'series': [float(x) for x in range(100, 130, 2)],
                             'symbol': 'UPCO'}}
        response = self.agent.execute(self._request('market direction', spec))
        self.assertTrue(response.success)
        self.assertEqual(response.output['symbol'], 'UPCO')
        self.assertEqual(response.output['verdict'], 'UP')

    def test_execute_insufficient_data_fails_cleanly(self):
        response = self.agent.execute(self._request('forecast next value', {}))
        self.assertFalse(response.success)
        self.assertTrue(response.errors)


if __name__ == '__main__':
    unittest.main()
