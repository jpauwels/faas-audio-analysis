import os
import sys
import itertools
import logging
from accept_types import get_best_match
import pymongo
import requests
from requests.exceptions import HTTPError
import os.path
from urllib.parse import urlsplit
from base64 import b64encode
from . import config
from . import ld_converter
from .secrets import get_secrets


logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


# Candidate content-types: 'text/plain', 'text/n3', 'application/rdf+xml'
supported_output = {
    'chords': ['application/json', 'application/ld+json'],
    'instruments': ['application/json'],
    'keys': ['application/json'],
    'tempo': ['application/json'],
    'global-key': ['application/json'],
    'tuning': ['application/json'],
    'beats': ['application/json'],
    'mood': ['application/json'],
}
_descriptor_mapping = {
    'tempo': 'essentia-music',
    'global-key': 'essentia-music',
    'tuning': 'essentia-music',
    'beats': 'essentia-music'
}
_client = None
_instrument_names = ['Shaker', 'Electronic Beats', 'Drum Kit', 'Synthesizer', 'Female Voice', 'Male Voice', 'Violin', 'Flute', 'Harpsichord', 'Electric Guitar', 'Clarinet', 'Choir', 'Organ', 'Acoustic Guitar', 'Viola', 'French Horn', 'Piano', 'Cello', 'Harp', 'Conga', 'Synthetic Bass', 'Electric Piano', 'Acoustic Bass', 'Electric Bass']
_secrets = get_secrets(['database-connection'])


def lambda_handler(event, context):
    """handle a request to the function
    """
    method = event.get('requestContext', {}).get('http', {}).get('method')
    body = event.get('body')
    path = event['rawPath']
    query = event.get('queryStringParameters', {})
    headers = event['headers']
    try:
        if method == 'GET':
            if path == '/descriptors':
                return {
                    'statusCode': 200,
                    'body': list(supported_output.keys()),
                }
            if path == '/collections':
                return {
                    'statusCode': 200,
                    'body': config.all_collections,
                }
            if body:
                raise HTTPError(400, 'Unexpected body in request. Perhaps you meant to POST?')
            try:
                collection, named_ids = path.strip('/').split('/', 1)
            except ValueError:
                raise HTTPError(204, 'Nothing to do')
            if collection not in config.all_collections:
                raise HTTPError(400, 'Unknown collection "{}"'.format(collection))
            if named_ids == 'namespaces':
                return {
                    'statusCode': 200,
                    'body': config.namespaces.get(collection, []),
                }
            named_ids = named_ids.split(',')
        elif method == 'POST':
            if not body:
                raise HTTPError(400, 'Missing audio body')
            named_ids = [path.lstrip('/')]
        else:
            raise HTTPError(405, f'{method} Method Not Allowed')

        try:
            descriptors = query['descriptors'].split(',')
            unknown_descriptors = list(filter(lambda d: d not in supported_output.keys(), descriptors))
            if unknown_descriptors:
                raise HTTPError(400, 'Unknown descriptor{} "{}". Allowed descriptors are : "{}"'.format(
                    's' if len(unknown_descriptors) > 1 else '', '", "'.join(unknown_descriptors), '", "'.join(supported_output.keys())
                ))
        except KeyError:
            descriptors = list(supported_output.keys())

        accept_header = headers.get('accept', '*/*')
        acceptables = [s for s in supported_output[descriptors[0]] if all([s in supported_output[k] for k in descriptors[1:]])]
        mime_type = get_best_match(accept_header, acceptables)
        if not mime_type:
            raise HTTPError(406, 'No MIME type in "{}" acceptable for descriptor{} "{}". The accepted type{} "{}".'.format(
                accept_header,
                's' if len(descriptors) > 1 else '',
                '", "'.join(descriptors),
                's are' if len(acceptables) > 1 else ' is',
                '", "'.join(sorted(acceptables))
            ))

        response_list = []
        mapped_descriptors = {_descriptor_mapping.get(d, d) for d in descriptors}
        for named_id in named_ids:
            response = {'id': named_id}

            result = {}
            for descriptor in mapped_descriptors:
                if method == 'POST':
                    result[descriptor] = calculate_descriptor(named_id, body, descriptor)
                else:
                    overwrite = query.get('overwrite', 'n').lower() in ('y', 'yes', 'on', '1', 'true', 't')
                    result[descriptor] = get_descriptor(collection, named_id, descriptor, overwrite)

            for descriptor in descriptors:
                response[descriptor] = format_descriptor_output(descriptor, result[_descriptor_mapping.get(descriptor, descriptor)])

            if mime_type == 'application/ld+json':
                response = ld_converter.convert(descriptors, response, 'json-ld')

            if len(named_ids) == 1:
                return {
                    'statusCode': 200,
                    'body': response,
                }
            response_list.append(response)

        return {
            'statusCode': 200,
            'body': response_list,
        }
    except HTTPError as e:
        return {
            'statusCode': e.errno,
            'body': {'error': e.strerror},
        }
    except Exception as err:
        logger.error('Error in analysis function', exc_info=err)
        return {
            'statusCode': 500,
            'body': {'error': 'Internal server error in analysis function'},
        }


