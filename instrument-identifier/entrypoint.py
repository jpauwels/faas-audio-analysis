#!/usr/bin/env python2
import sys
import requests
import subprocess
import urlparse
import os.path

if __name__ == '__main__':
    print(sys.argv)
    p = urlparse.urlparse(sys.argv[-1])
    if p.scheme.startswith('http'):
        audio_path = os.path.join(os.getcwd(), os.path.basename(p.path))
        sys.stderr.write('Downloading {} and writing to {}\n'.format(sys.argv[-1], audio_path))
        with open(audio_path, 'wb') as audio_file:
            audio_file.write(requests.get(sys.argv[-1]).content)
    else:
        audio_path = sys.argv[-1]
    cmd = ['sonic-annotator'] + sys.argv[1:-1] + [audio_path]
    sys.stderr.write(' '.join(cmd) + '\n')
    print(subprocess.check_output(cmd))
    if p.scheme.startswith('http'):
        os.remove(audio_path)
        sys.stderr.write('Deleted {}\n'.format(audio_path))