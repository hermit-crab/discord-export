import argparse
import asyncio
import json
import os
import re
import time
import traceback
from contextlib import closing
from datetime import datetime
from pprint import pformat
from urllib.parse import quote as urlquote

import aiohttp
import dateparser
import tqdm

# TODO (maybe maybe): simplistic continuation?
# WONTDO: browse servers / channels
# WONTDO: rate limits (doesn't seem needed)
# WONTDO: CLI interactivity
# WONTDO: UI
# WONTDO: --before (overcomplicates code, maybe consider explicit --stop-after)


DISCORD_EPOCH = 1420070400000
GOOD_CHANNEL_TYPES = {
    # https://discord.com/developers/docs/resources/channel#channel-object-channel-types
    0: 'GUILD_TEXT',
    1: 'DM',
    3: 'GROUP_DM',
    5: 'GUILD_NEWS',
}
GOOD_CHANNEL_NAMES = {n: v for v, n in GOOD_CHANNEL_TYPES.items()}
IS_WINDOWS = os.name == 'nt'


class DiscordHTTP:
    def __init__(self, token):
        self._token = token

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._session.close()

    async def get(self, path, **params):
        url = 'https://discord.com/api/v8' + path
        if params:
            url += '?' + '&'.join(f'{k}={v}' for k, v in params.items())
        async with self._session.get(url, headers={'Authorization': self._token}) as rp:
            data = await rp.json()
            if 'code' in data:
                raise Exception(f'Error HTTP{rp.status} on an API request to {url!r}:\n{pformat(data)}')
            return data


def dump_record(file, type, data):
    file.write(json.dumps({'type': type, 'data': data, 'ts': time.time()}, separators=(',', ':'), ensure_ascii=False))
    file.write('\n')


def snowflake_from_ts(ts):
    return int(ts * 1000 - DISCORD_EPOCH) << 22


def snowflake_to_ts(snowflake):
    return ((int(snowflake) >> 22) + DISCORD_EPOCH) / 1000


def safe_str(val):
    val = re.sub(r'[\s|\.]+', '_', val.strip())
    return ''.join(c for c in val if c.isalnum() or c in {'_', '-'})


def clean_content(message, guild=None):
    text = message.get('content')
    if not isinstance(text, str):
        return ''

    for member in message.get('mentions', []):
        text = re.sub('<@%s>' % member['id'], '@' + member['username'], text)
        text = re.sub('<@!%s>' % member['id'],'@' + member['username'], text)

    if guild:
        for channel in guild.get('__channels', []):
            text = re.sub('<#%s>' % channel['id'], '#' + channel['name'], text)

        for role in guild.get('roles', []):
            text = re.sub('<@&%s>' % role['id'], '@' + role['name'], text)

    return text


def make_filename(channel, current_user, guild=None):
    if guild:
        a = guild['name']
    else:
        a = GOOD_CHANNEL_TYPES[channel['type']] + '_' + current_user['username']
    b = make_channel_name(channel)
    c = datetime.utcnow().isoformat().replace(':', '_') + 'Z'
    return '{}.{}.{}.jl'.format(safe_str(a), safe_str(b), c)


def make_channel_name(channel):
    if channel.get('name'):
        return channel['name']
    elif channel['type'] == GOOD_CHANNEL_NAMES['DM']:
        return channel['recipients'][0]['username']
    elif channel['type'] == GOOD_CHANNEL_NAMES['GROUP_DM']:
        users = channel['recipients']
        return users[0]['username'] + f' and {len(users)-1} others'
    raise Exception('unexpected channel type, couldn\'t figure channel name')


async def export_server(discord, guild_id, args):
    channels = await discord.get(f'/guilds/{guild_id}/channels')
    channels = [ch for ch in channels if ch['type'] in GOOD_CHANNEL_TYPES]
    print(f'** will pull {len(channels)} channels: {[ch["name"] for ch in channels]}')
    for n, ch in enumerate(channels, 1):
        print(f'==> channel {n}/{len(channels)}: {ch["name"]} ({ch["id"]})')
        try:
            await export_channel(discord, ch['id'], args)
        except Exception:
            print(f'** failed archiving the channel, full traceback:\n{traceback.format_exc()}', end='')


async def export_dms(discord, args):
    channels = await discord.get('/users/@me/channels')
    print(f'** will pull {len(channels)} DM channels')
    for n, ch in enumerate(channels, 1):
        print(f'==> channel {n}/{len(channels)}: {make_channel_name(ch)} ({ch["id"]})')
        try:
            await export_channel(discord, ch['id'], args)
        except Exception:
            print(f'** failed archiving the channel, full traceback:\n{traceback.format_exc()}', end='')


