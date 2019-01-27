import os
import sys
import json
import re
import pymongo
from bson.son import SON
from urllib.parse import parse_qs
from .config import providers


descriptors = ['chords', 'tempo', 'tuning', 'global-key']
_key_regex = re.compile('^(A#|C#|D#|F#|G#|[A-G])?(major|minor)?$')
_key_variants = ['edma', 'krumhansl', 'temperley']
_chord_regex = re.compile('^(Ab|Bb|Db|Eb|Gb|[A-G])(maj|min|7|maj7|min7)$')
_client = None


def handle(_):
    """handle a request to the function
    Args:
        req (str): request body
    """
    args = parse_qs(os.getenv('Http_Query'), keep_blank_values=True)
    unknown_descriptors = list(filter(lambda d: d not in descriptors, args.keys()))
    if unknown_descriptors:
        return json.dumps('Unknown descriptor{} "{}". Allowed descriptors for searching are : "{}"'.format(
        's' if len(unknown_descriptors) > 1 else '', '", "'.join(unknown_descriptors), '", "'.join(descriptors)))

    paging = os.getenv('Http_Path')[1:].split('/')
    try:
        num_results = int(paging[0]) if len(paging) > 0 and paging[0] else 1
        offset = int(paging[1]) if len(paging) > 1 and paging[1] else 0
    except ValueError:
        return json.dumps('Invalid paging controls "{}". The correct syntax is "ac-search[/<num-results>[/<offset>]]"'.format(paging))

    return json.dumps(search(args, num_results, offset))


def search(args, num_results, offset):
    agg_pipeline = []
    projection = {}

    try:
        if 'tempo' in args:
            param = args['tempo'][0]
            if param:
                agg_pipeline.extend(_parse_single_number_query('tempo', param, 'essentia-music.rhythm.bpm'))
            projection['tempo'] = '$essentia-music.rhythm.bpm'
        if 'tuning' in args:
            param = args['tuning'][0]
            if param:
                agg_pipeline.extend(_parse_single_number_query('tuning', param, 'essentia-music.tonal.tuning_frequency'))
            projection['tuning'] = '$essentia-music.tonal.tuning_frequency'
        if 'global-key' in args:
            param = args['global-key'][0]
            if param:
                agg_pipeline.extend(_parse_key_query(param))
            else:
                agg_pipeline.append({'$addFields': {'key_best_matching':
                    {'$let': {'vars': {'allKeys': ['$essentia-music.tonal.key_{}'.format(k) for k in _key_variants]},
                              'in': {'$arrayElemAt': ['$$allKeys', {'$indexOfArray': ['$$allKeys.strength', {'$max': ['$$allKeys.strength']}]}]}}}
                }})
            projection['global-key'] = {'key': {'$concat': ['$key_best_matching.key', ' ', '$key_best_matching.scale']}, 
                                        'confidence': '$key_best_matching.strength'}
        if 'chords' in args:
            param = args['chords'][0]
            if param:
                agg_pipeline.extend(_parse_chord_query(param))
            agg_pipeline.append({'$project': {'chords.distinctChords': False, 'chords.chordRatio': False}})
            projection['chords'] = '$chords'
    except SyntaxError as e:
        return str(e)
    
    agg_pipeline.extend([{'$skip': offset}, {'$limit': num_results}])
    if not projection:
        projection['_id'] = True
    agg_pipeline.append({'$project': projection})

    cursor = _get_db().descriptors.aggregate(agg_pipeline, allowDiskUse=True)
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
        raise SyntaxError('The {} search parameters need to be of the form "[<|>|<=|>=]<value>", "<min>-<max>" or "<value>+-<tolerance>%"'.format(descriptor))


def _parse_key_query(param):
    split_key = _key_regex.match(param)
    try:
        tonic = split_key.group(1)
        scale = split_key.group(2)
    except AttributeError:
        raise SyntaxError('The global-key search parameters need to be of the form [A|A#|B|C|C#|D|D#|E|F|F#|G|G#][major|minor]')
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
        raise SyntaxError('The syntax for the chords used as a search parameters is [A|Ab|B|Bb|C|D|Db|E|Eb|F|G|Gb][maj|min|7|maj7|min7], separated by hyphens')
    if len(params) > 1 and params[1]:
        coverage = float(params[1][:-1]) / 100
        if not params[1].endswith('%') or coverage > 1 or coverage < 0:
            raise SyntaxError('The coverage parameter for the chord search needs to be a number between 0 and 100, followed by a percentage sign')
    else:
        coverage = 1.
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


def _get_db():
    global _client
    if _client is None:
        sys.stderr.write('Connecting to DB\n')
        _client = pymongo.MongoClient(os.getenv('MONGO_CONNECTION'))
    sys.stderr.write('Connected to DB: {}\n'.format(_client))
    return _client.ac_analysis_service
