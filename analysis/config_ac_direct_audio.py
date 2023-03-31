import requests
from .secrets import get_secrets

all_collections = ['audiocommons']
namespaces = {'audiocommons': ['jamendo-tracks', 'freesound-sounds', 'europeana-res']}
_secrets = get_secrets(['freesound-api-key', 'europeana-api-key'])


def audio_uri(collection, linked_id):
    if collection == 'audiocommons':
        provider, provider_id = validate_audiocommons_id(linked_id)
        return audiocommons_uri(provider, provider_id)
    else:
        raise ValueError('Unknown collection "{collection}"')


def validate_audiocommons_id(linked_id):
    try:
        provider, provider_id = linked_id.split(':')
    except ValueError:
        raise ValueError(f'Malformed id "{linked_id}". Needs to be of the form "content-provider:provider-id"')
    if provider not in namespaces['audiocommons']:
        raise ValueError(f'Unknown content provider "{provider}". Allowed providers are : {namespaces["audiocommons"]}')
    return provider, provider_id


def audiocommons_uri(provider, provider_id):
    if provider == 'jamendo-tracks':
        return f'https://prod-1.storage.jamendo.com/download/track/{provider_id}/flac/'
    elif provider == 'freesound-sounds':
        r = requests.get(f'https://freesound.org/apiv2/sounds/{provider_id}/', params={'token': _secrets['freesound-api-key'], 'fields': 'previews'})
        return r.json()['previews']['preview-hq-ogg']
    elif provider == 'europeana-res':
        r = requests.get(f'http://www.europeana.eu/api/v2/record/{provider_id}.json', params={'wskey': _secrets['europeana-api-key']})
        if r.status_code == requests.codes['ok'] and r.json()['success']:
            return r.json()['object']['aggregations'][0]['edmIsShownBy']
        else:
            raise  ValueError(f'The audio file for id "{provider_id}" could not be retrieved from Europeana')
    else:
        raise ValueError(f'Unknown AudioCommons audio provider "{provider}"')
