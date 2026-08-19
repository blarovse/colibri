"""Tests for the Jarvis console (parsing, routing, persona, files)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from monday.jarvis import JarvisConsole, _numbers, _symbol_from  # noqa: E402


class TestParsing(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(_numbers('a 1 b -2.5 c 3'), [1.0, -2.5, 3.0])

    def test_symbol_crypto_alias(self):
        self.assertEqual(_symbol_from('will btc go up'), 'BTC')
        self.assertEqual(_symbol_from('ETH prices tomorrow'), 'ETH')

    def test_symbol_ticker(self):
        self.assertEqual(_symbol_from('AAPL next bar'), 'AAPL')

    def test_symbol_ignores_stopwords(self):
        self.assertIsNone(_symbol_from('WHAT will it DO NEXT'))


class TestConsole(unittest.TestCase):
    def setUp(self):
        self.console = JarvisConsole()

    def test_sequence_question(self):
        reply = self.console.ask('next number in 2 4 8 16 32')
        self.assertIn('64', reply)
        self.assertIn('geometric', reply)

    def test_direction_question(self):
        reply = self.console.ask(
            'will BTC go up or down? 44000 44500 44100 45200 45800 45400 46100 46700')
        self.assertIn('BTC', reply)
        self.assertIn('Verdict', reply)
        self.assertIn('Not financial advice', reply)

    def test_down_trend_recognised(self):
        reply = self.console.ask(
            'direction for 130 128 126 124 122 120 118 116')
        self.assertIn('DOWN', reply)

    def test_forecast_question(self):
        reply = self.console.ask('predict the next value for 10 12 11 14 13 16')
        self.assertIn('Next value', reply)
        self.assertIn('95% range', reply)

    def test_event_odds_frequency(self):
        reply = self.console.ask('odds 7 of 10')
        self.assertIn('66.7%', reply)

    def test_event_odds_base_rate(self):
        reply = self.console.ask('odds base 30% with strong evidence for')
        self.assertIn('Probability', reply)
        self.assertIn('30.0%', reply)

    def test_off_topic_refused(self):
        reply = self.console.ask('write me a poem about cats')
        self.assertIn('what happens next', reply)

    def test_session_state_and_commands(self):
        self.console.ask('prices: 100 101 102 103 104 105')
        self.assertEqual(len(self.console.series), 6)
        reply = self.console.ask('show')
        self.assertIn('6 points', reply)
        reply = self.console.ask('direction')
        self.assertIn('UP', reply)
        self.console.ask('reset')
        self.assertEqual(self.console.series, [])
        reply = self.console.ask('direction')
        self.assertIn('need numbers', reply.lower())

    def test_risk_command(self):
        self.console.ask('prices: 100 101 99 102 103 101 104')
        reply = self.console.ask('risk')
        self.assertIn('Risk', reply)
        self.assertIn('drawdown', reply.lower())

    def test_scenarios_command(self):
        self.console.ask('prices: 100 101 99 102 103 101 104')
        reply = self.console.ask('scenarios')
        self.assertIn('bull', reply)
        self.assertIn('bear', reply)

    def test_load_file(self):
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as fh:
            fh.write('101.5\n103.2\n102.8\n104.9\n106.1\n105.5\n107.3\n')
            path = fh.name
        try:
            reply = self.console.ask(f'load {path}')
            self.assertIn('Loaded 7 points', reply)
            self.assertEqual(len(self.console.series), 7)
        finally:
            os.unlink(path)

    def test_load_missing_file(self):
        reply = self.console.ask('load /nonexistent/file.txt')
        self.assertIn("can't read", reply)

    def test_help(self):
        self.assertIn('Commands', self.console.ask('help'))

    def test_quit(self):
        self.assertIn('Goodbye', self.console.ask('quit'))


if __name__ == '__main__':
    unittest.main()
