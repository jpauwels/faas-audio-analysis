import os
import sys
import json
import pymongo
import requests
import os.path
from urllib.parse import parse_qs
from .config import providers, audio_uri


descriptors = ['chords', 'instruments', 'beats-beatroot', 'keys']
content_types = ['application/json', 'text/plain', 'text/rdf', 'text/csv'] #'audiodb', 'default', 'jams', 'lab', 'midi']
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
        content_type = os.getenv('Http_Content_Type')
        if content_type not in content_types:
            return 'Unknown content type "{}" requested. Allowed content types are: {}'.format(content_type, content_types)

        if descriptor not in descriptors:
            return 'Unknown descriptor "{}". Allowed descriptors are : {}'.format(descriptor, descriptors)
        response = []
        for ld_id in args['id']:
            try:
                provider, file_id = ld_id.split(':')
            except ValueError:
                return 'Malformed id. Needs to be of the form "content-provider:file_id"'
            if provider not in providers:
                return 'Unknown content provider "{}". Allowed providers are : {}'.format(provider, providers)
            response.append(analysis(provider, file_id, descriptor, os.path.basename(content_type)))
        if content_type == 'application/json':
            return json.dumps(response)
        else:
            return response


def analysis(provider, file_id, descriptor, writer):
    db = _get_db()
    result = db[provider].find_one({'_id': file_id, '{}.{}'.format(descriptor, writer): {'$exists': True}})
    if result is not None:
        sys.stderr.write('Result found in DB\n')
        return result[descriptor][writer]
    else:
        uri = audio_uri(file_id, provider)
        if descriptor == 'chords':
            if writer != 'json':
                return 'Only "json" content type supported for "chords" descriptor'
            result = requests.post('http://gateway:8080/function/confident-chord-estimator', data=uri)
        elif descriptor == 'instruments':
            if writer not in ['csv', 'rdf']:
                return 'Only "rdf" and "csv" content types supported for "instruments" descriptor'
            sa_arg = '-t transforms/instrument-probabilities.n3 -w {writer} --{writer}-stdout {uri}'.format(writer=writer, uri=uri)
            result = requests.post('http://gateway:8080/function/instrument-identifier', data=sa_arg)
        else:
            if writer not in ['csv', 'rdf']:
                return 'Only "rdf" and "csv" content types supported for "{}" descriptor'.format(descriptor)
            sa_arg = '-t transforms/{descriptor}.n3 -w {writer} --{writer}-stdout {uri}'.format(descriptor=descriptor, writer=writer, uri=uri)
            sys.stderr.write('Calling sonic-annotator {}\n'.format(sa_arg))
            result = requests.get('http://gateway:8080/function/sonic-annotator', data=sa_arg)
        if result.status_code == requests.codes.ok:
            if writer == 'json':
                result_content = result.json()
            else:
                result_content = result.text
            r = db[provider].update_one({'_id': file_id}, {'$set': {'{}.{}'.format(descriptor, writer): result_content}}, upsert=True)
            sys.stderr.write('Result stored in DB: {}\n'.format(r.raw_result))
            return result_content
        else:
            sys.stderr.write('Calculation of "{}" failed with status code "{}"\n'.format(descriptor, result.status_code))
            return json.dumps({'status_code': result.status_code})


def _get_db():
    global _client
    if _client is None:
        sys.stderr.write('Connecting to DB\n')
        _client = pymongo.MongoClient(os.getenv('MONGO_CONNECTION'))
    sys.stderr.write('Connected to DB: {}\n'.format(_client))
    return _client.ac_analysis_service
