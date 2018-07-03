providers = ['jamendo', 'freesound', 'europeana']

def audio_uri(file_id, provider):
    if provider == 'jamendo':
        return 'https://flac.jamendo.com/download/track/{}/flac'.format(file_id)
    elif provider == 'freesound':
        return 'http://freesound.org/data/previews/{id:.3}/{id}-hq.ogg'.format(id=file_id)
    elif provider == 'europeana':
        return 'http://{}'.format(file_id)
    else:
        raise ValueError('Unknown audio provider "{}"'.format(provider))
