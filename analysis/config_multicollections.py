import requests
import yt_dlp
import internetarchive
import content_types
import os
import tempfile
import minio
import io
import os.path
import urllib.parse
from email.message import Message
import mimetypes
from datetime import timedelta
from pathlib import Path
from .secrets import get_secrets
from . import database


_secrets = get_secrets(['object-store-access-key', 'object-store-secret-key', 'freesound-api-key', 'europeana-api-key'])
_cache_storage = minio.Minio(os.getenv('OBJECT_STORE_HOSTNAME', 'localhost'), access_key=_secrets['object-store-access-key'], secret_key=_secrets['object-store-secret-key'], secure=False)
_ydl_opts = {
    'quiet': False,
    'format': 'bestaudio/best',
    'keepvideo': False,
    'nooverwrites': True,
    'outtmpl': '%(id)s.%(ext)s',
    'paths': {},
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'best',
    }],
}

all_collections = ['jamendo', 'freesound', 'europeana', 'deezer', 'ilikemusic', 'youtube', 'internet-archive'] # free-music-archive, soundcloud?, spotify
namespaces = {'deezer': ['deezer', 'wasabi']}


def alias_id(collection, named_id):
    if collection == 'deezer':
        namespace, file_id = named_id.split(':')
        if namespace == 'wasabi':
            return database.map_id(file_id, 'deezer', 'wasabi_song', 'id_song_deezer')
        return file_id
    elif collection in ('jamendo', 'freesound'):
        return int(named_id)
    else:
        return named_id


def audio_url(collection, file_id):
    if collection == 'jamendo':
        return f'https://prod-1.storage.jamendo.com/download/track/{file_id}/flac/'
    if collection == 'freesound':
        r = requests.get(f'https://freesound.org/apiv2/sounds/{file_id}/', params={'token': _secrets['freesound-api-key'], 'fields': 'previews'})
        if r.status_code == requests.codes['ok']:
            return r.json()['previews']['preview-hq-ogg']
        else:
            raise FileNotFoundError(f'The audio file for id "{file_id}" could not be retrieved from Freesound')
    if collection == 'europeana':
        r = requests.get(f'http://www.europeana.eu/api/v2/record/{file_id}.json', headers={'X-Api-Key': _secrets['europeana-api-key']})
        if r.status_code == requests.codes['ok'] and r.json()['success']:
            return r.json()['object']['aggregations'][0]['edmIsShownBy']
        else:
            raise FileNotFoundError(f'The audio file for id "{file_id}" could not be retrieved from Europeana')
    raise ValueError(f'No direct audio URL available for collection "{collection}"')


def audio_uri(collection, file_id):
    if collection not in all_collections:
        raise ValueError('Unknown collection "{}"'.format(collection))
    if collection == 'deezer':
        if isinstance(file_id, int):
            file_id = f'deezer:{file_id}'
        raise FileNotFoundError(f'No audio available for id "{file_id}"')
    if collection in ['europeana', 'internet-archive']:
        object_prefix = file_id
    else:
        object_prefix = f'{str(file_id)[-2:]}/{file_id}'

    # Check if the file is already in the cache
    try:
        object_name = next(_cache_storage.list_objects(collection, prefix=object_prefix)).object_name
    except (StopIteration, minio.error.S3Error):
        # Use libraries to download the file
        if collection in ['youtube', 'internet-archive']:
            with tempfile.TemporaryDirectory() as tmpdir:
                if collection == 'youtube':
                    _ydl_opts['paths'].update({'home': tmpdir})
                    try:
                        with yt_dlp.YoutubeDL(_ydl_opts) as ydl:
                            ydl.download([file_id])
                    except yt_dlp.DownloadError:
                        raise FileNotFoundError(f'Invalid Youtube ID "{file_id}"')
                    object_path = list(Path(tmpdir).glob(f'{file_id}.*'))[0]
                    object_name = object_prefix + object_path.suffix
                elif collection == 'internet-archive':
                    try:
                        item, file_name = file_id.split('/', 1)
                    except ValueError:
                        raise FileNotFoundError(f'Invalid Internet Archive ID "{file_id}". Needs to be of the form "item/file_name"')
                    internetarchive.download(
                        item,
                        files=[file_name],
                        destdir=tmpdir,
                        on_the_fly=False,
                        verbose=True,
                    )
                    object_path = list(Path(tmpdir).glob(f'{file_id}*'))[0]
                    object_name = file_id
                object_type = content_types.get_content_type(object_name, treat_as_binary=True)
                try:
                    _cache_storage.fput_object(collection, object_name, object_path, object_type)
                except minio.error.S3Error as err:
                    if err.code == 'NoSuchBucket':
                        _cache_storage.make_bucket(collection)
                        _cache_storage.fput_object(collection, object_name, object_path, object_type)
        # Download url into memory
        else:
            url = audio_url(collection, file_id)
            r = requests.get(url)
            r.raise_for_status()
            content_type = r.headers['Content-Type']
            msg = Message()
            try:
                msg['Content-Disposition'] = r.headers['Content-Disposition']
                file_name = msg.get_filename()
                file_ext = os.path.splitext(file_name)[1]
            except KeyError:
                file_ext = os.path.splitext(urllib.parse.urlparse(url).path)[1]
                if not file_ext:
                    try:
                        msg['Content-Type'] = content_type
                        file_ext = mimetypes.guess_extension(msg.get_content_type(), strict=False)
                    except KeyError:
                        pass
                    file_ext = '' if file_ext is None else file_ext
            object_name = object_prefix+file_ext
            object_content = io.BytesIO(r.content)
            object_size = object_content.getbuffer().nbytes
            object_type = content_type if content_type.startswith('audio/') else content_types.get_content_type(object_name, treat_as_binary=True)
            try:
                _cache_storage.put_object(collection, object_name, object_content, object_size, object_type)
            except minio.error.S3Error as err:
                if err.code == 'NoSuchBucket':
                    _cache_storage.make_bucket(collection)
                    _cache_storage.put_object(collection, object_name, object_content, object_size, object_type)
    return _cache_storage.presigned_get_object(collection, object_name, expires=timedelta(minutes=3))
