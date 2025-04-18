import requests
import os
import minio
import io
import os.path
import urllib.parse
from email.message import Message
import mimetypes
from datetime import timedelta
from .config_ac_direct_audio import all_collections, namespaces, validate_audiocommons_id, audiocommons_uri
from .secrets import get_secrets

_secrets = get_secrets(['object-store-access-key', 'object-store-secret-key'])
_cache_storage = minio.Minio(os.getenv('OBJECT_STORE_HOSTNAME', 'localhost'), access_key=_secrets['object-store-access-key'], secret_key=_secrets['object-store-secret-key'], secure=False)


def audio_uri(collection, named_id):
    if collection == 'audiocommons':
        provider, provider_id = validate_audiocommons_id(named_id)
        if provider in ['jamendo-tracks', 'freesound-sounds']:
            object_prefix = provider_id[-2:] + '/' + provider_id
        else:
            object_prefix = provider_id
        try:
            object_name = next(_cache_storage.list_objects(provider, prefix=object_prefix)).object_name
        except (StopIteration, minio.error.S3Error):
            url = audiocommons_uri(provider, provider_id)
            r = requests.get(url)
            r.raise_for_status()
            msg = Message()
            try:
                msg['Content-Disposition'] = r.headers['Content-Disposition']
                file_name = msg.get_filename()
                file_ext = os.path.splitext(file_name)[1]
            except KeyError:
                file_ext = os.path.splitext(urllib.parse.urlparse(url).path)[1]
                if not file_ext:
                    try:
                        msg['Content-Type'] = r.headers['Content-Type']
                        file_ext = mimetypes.guess_extension(msg.get_content_type())
                    except KeyError:
                        pass
                    file_ext = '' if file_ext is None else file_ext
            object_name = object_prefix+file_ext
            try:
                _cache_storage.put_object(provider, object_name, io.BytesIO(r.content), int(r.headers['Content-Length']), r.headers['Content-Type'])
            except minio.error.S3Error as err:
                if err.code == 'NoSuchBucket':
                    _cache_storage.make_bucket(provider)
                    _cache_storage.put_object(provider, object_name, io.BytesIO(r.content), int(r.headers['Content-Length']), r.headers['Content-Type'])
        return _cache_storage.presigned_get_object(provider, object_name, expires=timedelta(minutes=3))
    else:
        raise ValueError('Unknown collection "{}"'.format(collection))
