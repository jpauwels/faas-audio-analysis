# -*- coding: utf-8 -*-
import openl3
import soundfile as sf
import logging
import tempfile
from collections.abc import Mapping
from urllib.error import HTTPError


logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class LazyModelLoader(Mapping):
    def __init__(self):
        self._data = {}

    def __getitem__(self, key):
        input_repr, content_type, embedding_size = key
        if key not in self._data:
            self._data[key] = openl3.models.load_audio_embedding_model(input_repr=input_repr, content_type=content_type, embedding_size=embedding_size)
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._input_repr) * len(self._content_type) * len(self._embedding_size)

_models = LazyModelLoader()


def lambda_handler(event, context):
    method = event.get('requestContext', {}).get('http', {}).get('method')
    body = event.get('body')
    query = event.get('queryStringParameters', {})
    try:
        if method != 'POST' or not body:
                raise HTTPError(None, 400, 'Expecting audio file to be POSTed', None, None)
        input_repr = query.get('input-repr', 'mel128')
        if input_repr not in ('linear', 'mel128', 'mel256'):
            raise HTTPError(None, 400, 'Input representation needs to be "linear", "mel128", or "mel256"', None, None)
        content_type = query.get('content-type', 'music')
        if content_type not in ('env', 'music'):
            raise HTTPError(None, 400, 'Content type needs to be "env" or "music"', None, None)
        if query.get('embedding-size', '512') not in ('512', '6144'):
            raise HTTPError(None, 400, 'Embedding size needs to be 512 or 6144', None, None)
        embedding_size = int(query.get('embedding-size', '512'))
        mean = query.get('mean', 'true').lower() in ('y', 'yes', 'on', '1', 'true', 't')

        with tempfile.NamedTemporaryFile('wb') as audio_file:
            audio_file.write(body)
            audio, sample_rate = sf.read(audio_file.name)
        embedding, _ = openl3.get_audio_embedding(audio, sample_rate, model=_models[input_repr, content_type, embedding_size], center=True, hop_size=0.1, batch_size=32, verbose=False)

        return {
            'statusCode': 200,
            'body': embedding.mean(axis=0).tolist() if mean else embedding.tolist(),
        }
    except HTTPError as err:
        return {
            'statusCode': err.code,
            'body': {'error': err.msg},
        }
    except Exception as err:
        logger.error('Error in open-l3 function', exc_info=err)
        return {
            'statusCode': 500,
            'body': {'error': 'Internal server error in open-l3 function'},
        }
