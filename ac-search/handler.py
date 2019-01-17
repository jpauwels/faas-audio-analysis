import os
import sys
import json
import pymongo
from bson.son import SON
from urllib.parse import parse_qs
from .config import providers


descriptors = ['chords', 'tempo']
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
    if 'tempo' in args:
        param = args['tempo'][0]
        if param.startswith('<='):
            agg_pipeline.extend([{'$match': {'essentia-music.json.rhythm.bpm': {'$lte': float(param[2:])}}},
                                 {'$sort': {'essentia-music.json.rhythm.bpm': pymongo.DESCENDING}}])
        elif param.startswith('>='):
            agg_pipeline.extend([{'$match': {'essentia-music.json.rhythm.bpm': {'$gte': float(param[2:])}}},
                                 {'$sort': {'essentia-music.json.rhythm.bpm': pymongo.ASCENDING}}])
        elif param.startswith('<'):
            agg_pipeline.extend([{'$match': {'essentia-music.json.rhythm.bpm': {'$lt': float(param[1:])}}},
                                 {'$sort': {'essentia-music.json.rhythm.bpm': pymongo.DESCENDING}}])
        elif param.startswith('>'):
            agg_pipeline.extend([{'$match': {'essentia-music.json.rhythm.bpm': {'$gt': float(param[1:])}}},
                                 {'$sort': {'essentia-music.json.rhythm.bpm': pymongo.ASCENDING}}])
        else:
            params = param.split('-')
            if len(params) == 2:
                if params[1][-1] == '%':
                    # BPM tolerance
                    params[1] = params[1][:-1]
                    target_bpm, tolerance = map(float, params)
                    min_bpm = target_bpm * (100 - tolerance) / 100
                    max_bpm = target_bpm * (100 + tolerance) / 100
                else:
                    # BPM range
                    min_bpm, max_bpm = map(float, params)
                    target_bpm = (min_bpm + max_bpm) / 2
                agg_pipeline.extend([{'$match': {'essentia-music.json.rhythm.bpm': {'$gte': min_bpm, '$lt': max_bpm}}},
                                     {'$addFields': {'bpmDistance': {'$abs': {'$subtract': [target_bpm, '$essentia-music.json.rhythm.bpm']}}}},
                                     {'$sort': {'bpmDistance': pymongo.ASCENDING}}])
            else:
                return 'The tempo search parameters need to be of the form "<min BPM>-<max BPM>" or "<BPM>-<tolerance>%"'
        projection['tempo'] = '$essentia-music.json.rhythm.bpm'
    if 'chords' in args:
        params = args['chords'][0].split(',')
        chords = params[0]
        coverage = float(params[1]) if len(params) > 1 and params[1] else 1.
        requested_chords = chords.split('-')
        agg_pipeline.extend([
            {
                '$addFields':
                {
                    'coverage': {'$sum': ['$chords.json.chordRatio.{}'.format(c) for c in requested_chords]},
                    'coveredChords': {'$sum': [{'$cond': [{'$gt': ['$chords.json.chordRatio.{}'.format(c), 0]}, 1, 0]} for c in requested_chords]}
                }
            },
            {
                '$match': {'coverage': {'$gte': coverage}}
            },
            {
                '$sort': SON([('coveredChords', pymongo.DESCENDING),
                            ('confidence', pymongo.DESCENDING)])
            },
            {
                '$project': {'chords.json.distinctChords': False, 'chords.json.chordRatio': False, 'chords.json.frameSpls': False}
            },
        ])
        projection['chords'] = '$chords.json'
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
