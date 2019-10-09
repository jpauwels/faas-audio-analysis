import os
import sys
import json
import re
import requests
from requests.exceptions import HTTPError
import pymongo
from bson.son import SON
from urllib.parse import parse_qsl, unquote


descriptors = ['chords', 'tempo', 'tuning', 'global-key', 'duration']
all_collections = ['audiocommons', 'deezer', 'ilikemusic']
namespaces = {'audiocommons': ['jamendo-tracks', 'freesound-sounds', 'europeana-res'],
              'deezer': ['deezer'],
              'ilikemusic': []}
_key_regex = re.compile('^(A#|C#|D#|F#|G#|[A-G])?(major|minor)?$')
_key_variants = ['edma', 'krumhansl', 'temperley']
_chord_regex = re.compile('^(Ab|Bb|Db|Eb|Gb|[A-G])(maj|min|7|maj7|min7)$')
_client = None


def handle(audio_content):
    """handle a request to the function
    Args:
        req (str): request body
    """
    try:
        query = dict(parse_qsl(unquote(os.getenv('Http_Query', '')), keep_blank_values=True))
        unknown_descriptors = list(filter(lambda d: d not in descriptors+['namespaces'], query.keys()))
        if unknown_descriptors:
            raise HTTPError('Unknown descriptor{} "{}". Allowed descriptors for searching are : "{}"'.format(
            's' if len(unknown_descriptors) > 1 else '', '", "'.join(unknown_descriptors), '", "'.join(descriptors)))

        collection, *paging = os.getenv('Http_Path', '').lstrip('/').split('/')
        if collection not in all_collections:
            raise HTTPError('Unknown collection "{}"'.format(collection))
        try:
            num_results = int(paging[0]) if len(paging) > 0 and paging[0] else 1
            offset = int(paging[1]) if len(paging) > 1 and paging[1] else 0
        except ValueError:
            raise HTTPError('Invalid paging controls "{}". The correct syntax is "search/<collection>[/<num-results>[/<offset>]]"'.format(paging))

        if audio_content:
            query = text_search_params(audio_content, query)
        return json.dumps(search(collection, query, num_results, offset))
    except HTTPError as e:
        return json.dumps(str(e))


def text_search_params(audio_content, audio_query):
    analysis_descriptors = [k for k,v in audio_query.items() if k != 'namespaces' and (k not in ['tempo', 'tuning', 'duration'] or v)]
    analysis_response = requests.get('http://gateway:8080/function/analysis/{}'.format('/'.join(analysis_descriptors)), data=audio_content)
    analysis_response.raise_for_status()
    query_descriptors = analysis_response.json()

    text_params = {}
    for descriptor, audio_params in audio_query.items():
        if descriptor == 'namespaces':
            text_params[descriptor] = audio_params
        elif descriptor in ['tempo', 'tuning', 'duration']:
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


