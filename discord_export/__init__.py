import argparse
import asyncio
import json
import os
import re
from datetime import datetime
from pprint import pformat

import aiohttp
import dateparser
import tqdm

# TODO: dms / server
# TODO: dont fail full server pull if you cant read channel
# TODO: --after support snowflake
# TODO: render command
# WONTDO: browse servers / channels
# WONTDO: rate limits
# WONTDO: CLI interactivity
# WONTDO: UI
# WONTDO: --before

DISCORD_EPOCH = 1420070400000


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
    file.write(json.dumps({'type': type, 'data': data}, separators=(',', ': '), ensure_ascii=False))
    file.write('\n')


def snowflake_from_ts(ts):
    return int(ts * 1000 - DISCORD_EPOCH) << 22


def snowflake_to_ts(snowflake):
    return ((int(snowflake) >> 22) + DISCORD_EPOCH) / 1000


def safe_str(val):
    val = re.sub(r'[\s|\.]+', '_', val.strip())
    return ''.join(c for c in val if c.isalnum() or c in {'_', '-'})


def clean_content(message, guild):
    text = message.get('content')
    if not isinstance(text, str):
        return ''

    for member in message.get('mentions', []):
        text = re.sub('<@%s>' % member['id'], '@' + member['username'], text)
        text = re.sub('<@!%s>' % member['id'],'@' + member['username'], text)

    for channel in guild.get('__channels', []):
        text = re.sub('<#%s>' % channel['id'], '#' + channel['name'], text)

    for role in guild.get('roles', []):
        text = re.sub('<@&%s>' % role['id'], '@' + role['name'], text)

    return text


async def export_channel(discord, args):
    d = discord

    channel = await d.get(f'/channels/{args.channel_id}')
    guild_id = channel['guild_id']
    guild = await d.get(f'/guilds/{guild_id}')

    fname = '{}.{}.{}.jl'.format(
        safe_str(guild['name']),
        safe_str(channel['name']),
        datetime.utcnow().isoformat().replace(':', '_') + 'Z'
    )
    fpath = os.path.join(args.output_dir, fname)
    print(f'==> exporting {fname}')

    with open(fpath, 'w') as f:
        channel['__pinned_messages'] = await d.get(f'/channels/{args.channel_id}/pins')
        dump_record(f, 'channel', channel)
        guild['__channels'] = await d.get(f'/guilds/{guild_id}/channels')
        dump_record(f, 'guild', guild)
        dump_record(f, 'me', await d.get('/users/@me'))

        after = args.after or 0

        first_msg = next(iter(await d.get(f'/channels/{args.channel_id}/messages', after=after, limit=1)), None)
        if not first_msg:
            print('** no messages')
        last_msg = next(iter(await d.get(f'/channels/{args.channel_id}/messages', limit=1)), None)
        pbar_a, pbar_b = snowflake_to_ts(first_msg['id']), snowflake_to_ts(last_msg['id'])

        exported = 0
        limit = 100
        bar_fmt = '{desc} [{bar}] {percentage:3.2f}% | {elapsed}<{remaining}'
        with tqdm.tqdm(total=100, dynamic_ncols=True, bar_format=bar_fmt) as pbar:
            while True:
                messages = await d.get(f'/channels/{args.channel_id}/messages', after=after, limit=limit)
                messages = list(reversed(messages))
                after = messages[-1]['id']
                for message in messages:
                    for reaction in message.get('reactions', []):
                        emoji = reaction['emoji']
                        if reaction['emoji']['id']:
                            emoji = emoji['name'] + ':' + emoji['id']
                        else:
                            emoji = emoji['name']
                        reaction['__users'] = await d.get(
                            f'/channels/{args.channel_id}/messages/{message["id"]}/reactions/{emoji}', limit=100
                        )
                        # XXX: deliberately not paginating reaction users further
                    message['__clean_content'] = clean_content(message, guild)
                    dump_record(f, 'message', message)

                ts = snowflake_to_ts(after)
                exported += len(messages)
                pbar.set_description_str(f'{exported:,} msgs saved')
                if len(messages) == limit:
                    pbar.update((ts - pbar_a) / (pbar_b - pbar_a) * 100 - pbar.n)
                else:
                    pbar.update(100 - pbar.n)
                    break


async def async_cli():
    def date_arg(val):
        date = dateparser.parse(val)
        if not date:
            raise ValueError(f'failed to parse as {val!r} date')
        return date

    def add_common_args(parser):
        parser.add_argument('--token', '-t')
        parser.add_argument('--output-dir', '-o', default='.')
        parser.add_argument('--after', type=date_arg)

    parser = argparse.ArgumentParser(prog='discord-export')
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparser = subparsers.add_parser('export-channel')
    subparser.add_argument('channel_id')
    add_common_args(subparser)
    args = parser.parse_args()

    if args.after:
        msg = f'** --after parsed as {args.after}'
        if not args.after.tzinfo:
            msg += ' (local timezone)'
        print(msg)
        args.after = snowflake_from_ts(args.after.timestamp())

    if args.command in ['export-channel']:
        async with DiscordHTTP(args.token) as discord:
            await export_channel(discord, args)


def cli():
    asyncio.run(async_cli())
