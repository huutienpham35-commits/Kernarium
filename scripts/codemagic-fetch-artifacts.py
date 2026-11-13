#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Download accepted upstream build inputs, never substitute another release."""
import hashlib
import json
from pathlib import Path
import shlex
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def descriptor(path, key):
    for line in (ROOT / path).read_text().splitlines():
        if line.startswith(key + '='):
            return shlex.split(line.split('=', 1)[1])[0]
    raise RuntimeError('Missing descriptor key: ' + key)

def main():
    # Pinned release metadata avoids shared CI IP GitHub API rate limits.
    assets = json.loads((ROOT / 'scripts/codemagic-artifacts.json').read_text())
    specs = [
        ('kernel/mainline-6.18/artifacts/accepted-android-4k.env', 'UML_KERNEL_ARTIFACT_DIRECTORY_NAME', '.build/kernel/artifacts'),
        ('android/lineage-24/metadata/accepted-release.env', 'LINEAGE24_ACCEPTED_DIRECTORY_NAME', '.build/android/releases'),
    ]
    for desc, key, destination in specs:
        name = descriptor(desc, key)
        asset = assets.get(name + '.tar.gz')
        if not asset:
            raise RuntimeError('Accepted artifact is not published: ' + name)
        digest = asset.get('digest', '')
        if not digest.startswith('sha256:'):
            raise RuntimeError('Release asset has no SHA-256 digest: ' + name)
        cache = ROOT / '.build/downloads'
        cache.mkdir(parents=True, exist_ok=True)
        archive = cache / asset['name']
        sha = hashlib.sha256()
        with urllib.request.urlopen(asset['browser_download_url'], timeout=180) as response, archive.open('wb') as out:
            while block := response.read(4 * 1024 * 1024):
                sha.update(block)
                out.write(block)
        if archive.stat().st_size != asset['size'] or sha.hexdigest() != digest.split(':', 1)[1]:
            raise RuntimeError('Artifact integrity failure: ' + name)
        target = ROOT / destination
        target.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as bundle:
            members = bundle.getmembers()
            if not all(m.name.split('/')[0] in (name, '.') for m in members):
                raise RuntimeError('Unexpected archive layout: ' + name)
            bundle.extractall(target, filter='data')
        if not (target / name).is_dir():
            raise RuntimeError('Missing extracted release directory: ' + name)
        print('Verified and installed:', name)

if __name__ == '__main__':
    main()
