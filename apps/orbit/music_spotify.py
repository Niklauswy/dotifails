"""Import public Spotify lists from their published embed metadata, without an account."""
import json
import re
from urllib.parse import urlparse
from music_metadata import fetch


def spotify_entity(url):
    if url.startswith('spotify:'):
        match=re.fullmatch(r'spotify:(playlist|album|track):([A-Za-z0-9]{22})',url.strip())
    else:
        parsed=urlparse(url.strip())
        if parsed.scheme!='https' or parsed.hostname!='open.spotify.com':
            raise ValueError('Usa el enlace público de una playlist, álbum o canción de Spotify.')
        match=re.search(r'/(playlist|album|track)/([A-Za-z0-9]{22})(?:/|$)',parsed.path)
    if not match:raise ValueError('El enlace de Spotify no tiene un identificador válido.')
    return match.group(1),match.group(2)


def parse_embed(page,kind,key):
    match=re.search(r'<script\b(?=[^>]*\bid=[\"\']__NEXT_DATA__[\"\'])[^>]*>(.*?)</script>',page,re.S)
    if not match:raise ValueError('Spotify no publicó los datos de esta lista. Comprueba que sea pública.')
    try:entity=json.loads(match[1])['props']['pageProps']['state']['data']['entity']
    except (KeyError,ValueError,TypeError):raise ValueError('La lista de Spotify no se pudo leer.')
    tracks=[]
    entries=entity.get('trackList') or ([entity] if kind=='track' else [])
    for row in entries:
        uri=row.get('uri','')
        if not uri.startswith('spotify:track:') or not row.get('title'):continue
        artist=row.get('subtitle') or ', '.join(a.get('name','') for a in row.get('artists',[]))
        if not artist:continue
        tracks.append(dict(id=uri.split(':')[-1],title=row['title'],artist=artist.replace('\xa0',' '),
                           duration=(row.get('duration') or 0)/1000,prefer_audio=True))
    if not tracks:raise ValueError('Spotify no expone canciones para esta lista. Puede ser privada o no estar disponible.')
    cover=next((s.get('url') for s in entity.get('coverArt',{}).get('sources',[]) if s.get('url')),None)
    source=f'https://open.spotify.com/{kind}/{key}'
    return {'collections':[dict(id='spotify-'+key,title=entity.get('title') or entity.get('name') or 'Spotify',source=source,cover_url=cover,tracks=tracks)],'published_count':len(tracks)}


def import_link(url):
    kind,key=spotify_entity(url)
    page=fetch(f'https://open.spotify.com/embed/{kind}/{key}',limit=8*1024*1024).decode('utf-8')
    return parse_embed(page,kind,key)