def format_descriptor_output(descriptor, result):
    if descriptor == 'tempo':
        return result['rhythm']['bpm']
    if descriptor == 'global-key':
        most_likely_key = sorted([v for k, v in result['tonal'].items() if k.startswith('key_')], key=lambda v: v['strength'], reverse=True)[0]
        return {'key': most_likely_key['key']+' '+most_likely_key['scale'], 'confidence': most_likely_key['strength']}
    if descriptor == 'tuning':
        return result['tonal']['tuning_frequency']
    if descriptor == 'beats':
        return result['rhythm']['beats_position']
    if descriptor == 'instruments':
        return {k:v for k,v in zip(_instrument_names, result['annotations'][0]['data'][0]['value'])}
    if descriptor == 'chords':
        result.pop('chordRatio')
        result.pop('distinctChords')
        return result
    if descriptor == 'keys':
        return [{'time': k['time'], 'label': k['label']} for k in result['annotations'][0]['data']]
    if descriptor == 'mood':
        renamed_result = {k.lstrip('mood_').split('-')[0]: v for k, v in result.items()}
        return {name: values[1] if name in ('sad', 'relaxed') else values[0] for name, values in renamed_result.items()}
    else:
        return result


def get_descriptor(collection, named_id, descriptor, overwrite):
    db = _get_client()[collection]
    try:
        named_id = config.alias_id(collection, named_id, db)
    except Exception:
        pass
    if not overwrite:
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
        result = requests.post(f"{os.getenv('CHORD_API')}/{file_name}", data=audio_content)
    elif descriptor == 'essentia-music':
        result = requests.post(f"{os.getenv('ESSENTIA_API')}/{file_name}", data=audio_content, headers={'Content-Type': 'audio/*'})
    elif descriptor == 'mood':
        model_names = [f'mood_{emotion}-{architecture}-{dataset}-2' for emotion, architecture, dataset in itertools.product(['aggressive', 'happy', 'relaxed', 'sad'], ['musicnn'], ['mtt'])] #, 'vgg'], ['msd', 'mtt'])]
        result = requests.post(f"{os.getenv('ESSENTIA_TF_MODELS_API')}/{'/'.join(model_names)}", data=audio_content)
    elif descriptor == 'instruments':
        sa_arg = {'-t': '/home/app/transforms/instrument-probabilities.n3', '-w': 'jams', '--jams-stdout': ''}
        result = requests.post(f"{os.getenv('INSTRUMENTS_API')}/instrument-identifier", data={'audio_data': b64encode(audio_content), 'audio_path': file_name}, params=sa_arg)
    else:
        sa_arg = {'-t': '/home/app/transforms/{}.n3'.format(descriptor), '-w': 'jams', '--jams-stdout': ''}
        result = requests.post(f"{os.getenv('SONIC_ANNOTATOR_API')}/sonic-annotator", data={'audio_data': b64encode(audio_content), 'audio_path': file_name}, params=sa_arg)

    if result.status_code != requests.codes.ok or len(result.text) == 0:
        raise HTTPError(502, 'Calculation of "{}" failed'.format(descriptor))
    return result.json()


def _get_client():
    global _client
    if _client is None:
        sys.stderr.write('Connecting to DB\n')
        _client = pymongo.MongoClient(_secrets['database-connection'])
    sys.stderr.write('Connected to DB: {}\n'.format(_client))
    return _client
