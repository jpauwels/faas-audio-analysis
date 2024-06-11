import os
import sys
import re
import requests
from requests.exceptions import HTTPError
import pymongo
from bson.son import SON
from .secrets import get_secrets


all_descriptors = ['chords', 'tempo', 'tuning', 'global-key', 'duration']
all_collections = ['audiocommons', 'deezer', 'ilikemusic']
namespaces = {'audiocommons': ['jamendo-tracks', 'freesound-sounds', 'europeana-res'],
              'deezer': ['deezer'],
              'ilikemusic': []}
_key_regex = re.compile('^(A#|C#|D#|F#|G#|[A-G])?(major|minor)?$')
_key_variants = ['edma', 'krumhansl', 'temperley']
_chord_regex = re.compile('^(Ab|Bb|Db|Eb|Gb|[A-G])(maj|min|7|maj7|min7)$')
_moods = ('agressive', 'happy', 'relaxed', 'sad')
_client = None
_secrets = get_secrets(['database-connection'])


def handle(event, context):
    try:
        if event.path == '/descriptors':
            return {
                'statusCode': 200,
                'body': all_descriptors,
            }
        if event.path == '/collections':
            return {
                'statusCode': 200,
                'body': all_collections,
            }
        collection, *req_namespaces = event.path.strip('/').split('/')
        if collection not in all_collections:
            raise HTTPError(400, 'Unknown collection "{}"'.format(collection))
        if 'namespaces' in req_namespaces:
            return {
                'statusCode': 200,
                'body': namespaces[collection],
            }
        unknown_namespaces = list(filter(lambda p: p not in namespaces[collection], req_namespaces))
        if unknown_namespaces:
            raise HTTPError(400, 'Unknown namespace{} "{}". Allowed namespaces are : "{}"'.format(
                's' if len(unknown_namespaces) > 1 else '', '", "'.join(unknown_namespaces), '", "'.join(namespaces[collection])
        ))

        query = dict(event.query)
        num_results = int(query.pop('limit', '1'))
        offset = int(query.pop('skip', '0'))
        unknown_descriptors = list(filter(lambda d: d not in all_descriptors, query.keys()))
        if unknown_descriptors:
            raise HTTPError(400, 'Unknown descriptor{} "{}". Allowed descriptors for searching are : "{}"'.format(
                's' if len(unknown_descriptors) > 1 else '', '", "'.join(unknown_descriptors), '", "'.join(all_descriptors)
            ))

        if event.method == 'GET':
            if event.body:
                raise HTTPError(400, 'Unexpected body in request. Perhaps you meant to POST?')
        elif event.method == 'POST':
            if not event.body:
                raise HTTPError(400, 'Missing audio body')
            query = text_search_params(event.body, query)
        else:
            raise HTTPError(405, f'{event.method} Method Not Allowed')

        return {
            'statusCode': 200,
            'body': search(collection, req_namespaces, query, num_results, offset),
        }
    except HTTPError as e:
        return {
            'statusCode': e.errno,
            'body': {'error': e.strerror},
        }


def text_search_params(audio_content, audio_query):
    analysis_descriptors = [k for k,v in audio_query.items() if k not in ['tempo', 'tuning', 'duration'] or v]
    if len(analysis_descriptors) == 0:
        raise HTTPError(400, 'Specify at least one search criterion when querying by audio file')
    analysis_response = requests.post(f"{os.getenv('ANALYSIS_API')}?descriptors={','.join(analysis_descriptors)}", data=audio_content)
    if analysis_response.status_code != 200:
        raise HTTPError(analysis_response.status_code, analysis_response.json()['error'])
    query_descriptors = analysis_response.json()

    text_params = {}
    for descriptor, audio_params in audio_query.items():
        if descriptor in ['tempo', 'tuning', 'duration']:
            if audio_params == '':
                text_params[descriptor] = ''
            elif audio_params[0] in ['<', '>']:
                text_params[descriptor] = '{}{}'.format(audio_params, query_descriptors[descriptor])
            else:
                text_params[descriptor] = '{}{}'.format(query_descriptors[descriptor], audio_params)
        elif descriptor == 'global-key':
            text_params['global-key'] = query_descriptors['global-key']['key'].replace(" ", "")
        elif descriptor == 'chords':
            chord_set = set([c['label'] for c in query_descriptors['chords']['chordSequence']])
            chord_set.discard('N')
            text_params[descriptor] = '-'.join(list(chord_set))
            if audio_params:
                text_params[descriptor] += ',{}'.format(audio_params)

    sys.stderr.write('Performing textual descriptor search with {}\n'.format(text_params))
    return text_params


