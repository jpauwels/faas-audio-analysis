import pymongo
from bson.son import SON
from .secrets import get_secrets
import sys


_mongo_client = None
_secrets = get_secrets(['database-connection'])
_key_variants = ['edma', 'krumhansl', 'temperley']


def search(collection, req_namespaces, text_query, num_results, offset, query_vector=None):
    agg_pipeline = []
    projection = {'_id': False, 'id': '$_id'}

    if req_namespaces:
        agg_pipeline.append({'$match': {'_id': {'$regex': '^'+'|^'.join(req_namespaces)}}})
    if 'duration' in text_query:
        agg_pipeline.extend(_add_single_number_query(text_query['duration'], 'essentia-music.metadata.audio_properties.length'))
        projection['duration'] = '$essentia-music.metadata.audio_properties.length'
    if 'tempo' in text_query:
        agg_pipeline.extend(_add_single_number_query(text_query['tempo'], 'essentia-music.rhythm.bpm'))
        projection['tempo'] = '$essentia-music.rhythm.bpm'
    if 'tuning' in text_query:
        agg_pipeline.extend(_add_single_number_query(text_query['tuning'], 'essentia-music.tonal.tuning_frequency'))
        projection['tuning'] = '$essentia-music.tonal.tuning_frequency'
    if 'global-key' in text_query:
        agg_pipeline.extend(_add_key_query(text_query['global-key']))
        projection['global-key'] = {'key': {'$concat': ['$key_best_matching.key', ' ', '$key_best_matching.scale']},
                                    'confidence': '$key_best_matching.strength'}
    if 'chords' in text_query:
        agg_pipeline.extend(_add_chord_query(text_query['chords']))
        projection['chords'] = True
    if 'dominant-mood' in text_query:
        agg_pipeline.extend(_add_mood_query(text_query['dominant-mood']))
        projection['mood'] = '$maxMood'

    agg_pipeline.extend([{'$skip': offset}, {'$limit': num_results}])
    agg_pipeline.append({'$project': projection})

    cursor = _get_db(collection).descriptors.aggregate(agg_pipeline, allowDiskUse=True)
    return list(cursor)


def _add_single_number_query(parsed_value, mongo_field):
    if parsed_value:
        if parsed_value['operator'] == '<=':
            return [{'$match': {mongo_field: {'$lte': parsed_value['number']}}},
                    {'$sort': {mongo_field: pymongo.DESCENDING}}]
        elif parsed_value['operator'] == '>=':
            return [{'$match': {mongo_field: {'$gte': parsed_value['number']}}},
                    {'$sort': {mongo_field: pymongo.ASCENDING}}]
        elif parsed_value['operator'] == '<':
            return [{'$match': {mongo_field: {'$lt': parsed_value['number']}}},
                    {'$sort': {mongo_field: pymongo.DESCENDING}}]
        elif parsed_value['operator'] == '>':
            return [{'$match': {mongo_field: {'$gt': parsed_value['number']}}},
                    {'$sort': {mongo_field: pymongo.ASCENDING}}]
        else:
            return [{'$match': {mongo_field: {'$gte': parsed_value['lower'], '$lt': parsed_value['upper']}}},
                    {'$addFields': {'distance': {'$abs': {'$subtract': [parsed_value['target'], '${}'.format(mongo_field)]}}}},
                    {'$sort': {'distance': pymongo.ASCENDING}}]
    else:
        return []


def _add_key_query(key_value):
    if key_value:
        tonic = key_value['tonic']
        scale = key_value['scale']
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


def _add_chord_query(chord_value):
    agg_stages = []
    if chord_value:
        chords = chord_value['chords']
        coverage = chord_value['coverage']
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


def _add_mood_query(mood_value):
    agg_stages = []
    if mood_value:
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
    if mood_value:
        agg_stages.extend([
            {'$match': {f'maxMood.{mood_value}': {'$exists': True}}},
            {'$sort': {f'maxMood.{mood_value}': pymongo.DESCENDING}},
        ])
    return agg_stages


def _get_db(db_name):
    global _mongo_client
    if _mongo_client is None:
        sys.stderr.write('Connecting to MongoDB\n')
        _mongo_client = pymongo.MongoClient(_secrets['database-connection'])
    return _mongo_client[db_name]
