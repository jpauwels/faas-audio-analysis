import requests
import os
import minio
import io
import os.path
import urllib.parse
import cgi
import mimetypes
from datetime import timedelta
from .config_direct_audio import providers, audio_uri as provider_uri


_client = minio.Minio(os.getenv('MINIO_HOSTNAME'), access_key=os.getenv('MINIO_ACCESS_KEY'), secret_key=os.getenv('MINIO_SECRET_KEY'), secure=False)


def audio_uri(provider_id, provider):
    if provider in ['jamendo-tracks', 'freesound-sounds']:
        object_prefix = provider_id[-2:] + '/' + provider_id
    else:
        object_prefix = provider_id
    try:
        object_name = next(_client.list_objects(provider, prefix=object_prefix)).object_name
    except (StopIteration, minio.error.NoSuchBucket):
        url = provider_uri(provider_id, provider)
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
        _client.put_object(provider, object_name, io.BytesIO(r.content), int(r.headers['Content-Length']), r.headers['Content-Type'])
    return _client.presigned_get_object(provider, object_name, expires=timedelta(minutes=3))
