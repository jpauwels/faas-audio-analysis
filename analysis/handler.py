import os
import sys
import json
import itertools
from accept_types import get_best_match
import pymongo
import requests
from requests.exceptions import HTTPError
import os.path
from urllib.parse import parse_qsl, urlsplit, unquote
from . import config
from . import ld_converter


# Candidate content-types: 'text/plain', 'text/n3', 'application/rdf+xml'
supported_output = {'chords': ['application/json', 'application/ld+json'],
                    'instruments': ['application/json'],
                    'keys': ['application/json'],
                    'tempo': ['application/json'],
                    'global-key': ['application/json'],
                    'tuning': ['application/json'],
                    'beats': ['application/json'],
                    'mood': ['application/json'],
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
                raise HTTPError(400, 'Unknown collection "{}"'.format(collection))
            if 'namespaces' in descriptors:
                return json.dumps(config.namespaces[collection])
            elif 'descriptors' in descriptors:
                return json.dumps(list(supported_output.keys()))
            elif 'id' in query:
                named_id = query['id']
            else:
                raise HTTPError(204, 'Nothing to do')

        if 'all' in descriptors:
            descriptors = supported_output.keys()
        else:
            unknown_descriptors = list(filter(lambda d: d not in supported_output.keys(), descriptors))
            if unknown_descriptors:
                raise HTTPError(400, 'Unknown descriptor{} "{}". Allowed descriptors are : "{}"'.format(
                's' if len(unknown_descriptors) > 1 else '', '", "'.join(unknown_descriptors), '", "'.join(supported_output.keys())))

        accept_header = os.getenv('Http_Accept', '*/*')
        acceptables = set.intersection(*[set(supported_output[k]) for k in descriptors])
        mime_type = get_best_match(accept_header, acceptables)
        if not mime_type:
            raise HTTPError(406, 'No MIME type in "{}" acceptable for descriptor{} "{}". The accepted type{} "{}".'.format(
                accept_header, 
                's' if len(descriptors) > 1 else '',
                '", "'.join(descriptors),
                's are' if len(acceptables) > 1 else ' is',
                '", "'.join(sorted(acceptables))
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
        
        if mime_type == 'application/json':
            return json.dumps(response)
        elif mime_type == 'application/ld+json':
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
        raise HTTPError(404, str(e))
    file_name = os.path.basename(urlsplit(uri).path)
    audio_content = requests.get(uri).content

    result_content = calculate_descriptor(file_name, audio_content, descriptor)

    r = db.descriptors.update_one({'_id': named_id}, {'$set': {descriptor: result_content}}, upsert=True)
    sys.stderr.write('Result stored in DB: {}\n'.format(r.raw_result))
    return result_content


def calculate_descriptor(file_name, audio_content, descriptor):
    file_name = file_name.lstrip('/')
    if descriptor == 'chords':
        result = requests.get(f"{os.getenv('CHORD_API')}/{file_name}", data=audio_content)
    elif descriptor == 'essentia-music':
        result = requests.get(f"{os.getenv('ESSENTIA_API')}/{file_name}", data=audio_content)
    elif descriptor == 'mood':
        model_names = [f'mood_{emotion}-{architecture}-{dataset}-2' for emotion, architecture, dataset in itertools.product(['aggressive', 'happy', 'relaxed', 'sad'], ['musicnn', 'vgg'], ['msd', 'mtt'])]
        result = requests.post(f"{os.getenv('ESSENTIA_TF_MODELS_API')}/{'/'.join(model_names)}", data=audio_content)
    elif descriptor == 'instruments':
        sa_arg = {'-t': '/home/app/transforms/instrument-probabilities.n3', '-w': 'jams', '--jams-stdout': ''}
        result = requests.get(f"{os.getenv('INSTRUMENTS_API')}/{file_name}", data=audio_content, params=sa_arg)
    else:
        sa_arg = {'-t': '/home/app/transforms/{}.n3'.format(descriptor), '-w': 'jams', '--jams-stdout': ''}
        result = requests.get(f"{os.getenv('SONIC_ANNOTATOR_API')}/{file_name}", data=audio_content, params=sa_arg)

    if result.status_code != requests.codes.ok or len(result.text) == 0:
        raise HTTPError(502, 'Calculation of "{}" failed'.format(descriptor))
    return result.json()


def _get_client():
    global _client
    if _client is None:
        sys.stderr.write('Connecting to DB\n')
        _client = pymongo.MongoClient(os.getenv('MONGO_CONNECTION'))
    sys.stderr.write('Connected to DB: {}\n'.format(_client))
    return _client
