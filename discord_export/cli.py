#!/usr/bin/env python
import os
import sys
import re
import argparse
import asyncio
import json
import time
from datetime import datetime, timedelta
from getpass import getpass
import dateparser
from packaging import version

import discord
import colorama
from colorama import Style
from aioconsole import ainput
from logzero import logger, LogFormatter

from .crawl import crawl
from .serialize import *
from .util import channel_name, filter_channels, patch_http, load_messages
from . import __version__


async def connect(client):
    if not client.ws:
        asyncio.ensure_future(client.connect())
        logger.info('awaiting client ready state')
        await client.wait_until_ready()


async def ainput_nonempty(*args, **kw):
    while True:
        ret = (await ainput(*args, **kw)).strip()
        if ret:
            return ret


def continuation_get_conf(file):
    conf = {}
    timestamps = {}
    with open(file) as f:
        for l in f:
            type_, data = l.split(',', 1)
            if not conf and type_ == 'run_info':
                data = json.loads(data)
                ver = data.get('version', '0.0.0')
                req = '0.1.0'
                if version.parse(ver) < version.parse(req):
                    raise Exception(f'incompatible version {ver} < {req}')
                conf = data['conf']
            elif type_ == 'message':
                data = json.loads(data)
                ch = data['channel']
                t = data['timestamp']
                current = timestamps.get(ch, 0)
                if t > current:
                    timestamps[ch] = t
    assert conf, f'no run_info found in {file}'
    return argparse.Namespace(**conf), timestamps


async def interactive_get_conf(client):
    conf = {}

    guild = None
    guild_names = ['[Direct Messages]'] + [s.name for s in client.guilds]
    print()
    for i, name in enumerate(guild_names, 1):
        print(f'{i}. {name}')
    i = int(await ainput_nonempty('Pick a server (number): '))
    print(f'\n==> {guild_names[i-1]}\n')

    if i == 1:

        channels = client.private_channels
        for i, ch in enumerate(channels, 1):
            name = f'{i}. '
            if isinstance(ch, discord.DMChannel):
                name += ch.recipient.name
            else:
                name += f'(group {len(ch.recipients)}) {channel_name(ch)}'
            print(name)
        answer = (await ainput('Select channels (numbers, blank for all): ')).strip().split()
        conf['mode'] = 'dm'
        if answer:
            channels = [channels[int(i)-1] for i in answer]
            conf['mode'] = 'channels'
            conf['id'] = [ch.id for ch in channels]

    else:

        guild = client.guilds[i-2]
        channels, skipped = filter_channels(guild.channels)
        for reason, ch in skipped:
            if 'non-text' not in reason:
                logger.info(f'filtering out {ch.id} ({channel_name(ch)}), {reason}')

        channels.sort(key=lambda c: c.position)
        for i, ch in enumerate(channels, 1):
            cat = getattr(ch, 'category', None)
            cat = f'({cat.name}) ' if cat else ''
            print(f'{i}. {cat}{channel_name(ch)}')
        answer = (await ainput('Select channels (numbers, blank for all): ')).strip().split()
        conf['mode'] = 'server'
        conf['id'] = guild.id
        if answer:
            channels = [channels[int(i)-1] for i in answer]
            conf['mode'] = 'channels'
            conf['id'] = [ch.id for ch in channels]

    date = None
    while True:
        answer = (await ainput('Start date (or leave blank): '))
        if not answer:
            date = None
            break
        date = dateparser.parse(answer)
        if date:
            break
        print('==x can\'t understand the date specified')

    date_s = date or 'from the beginning'
    print()
    print(f'==> start date: {date_s}')
    print(f'==> server: {guild or "dm"}')
    print(f'==> channels:')
    for ch in channels:
        cat = getattr(ch, 'category', None)
        cat = f'({cat.name}) ' if cat else ''
        print(f'{cat}{channel_name(ch)}')
    print()

    conf['after'] = date.timestamp() if date else None

    answer = await ainput_nonempty('Confirm? [y/n]: ')
    if answer.lower() == 'n':
        return await interactive_get_conf(client)

    return argparse.Namespace(**conf)


def validate_conf(client, conf):

    guild = None
    file = container_id = container_name = None
    date_s = '-'.join(datetime.now().isoformat().split(':')[:2])

    if conf.mode == 'dm':

        channels = client.private_channels
        container_id = container_name = 'dm'

    elif conf.mode == 'server':

        guild = client.get_guild(conf.id)
        assert guild, 'server was not found'
        channels, skipped = filter_channels(guild.channels)
        for reason, ch in skipped:
            logger.info(f'filtering out {ch.id} ({channel_name(ch)}), {reason}')
        container_id = guild.id
        container_name = guild.name

    elif conf.mode == 'channels':

        channels = []
        for id in conf.id:
            channel = client.get_channel(id)
            if not channel:
                logger.error(f'channel {id} was not found')
            else:
                channels.append(channel)

        assert channels, 'no channels to work with'
        assert len(set(getattr(ch, 'guild', None) for ch in channels)) <= 1, \
                'when specifying channels only one source is allowed'

        if isinstance(channels[0], discord.abc.PrivateChannel):
            container_id = 'dm'
            container_name = 'dm'
            if len(channels) == 1:
                container_name = channel_name(channels[0])
        else:
            guild = channels[0].guild

            container_id = guild.id
            container_name = guild.name

            channels, bad = filter_channels(channels)
            if bad:
                for reason, ch in bad:
                    logger.error(f'filtering out {ch.id} ({channel_name(ch)}), {reason}')

    assert channels, 'no channels to work with'

    container_name = re.sub(r'[^A-Za-z\d_()-]', '_', container_name)
    file = f'{container_id}.{date_s}.{container_name}.records'

    return guild, channels, file


