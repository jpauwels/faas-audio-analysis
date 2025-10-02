import json
import os
import re
import logging
import requests
from requests.exceptions import HTTPError
from .config import all_collections, namespaces
from . import database


logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


all_descriptors = ['chords', 'tempo', 'tuning', 'global-key', 'duration', 'dominant-mood', 'embedding']
_num_operator_regex = re.compile(r'^(<=|>=|<|>)(\d+(\.\d*)?)$')
_num_tolerance_regex = re.compile(r'^(\d+(\.\d*)?) -(\d+(\.\d+)?)%$')
_num_range_regex = re.compile(r'^(\d+(\.\d*)?)-(\d+(\.\d+)?)$')
_key_regex = re.compile('^(C#|F#|Ab|Bb|Eb|[A-G])?(major|minor)?$')
_chord_regex = re.compile('^(Ab|Bb|Db|Eb|Gb|[A-G])(maj|min|7|maj7|min7)$')
_moods = ('agressive', 'happy', 'relaxed', 'sad')


def lambda_handler(event, context):
    method = event.get('requestContext', {}).get('http', {}).get('method')
    body = event.get('body')
    path = event['rawPath']
    query = event.get('queryStringParameters', {})
    headers = event['headers']
    try:
        if path == '/descriptors':
            return {
                'statusCode': 200,
                'body': all_descriptors,
            }
        if path == '/collections':
            return {
                'statusCode': 200,
                'body': all_collections,
            }
        collection, *req_namespaces = path.strip('/').split('/')
        if collection not in all_collections:
            raise HTTPError(400, 'Unknown collection "{}"'.format(collection))
        if 'namespaces' in req_namespaces:
            return {
                'statusCode': 200,
                'body': namespaces.get(collection, []),
            }
        unknown_namespaces = list(filter(lambda p: p not in namespaces.get(collection, []), req_namespaces))
        if unknown_namespaces:
            raise HTTPError(400, 'Unknown namespace{} "{}". Allowed namespaces are : "{}"'.format(
                's' if len(unknown_namespaces) > 1 else '', '", "'.join(unknown_namespaces), '", "'.join(namespaces.get(collection, []))
        ))

        query = dict(query)
        num_results = int(query.pop('limit', '1'))
        offset = int(query.pop('skip', '0'))
        unknown_descriptors = list(filter(lambda d: d not in all_descriptors, query.keys()))
        if unknown_descriptors:
            raise HTTPError(400, 'Unknown descriptor{} "{}". Allowed descriptors for searching are : "{}"'.format(
                's' if len(unknown_descriptors) > 1 else '', '", "'.join(unknown_descriptors), '", "'.join(all_descriptors)
            ))

        if method == 'GET':
            if body:
                raise HTTPError(400, 'Unexpected body in request. Perhaps you meant to POST?')
            query_vector = []
        elif method == 'POST':
            if not body:
                raise HTTPError(400, 'Missing audio body')
            query, query_vector = text_search_params(body, headers.get('content-type', 'application/octet-stream'), query)
        else:
            raise HTTPError(405, f'{method} Method Not Allowed')

        # Verify and parse query parameter values
        if 'embedding' in query and query['embedding']:
            if query['embedding'] not in ('qvim', 'l3'):
                raise HTTPError(400, 'The embedding search parameter needs to be either "qvim" or "l3"')
            if not query_vector:
                raise HTTPError(400, 'Embedding search requires an audio file or query vector to be sent via POST')

        for descriptor in ('tempo', 'tuning', 'duration'):
            if descriptor in query and query[descriptor]:
                try:
                    try:
                        parsed_value = _num_operator_regex.match(query[descriptor])
                        query[descriptor] = {'operator': parsed_value.group(1), 'number': float(parsed_value.group(2))}
                    except (ValueError, AttributeError):
                        try:
                            parsed_value = _num_tolerance_regex.match(query[descriptor])
                            target = float(parsed_value.group(1))
                            tolerance = float(parsed_value.group(3))
                            lower = target * (100 - tolerance) / 100
                            upper = target * (100 + tolerance) / 100
                        except (ValueError, AttributeError):
                            parsed_value = _num_range_regex.match(query[descriptor])
                            lower = float(parsed_value.group(1))
                            upper = float(parsed_value.group(3))
                            target = (lower + upper) / 2
                        query[descriptor] = {'operator': '-', 'target': target, 'lower': lower, 'upper': upper}
                except (ValueError, IndexError):
                    raise HTTPError(400, 'The {} search parameters need to be of the form "[<|>|<=|>=]<value>", "<min>-<max>" or "<value>+-<tolerance>%"'.format(descriptor))

        if 'global-key' in query and query['global-key']:
            split_key = _key_regex.match(query['global-key'])
            try:
                tonic = split_key.group(1)
                scale = split_key.group(2)
            except AttributeError:
                raise HTTPError(400, 'The global-key search parameters need to be of the form [A|A#|B|C|C#|D|D#|E|F|F#|G|G#][major|minor]')
            query['global-key'] = {'tonic': tonic, 'scale': scale}

        if 'chords' in query and query['chords']:
            params = query['chords'].split(',')
            chords = params[0].split('-')
            if not all([_chord_regex.match(c) for c in chords]):
                raise HTTPError(400, 'The syntax for the chords used as a search parameters is [A|Ab|B|Bb|C|D|Db|E|Eb|F|G|Gb][maj|min|7|maj7|min7], separated by hyphens')
            if len(params) == 1:
                coverage = 1.
            else:
                try:
                    coverage = float(params[1][:-1]) / 100
                    if len(params) > 2 or not params[1].endswith('%') or coverage > 1 or coverage < 0:
                        raise ValueError
                except ValueError:
                    raise HTTPError(400, 'The coverage parameter for the chord search needs to be a number between 0 and 100, followed by a percentage sign and separated from the chords by a single comma')
            query['chords'] = {'chords': chords, 'coverage': coverage}

        if 'dominant-mood' in query and query['dominant-mood']:
            if query['dominant-mood'] not in _moods:
                raise HTTPError(400, f'The dominant-mood search parameter needs to be one of {{{", ".join(_moods)}}}')

        return {
            'statusCode': 200,
            'body': database.search(collection, req_namespaces, query, num_results, offset, query_vector),
        }
    except HTTPError as e:
        return {
            'statusCode': e.errno,
            'body': {'error': e.strerror},
        }
    except Exception as err:
        logger.error('Error in search function', exc_info=err)
        return {
            'statusCode': 500,
            'body': {'error': 'Internal server error in search function'},
        }