def search(collection, text_query, num_results, offset):
    agg_pipeline = []
    projection = {'_id': False, 'id': '$_id'}

    if 'namespaces' in text_query:
        allowed_namespaces = text_query['namespaces'].split(',')
        unknown_namespaces = list(filter(lambda p: p not in namespaces[collection], allowed_namespaces))
        if unknown_namespaces:
            raise HTTPError('Unknown namespace{} "{}". Allowed namespaces are : "{}"'.format(
            's' if len(unknown_namespaces) > 1 else '', '", "'.join(unknown_namespaces), '", "'.join(namespaces[collection])))
        agg_pipeline.append({'$match': {'_id': {'$regex': '^'+'|^'.join(allowed_namespaces)}}})
    if 'duration' in text_query:
        param = text_query['duration']
        if param:
            agg_pipeline.extend(_parse_single_number_query('duration', param, 'essentia-music.metadata.audio_properties.length'))
        projection['duration'] = '$essentia-music.metadata.audio_properties.length'
    if 'tempo' in text_query:
        param = text_query['tempo']
        if param:
            agg_pipeline.extend(_parse_single_number_query('tempo', param, 'essentia-music.rhythm.bpm'))
        projection['tempo'] = '$essentia-music.rhythm.bpm'
    if 'tuning' in text_query:
        param = text_query['tuning']
        if param:
            agg_pipeline.extend(_parse_single_number_query('tuning', param, 'essentia-music.tonal.tuning_frequency'))
        projection['tuning'] = '$essentia-music.tonal.tuning_frequency'
    if 'global-key' in text_query:
        param = text_query['global-key']
        if param:
            agg_pipeline.extend(_parse_key_query(param))
        else:
            agg_pipeline.append({'$addFields': {'key_best_matching':
                {'$let': {'vars': {'allKeys': ['$essentia-music.tonal.key_{}'.format(k) for k in _key_variants]},
                            'in': {'$arrayElemAt': ['$$allKeys', {'$indexOfArray': ['$$allKeys.strength', {'$max': ['$$allKeys.strength']}]}]}}}
            }})
        projection['global-key'] = {'key': {'$concat': ['$key_best_matching.key', ' ', '$key_best_matching.scale']}, 
                                    'confidence': '$key_best_matching.strength'}
    if 'chords' in text_query:
        param = text_query['chords']
        if param:
            agg_pipeline.extend(_parse_chord_query(param))
        agg_pipeline.append({'$project': {'chords.distinctChords': False, 'chords.chordRatio': False}})
        projection['chords'] = True
    
    agg_pipeline.extend([{'$skip': offset}, {'$limit': num_results}])
    agg_pipeline.append({'$project': projection})

    cursor = _get_client()[collection].descriptors.aggregate(agg_pipeline, allowDiskUse=True)
    return list(cursor)


def _parse_single_number_query(descriptor, param, mongo_field):
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
        raise HTTPError('The {} search parameters need to be of the form "[<|>|<=|>=]<value>", "<min>-<max>" or "<value>+-<tolerance>%"'.format(descriptor))


def _parse_key_query(param):
    split_key = _key_regex.match(param)
    try:
        tonic = split_key.group(1)
        scale = split_key.group(2)
    except AttributeError:
        raise HTTPError('The global-key search parameters need to be of the form [A|A#|B|C|C#|D|D#|E|F|F#|G|G#][major|minor]')
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
    return [
        {'$match': {'$or': match_list}},
        {'$addFields': {'key_best_matching': 
            {'$let': {'vars': {'matchingKeys': {'$filter': {'input': ['$essentia-music.tonal.key_{}'.format(k) for k in _key_variants], 
                                                            'cond': {'$and': filter_list}}}},
                    'in': {'$arrayElemAt': ['$$matchingKeys', {'$indexOfArray': ['$$matchingKeys.strength', {'$max': ['$$matchingKeys.strength']}]}]}}}
        }},
        {'$sort': {'key_best_matching.strength': pymongo.DESCENDING}}
    ]


def _parse_chord_query(param):
    params = param.split(',')
    chords = params[0].split('-')
    if not all([_chord_regex.match(c) for c in chords]):
        raise HTTPError('The syntax for the chords used as a search parameters is [A|Ab|B|Bb|C|D|Db|E|Eb|F|G|Gb][maj|min|7|maj7|min7], separated by hyphens')
    if len(params) == 1:
        coverage = 1.
    else:
        try:
            coverage = float(params[1][:-1]) / 100
            if len(params) > 2 or not params[1].endswith('%') or coverage > 1 or coverage < 0:
                raise ValueError
        except ValueError:
            raise HTTPError('The coverage parameter for the chord search needs to be a number between 0 and 100, followed by a percentage sign and separated from the chords by a single comma')
    return [
        {
            '$addFields':
            {
                'coverage': {'$sum': ['$chords.chordRatio.{}'.format(c) for c in chords]},
                'coveredChords': {'$sum': [{'$cond': [{'$gt': ['$chords.chordRatio.{}'.format(c), 0]}, 1, 0]} for c in chords]}
            }
        },
        {
            '$match': {'coverage': {'$gte': coverage}}
        },
        {
            '$sort': SON([('coveredChords', pymongo.DESCENDING), ('chords.confidence', pymongo.DESCENDING)])
        },
    ]


def _get_client():
    global _client
    if _client is None:
        sys.stderr.write('Connecting to DB\n')
        _client = pymongo.MongoClient(os.getenv('MONGO_CONNECTION'))
    sys.stderr.write('Connected to DB: {}\n'.format(_client))
    return _client
