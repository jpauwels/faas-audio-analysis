from . import database_mongo
from pymilvus import MilvusClient, MilvusException
from .secrets import get_secrets
import os
import sys


_milvus_client = None
_secrets = get_secrets(['vector-db-token'])

def search(collection, req_namespaces, text_query, num_results, offset, query_vector):
    if 'embedding' in text_query:
        # Handle vector search
        if len(text_query) > 1:
            raise ValueError('When using embedding search, no other query parameters are allowed')
        try:
            cursor = _get_db(collection).search(
                collection_name='descriptors',
                anns_field=text_query['embedding'],
                data=[query_vector],
                filter=f'{text_query["embedding"]}_null == false',
                limit=num_results,
                offset=offset,
                search_params={'metric_type': 'COSINE'}
            )[0]
        except MilvusException as err:
            if err.code == 100:
                return []
            else:
                raise err
        results = []
        for item in cursor:
            item.pop('entity')
            item[text_query['embedding']] = item.pop('distance')
            results.append(dict(item))
        return results
    else:
        # Fallback to MongoDB search
        return database_mongo.search(collection, req_namespaces, text_query, num_results, offset)


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
