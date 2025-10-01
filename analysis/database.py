
import pymongo
from bson.objectid import ObjectId
from .secrets import get_secrets
import sys


_mongo_client = None
_secrets = get_secrets(['database-connection'])


def get(db_name, named_id, descriptor):
    db = _get_db(db_name)
    return db.descriptors.find_one({'_id': named_id, descriptor: {'$exists': True}})


def put(db_name, named_id, descriptor, data):
    db = _get_db(db_name)
    r = db.descriptors.update_one({'_id': named_id}, {'$set': {descriptor: data}}, upsert=True)
    return r.raw_result


def map_id(index_id, db_name, collection, map_field):
    db = _get_db(db_name)
    return db[collection].find_one({'_id': ObjectId(index_id)}, {'_id': False, map_field: True})[map_field]


def _get_db(db_name):
    global _mongo_client
    if _mongo_client is None:
        sys.stderr.write('Connecting to MongoDB\n')
        _mongo_client = pymongo.MongoClient(_secrets['database-connection'])
    return _mongo_client[db_name]
