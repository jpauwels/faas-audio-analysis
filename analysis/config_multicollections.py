import requests
import os
import minio
import io
import os.path
import urllib.parse
import cgi
import mimetypes
from datetime import timedelta
from bson.objectid import ObjectId
from .config_ac_direct_audio import validate_audiocommons_id, audiocommons_uri

all_collections = ['audiocommons', 'deezer', 'ilikemusic']
namespaces = {'audiocommons': ['jamendo-tracks', 'freesound-sounds', 'europeana-res'],
              'deezer': ['deezer', 'wasabi'],
              'ilikemusic': []}
_cache_storage = minio.Minio(os.getenv('MINIO_CACHE_HOSTNAME'), access_key=os.getenv('MINIO_CACHE_ACCESS_KEY'), secret_key=os.getenv('MINIO_CACHE_SECRET_KEY'), secure=False)
_readonly_storage = minio.Minio(os.getenv('MINIO_READONLY_HOSTNAME'), access_key=os.getenv('MINIO_READONLY_ACCESS_KEY'), secret_key=os.getenv('MINIO_READONLY_SECRET_KEY'), secure=False)


def alias_id(collection, named_id, db):
    if collection == 'deezer':
        namespace, file_id = named_id.split(':')
        if namespace == 'wasabi':
            file_id = db.wasabi_song.find_one({'_id': ObjectId(file_id)}, {'_id': False, 'id_song_deezer': True})['id_song_deezer']
        return int(file_id)
    else:
        return named_id


def audio_uri(collection, named_id):
    if collection == 'audiocommons':
        provider, provider_id = validate_audiocommons_id(named_id)
        if provider in ['jamendo-tracks', 'freesound-sounds']:
            object_prefix = provider_id[-2:] + '/' + provider_id
        else:
            object_prefix = provider_id
        try:
            object_name = next(_cache_storage.list_objects(provider, prefix=object_prefix)).object_name
        except (StopIteration, minio.error.NoSuchBucket):
            url = audiocommons_uri(provider_id, provider)
            r = requests.get(url)
            r.raise_for_status()
            try:
                _, params = cgi.parse_header(r.headers['Content-Disposition'])
                file_ext = os.path.splitext(params['filename'])[1]
                # TODO add handling of filename*
            except KeyError:
                file_ext = os.path.splitext(urllib.parse.urlparse(url).path)[1]
                if not file_ext:
                    try:
                        file_ext = mimetypes.guess_extension(r.headers['Content-Type'])
                    except KeyError:
                        pass
            object_name = object_prefix+file_ext
            _cache_storage.put_object(provider, object_name, io.BytesIO(r.content), int(r.headers['Content-Length']), r.headers['Content-Type'])
        return _cache_storage.presigned_get_object(provider, object_name, expires=timedelta(minutes=3))
    elif collection == 'deezer':
        if isinstance(named_id, int):
            named_id = 'deezer:{}'.format(named_id)
        raise FileNotFoundError('No audio available for id "{}"'.format(named_id))
    else:
        try:
            object_name = next(_readonly_storage.list_objects(collection, prefix=named_id)).object_name
            return _readonly_storage.presigned_get_object(collection, object_name, expires=timedelta(minutes=3))
        except (StopIteration, minio.error.NoSuchBucket):
            raise FileNotFoundError('No audio available for id "{}"'.format(named_id))
