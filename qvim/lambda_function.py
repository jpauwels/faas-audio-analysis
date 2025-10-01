# -*- coding: utf-8 -*-
import onnxruntime as ort
import soundfile as sf
import logging
import tempfile
from urllib.error import HTTPError


logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


_session = ort.InferenceSession('/home/app/function/thatsoundslike-me.onnx')


def lambda_handler(event, context):
    method = event.get('requestContext', {}).get('http', {}).get('method')
    body = event.get('body')
    try:
        if method != 'POST' or not body:
                raise HTTPError(None, 400, 'Expecting audio file to be POSTed', None, None)

        with tempfile.NamedTemporaryFile('wb') as audio_file:
            audio_file.write(body)
            audio, _ = sf.read(audio_file.name, dtype='float32', always_2d=True)
        mono_audio = audio.mean(axis=1, keepdims=True).T
        embedding = _session.run(None, {'waveform': mono_audio})[0][0]

        return {
            'statusCode': 200,
            'body': embedding.tolist(),
        }
    except HTTPError as err:
        return {
            'statusCode': err.code,
            'body': {'error': err.msg},
        }
    except Exception as err:
        logger.error('Error in qvim function', exc_info=err)
        return {
            'statusCode': 500,
            'body': {'error': 'Internal server error in qvim function'},
        }
