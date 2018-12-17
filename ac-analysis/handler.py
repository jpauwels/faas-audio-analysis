import os
import sys
import json
import pymongo
import requests
import os.path
from urllib.parse import parse_qs
from .config import providers, audio_uri
from . import ld_converter


descriptors = ['chords', 'instruments', 'beats-beatroot', 'keys', 'essentia-music']
# Candidate content-types: 'text/plain', 'text/n3', 'application/rdf+xml'
supported_output = {'chords': ['application/json', 'application/ld+json'],
                    'instruments': ['application/json', 'text/csv', 'text/turtle'],
                    'beats-beatroot': ['application/json', 'text/csv', 'text/turtle'],
                    'keys': ['application/json', 'text/csv', 'text/turtle'],
                    'essentia-music': ['application/json']} # default output first
_client = None


def handle(_):
    """handle a request to the function
    """
    args = parse_qs(os.getenv('Http_Query'))
    descriptor = os.path.relpath(os.getenv('Http_Path'), '/')
    if descriptor == 'register':
        pass
    elif descriptor == 'providers':
        pass
    elif descriptor == 'descriptors':
        pass
    else:
        if descriptor not in descriptors:
            return 'Unknown descriptor "{}". Allowed descriptors are : {}'.format(descriptor, descriptors)
        content_type = os.getenv('Http_Content_Type')
        if content_type:
            if content_type not in supported_output[descriptor]:
                return 'Only {} content-type{} are supported for the "{}" descriptor'.format(
                '"'+'", "'.join(supported_output[descriptor])+'"',
                's' if len(supported_output[descriptor]) > 1 else '',
                descriptor)
        else:
            content_type = supported_output[descriptor][0]
        response = []
        for ld_id in args['id']:
            try:
                provider, file_id = ld_id.split(':')
            except ValueError:
                return 'Malformed id. Needs to be of the form "content-provider:file_id"'
            if provider not in providers:
                return 'Unknown content provider "{}". Allowed providers are : {}'.format(provider, providers)
            response.append(analysis(provider, file_id, descriptor, os.path.basename(content_type)))
        if len(response) == 1:
            response = response[0]
        if content_type in ['application/json', 'application/ld+json']:
            return json.dumps(response)
        else:
            return response


def analysis(provider, file_id, descriptor, output_format):
    db = _get_db()
    result = db[provider].find_one({'_id': file_id, '{}.{}'.format(descriptor, output_format): {'$exists': True}})
    if result is not None:
        sys.stderr.write('Result found in DB\n')
        return result[descriptor][output_format]
    else:
        uri = audio_uri(file_id, provider)
        if descriptor == 'chords':
            result = requests.post('http://gateway:8080/function/confident-chord-estimator', data=uri)
        elif descriptor == 'instruments':
            sa_arg = '-t transforms/instrument-probabilities.n3 -w {writer} --{writer}-stdout {uri}'.format(writer=_sa_writers[output_format], uri=uri)
            result = requests.post('http://gateway:8080/function/instrument-identifier', data=sa_arg)
        elif descriptor == 'essentia-music':
            result = requests.post('http://gateway:8080/function/essentia', data=uri)
        else:
            sa_arg = '-t transforms/{descriptor}.n3 -w {writer} --{writer}-stdout {uri}'.format(descriptor=descriptor, writer=_sa_writers[output_format], uri=uri)
            sys.stderr.write('Calling sonic-annotator {}\n'.format(sa_arg))
            result = requests.get('http://gateway:8080/function/sonic-annotator', data=sa_arg)
        if result.status_code == requests.codes.ok:
            if output_format in ['json', 'ld+json']:
                result_content = result.json()
                if output_format == 'ld+json':
                    result_content = json.loads(ld_converter.convert(descriptor, file_id, result_content, 'json-ld'))
            else:
                result_content = result.text
            r = db[provider].update_one({'_id': file_id}, {'$set': {'{}.{}'.format(descriptor, output_format): result_content}}, upsert=True)
            sys.stderr.write('Result stored in DB: {}\n'.format(r.raw_result))
            return result_content
        else:
            sys.stderr.write('Calculation of "{}" failed with status code "{}"\n'.format(descriptor, result.status_code))
            return json.dumps({'status_code': result.status_code})


_sa_writers = {
    'octet-stream': 'audiodb',
    'csv': 'csv',
    'xml': 'default',
    'json': 'jams',
    'tab-separated-values': 'lab',
    'midi': 'midi',
    'turtle': 'rdf'
}


def _get_db():
    global _client
    if _client is None:
        sys.stderr.write('Connecting to DB\n')
        _client = pymongo.MongoClient(os.getenv('MONGO_CONNECTION'))
    sys.stderr.write('Connected to DB: {}\n'.format(_client))
    return _client.ac_analysis_service