def search(collection, req_namespaces, text_query, num_results, offset):
    agg_pipeline = []
    projection = {'_id': False, 'id': '$_id'}

    if req_namespaces:
        agg_pipeline.append({'$match': {'_id': {'$regex': '^'+'|^'.join(req_namespaces)}}})
    if 'duration' in text_query:
        agg_pipeline.extend(_parse_single_number_query('duration', text_query['duration'], 'essentia-music.metadata.audio_properties.length'))
        projection['duration'] = '$essentia-music.metadata.audio_properties.length'
    if 'tempo' in text_query:
        agg_pipeline.extend(_parse_single_number_query('tempo', text_query['tempo'], 'essentia-music.rhythm.bpm'))
        projection['tempo'] = '$essentia-music.rhythm.bpm'
    if 'tuning' in text_query:
        agg_pipeline.extend(_parse_single_number_query('tuning', text_query['tuning'], 'essentia-music.tonal.tuning_frequency'))
        projection['tuning'] = '$essentia-music.tonal.tuning_frequency'
    if 'global-key' in text_query:
        agg_pipeline.extend(_parse_key_query(text_query['global-key']))
        projection['global-key'] = {'key': {'$concat': ['$key_best_matching.key', ' ', '$key_best_matching.scale']}, 
                                    'confidence': '$key_best_matching.strength'}
    if 'chords' in text_query:
        agg_pipeline.extend(_parse_chord_query(text_query['chords']))
        projection['chords'] = True
    if 'mood' in text_query:
        agg_pipeline.extend(_parse_mood_query(text_query['mood']))
        projection['mood'] = '$maxMood'

    agg_pipeline.extend([{'$skip': offset}, {'$limit': num_results}])
    agg_pipeline.append({'$project': projection})

    cursor = _get_client()[collection].descriptors.aggregate(agg_pipeline, allowDiskUse=True)
    return list(cursor)


def _parse_single_number_query(descriptor, param, mongo_field):
    if param:
        try:
            if param.startswith('<='):
                return [{'$match': {mongo_field: {'$lte': float(param[2:])}}},
                        {'$sort': {mongo_field: pymongo.DESCENDING}}]
            elif param.startswith('>='):
                return [{'$match': {mongo_field: {'$gte': float(param[2:])}}},
                        {'$sort': {mongo_field: pymongo.ASCENDING}}]
            elif param.startswith('<'):
                return [{'$match': {mongo_field: {'$lt': float(param[1:])}}},
                        {'$sort': {mongo_field: pymongo.DESCENDING}}]
            elif param.startswith('>'):
                return [{'$match': {mongo_field: {'$gt': float(param[1:])}}},
                        {'$sort': {mongo_field: pymongo.ASCENDING}}]
            else:
                if param.endswith('%'):
                    # tolerance
                    params = param.split(' -')
                    params[1] = params[1][:-1]
                    target_value, tolerance = map(float, params)
                    lower = target_value * (100 - tolerance) / 100
                    upper = target_value * (100 + tolerance) / 100
                else:
                    # range
                    params = param.split('-')
                    lower, upper = map(float, params)
                    target_value = (lower + upper) / 2
                return [{'$match': {mongo_field: {'$gte': lower, '$lt': upper}}},
                        {'$addFields': {'distance': {'$abs': {'$subtract': [target_value, '${}'.format(mongo_field)]}}}},
                        {'$sort': {'distance': pymongo.ASCENDING}}]
        except (ValueError, IndexError):
            raise HTTPError(400, 'The {} search parameters need to be of the form "[<|>|<=|>=]<value>", "<min>-<max>" or "<value>+-<tolerance>%"'.format(descriptor))
    else:
        return []


