import os
import sys
import json
import pymongo
import requests
from requests.exceptions import HTTPError
import os.path
from urllib.parse import parse_qsl, urlsplit
from .config import providers, audio_uri
from . import ld_converter


descriptors = ['chords', 'instruments', 'beats-beatroot', 'keys', 'tempo', 'global-key', 'tuning', 'beats']
# Candidate content-types: 'text/plain', 'text/n3', 'application/rdf+xml'
supported_output = {'chords': ['application/json', 'application/ld+json'],
                    'instruments': ['application/json'],
                    'beats-beatroot': ['application/json', 'application/ld+json'],
                    'keys': ['application/json'],
                    'tempo': ['application/json'],
                    'global-key': ['application/json'],
                    'tuning': ['application/json'],
                    'beats': ['application/json'],
                    } # default output first
_client = None
_instrument_names = ['Shaker', 'Electronic Beats', 'Drum Kit', 'Synthesizer', 'Female Voice', 'Male Voice', 'Violin', 'Flute', 'Harpsichord', 'Electric Guitar', 'Clarinet', 'Choir', 'Organ', 'Acoustic Guitar', 'Viola', 'French Horn', 'Piano', 'Cello', 'Harp', 'Conga', 'Synthetic Bass', 'Electric Piano', 'Acoustic Bass', 'Electric Bass']


def handle(audio_content):
    """handle a request to the function
    """
    try:
        descriptor = os.getenv('Http_Path', '').lstrip('/')
        if descriptor == 'providers':
            return json.dumps(providers)
        elif descriptor == 'descriptors':
            return json.dumps(descriptors)
        elif descriptor not in descriptors:
            raise HTTPError('Unknown descriptor "{}". Allowed descriptors are : {}'.format(descriptor, descriptors))

        content_type = os.getenv('Http_Content_Type')
        if content_type:
            if content_type not in supported_output[descriptor]:
                raise HTTPError('Only {} content-type{} are supported for the "{}" descriptor'.format(
                '"'+'", "'.join(supported_output[descriptor])+'"',
                's' if len(supported_output[descriptor]) > 1 else '',
                descriptor))
        else:
            content_type = supported_output[descriptor][0]

        query = dict(parse_qsl(os.getenv('Http_Query')))

        req_descriptor = 'essentia-music' if descriptor in ['tempo', 'global-key', 'tuning', 'beats'] else descriptor
        if audio_content:
            file_id = query.get('id', 'undefined')
            response = calculate_descriptor(file_id, audio_content, req_descriptor)
        elif 'id' in query:
            file_id = query['id']
            response = get_descriptor(file_id, req_descriptor)
        else:
            raise HTTPError('Nothing to do')
        response = rewrite_descriptor_output(descriptor, response)
        response['id'] = file_id
        
        if content_type == 'application/json':
            return json.dumps(response)
        elif content_type == 'application/ld+json':
            return json.dumps(ld_converter.convert(descriptor, response, 'json-ld'))
    except HTTPError as e:
        return json.dumps(str(e))


def rewrite_descriptor_output(descriptor, response):
    if descriptor == 'tempo':
        response = {'tempo': response['rhythm']['bpm']}
    elif descriptor == 'global-key':
        most_likely_key = sorted([v for k, v in response['tonal'].items() if k.startswith('key_')], key=lambda v: v['strength'], reverse=True)[0]
        response = {'global-key': {'key': most_likely_key['key']+' '+most_likely_key['scale'], 'confidence': most_likely_key['strength']}}
    elif descriptor == 'tuning':
        response = {'tuning': response['tonal']['tuning_frequency']}
    elif descriptor == 'beats':
        response = {'beats': response['rhythm']['beats_position']}
    elif descriptor == 'instruments':
        response = {'instruments': {k:v for k,v in zip(_instrument_names, response['annotations'][0]['data'][0]['value'])}}
    elif descriptor == 'chords':
        response.pop('chordRatio')
        response.pop('distinctChords')
        response = {'chords': response}
    elif descriptor == 'keys':
        response = {'keys': [{'time': k['time'], 'label': k['label']} for k in response['annotations'][0]['data']]}
    return response


def get_descriptor(linked_id, descriptor):
    db = _get_db()
    result = db.descriptors.find_one({'_id': linked_id, descriptor: {'$exists': True}})
    if result is not None:
        sys.stderr.write('Result found in DB\n')
        return result[descriptor]

    try:
        provider, provider_id = linked_id.split(':')
    except ValueError:
        raise HTTPError('Malformed id "{}". Needs to be of the form "content-provider:provider-id"'.format(linked_id))
    if provider not in providers:
        raise HTTPError('Unknown content provider "{}". Allowed providers are : {}'.format(provider, providers))
    uri = audio_uri(provider_id, provider)
    file_name = os.path.basename(urlsplit(uri).path)
    audio_content = requests.get(uri).content

    result_content = calculate_descriptor(file_name, audio_content, descriptor)

    r = db.descriptors.update_one({'_id': linked_id}, {'$set': {descriptor: result_content}}, upsert=True)
    sys.stderr.write('Result stored in DB: {}\n'.format(r.raw_result))
    return result_content


def calculate_descriptor(file_name, audio_content, descriptor):
    file_name = file_name.lstrip('/')
    if descriptor == 'chords':
        result = requests.get('http://gateway:8080/function/confident-chord-estimator/{}'.format(file_name), data=audio_content)
    elif descriptor == 'essentia-music':
        result = requests.get('http://gateway:8080/function/essentia/{}'.format(file_name), data=audio_content)
    elif descriptor == 'instruments':
        sa_arg = {'-t': '/home/app/transforms/instrument-probabilities.n3', '-w': 'jams', '--jams-stdout': ''}
        result = requests.get('http://gateway:8080/function/instrument-identifier/{}'.format(file_name), data=audio_content, params=sa_arg)
    else:
        sa_arg = {'-t': '/home/app/transforms/{}.n3'.format(descriptor), '-w': 'jams', '--jams-stdout': ''}
        result = requests.get('http://gateway:8080/function/sonic-annotator/{}'.format(file_name), data=audio_content, params=sa_arg)

    if result.status_code != requests.codes.ok or len(result.text) == 0:
        raise HTTPError('Calculation of "{}" failed'.format(descriptor))
    return result.json()


def _get_db():
    global _client
    if _client is None:
        sys.stderr.write('Connecting to DB\n')
        _client = pymongo.MongoClient(os.getenv('MONGO_CONNECTION'))
    sys.stderr.write('Connected to DB: {}\n'.format(_client))
    return _client.ac_analysis_service
