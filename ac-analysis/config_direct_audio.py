import requests
import os


providers = ['jamendo-tracks', 'freesound-sounds', 'europeana-res']


def audio_uri(provider_id, provider):
    if provider == 'jamendo-tracks':
        return 'https://flac.jamendo.com/download/track/{}/flac'.format(provider_id)
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
        raise ValueError('Unknown audio provider "{}"'.format(provider))
