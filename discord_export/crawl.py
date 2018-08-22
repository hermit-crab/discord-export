import json
from datetime import datetime, timedelta
from urllib.parse import quote

import discord
from logzero import logger

from .util import channel_name
from .serialize import *


TIME_BEFORE_DISCORD = datetime(2015, 5, 1)


async def get_reaction_users(reaction):
    r_after = None
    r_limit = 100
    fail404 = False
    started = False
    orig = None
    while True:
        try:
            users = [e async for e in reaction.users(limit=r_limit, after=r_after)]
            started = True
            for user in users:
                yield user
            if len(users) < r_limit:
                break
            r_after = users[-1]
        except discord.NotFound:
            if fail404 or started or isinstance(reaction.emoji, discord.Emoji):
                raise
            orig = reaction.emoji
            fail404 = True
            reaction.emoji = quote(reaction.emoji)

    if orig:
        reaction.emoji = orig


async def crawl(client, channels, timestamps):
    logger.info(f'starting crawl')

    users_seen = set()
    guild = None
    if not isinstance(channels[0], discord.abc.PrivateChannel):
        guild = channels[0].guild

    def ensure_user(user):
        if user.id not in users_seen:
            member = None
            if guild:
                member = guild.get_member(user.id)
            yield ['user', serialize_user(member or user)]
        users_seen.add(user.id)

    ch_n = 1
    now = datetime.utcnow()
    for ch in channels:
        logger.info(f'==> {ch.id} ({channel_name(ch)})')

        beginning = timestamps.get(ch.id, TIME_BEFORE_DISCORD.timestamp())
        beginning = datetime.utcfromtimestamp(beginning)
        after = beginning - timedelta(hours=1) # shift one hour to be sure
        first_message = timespan = None
        messages_count = 0
        while True:
            messages = [m async for m in ch.history(limit=500, after=after) if m.type == discord.MessageType.default]
            if not messages:
                if not first_message:
                    logger.info(f'{ch.id} ({channel_name(ch)}) has no messages')
                else:
                    logger.info(f'{ch.id} ({channel_name(ch)}) done')
                break

            messages.sort(key=lambda m: m.created_at)
            if not first_message:
                first_message = messages[0]
                timespan = now - first_message.created_at

            for m in messages:
                for record in ensure_user(m.author):
                    yield record

                if m.created_at <= beginning:
                    continue
                messages_count += 1

                m_obj = serialize_message(m)

                m_obj['reactions'] = []
                for reaction in m.reactions:
                    r_obj = serialize_reaction(reaction)
                    r_obj['users'] = []

                    async for user in get_reaction_users(reaction):
                        for record in ensure_user(user):
                            yield record

                        r_obj['users'].append(user.id)

                    m_obj['reactions'].append(r_obj)

                yield ['message', m_obj]

            after = messages[-1]

            covered = now - after.created_at
            percent = (1-covered/timespan)*100
            at = after.created_at.isoformat().split('T')[0]
            logger.info(f'{ch_n}/{len(channels)} {ch.id} ({channel_name(ch)}): {percent:.2f}% ({messages_count:,} messages, at {at})')

        ch_n += 1