def text_search_params(body, content_type, audio_query):
    analysis_descriptors = []
    for k, v in audio_query.items():
        if k == 'embedding':
            if content_type != 'application/json':
                analysis_descriptors.append(v)
        elif v or k in ['tempo', 'tuning', 'duration']:
            analysis_descriptors.append(k)
    if len(analysis_descriptors) == 0:
        if 'embedding' not in audio_query:
            raise HTTPError(400, 'Specify at least one search criterion when querying by audio file')
    else:
        analysis_response = requests.post(f"{os.getenv('ANALYSIS_API')}?descriptors={','.join(analysis_descriptors)}", data=body)
        if analysis_response.status_code != 200:
            raise HTTPError(analysis_response.status_code, analysis_response.json()['error'])
        query_descriptors = analysis_response.json()

    text_params = {}
    query_vector = []
    for query_key, query_value in audio_query.items():
        if query_key in ['tempo', 'tuning', 'duration']:
            if query_value == '':
                text_params[query_key] = ''
            elif query_value[0] in ('<', '>'):
                text_params[query_key] = '{}{}'.format(query_value, query_descriptors[query_key])
            else:
                text_params[query_key] = '{}{}'.format(query_descriptors[query_key], query_value)
        elif query_key == 'global-key':
            text_params['global-key'] = query_descriptors['global-key']['key'].replace(" ", "")
        elif query_key == 'chords':
            chord_set = set([c['label'] for c in query_descriptors['chords']['chordSequence']])
            chord_set.discard('N')
            text_params[query_key] = '-'.join(list(chord_set))
            if query_value:
                text_params[query_key] += ',{}'.format(query_value)
        elif query_key == 'dominant-mood':
            text_params[query_key] = max(query_descriptors['dominant-mood'], key=query_descriptors['dominant-mood'].get)
        elif query_key == 'embedding':
            text_params[query_key] = query_value
            if content_type == 'application/json':
                query_vector = json.loads(body)
            else:
                query_vector = query_descriptors[query_value]

    logger.info(f'Performing textual descriptor search with {text_params}')
    return text_params, query_vector
