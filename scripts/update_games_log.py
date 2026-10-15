#!/usr/bin/env python3
"""Update a unified beaten/mastered log using the RA Web API; key stays in Actions."""
from __future__ import annotations
import json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path
from ra_api import RetroAchievementsClient, RetroAchievementsAPIError

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'games-log.json'
LEGACY = ROOT / 'legacy'
USER = os.getenv('RA_USERNAME', 'berti').strip() or 'berti'
AWARDS = {'mastered', 'beaten-hardcore'}

def field(obj, *keys):
    for key in keys:
        if key in obj and obj[key] not in (None, ''):
            return obj[key]
    return None

def is_subset(name, detail=None):
    text = str(name or '').lower()
    if re.search(r'\bsubset\b', text) or '[bonus]' in text:
        return True
    if detail:
        for key in ('IsSubset', 'isSubset', 'Subset', 'subset'):
            if detail.get(key) is True:
                return True
    return False

def load(path, fallback):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return fallback

def series_map():
    series = load(LEGACY/'franchises-source.json', {}).get('series', [])
    output = {}
    for item in series:
        for game in item.get('games', []):
            output.setdefault(int(game['id']), []).append((item['name'], game.get('releaseDate')))
        for gid in item.get('triggerMasteredGameIds', []):
            output.setdefault(int(gid), []).append((item['name'], None))
    return output

def release_choice(info, fallback=None):
    # The RA API can expose only one global release date. Use explicit region
    # fields when present; otherwise label the region as unknown.
    variants = [
        ('US', ('ReleaseDateUS','ReleasedUS','ReleaseDateNA','ReleasedNA', 'ReleaseDateNorthAmerica')),
        ('JP', ('ReleaseDateJP','ReleasedJP','ReleaseDateJapan','ReleasedJapan')),
        ('EU', ('ReleaseDateEU','ReleasedEU','ReleaseDateEurope','ReleasedEurope')),
        (None, ('Released','ReleaseDate','ReleasedAt','released','releaseDate')),
    ]
    for region, keys in variants:
        value = field(info, *keys)
        if value:
            return str(value)[:10], region
    if fallback:
        return fallback, None
    return None, None

def update():
    key = os.environ.get('RA_API_KEY', '').strip()
    if not key:
        raise RuntimeError('RA_API_KEY is missing: configure the repository Actions secret')
    client = RetroAchievementsClient(key)
    cache = {int(game['id']):game for game in load(TARGET, {}).get('games', [])}
    series = series_map()
    progress, offset = [], 0
    while True:
        data = client.user_completion_progress(USER, count=500, offset=offset)
        batch = field(data,'Results','results') or []
        progress.extend(batch)
        offset += len(batch)
        if not batch or offset >= int(field(data,'Total','total') or offset):
            break
    if not progress:
        raise RuntimeError('No completion records returned: refusing to overwrite the existing log')
    games = []
    for record in progress:
        kind = field(record, 'HighestAwardKind','highestAwardKind')
        if kind not in AWARDS:
            continue
        gid = int(field(record,'GameID','gameId'))
        title = field(record,'Title','title') or f'Game {gid}'
        if is_subset(title):
            continue
        prior = cache.get(gid, {})
        memberships = series.get(gid, [])
        result = {
            'id':gid, 'name':title,
            'console': field(record,'ConsoleName','consoleName') or prior.get('console'),
            'developer':prior.get('developer'), 'publisher':prior.get('publisher'),
            'genre':prior.get('genre'), 'releaseDate':prior.get('releaseDate'),
            'releaseRegion':prior.get('releaseRegion'), 'releaseDateGranularity':prior.get('releaseDateGranularity'),
            'franchise': memberships[0][0] if memberships else prior.get('franchise'),
            # User-curated cover badge: never replace from the RA API.
            'badge_url': prior.get('badge_url') or None,
            'timeToBeat': prior.get('timeToBeat'),
            'beatenCondition': prior.get('beatenCondition'),
            'beatenDate': prior.get('beatenDate') or (field(record,'HighestAwardDate','highestAwardDate') if kind == 'beaten-hardcore' else None),
            'masteryDate': prior.get('masteryDate') or (field(record,'HighestAwardDate','highestAwardDate') if kind == 'mastered' else None),
            'beaten':True, 'mastered':kind=='mastered',
            'awardKind':kind,
        }
        # Need details for first import or incomplete metadata. Do not retry
        # unsupported fields indefinitely every day: after the first lookup,
        # record that the API metadata was checked.
        if not prior.get('metadataChecked') or any(not prior.get(k) for k in ('developer', 'publisher', 'genre', 'releaseDate')):
            try:
                details = client.game_extended(gid)
                if is_subset(title, details):
                    continue
                for output, names in (
                    ('developer',('Developer','developer')),
                    ('publisher',('Publisher','publisher')),
                    ('genre',('Genre','genre')),
                    ('console',('ConsoleName','consoleName')),
                ):
                    result[output] = result[output] or field(details,*names)
                fallback_release = next((date for _,date in memberships if date),None) or result['releaseDate']
                
                if not result['releaseDate']:
                    result['releaseDate'],result['releaseRegion'] = release_choice(details,fallback_release)
                result['releaseDateGranularity'] = field(details, 'ReleasedAtGranularity', 'releasedAtGranularity') or result['releaseDateGranularity']
                result['metadataChecked'] = True
            except RetroAchievementsAPIError as exc:
                print(f'Warning: metadata for {gid}: {exc}', file=sys.stderr)
                result['metadataChecked'] = False
        else:
            result['metadataChecked'] = True
        games.append(result)
    # RA game id determines unique game; preserve profile awards, exclude subsets.
    games = sorted({g['id']:g for g in games}.values(),key=lambda x:(x['name'].casefold(), x['id']))
    validation = {
        'uniqueBaseGames': len(games),
        'masteredBaseGames': sum(g['mastered'] for g in games),
        'beatenOnlyBaseGames': sum(not g['mastered'] for g in games),
        'excludedSubsets': sum(
            field(r,'HighestAwardKind','highestAwardKind') in AWARDS
            and is_subset(field(r,'Title','title')) for r in progress
        ),
        'missingMetadata': {k: sum(not g.get(k) for g in games) for k in ('developer','publisher','genre','releaseDate','franchise')},
        'sourceCompletionRecords': len(progress),
    }
    payload = {
        'schemaVersion':2,
        'generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'source':f'https://retroachievements.org/user/{USER}',
        'username':USER,'dataStatus':'updated-from-api-metadata-may-be-incomplete',
        'total':len(games), 'masteredCount':sum(g['mastered'] for g in games),
        'validation':validation, 'dateNotes':'Mastery awards are not beaten dates. For mastered games, beatenDate must be independently verified or manually entered.', 'games':games,
    }
    TARGET.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'Wrote {len(games)} base games ({payload["masteredCount"]} mastered)')

if __name__ == '__main__':
    try:
        update()
    except (RetroAchievementsAPIError, RuntimeError) as exc:
        sys.exit(str(exc))