def dump_history(conf):
    colorama.init()
    for m in load_messages([conf.file]):
        room = m['channel']['name']
        date = str(m['timestamp'])
        if m['edited_timestamp']:
            date += '*'
        author = m['author']['name']
        print(f'{Style.DIM} -- #{room} {author} {date}{Style.RESET_ALL}')
        print(m['clean_content'])


async def run(client, conf, creds):
    logger.info('initializing and logging in')
    if len(creds) == 1:
        x = await client.login(*creds)
    else:
        x = await client.http.email_login(*creds)
        client._connection.is_bot = False

    file = None
    timestamps = {}

    if conf.mode == 'continue':
        logger.info('reading previous run info')
        file = conf.file
        conf, timestamps = continuation_get_conf(conf.file)

    await connect(client)
    if conf.mode == 'interactive':
        conf = await interactive_get_conf(client)
        if not conf:
            logger.info('cancelled, exiting')
            await client.close()
            return

    guild, channels, file_ = validate_conf(client, conf)

    if not file:
        file = file_

    if conf.after:
        timestamps = {ch.id: conf.after for ch in channels}

    logger.info(f'file: {file}')
    guild_ = f'{guild.id} ({guild.name})' if guild else 'dm'
    logger.info(f'server: {guild_}')
    for ch in channels:
        date_s = 'the beginning'
        if ch.id in timestamps:
            date_s = datetime.fromtimestamp(timestamps.get(ch.id))
        logger.info(f'channel: {ch.id} ({channel_name(ch)}) from {date_s}')

    with open(file, 'a+') as f:
        run_info = {
            'argv': sys.argv[1:],
            'time': time.time(),
            'client.user.id': client.user.id,
            'discord.__version__': discord.__version__,
            'server': guild.id if guild else None,
            'conf': vars(conf),
            'file': file,
            'channels': [ch.id for ch in channels],
            'timestamps': timestamps,
            'version': __version__
        }

        def format_record(type, data):
            return f'{type},{json.dumps(data)}'

        f.write(format_record('run_info', run_info))
        f.write('\n')

        async for record in crawl(client, channels, timestamps):
            f.write(format_record(*record))
            f.write('\n')

        f.write(format_record('run_finished', {'time': time.time()}))
        f.write('\n')

    await client.close()


def parse_args():
    epilog = '''
        With no arguments will run in an interactive mode.
        Accepts TOKEN or EMAIL/PASS environment variables.
    '''.replace('  ', '')
    parser = argparse.ArgumentParser(prog='discord-extract', epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    subparsers = parser.add_subparsers()

    sub = subparsers.add_parser('interactive')
    sub.set_defaults(mode='interactive')

    def date(date):
        date = dateparser.parse(date)
        if not date:
            raise ValueError
        return date.timestamp()

    def add_common_for_crawl(parser):
        sub.add_argument('--after', type=date, help='date after which to start extracting')

    sub = subparsers.add_parser('dm')
    sub.set_defaults(mode='dm')
    add_common_for_crawl(sub)

    sub = subparsers.add_parser('channels')
    sub.set_defaults(mode='channels')
    sub.add_argument('id', type=int, nargs='+', help='must come from the same source')
    add_common_for_crawl(sub)

    sub = subparsers.add_parser('server')
    sub.set_defaults(mode='server')
    sub.add_argument('id', type=int)
    add_common_for_crawl(sub)

    sub = subparsers.add_parser('continue')
    sub.set_defaults(mode='continue')
    sub.add_argument('file')

    sub = subparsers.add_parser('dump-history')
    sub.set_defaults(mode='dump_history')
    sub.add_argument('file')

    if not sys.argv[1:]:
        sys.argv.append('interactive')

    conf = parser.parse_args()
    if conf.mode == 'channels' and len(conf.id) != len(set(conf.id)):
        logger.warning('repeated identifiers given')

    return conf


def get_creds():
    token = os.environ.get('TOKEN')
    email = os.environ.get('EMAIL')
    pw = os.environ.get('PASS')

    if not token and not email:
        token = input('Token (can be empty): ')
    if not token and not email:
        email = input('Email: ')

    if token:
        return (token, )
    elif email:
        if not pw:
            pw = getpass()
        return (email, pw)


def main():
    formatter = LogFormatter(fmt='%(color)s[%(levelname)1.1s %(asctime)s]%(end_color)s %(message)s')
    logger.handlers[0].setFormatter(formatter)
    logger.info(f'argv: {sys.argv[1:]}')

    conf = parse_args()
    if conf.mode == 'dump_history':
        dump_history(conf)
        return

    creds = get_creds()
    if not creds:
        logger.error('no credentials are set')
        return 2

    patch_http()
    loop = asyncio.get_event_loop()
    client = discord.client.Client()

    try:
        loop.run_until_complete(run(client, conf, creds))
    except (KeyboardInterrupt, Exception) as e:
        if isinstance(e, KeyboardInterrupt):
            print()
            logger.info('interrupted')
        else:
            logger.exception(e)
        logger.info('cleaning up')
        loop.run_until_complete(client.logout())
        pending = asyncio.Task.all_tasks()
        gathered = asyncio.gather(*pending)
        try:
            gathered.cancel()
            loop.run_until_complete(gathered)
            gathered.exception()
        except:
            pass
        return 1
    finally:
        loop.close()