def _parse_key_query(key_param):
    if key_param:
        split_key = _key_regex.match(key_param)
        try:
            tonic = split_key.group(1)
            scale = split_key.group(2)
        except AttributeError:
            raise HTTPError(400, 'The global-key search parameters need to be of the form [A|A#|B|C|C#|D|D#|E|F|F#|G|G#][major|minor]')
        match_list = [dict() for k in _key_variants]
        filter_list = []
        if tonic:
            for m, k in zip(match_list, _key_variants):
                m['essentia-music.tonal.key_{}.key'.format(k)] = tonic
            filter_list.append({'$eq': ['$$this.key', tonic]})
        if scale:
            for m, k in zip(match_list, _key_variants):
                m['essentia-music.tonal.key_{}.scale'.format(k)] = scale
            filter_list.append({'$eq': ['$$this.scale', scale]})
    if key_param:
        return [
            {'$match': {'$or': match_list}},
            {
                '$addFields': {
                    'key_best_matching': {
                        '$let': {
                            'vars': {
                                'matchingKeys': {
                                    '$filter': {
                                        'input': ['$essentia-music.tonal.key_{}'.format(k) for k in _key_variants],
                                        'cond': {'$and': filter_list}
                                        }
                                    }
                            },
                            'in': {
                                '$arrayElemAt': ['$$matchingKeys', {'$indexOfArray': ['$$matchingKeys.strength', {'$max': ['$$matchingKeys.strength']}]}]
                            }
                        }
                    }
                }
            },
            {'$sort': {'key_best_matching.strength': pymongo.DESCENDING}}
        ]
    else:
        return [
            {
                '$addFields': {
                    'key_best_matching': {
                        '$let': {
                            'vars': {
                                'allKeys': ['$essentia-music.tonal.key_{}'.format(k) for k in _key_variants]
                            },
                            'in': {
                                '$arrayElemAt': ['$$allKeys', {'$indexOfArray': ['$$allKeys.strength', {'$max': ['$$allKeys.strength']}]}]
                            }
                        }
                    }
                }
            }
        ]


def _parse_chord_query(chord_param):
    agg_stages = []
    if chord_param:
        params = chord_param.split(',')
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
        agg_stages.extend([
            {
                '$match': {'$or': [ {f'chords.chordRatio.{c}': {'$gt': 0}} for c in chords ]},
            },
            {
                '$addFields': {'coverage': {'$sum': [ f'$chords.chordRatio.{c}' for c in chords ]}},
            },
            {
                '$match': {'coverage': {'$gte': coverage}},
            },
            {
                '$addFields': {'coveredChords': {'$sum': [ {'$cond': [{ '$gt': [ f'$chords.chordRatio.{c}', 0 ] }, 1, 0]} for c in chords ]}},
            },
            {
                '$sort': SON([('coveredChords', pymongo.DESCENDING), ('chords.confidence', pymongo.DESCENDING)]),
            },
        ])
    agg_stages.append({'$project': {'chords.distinctChords': False, 'chords.chordRatio': False}})
    return agg_stages


def _parse_mood_query(mood_param):
    if mood_param not in _moods:
        raise HTTPError(400, f'The mood search parameter needs to be one of {_moods.joint(" ")}')
    agg_stages = []
    if mood_param:
        agg_stages.append({'$match': {'mood': {'$exists': True}}})
    agg_stages.append({
        '$addFields': {
            'maxMood': {
                '$let': {
                    'vars': {
                        'moodValues': {
                            '$map': {
                                'input': {'$objectToArray': '$mood'},
                                'in': {
                                    '$let': {
                                        'vars': {
                                            'name': {'$arrayElemAt': [{'$split': [{'$trim': {'input': '$$this.k', 'chars': 'mood_'}}, '-']}, 0]}
                                        },
                                        'in': {
                                            'k': '$$name', 'v': {'$arrayElemAt': ['$$this.v', {'$cond': {'if': {'$in': ['$$name', ['sad', 'relaxed']]}, 'then': 1, 'else': 0}}]}
                                        }
                                    }
                                }
                            }
                        }
                    },
                    'in': {
                        '$let': {
                            'vars': {
                                'maxMood': [{'$arrayElemAt': ['$$moodValues', {'$indexOfArray': ['$$moodValues.v', {'$max': ['$$moodValues.v']}]}]}]
                            },
                            'in': {
                                '$arrayToObject': '$$maxMood'
                            }
                        }
                    }
                }
            }
        }
    })
    if mood_param:
        agg_stages.extend([
            {'$match': {f'maxMood.{mood_param}': {'$exists': True}}},
            {'$sort': {f'maxMood.{mood_param}': pymongo.DESCENDING}},
        ])
    return agg_stages


def _get_client():
    global _client
    if _client is None:
        sys.stderr.write('Connecting to DB\n')
        _client = pymongo.MongoClient(_secrets['database-connection'])
    sys.stderr.write('Connected to DB: {}\n'.format(_client))
    return _client
