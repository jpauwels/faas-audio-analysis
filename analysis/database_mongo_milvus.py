from . import database_mongo
from .database_mongo import map_id
from pymilvus import DataType, MilvusClient, MilvusException
from .secrets import get_secrets
import os
import sys


_milvus_client = None
_secrets = get_secrets(['vector-db-token'])


def get(db_name, named_id, descriptor):
    if descriptor in ('qvim', 'l3'):
        try:
            record = _get_db(db_name).get(collection_name='descriptors', ids=[named_id], output_fields=[descriptor, f'{descriptor}_null'])[0]
        except (MilvusException, IndexError):
            return
        if record[f'{descriptor}_null']:
            return
        return record
    else:
        return database_mongo.get(db_name, named_id, descriptor)


def put(db_name, named_id, descriptor, data):
    if descriptor in ('qvim', 'l3'):
        try:
            record = _get_db(db_name).get(collection_name='descriptors', ids=[named_id])[0]
        except (MilvusException, IndexError):
            record = {'id': named_id, 'l3': [0.]*512, 'l3_null': True, 'qvim': [0.]*960, 'qvim_null': True}
        record[descriptor] = data
        record[f'{descriptor}_null'] = False
        try:
            return _get_db(db_name).upsert('descriptors', record)
        except MilvusException as err:
            if err.code == 0:
                schema = _get_db(db_name).create_schema(auto_id=False)
                schema.add_field(field_name='id', datatype=DataType.INT64 if isinstance(named_id, int) else DataType.STRING, is_primary=True)
                schema.add_field(field_name='l3', datatype=DataType.FLOAT_VECTOR, dim=512)
                schema.add_field(field_name='l3_null', datatype=DataType.BOOL, default_value=True)
                schema.add_field(field_name='qvim', datatype=DataType.FLOAT_VECTOR, dim=960)
                schema.add_field(field_name='qvim_null', datatype=DataType.BOOL, default_value=True)
                index_params = _get_db(db_name).prepare_index_params()
                index_params.add_index(field_name='l3', index_name='l3_index', index_type='AUTOINDEX', metric_type='COSINE')
                index_params.add_index(field_name='qvim', index_name='qvim_index', index_type='AUTOINDEX', metric_type='COSINE')
                _get_db(db_name).create_collection('descriptors', schema=schema, index_params=index_params)
                sys.stderr.write(f'Created descriptors collection in MilvusDB "{db_name}"\n')
                return _get_db(db_name).upsert('descriptors', record)
            raise err
    else:
        return database_mongo.put(db_name, named_id, descriptor, data)


def _get_db(db_name):
    global _milvus_client
    if _milvus_client is None:
        sys.stderr.write('Connecting to MilvusDB\n')
        _milvus_client = MilvusClient(os.getenv('VECTOR_DB_URI', 'http://localhost:19530'), token=_secrets['vector-db-token'])
    try:
        _milvus_client.using_database(db_name)
    except MilvusException as err:
        if err.code == 800:
            _milvus_client.create_database(db_name)
            sys.stderr.write(f'Created MilvusDB "{db_name}"\n')
            _milvus_client.using_database(db_name)
        else:
            raise err
    return _milvus_client
