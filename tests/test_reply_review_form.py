from copy import deepcopy
import contextlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import tempfile
import unittest

from personal_context.frozen_retrieval import digest
from personal_context.reply_quality_cli import main
from personal_context.reply_review_form import rating_template, render_review_form
import test_reply_quality as fixtures
from test_reply_quality import ROOT, FIXTURE


class FormParts(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.scripts = []
        self.active = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.active = True
            self.scripts.append('')

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = False

    def handle_data(self, text):
        if self.active:
            self.scripts[-1] += text


class ReviewFormTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.ReplyQualityTests()
        fixture.setUp()
        self.packet, self.key = fixture.prepare()

    def test_form_contains_exact_masked_data_and_no_coordinator_labels(self):
        text = render_review_form(self.packet, self.key)
        parts = FormParts(text)
        self.assertEqual(2, len(parts.scripts))
        data = json.loads(parts.scripts[0])
        self.assertEqual(self.packet, data['packet'])
        self.assertEqual(rating_template(self.packet), data['rating_template'])
        for hidden in ('flat_schema', 'prompt_only', 'workshop_schedule', self.key['study_sha256']):
            self.assertNotIn(hidden, text)
        self.assertIn("connect-src 'none'", text)
        self.assertNotIn('<script src=', text)
        self.assertNotIn('http://', text)

    def test_history_wording_and_criteria_cannot_escape_the_data_script(self):
        packet = deepcopy(self.packet)
        attack = '</script><script>alert("injected")</script><img src=x onerror=alert(1)>'
        case = packet['cases'][0]
        case['history'][0]['body'] = attack
        case['candidates'][0]['wording'] = attack
        case['criteria']['time'] = attack
        key = self.key | {'packet_sha256': digest(packet)}
        text = render_review_form(packet, key)
        self.assertNotIn(attack, text)
        parts = FormParts(text)
        self.assertEqual(2, len(parts.scripts))
        self.assertEqual(attack, json.loads(parts.scripts[0])['packet']['cases'][0]['history'][0]['body'])
        self.assertIn('el.textContent = text', parts.scripts[1])
        self.assertNotIn('innerHTML', parts.scripts[1])

    def test_invalid_key_or_oversized_packet_refused(self):
        with self.assertRaises(ValueError):
            render_review_form(self.packet, self.key | {'attempts': []})
        packet = deepcopy(self.packet)
        packet['cases'][0]['history'][0]['body'] = 'x'*1_000_001
        with self.assertRaisesRegex(ValueError, 'size limit'):
            render_review_form(packet, self.key | {'packet_sha256': digest(packet)})

    def test_cli_exports_form_without_overwriting_an_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'review.html'
            args = ['form', str(FIXTURE/'manifest.json'),
                    str(ROOT/'experiments/reply-union-2026-11-13/results.json'),
                    str(FIXTURE/'criteria.json'), '--seed', '17', '--output', str(output)]
            with contextlib.redirect_stdout(io.StringIO()):
                main(args)
            self.assertEqual(render_review_form(self.packet, self.key), output.read_text())
            original = output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(args)
            self.assertEqual(original, output.read_bytes())

    def test_cli_reports_pending_work_but_will_not_score_it(self):
        with tempfile.TemporaryDirectory() as directory:
            rating_path, output = Path(directory)/'ratings.json', Path(directory)/'progress.json'
            rating_path.write_text(json.dumps(rating_template(self.packet)))
            base = [str(FIXTURE/'manifest.json'), str(ROOT/'experiments/reply-union-2026-11-13/results.json'),
                    str(FIXTURE/'criteria.json'), '--seed', '17', '--ratings', str(rating_path)]
            with contextlib.redirect_stdout(io.StringIO()):
                main(['progress', *base, '--output', str(output)])
            self.assertEqual(0, json.loads(output.read_text())['rated'])
            score = Path(directory)/'score.json'
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(['score', *base, '--output', str(score)])
            self.assertFalse(score.exists())
