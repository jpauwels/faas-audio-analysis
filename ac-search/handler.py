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
_chord_regex = re.compile('^(Ab|Bb|Db|Eb|Gb|[A-G])(maj|min|7|maj7|min7)$')
_client = None


def handle(_):
    """handle a request to the function
    Args:
        req (str): request body
    """
    args = parse_qs(os.getenv('Http_Query'))
    conf = os.getenv('Http_Path')[1:].split('/')
    provider = conf[0]
    if provider not in providers:
        return 'Unknown content provider "{}". Allowed providers are : "{}"'.format(provider, ','.join(providers))
    num_results = int(conf[1]) if len(conf) > 1 and conf[1] else 1
    offset = int(conf[2]) if len(conf) > 2 and conf[2] else 0

    return json.dumps(search(provider, args, num_results, offset))


def search(provider, args, num_results, offset):
    agg_pipeline = []
    projection = {}

    def _parse_single_number_query(descriptor, args, mongo_field):
        param = args[descriptor][0]
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

    try:
        if 'tempo' in args:
            agg_pipeline.extend(_parse_single_number_query('tempo', args, 'essentia-music.json.rhythm.bpm'))
            projection['tempo'] = '$essentia-music.json.rhythm.bpm'
        elif 'tuning' in args:
            agg_pipeline.extend(_parse_single_number_query('tuning', args, 'essentia-music.json.tonal.tuning_frequency'))
            projection['tuning'] = '$essentia-music.json.tonal.tuning_frequency'
        if 'global-key' in args:
            key = args['global-key'][0]
            split_key = _key_regex.match(key)
            try:
                tonic = split_key.group(1)
                scale = split_key.group(2)
            except AttributeError:
                raise SyntaxError('The global-key search parameters need to be of the form [A|A#|B|C|C#|D|D#|E|F|F#|G|G#][major|minor]')
            key_variants = ['edma', 'krumhansl', 'temperley']
            agg_pipeline.extend([
                {'$match': {'$or': [{'essentia-music.json.tonal.key_{}.key'.format(k): tonic, 'essentia-music.json.tonal.key_{}.scale'.format(k): scale} for k in key_variants]}},
                {'$addFields': {'essentia-music.json.tonal.key_best_matching': 
                    {'$let': {'vars': {'matchingKeys': {'$filter': {'input': ['$essentia-music.json.tonal.key_{}'.format(k) for k in key_variants], 
                                                                    'cond': {'$and': [{'$eq': ['$$this.key', tonic]}, {'$eq': ['$$this.scale', scale]}]}}}},
                            'in': {'$arrayElemAt': ['$$matchingKeys', {'$indexOfArray': ['$$matchingKeys.strength', {'$max': ['$$matchingKeys.strength']}]}]}}}
                }},
                {'$sort': {'essentia-music.json.tonal.key_best_matching.strength': pymongo.DESCENDING}}
            ])
            projection['global-key'] = {'key': {'$concat': ['$essentia-music.json.tonal.key_best_matching.key', ' ', '$essentia-music.json.tonal.key_best_matching.scale']}, 
                                        'confidence': '$essentia-music.json.tonal.key_best_matching.strength'}
        if 'chords' in args:
            params = args['chords'][0].split(',')
            chords = params[0].split('-')
            if not all([_chord_regex.match(c) for c in chords]):
                raise SyntaxError('The syntax for the chords used as a search parameters is [A|Ab|B|Bb|C|D|Db|E|Eb|F|G|Gb][maj|min|7|maj7|min7], separated by hyphens')
            if len(params) > 1 and params[1]:
                coverage = float(params[1][:-1]) / 100
                if not params[1].endswith('%') or coverage > 1 or coverage < 0:
                    raise SyntaxError('The coverage parameter for the chord search needs to be a number between 0 and 100, followed by a percentage sign')
            else:
                coverage = 1.
            agg_pipeline.extend([
                {
                    '$addFields':
                    {
                        'coverage': {'$sum': ['$chords.json.chordRatio.{}'.format(c) for c in chords]},
                        'coveredChords': {'$sum': [{'$cond': [{'$gt': ['$chords.json.chordRatio.{}'.format(c), 0]}, 1, 0]} for c in chords]}
                    }
                },
                {
                    '$match': {'coverage': {'$gte': coverage}}
                },
                {
                    '$sort': SON([('coveredChords', pymongo.DESCENDING), ('chords.json.confidence', pymongo.DESCENDING)])
                },
                {
                    '$project': {'chords.json.distinctChords': False, 'chords.json.chordRatio': False}
                },
            ])
            projection['chords'] = '$chords.json'
    except SyntaxError as e:
        return str(e)
    
    agg_pipeline.extend([{'$skip': offset}, {'$limit': num_results}])
    agg_pipeline.append({'$project': projection})

    cursor = _get_db()[provider].aggregate(agg_pipeline, allowDiskUse=True)
    return list(cursor)


def _get_db():
    global _client
    if _client is None:
        sys.stderr.write('Connecting to DB\n')
        _client = pymongo.MongoClient(os.getenv('MONGO_CONNECTION'))
    sys.stderr.write('Connected to DB: {}\n'.format(_client))
    return _client.ac_analysis_service
