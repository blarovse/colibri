"""End-to-end wiring tests: prediction requests flow through Monday's core."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from monday.core.task_analyzer import TaskAnalyzer, TaskType, Intent  # noqa: E402
from monday.core.task_planner import TaskPlanner  # noqa: E402
from monday.core.agent_registry import get_registry, AgentType  # noqa: E402
from monday.core.orchestrator import MondayOrchestrator  # noqa: E402
from monday.agents import register_default_agents  # noqa: E402


class TestAnalyzerRouting(unittest.TestCase):
    def setUp(self):
        self.analyzer = TaskAnalyzer()

    def test_prediction_request_detected(self):
        spec = self.analyzer.analyze('Predict the next number in 2 4 8 16 32')
        self.assertEqual(spec.task_type, TaskType.PREDICTION)
        self.assertEqual(spec.intent, Intent.PREDICT)
        self.assertEqual(spec.entities['series'], [2.0, 4.0, 8.0, 16.0, 32.0])

    def test_trading_request_detected(self):
        spec = self.analyzer.analyze(
            'will BTC go up or down? prices 44000 44500 44100 45200 45800')
        self.assertEqual(spec.task_type, TaskType.PREDICTION)
        self.assertEqual(spec.entities['symbol'], 'BTC')

    def test_existing_types_unaffected(self):
        cases = {
            'Create an app for managing my school timetable':
                TaskType.SOFTWARE_DEVELOPMENT,
            'Research the best Kotlin tutorials': TaskType.RESEARCH,
            'Make a poster for my school event': TaskType.CREATIVE,
        }
        for text, expected in cases.items():
            self.assertEqual(self.analyzer.analyze(text).task_type, expected)


class TestRegistry(unittest.TestCase):
    def test_prediction_agent_registered(self):
        register_default_agents()
        registry = get_registry()
        cls = registry.get(AgentType.PREDICTION)
        self.assertIsNotNone(cls)
        info = registry.get_agent_info(AgentType.PREDICTION)
        self.assertTrue(info['enabled'])
        caps = {c['name'] for c in info['capabilities']}
        self.assertIn('market_analysis', caps)
        self.assertIn('sequence_prediction', caps)

    def test_capability_lookup(self):
        register_default_agents()
        found = get_registry().find_by_capability('forecasting')
        self.assertIn(AgentType.PREDICTION, found)


class TestPlanner(unittest.TestCase):
    def test_prediction_template_created(self):
        graph = TaskPlanner().plan(
            TaskAnalyzer().analyze('Predict the next number in 2 4 8 16 32'))
        names = [n.name for n in graph.nodes.values()]
        self.assertTrue(any('Prediction Generation' in n for n in names))
        agents = {n.agent_type for n in graph.nodes.values()}
        self.assertIn('prediction', agents)


class TestOrchestratorEndToEnd(unittest.TestCase):
    def setUp(self):
        self.orchestrator = MondayOrchestrator()

    def test_sequence_prediction_e2e(self):
        result = self.orchestrator.process(
            'Predict the next number in the sequence 2 4 8 16 32')
        self.assertEqual(result.status, 'success')
        self.assertEqual(len(result.outputs), 5)
        seq_outputs = [o for o in result.outputs.values()
                       if isinstance(o, dict) and o.get('kind') == 'sequence']
        self.assertTrue(seq_outputs)
        self.assertEqual(seq_outputs[0]['next_value'], 64.0)

    def test_direction_prediction_e2e(self):
        result = self.orchestrator.process(
            'Will BTC go up or down? prices 44000 44500 44100 45200 45800 45400 46100 46700')
        self.assertEqual(result.status, 'success')
        dirs = [o for o in result.outputs.values()
                if isinstance(o, dict) and o.get('kind') == 'direction']
        self.assertTrue(dirs)
        self.assertEqual(dirs[0]['symbol'], 'BTC')
        probs = dirs[0]['probabilities']
        self.assertAlmostEqual(
            probs['up'] + probs['down'] + probs['sideways'], 1.0, places=2)

    def test_coding_pipeline_still_works(self):
        result = self.orchestrator.process(
            'Create an app for managing my school timetable')
        self.assertEqual(result.status, 'success')
        self.assertEqual(len(result.outputs), 10)


if __name__ == '__main__':
    unittest.main()