async def export_channel(discord, channel_id, args):
    d = discord

    channel = await d.get(f'/channels/{channel_id}')
    guild_id = channel.get('guild_id')
    guild = await d.get(f'/guilds/{guild_id}') if guild_id else None

    current_user = await d.get('/users/@me')
    fname = make_filename(channel, current_user, guild)
    fpath = os.path.join(args.output_dir, fname)
    print(f'==> exporting to {fname}')

    with open(fpath, 'w', encoding='utf-8') as f:
        dump_record(f, 'me', current_user)
        channel['__pinned_messages'] = await d.get(f'/channels/{channel_id}/pins')
        dump_record(f, 'channel', channel)
        if guild:
            guild['__channels'] = await d.get(f'/guilds/{guild_id}/channels')
            dump_record(f, 'guild', guild)

        after = args.after or 0

        first_msg = next(iter(await d.get(f'/channels/{channel_id}/messages', after=after, limit=1)), None)
        if not first_msg:
            print('** no messages')
            return
        last_msg = next(iter(await d.get(f'/channels/{channel_id}/messages', limit=1)), None)
        pbar_a, pbar_b = snowflake_to_ts(first_msg['id']), snowflake_to_ts(last_msg['id'])

        exported = 0
        limit = 100
        bar_fmt = '{desc} [{bar}] {percentage:3.2f}% | {elapsed}<{remaining}'
        with tqdm.tqdm(total=100, dynamic_ncols=True, bar_format=bar_fmt, ascii=IS_WINDOWS) as pbar:
            while True:
                messages = await d.get(f'/channels/{channel_id}/messages', after=after, limit=limit)
                messages = list(reversed(messages))
                for message in messages:
                    query_reaction_users = message.get('reactions', [])
                    if args.skip_reaction_users:
                        query_reaction_users = []
                    for reaction in query_reaction_users:
                        emoji = reaction['emoji']
                        if reaction['emoji']['id']:
                            emoji = emoji['name'] + ':' + emoji['id']
                        else:
                            emoji = emoji['name']
                        reaction['__users'] = await d.get(
                            f'/channels/{channel_id}/messages/{message["id"]}/reactions/{urlquote(emoji)}', limit=100
                        )
                        # XXX: deliberately not paginating reaction users further
                    message['__clean_content'] = clean_content(message, guild)
                    dump_record(f, 'message', message)
                    after = message['id']

                ts = snowflake_to_ts(after)
                exported += len(messages)
                at = datetime.fromtimestamp(ts).strftime('%b %Y')
                pbar.set_description_str(f'{exported:,} msgs saved, at {at}')
                if len(messages) == limit:
                    pbar.update((ts - pbar_a) / (pbar_b - pbar_a) * 100 - pbar.n)
                else:
                    pbar.update(100 - pbar.n)
                    break


def render(file):
    for l in file:
        record = json.loads(l)
        type_, data = record['type'], record['data']
        if type_ == 'me':
            print('** archive initiator: {}#{} ({})'.format(data['username'], data['discriminator'], data['id']))
        elif type_ == 'channel':
            print('** channel: {} ({})'.format(make_channel_name(data), data['id']))
        elif type_ == 'guild':
            print('** server: {} ({})'.format(data['name'], data['id']))
        elif type_ == 'message':
            date = datetime.fromtimestamp(snowflake_to_ts(data['id']))
            date = str(date).split('.')[0]  # remove milliseconds
            author = data.get('author', {}).get('username', {}) or '?UNKNOWN?'
            content = re.sub(r'<\w?(:\w+:)\d+>', r'\1', data['__clean_content'])
            print(date, author + ':', content)

            tab = '                    '

            for attch in data.get('attachments', []):
                print(tab + f'[file: {attch["url"]}]')

            reacts = data.get('reactions', [])
            reacts_parts = []
            for react in reacts:
                count, emoji = react.get('count') or 1, react['emoji']
                reacts_parts.append(emoji['name'])
                if count > 1:
                    reacts_parts[-1] += f'x{count}'
            if reacts: print(tab + '[reacts: {}]'.format(', '.join(reacts_parts)))
        else:
            print(f'** unrecognized record type {type_!r}')


def date_or_message_id(val):
    ret = None
    if val.isdigit():
        try:
            if snowflake_to_ts(val) < DISCORD_EPOCH/1000: raise ValueError
            ret = int(val)
        except Exception as e:
            pass
    if not ret: ret = dateparser.parse(val)
    if not ret: raise argparse.ArgumentTypeError(f'failed to parse {val!r} as date or message_id')
    return ret


async def async_cli():

    def add_common_export_args(parser):
        parser.add_argument('--token', '-t')
        parser.add_argument('--output-dir', '-o', default='.')
        parser.add_argument('--after', type=date_or_message_id)
        parser.add_argument('--skip-reaction-users', action='store_true')

    parser = argparse.ArgumentParser(prog='discord-export')
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparser = subparsers.add_parser('export-channel')
    subparser.add_argument('channel_id')
    add_common_export_args(subparser)

    subparser = subparsers.add_parser('export-server')
    subparser.add_argument('server_id')
    add_common_export_args(subparser)

    subparser = subparsers.add_parser('export-dms')
    add_common_export_args(subparser)

    subparser = subparsers.add_parser('render')
    subparser.add_argument('file', type=argparse.FileType())

    args = parser.parse_args()

    if getattr(args, 'after', None):
        msg = '** --after parsed as '
        if isinstance(args.after, int):
            # already snowflake
            msg += str(datetime.fromtimestamp(snowflake_to_ts(args.after)))
            msg += ' (local timezone, using snowflake)'
        else:
            # parsed as date
            msg += str(args.after)
            if not args.after.tzinfo:
                msg += ' (local timezone)'
            args.after = snowflake_from_ts(args.after.timestamp())
        print(msg)

    if args.command in ['export-channel', 'export-server', 'export-dms']:
        async with DiscordHTTP(args.token) as discord:
            if args.command == 'export-channel':
                await export_channel(discord, args.channel_id, args)
            elif args.command == 'export-server':
                await export_server(discord, args.server_id, args)
            elif args.command == 'export-dms':
                await export_dms(discord, args)
    elif args.command == 'render':
        with closing(args.file):
            render(args.file)


def cli():
    asyncio.run(async_cli())
