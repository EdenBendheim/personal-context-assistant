import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from personal_context.draft_cli import main
from personal_context.generation import GeneratedProposal
from personal_context.local_model import LocalModelError
from personal_context.review_server import ReviewServer
from personal_context.store import Store
from test_generation import Provider,proposal
from test_reviews import seed,OWNER,CONTACT
import test_review_server as fixtures


class GenerationEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.db=Path(self.directory.name)/'store.sqlite'
        store=Store(str(self.db));seed(store);store.close()
        self.server=ReviewServer(self.db,owner=OWNER,provider=Provider(proposal()))
        self.thread=Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown();self.thread.join();self.server.server_close();self.directory.cleanup()

    call=fixtures.ServerTests.call
    create=fixtures.ServerTests.create

    def test_fixed_provider_config_and_support_feedback_are_exposed_without_request_override(self):
        status,config,_=self.call('/api/config');self.assertEqual(200,status)
        self.assertEqual('generative',config['drafting']);self.assertFalse(config['sending_available'])
        self.assertEqual(401,self.call('/api/config',headers={'Authorization':''})[0])
        status,review,_=self.create();self.assertEqual(200,status)
        self.assertEqual('generative',review['original']['generation_kind']);path='/api/reviews/'+review['review_id']
        self.assertEqual(400,self.call(path+'/feedback',dict(expected_revision=1,decision='usable'))[0])
        self.assertEqual(200,self.call(path+'/feedback',dict(expected_revision=1,decision='usable',support='supported'))[0])
        self.assertEqual('supported',self.call(path)[1]['feedback'][0]['support'])
        self.assertEqual(400,self.call('/api/reviews',dict(contact=CONTACT,before='2026-09-04T00:00:00Z',query='demo',provider='external'))[0])
        self.server.provider=None;self.assertEqual('extractive',self.call('/api/config')[1]['drafting'])

    def test_model_failure_and_abstention_do_not_persist_fake_success(self):
        class Failed:
            def generate(self,packet):raise LocalModelError('Local model unavailable')
        self.server.provider=Failed();self.assertEqual(503,self.create()[0])
        self.assertEqual([],self.call('/api/reviews?contact='+CONTACT)[1])
        self.server.provider=Provider(GeneratedProposal(abstain_reason='Need confirmation'))
        self.assertEqual('provider_abstained',self.create()[1]['status'])
        self.assertEqual([],self.call('/api/reviews?contact='+CONTACT)[1])

    def test_cli_opt_in_default_and_failed_generation_have_no_fallback(self):
        base=['draft','--db',str(self.db),'--owner',OWNER,'--contact',CONTACT,'--before','2026-09-04T00:00:00Z','--query','demo']
        output=io.StringIO()
        with patch.object(sys,'argv',base),contextlib.redirect_stdout(output):main()
        self.assertEqual('ExtractiveProvider',json.loads(output.getvalue())['provider'])
        for options in (['--confirm-local-only'],['--local-model','fixture'],['--model-timeout','2'],
                ['--draft-prompt','grounded-draft-v5'],['--response-format','prompt_only']):
            with patch.object(sys,'argv',base+options),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):main()
        output=io.StringIO()
        with patch.object(sys,'argv',base+['--local-model','fixture','--confirm-local-only']),\
                patch('personal_context.local_model.OllamaProvider.generate',return_value=proposal()),contextlib.redirect_stdout(output):main()
        self.assertEqual('generative',json.loads(output.getvalue())['generation_kind'])
        with patch.object(sys,'argv',base+['--local-model','fixture','--confirm-local-only']),\
                patch('personal_context.local_model.OllamaProvider.generate',side_effect=LocalModelError('Unavailable')),\
                contextlib.redirect_stderr(io.StringIO()),contextlib.redirect_stdout(io.StringIO()) as out,self.assertRaises(SystemExit):main()
        self.assertEqual('',out.getvalue())

    def test_experimental_cli_configuration_is_saved_and_server_launch_is_fixed(self):
        import argparse
        from personal_context.model_options import add_model_options, configured_provider
        options = ['--local-model','fixture','--confirm-local-only',
                   '--draft-prompt','grounded-draft-v5','--response-format','prompt_only']
        args = ['draft','--db',str(self.db),'--owner',OWNER,'--contact',CONTACT,
                '--before','2026-09-04T00:00:00Z','--query','demo'] + options
        with patch.object(sys,'argv',args), contextlib.redirect_stdout(io.StringIO()) as output, \
                patch('personal_context.local_model.OllamaProvider.generate',return_value=proposal()):
            main()
        provenance = json.loads(output.getvalue())['generation_provenance']
        self.assertEqual('grounded-draft-v5', provenance['prompt_version'])
        self.assertEqual('prompt_only', provenance['response_format'])
        parser = argparse.ArgumentParser()
        add_model_options(parser)
        self.server.provider = configured_provider(parser.parse_args(options))
        config = self.call('/api/config')[1]['configuration']
        self.assertEqual(provenance, config)
        for name, value in (('draft_prompt','grounded-draft-v4'),('response_format','union_schema')):
            self.assertEqual(400, self.call('/api/reviews',dict(contact=CONTACT,
                before='2026-09-04T00:00:00Z',query='demo',**{name:value}))[0])

    def test_reply_task_round_trips_cli_http_and_saved_review_with_support_gate(self):
        task = dict(current_message='Could you confirm the demo topic?', intent='Thank them and ask about the agenda.')
        payload = dict(contact=CONTACT, before='2026-09-04T00:00:00Z', query='demo', **task)
        status, saved, _ = self.call('/api/reviews', payload)
        self.assertEqual(200, status)
        reopened = self.call('/api/reviews/'+saved['review_id'])[1]
        self.assertTrue(reopened['context_current'])
        for key, value in task.items():
            self.assertEqual(value, reopened['original']['packet']['request'][key])
        self.assertEqual(400, self.call('/api/reviews/'+saved['review_id']+'/feedback',
            dict(expected_revision=1, decision='usable'))[0])
        self.assertEqual(400, self.call('/api/reviews', payload | dict(intent='x'*501))[0])
        args = ['draft', '--db', str(self.db), '--owner', OWNER, '--contact', CONTACT,
            '--before', payload['before'], '--query', 'demo', '--current-message', task['current_message'], '--intent', task['intent']]
        with patch('sys.argv', args), contextlib.redirect_stdout(io.StringIO()) as output:
            main()
        request = json.loads(output.getvalue())['packet']['request']
        self.assertTrue(all(request[key] == value for key, value in task.items()))
