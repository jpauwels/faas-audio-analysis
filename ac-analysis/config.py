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
        return 'http://{}'.format(file_id)
    else:
        raise ValueError('Unknown audio provider "{}"'.format(provider))
