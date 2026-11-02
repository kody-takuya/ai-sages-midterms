import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('predict', Path(__file__).parents[1] / 'scripts/predict.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class ElectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.paths = patch.multiple(p, HISTORY_DIR=root/'history', SITE_DATA=root/'predictions.json',
                                   FINAL_FILE=root/'final.json', REVIEW_FILE=root/'review.json')
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.addCleanup(self.tmp.cleanup)
        self.args = types.SimpleNamespace(only=None, effort='low')
        self.entry = dict(date='2026-11-03', generated_at='2026-11-03T07:00:00+09:00',
                          senate={'dem': 49, 'rep': 51}, house={'dem': 220, 'rep': 215},
                          comment='before', analysis='original analysis')
        for m in p.MODELS:
            p.save_history(m['slug'], [copy.deepcopy(self.entry)])

    def run_main_at(self, now):
        real_datetime = dt.datetime
        class Clock(real_datetime):
            @classmethod
            def now(cls, tz=None):
                return now.astimezone(tz)
        with patch.object(p.dt, 'datetime', Clock), patch.object(p.sys, 'argv', ['predict.py']), \
             patch.object(p.sys, 'stdout'), patch.object(p.sys, 'stderr'):
            return p.main()

    def test_main_final_then_repeat_never_calls_prediction_again(self):
        def model_run(model, key, today, now, effort):
            entry = {**self.entry, 'date': today, 'generated_at': now.isoformat(),
                     'searches': 1, 'cost_usd': 0}
            p.save_history(model['slug'], [self.entry, entry])
            return entry
        with patch.object(p, 'load_key', return_value='test'), patch.object(p, 'run_model', side_effect=model_run) as call:
            self.assertEqual(self.run_main_at(p.FINAL_AT), 0)
            self.assertEqual(call.call_count, 5)
            original = p.FINAL_FILE.read_bytes()
            self.assertEqual(self.run_main_at(p.FINAL_AT + dt.timedelta(hours=1)), 0)
            self.assertEqual(call.call_count, 5)
            self.assertEqual(p.FINAL_FILE.read_bytes(), original)
        self.assertTrue(all(m['final_status'] == 'final' for m in json.loads(original)['models']))

    def test_main_late_start_preserves_last_prediction_without_api(self):
        with patch.object(p, 'load_key', side_effect=AssertionError('no API')):
            self.assertEqual(self.run_main_at(p.FINAL_AT + dt.timedelta(minutes=30)), 1)
        self.assertEqual(json.loads(p.FINAL_FILE.read_text())['models'][0]['final_status'], 'fallback')

    def test_phase_boundaries_and_utc(self):
        self.assertEqual(p.phase(p.FINAL_AT-dt.timedelta(seconds=1)), 'daily')
        self.assertEqual(p.phase(p.FINAL_AT), 'final')
        self.assertEqual(p.phase(p.REVIEW_AT-dt.timedelta(seconds=1)), 'final')
        self.assertEqual(p.phase(p.REVIEW_AT.astimezone(dt.timezone.utc)), 'review')

    def test_snapshot_and_site_rebuild_are_immutable(self):
        p.freeze_forecasts(p.FINAL_AT)
        original = p.FINAL_FILE.read_bytes()
        snapshot = json.loads(original)
        self.assertTrue(all(m['final_status'] == 'fallback' for m in snapshot['models']))
        p.save_history(p.MODELS[0]['slug'], [{**self.entry, 'comment': 'changed'}])
        p.freeze_forecasts(p.REVIEW_AT)
        p.build_site_data(p.REVIEW_AT)
        self.assertEqual(p.FINAL_FILE.read_bytes(), original)
        self.assertEqual(json.loads(p.SITE_DATA.read_text())['models'], snapshot['models'])

    def test_review_partial_failure_and_retry_preserves_success_and_forecast(self):
        p.freeze_forecasts(p.FINAL_AT)
        frozen = p.FINAL_FILE.read_bytes()
        histories = {m['slug']: p.history_path(m['slug']).read_bytes() for m in p.MODELS}
        failed_slug = p.MODELS[0]['slug']
        def review(model, forecast, *_):
            self.assertEqual(forecast, self.entry)
            if model['slug'] == failed_slug:
                raise RuntimeError('simulated API failure')
            return {'slug': model['slug'], 'comment': 'review'}
        with patch.object(p, 'load_key', return_value='test'), patch.object(p, 'run_review', side_effect=review):
            self.assertEqual(p.retrospective(p.REVIEW_AT, self.args), 1)
        first = json.loads(p.REVIEW_FILE.read_text())['models']
        self.assertEqual(len(first), 4)
        with patch.object(p, 'load_key', return_value='test'), patch.object(p, 'run_review', return_value={'slug': failed_slug}) as call:
            self.assertEqual(p.retrospective(p.REVIEW_AT, self.args), 0)
            self.assertEqual(call.call_count, 1)
        with patch.object(p, 'load_key', side_effect=AssertionError('should not call API')):
            self.assertEqual(p.retrospective(p.REVIEW_AT, self.args), 0)
        self.assertEqual(p.FINAL_FILE.read_bytes(), frozen)
        site = json.loads(p.SITE_DATA.read_text())
        self.assertEqual(site['models'], json.loads(frozen)['models'])
        self.assertEqual(len(site['retrospective']['models']), 5)
        for m in p.MODELS:
            self.assertEqual(p.history_path(m['slug']).read_bytes(), histories[m['slug']])

    def test_review_schema_allows_uncalled_but_rejects_bad_totals(self):
        data = dict(comment='comment', analysis='analysis', lessons='lessons', reflection='reflection',
                    results_as_of=p.REVIEW_AT.isoformat(), sources=[{'title': 'AP', 'url': 'https://apnews.com/'}],
                    results={'senate': {'dem': 48, 'rep': 49, 'other': 0, 'uncalled': 3},
                             'house': {'dem': 200, 'rep': 200, 'other': 0, 'uncalled': 35}})
        p.validate_review(data)
        data['results']['house']['uncalled'] = 34
        with self.assertRaises(ValueError): p.validate_review(data)
        data['results']['house']['uncalled'] = 35
        data['sources'][0]['url'] = 'javascript:alert(1)'
        with self.assertRaises(ValueError): p.validate_review(data)

    def test_missed_final_does_not_generate_post_election_prediction(self):
        with patch.object(p, 'load_key', return_value='test'), patch.object(p, 'run_review', return_value={'slug': p.MODELS[0]['slug']}):
            self.args.only = [p.MODELS[0]['slug']]
            p.retrospective(p.REVIEW_AT, self.args)
        frozen = json.loads(p.FINAL_FILE.read_text())
        self.assertEqual(frozen['models'][0]['latest']['date'], '2026-11-03')
        self.assertEqual(frozen['models'][0]['final_status'], 'fallback')

    def test_review_prompt_only_sees_own_forecast_and_cutoff(self):
        response = dict(comment='c', analysis='a', lessons='l', reflection='r', results_as_of=p.REVIEW_AT.isoformat(),
                        sources=[{'title': 'AP', 'url': 'https://apnews.com/'}],
                        results={'senate': {'dem': 45, 'rep': 48, 'other': 0, 'uncalled': 7},
                                 'house': {'dem': 200, 'rep': 210, 'other': 0, 'uncalled': 25}})
        with patch.object(p, 'call_openrouter', return_value={'choices':[{'message':{'content':json.dumps(response)}}]}) as call:
            p.run_review(p.MODELS[0], self.entry, 'key', p.REVIEW_AT, 'low')
        messages = call.call_args.args[1]['messages']
        self.assertEqual(json.loads(messages[1]['content']), self.entry)
        self.assertIn(p.REVIEW_AT.isoformat(), messages[0]['content'])

    def test_score_forecast_hit_miss_pending(self):
        res = lambda sd, su, hd, hu: {'senate': {'dem': sd, 'rep': 100 - sd - su, 'other': 0, 'uncalled': su},
                                      'house': {'dem': hd, 'rep': 435 - hd - hu, 'other': 0, 'uncalled': hu}}
        fc = {'senate': {'dem': 51}, 'house': {'dem': 233}}
        card = p.score_forecast(fc, res(52, 0, 230, 0))
        self.assertEqual((card['senate']['verdict'], card['house']['verdict']), ('hit', 'hit'))
        card = p.score_forecast(fc, res(49, 0, 233, 0))           # wrong Senate majority
        self.assertEqual(card['senate']['verdict'], 'miss')
        self.assertEqual(card['senate']['control_result'], 'rep')
        card = p.score_forecast(fc, res(51, 0, 220, 0))           # House majority right but 13 seats off
        self.assertEqual(card['house']['verdict'], 'miss')
        card = p.score_forecast(fc, res(49, 3, 214, 20))          # undecided, forecast still possible
        self.assertEqual((card['senate']['verdict'], card['house']['verdict']), ('pending', 'pending'))
        card = p.score_forecast({'senate': {'dem': 50}, 'house': {'dem': 233}}, res(50, 0, 233, 0))
        self.assertEqual(card['senate']['verdict'], 'hit')        # 50-50 is a Republican Senate, as forecast

    def test_review_miss_requires_reflection_and_retries_without_new_search(self):
        base = dict(comment='c', analysis='a', lessons='l', results_as_of=p.REVIEW_AT.isoformat(),
                    sources=[{'title': 'AP', 'url': 'https://apnews.com/'}],
                    results={'senate': {'dem': 47, 'rep': 53, 'other': 0, 'uncalled': 0},
                             'house': {'dem': 200, 'rep': 235, 'other': 0, 'uncalled': 0}})
        short, long_ = {**base, 'reflection': '外れた'}, {**base, 'reflection': '反省' * 120}
        replies = [{'choices': [{'message': {'content': json.dumps(r, ensure_ascii=False)}}]} for r in (short, long_)]
        forecast = {**self.entry, 'senate': {'dem': 52, 'rep': 48}, 'house': {'dem': 233, 'rep': 202}}
        with patch.object(p, 'call_openrouter', side_effect=replies) as call:
            out = p.run_review(p.MODELS[0], forecast, 'key', p.REVIEW_AT, 'low')
        self.assertEqual(call.call_count, 2)
        self.assertIn('tools', call.call_args_list[0].args[1])
        self.assertNotIn('tools', call.call_args_list[1].args[1])
        self.assertIn('MISSED', call.call_args_list[1].args[1]['messages'][-1]['content'])
        self.assertEqual(out['reflection'], long_['reflection'])
        self.assertEqual(out['scorecard']['senate']['verdict'], 'miss')

    def test_review_hit_accepts_short_reflection(self):
        reply = dict(comment='c', analysis='a', lessons='l', reflection='運も味方した', results_as_of=p.REVIEW_AT.isoformat(),
                     sources=[{'title': 'AP', 'url': 'https://apnews.com/'}],
                     results={'senate': {'dem': 49, 'rep': 51, 'other': 0, 'uncalled': 0},
                              'house': {'dem': 221, 'rep': 214, 'other': 0, 'uncalled': 0}})
        with patch.object(p, 'call_openrouter', return_value={'choices': [{'message': {'content': json.dumps(reply, ensure_ascii=False)}}]}) as call:
            out = p.run_review(p.MODELS[0], self.entry, 'key', p.REVIEW_AT, 'low')
        self.assertEqual(call.call_count, 1)
        self.assertEqual({c['verdict'] for c in out['scorecard'].values()}, {'hit'})

if __name__ == '__main__': unittest.main()
