import os
import sys
import json
import pymongo
import requests
from requests.exceptions import HTTPError
import os.path
from urllib.parse import parse_qsl, urlsplit, unquote
from . import config
from . import ld_converter


all_descriptors = ['chords', 'instruments', 'keys', 'tempo', 'global-key', 'tuning', 'beats']
# Candidate content-types: 'text/plain', 'text/n3', 'application/rdf+xml'
supported_output = {'chords': ['application/json', 'application/ld+json'],
                    'instruments': ['application/json'],
                    'keys': ['application/json'],
                    'tempo': ['application/json'],
                    'global-key': ['application/json'],
                    'tuning': ['application/json'],
                    'beats': ['application/json'],
                    }
_client = None
_instrument_names = ['Shaker', 'Electronic Beats', 'Drum Kit', 'Synthesizer', 'Female Voice', 'Male Voice', 'Violin', 'Flute', 'Harpsichord', 'Electric Guitar', 'Clarinet', 'Choir', 'Organ', 'Acoustic Guitar', 'Viola', 'French Horn', 'Piano', 'Cello', 'Harp', 'Conga', 'Synthetic Bass', 'Electric Piano', 'Acoustic Bass', 'Electric Bass']


def handle(audio_content):
    """handle a request to the function
    """
    try:
        query = dict(parse_qsl(unquote(os.getenv('Http_Query', ''))))
        if audio_content:
            descriptors = os.getenv('Http_Path', '').lstrip('/').split('/')
            named_id = query.get('id', 'undefined')
        else:
            collection, *descriptors = os.getenv('Http_Path', '').lstrip('/').split('/')
            if collection not in config.all_collections:
                raise HTTPError('Unknown collection "{}"'.format(collection))
            if 'namespaces' in descriptors:
                return json.dumps(config.namespaces[collection])
            elif 'id' in query:
                named_id = query['id']
            else:
                raise HTTPError('Nothing to do')

        if 'descriptors' in descriptors:
            return json.dumps(all_descriptors)
        elif 'all' in descriptors:
            descriptors = all_descriptors
        else:
            unknown_descriptors = list(filter(lambda d: d not in all_descriptors, descriptors))
            if unknown_descriptors:
                raise HTTPError('Unknown descriptor{} "{}". Allowed descriptors are : "{}"'.format(
                's' if len(unknown_descriptors) > 1 else '', '", "'.join(unknown_descriptors), '", "'.join(all_descriptors)))

        content_type = os.getenv('Http_Content_Type', 'application/json')
        unsupported_output = list(filter(lambda d: content_type not in supported_output[d], descriptors))
        if unsupported_output:
            raise HTTPError('Unsupported Content-Type "{}" for descriptor{} "{}"'.format(
            content_type, 
            's' if len(unsupported_output) > 1 else '',
            '"'+'", "'.join(unsupported_output)+'"'
            ))

        essentia_descriptors = []
        req_descriptors = []
        for descriptor in descriptors:
            if descriptor in ['tempo', 'global-key', 'tuning', 'beats']:
                essentia_descriptors.append(descriptor)
            else:
                req_descriptors.append(descriptor)
        if essentia_descriptors:
            req_descriptors.append('essentia-music')
        
        response = {'id': named_id}

        for descriptor in req_descriptors:
            if audio_content:
                result = calculate_descriptor(named_id, audio_content, descriptor)
            else:
                result = get_descriptor(collection, named_id, descriptor)
            if descriptor == 'essentia-music':
                response.update(essentia_descriptor_output(essentia_descriptors, result))
            else:
                response[descriptor] = rewrite_descriptor_output(descriptor, result)
        
        if content_type == 'application/json':
            return json.dumps(response)
        elif content_type == 'application/ld+json':
            return json.dumps(ld_converter.convert(descriptors, response, 'json-ld'))
    except HTTPError as e:
        return json.dumps(str(e))


def essentia_descriptor_output(essentia_descriptors, result):
    response = {}
    if 'tempo' in essentia_descriptors:
        response['tempo'] = result['rhythm']['bpm']
    if 'global-key' in essentia_descriptors:
        most_likely_key = sorted([v for k, v in result['tonal'].items() if k.startswith('key_')], key=lambda v: v['strength'], reverse=True)[0]
        response['global-key'] = {'key': most_likely_key['key']+' '+most_likely_key['scale'], 'confidence': most_likely_key['strength']}
    if 'tuning' in essentia_descriptors:
        response['tuning'] = result['tonal']['tuning_frequency']
    if 'beats' in essentia_descriptors:
        response['beats'] = result['rhythm']['beats_position']
    return response


def rewrite_descriptor_output(descriptor, result):
    if descriptor == 'instruments':
        response = {k:v for k,v in zip(_instrument_names, result['annotations'][0]['data'][0]['value'])}
    elif descriptor == 'chords':
        result.pop('chordRatio')
        result.pop('distinctChords')
        response = result
    elif descriptor == 'keys':
        response = [{'time': k['time'], 'label': k['label']} for k in result['annotations'][0]['data']]
    else:
        response = result
    return response


def get_descriptor(collection, named_id, descriptor):
    db = _get_client()[collection]
    try:
        named_id = config.alias_id(collection, named_id, db)
    except:
        pass
    result = db.descriptors.find_one({'_id': named_id, descriptor: {'$exists': True}})
    if result is not None:
        sys.stderr.write('Result found in DB\n')
        return result[descriptor]

    try:
        uri = config.audio_uri(collection, named_id)
    except Exception as e:
        raise HTTPError(e)
    file_name = os.path.basename(urlsplit(uri).path)
    audio_content = requests.get(uri).content

    result_content = calculate_descriptor(file_name, audio_content, descriptor)

    r = db.descriptors.update_one({'_id': named_id}, {'$set': {descriptor: result_content}}, upsert=True)
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


def _get_client():
    global _client
    if _client is None:
        sys.stderr.write('Connecting to DB\n')
        _client = pymongo.MongoClient(os.getenv('MONGO_CONNECTION'))
    sys.stderr.write('Connected to DB: {}\n'.format(_client))
    return _client
