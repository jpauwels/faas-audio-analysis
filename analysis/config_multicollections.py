import minio
from datetime import timedelta
from bson.objectid import ObjectId
from .config_ac_cached_audio import _cache_storage, audio_uri as ac_audio_uri

all_collections = ['audiocommons', 'deezer', 'ilikemusic']
namespaces = {'audiocommons': ['jamendo-tracks', 'freesound-sounds', 'europeana-res'],
              'deezer': ['deezer', 'wasabi'],
              'ilikemusic': []}


def alias_id(collection, named_id, db):
    if collection == 'deezer':
        namespace, file_id = named_id.split(':')
        if namespace == 'wasabi':
            file_id = db.wasabi_song.find_one({'_id': ObjectId(file_id)}, {'_id': False, 'id_song_deezer': True})['id_song_deezer']
        return file_id
    else:
        return named_id


def audio_uri(collection, named_id):
    try:
        return ac_audio_uri(collection, named_id)
    except ValueError:
        if collection == 'deezer':
            if isinstance(named_id, int):
                named_id = f'deezer:{named_id}'
            raise FileNotFoundError(f'No audio available for id "{named_id}"')
        else:
            try:
                object_name = next(_cache_storage.list_objects(collection, prefix=named_id)).object_name
                return _cache_storage.presigned_get_object(collection, object_name, expires=timedelta(minutes=3))
            except (StopIteration, minio.error.S3Error):
                raise FileNotFoundError(f'No audio available for id "{named_id}"')
