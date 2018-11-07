import requests
import os

providers = ['jamendo', 'freesound', 'europeana']

def audio_uri(file_id, provider):
    if provider == 'jamendo':
        return 'https://flac.jamendo.com/download/track/{}/flac'.format(file_id)
    elif provider == 'freesound':
        r = requests.get('https://freesound.org/apiv2/sounds/{id}/'.format(id=file_id), params={'token': os.getenv('FREESOUND_API_KEY'), 'fields': 'previews'})
        return r.json()['previews']['preview-hq-ogg']
    elif provider == 'europeana':
        r = requests.get('http://www.europeana.eu/api/v2/record/{id}.json'.format(id=file_id), params={'wskey': os.getenv('EUROPEANA_API_KEY')})
        if r.status_code == requests.codes['ok'] and r.json()['success']:
            return r.json()['object']['aggregations'][0]['edmIsShownBy']
        else:
            raise  ValueError('The audio file for id "{}" could not be retrieved from Europeana'.format(file_id))
    else:
        raise ValueError('Unknown audio provider "{}"'.format(provider))
