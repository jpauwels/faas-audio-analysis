import requests
import os

all_collections = ['audiocommons']
namespaces = {'audiocommons': ['jamendo-tracks', 'freesound-sounds', 'europeana-res']}


def audio_uri(collection, linked_id):
    if collection == 'audiocommons':
        provider, provider_id = validate_audiocommons_id(linked_id)
        return audiocommons_uri(provider, provider_id)
    else:
        raise ValueError('Unknown collection "{}"'.format(collection))


def validate_audiocommons_id(linked_id):
    try:
        provider, provider_id = linked_id.split(':')
    except ValueError:
        raise ValueError('Malformed id "{}". Needs to be of the form "content-provider:provider-id"'.format(linked_id))
    if provider not in namespaces['audiocommons']:
        raise ValueError('Unknown content provider "{}". Allowed providers are : {}'.format(provider, namespaces['audiocommons']))
    return provider, provider_id


def audiocommons_uri(provider, provider_id):
    if provider == 'jamendo-tracks':
        return 'https://prod-1.storage.jamendo.com/download/track/{}/flac/'.format(provider_id)
    elif provider == 'freesound-sounds':
        r = requests.get('https://freesound.org/apiv2/sounds/{id}/'.format(id=provider_id), params={'token': os.getenv('FREESOUND_API_KEY'), 'fields': 'previews'})
        return r.json()['previews']['preview-hq-ogg']
    elif provider == 'europeana-res':
        r = requests.get('http://www.europeana.eu/api/v2/record/{id}.json'.format(id=provider_id), params={'wskey': os.getenv('EUROPEANA_API_KEY')})
        if r.status_code == requests.codes['ok'] and r.json()['success']:
            return r.json()['object']['aggregations'][0]['edmIsShownBy']
        else:
            raise  ValueError('The audio file for id "{}" could not be retrieved from Europeana'.format(provider_id))
    else:
        raise ValueError('Unknown AudioCommons audio provider "{}"'.format(provider))