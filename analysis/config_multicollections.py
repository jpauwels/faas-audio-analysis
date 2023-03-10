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
from .secrets import get_secrets

all_collections = ['audiocommons', 'deezer', 'ilikemusic']
namespaces = {'audiocommons': ['jamendo-tracks', 'freesound-sounds', 'europeana-res'],
              'deezer': ['deezer', 'wasabi'],
              'ilikemusic': []}
_secrets = get_secrets(['object-store-readwrite-access', 'object-store-readwrite-secret', 'object-store-readonly-access', 'object-store-readonly-secret'])
_readwrite_storage = minio.Minio(os.getenv('OBJECT_STORE_HOSTNAME', 'localhost'), access_key=_secrets['object-store-readwrite-access'], secret_key=_secrets['object-store-readwrite-secret'], secure=False)
_readonly_storage = minio.Minio(os.getenv('OBJECT_STORE_HOSTNAME', 'localhost'), access_key=_secrets['object-store-readonly-access'], secret_key=_secrets['object-store-readonly-secret'], secure=False)


def alias_id(collection, named_id, db):
    if collection == 'deezer':
        namespace, file_id = named_id.split(':')
        if namespace == 'wasabi':
            file_id = db.wasabi_song.find_one({'_id': ObjectId(file_id)}, {'_id': False, 'id_song_deezer': True})['id_song_deezer']
        return file_id
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
            object_name = next(_readwrite_storage.list_objects(provider, prefix=object_prefix)).object_name
        except (StopIteration, minio.error.S3Error):
            url = audiocommons_uri(provider, provider_id)
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
            _readwrite_storage.put_object(provider, object_name, io.BytesIO(r.content), int(r.headers['Content-Length']), r.headers['Content-Type'])
        return _readwrite_storage.presigned_get_object(provider, object_name, expires=timedelta(minutes=3))
    elif collection == 'deezer':
        if isinstance(named_id, int):
            named_id = 'deezer:{}'.format(named_id)
        raise FileNotFoundError('No audio available for id "{}"'.format(named_id))
    else:
        try:
            object_name = next(_readonly_storage.list_objects(collection, prefix=named_id)).object_name
            return _readonly_storage.presigned_get_object(collection, object_name, expires=timedelta(minutes=3))
        except (StopIteration, minio.error.S3Error):
            raise FileNotFoundError('No audio available for id "{}"'.format(named_id))
