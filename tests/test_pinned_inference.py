from dataclasses import replace
import unittest
from unittest.mock import patch

from personal_context.generation import generate
from personal_context.local_model import OllamaProvider, LocalModelError
from personal_context.local_embeddings import OllamaEmbeddingProvider
import test_local_model as chat
import test_local_embeddings as embedding


class PinnedChatTests(unittest.TestCase):
    setUp = chat.LocalModelTests.setUp
    cleanup = chat.LocalModelTests.cleanup
    def test_response_model_and_post_request_runtime_changes_are_rejected(self):
        config=replace(self.config,expected_digest='a'*64)
        identity=dict(model=config.model,digest='a'*64,runtime_version='1')
        self.payload['model']=config.model
        with patch('personal_context.local_identity.inspect_model',return_value=identity):
            result=generate(self.engine,self.request,OllamaProvider(config))
        self.assertEqual(identity,result['generation_provenance']['model_identity'])
        self.payload['model']='different:tag'
        with patch('personal_context.local_identity.inspect_model',return_value=identity):
            with self.assertRaisesRegex(LocalModelError,'pinned model'):
                generate(self.engine,self.request,OllamaProvider(config))
        self.payload['model']=config.model
        with patch('personal_context.local_identity.inspect_model',side_effect=[identity,identity,identity|dict(runtime_version='changed')]):
            with self.assertRaisesRegex(LocalModelError,'identity changed'):
                generate(self.engine,self.request,OllamaProvider(config))


class PinnedEmbeddingTests(unittest.TestCase):
    setUp = embedding.LocalEmbeddingTests.setUp
    cleanup = embedding.LocalEmbeddingTests.cleanup
    def test_embedding_digest_is_checked_on_both_sides_of_request(self):
        config=replace(self.config,expected_digest='a'*64)
        identity=dict(model=config.model,digest='a'*64,runtime_version='1')
        self.payload['model']=config.model
        with patch('personal_context.local_identity.inspect_model',return_value=identity) as inspector:
            self.assertEqual([[.6,.8],[0.,1.]],OllamaEmbeddingProvider(config).embed(['a','b']))
            self.assertEqual(2,inspector.call_count)
        with patch('personal_context.local_identity.inspect_model',side_effect=[identity,identity|dict(digest='b'*64)]):
            with self.assertRaisesRegex(LocalModelError,'identity changed'):
                OllamaEmbeddingProvider(config).embed(['a','b'])
        self.payload['model']='wrong:tag'
        with patch('personal_context.local_identity.inspect_model',return_value=identity):
            with self.assertRaisesRegex(LocalModelError,'pinned model'):
                OllamaEmbeddingProvider(config).embed(['a','b'])
