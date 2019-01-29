import os
import sys
import json
import pymongo
import requests
import os.path
from urllib.parse import parse_qs
from .config import providers, audio_uri
from . import ld_converter


descriptors = ['chords', 'instruments', 'beats-beatroot', 'keys', 'tempo', 'global-key', 'tuning', 'beats']
# Candidate content-types: 'text/plain', 'text/n3', 'application/rdf+xml'
supported_output = {'chords': ['application/json', 'application/ld+json'],
                    'instruments': ['application/json'],
                    'beats-beatroot': ['application/json', 'application/ld+json'],
                    'keys': ['application/json', 'application/ld+json'],
                    'tempo': ['application/json'],
                    'global-key': ['application/json'],
                    'tuning': ['application/json'],
                    'beats': ['application/json'],
                    } # default output first
_client = None
_instrument_names = ['Shaker', 'Electronic Beats', 'Drum Kit', 'Synthesizer', 'Female Voice', 'Male Voice', 'Violin', 'Flute', 'Harpsichord', 'Electric Guitar', 'Clarinet', 'Choir', 'Organ', 'Acoustic Guitar', 'Viola', 'French Horn', 'Piano', 'Cello', 'Harp', 'Conga', 'Synthetic Bass', 'Electric Piano', 'Acoustic Bass', 'Electric Bass']


def handle(_):
    """handle a request to the function
    """
    args = parse_qs(os.getenv('Http_Query'))
    descriptor = os.getenv('Http_Path')[1:]
    if descriptor == 'providers':
        return json.dumps(providers)
    elif descriptor == 'descriptors':
        return json.dumps(descriptors)
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
        responses = []
        for ac_id in args['id']:
            try:
                provider, file_id = ac_id.split(':')
            except ValueError:
                return 'Malformed id "{}". Needs to be of the form "content-provider:provider-id"'.format(ac_id)
            if provider not in providers:
                return 'Unknown content provider "{}". Allowed providers are : {}'.format(provider, providers)
            req_descriptor = 'essentia-music' if descriptor in ['tempo', 'global-key', 'tuning', 'beats'] else descriptor
            response = analysis(provider, file_id, req_descriptor)
            if descriptor == 'tempo':
                response = {'tempo': response['rhythm']['bpm']}
            elif descriptor == 'global-key':
                most_likely_key = sorted([v for k, v in response['tonal'].items() if k.startswith('key_')], key=lambda v: v['strength'], reverse=True)[0]
                response = {'key': most_likely_key['key']+' '+most_likely_key['scale'], 'confidence': most_likely_key['strength']}
            elif descriptor == 'tuning':
                response = {'tuning': response['tonal']['tuning_frequency']}
            elif descriptor == 'beats':
                response = {'beats': response['rhythm']['beats_position']}
            elif descriptor == 'instruments':
                response = {'instruments': {k:v for k,v in zip(_instrument_names, response['annotations'][0]['data'][0]['value'])}}
            response['_id'] = ac_id
            responses.append(response)
        if len(responses) == 1:
            responses = responses[0]
        if content_type == 'application/json':
            return json.dumps(responses)
        elif content_type == 'application/ld+json':
            return json.dumps(ld_converter.convert(descriptor, file_id, responses, 'json-ld'))
        else:
            return responses


def analysis(provider, file_id, descriptor):
    db = _get_db()
    result = db.descriptors.find_one({'_id': '{}:{}'.format(provider, file_id), descriptor: {'$exists': True}})
    if result is not None:
        sys.stderr.write('Result found in DB\n')
        return result[descriptor]

    uri = audio_uri(file_id, provider)
    if descriptor == 'chords':
        result = requests.post('http://gateway:8080/function/confident-chord-estimator', data=uri)
    elif descriptor == 'instruments':
        sa_arg = '-t transforms/instrument-probabilities.n3 -w jams --jams-stdout {}'.format(uri)
        result = requests.post('http://gateway:8080/function/instrument-identifier', data=sa_arg)
    elif descriptor == 'essentia-music':
        result = requests.post('http://gateway:8080/function/essentia', data=uri)
    else:
        sa_arg = '-t transforms/{}.n3 -w jams --jams-stdout {}'.format(descriptor, uri)
        sys.stderr.write('Calling sonic-annotator {}\n'.format(sa_arg))
        result = requests.get('http://gateway:8080/function/sonic-annotator', data=sa_arg)
    if result.status_code != requests.codes.ok:
        sys.stderr.write('Calculation of "{}" failed with status code "{}"\n'.format(descriptor, result.status_code))
        return json.dumps({'status_code': result.status_code})

    result_content = result.json()

    r = db.descriptors.update_one({'_id': '{}:{}'.format(provider, file_id)}, {'$set': {descriptor: result_content}}, upsert=True)
    sys.stderr.write('Result stored in DB: {}\n'.format(r.raw_result))
    return result_content


def _get_db():
    global _client
    if _client is None:
        sys.stderr.write('Connecting to DB\n')
        _client = pymongo.MongoClient(os.getenv('MONGO_CONNECTION'))
    sys.stderr.write('Connected to DB: {}\n'.format(_client))
    return _client.ac_analysis_service
