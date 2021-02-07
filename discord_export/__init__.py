import argparse
import asyncio
import json
import os
from datetime import datetime
from pprint import pformat

import aiohttp


DISCORD_EPOCH = 1420070400000


class DiscordHTTPSession(aiohttp.ClientSession):
    def __init__(self, token, *args, **kw):
        self._discord_token = token
        super().__init__(*args, **kw)

    async def _request(self, method, path, **kwargs):
        url = 'https://discord.com/api/v8' + path
        headers = kwargs.setdefault('headers', {})
        headers['Authorization'] = self._discord_token
        rp = await super()._request(method, url, **kwargs)
        rp.data = await rp.json()
        if 'code' in rp.data:
            raise Exception(f'Error on an API request to {path!r}:\n{pformat(rp.data)}')
        return rp


def dump_record(file, type, data):
    file.write(json.dumps({'type': type, 'data': data}, indent=2))
    file.write('\n')


def snowflake(ts):
    return int(ts * 1000 - DISCORD_EPOCH) << 22


async def export_channel(session, args):
    s = session

    async with s.get(f'/channels/{args.channel_id}') as rp:
        channel = rp.data
        guild_id = channel['guild_id']
    async with s.get(f'/guilds/{guild_id}') as rp:
        guild = rp.data

    fname = '{}.{}.{}.jl'.format(guild['name'], channel['name'], datetime.utcnow().isoformat() + 'Z')
    fpath = os.path.join(args.output_dir, fname)
    print('Dumping to:', fpath)
    with open(fpath, 'w') as f:
        dump_record(f, 'guild', guild)
        dump_record(f, 'channel', channel)

        after = 0
        while True:
            async with s.get(f'/channels/{args.channel_id}/messages?after={after}&limit=100') as rp:
                messages = list(reversed(rp.data))
                if not messages:
                    return
                after = messages[-1]['id']
                for message in messages:
                    dump_record(f, 'message', message)


async def async_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', '-t')
    parser.add_argument('--output-dir', '-o', default='.')
    subparsers = parser.add_subparsers(dest='command')
    subparser = subparsers.add_parser('channel')
    subparser.add_argument('channel_id')
    args = parser.parse_args()

    if args.command in ['channel']:
        async with DiscordHTTPSession(args.token) as session:
            await export_channel(session, args)


def cli():
    asyncio.run(async_cli())
