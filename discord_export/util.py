import datetime
import json

import discord
from discord.http import HTTPClient, Route
from discord.errors import HTTPException, LoginFailure


def filter_channels(channels):
    good = []
    bad = []
    for ch in channels:
        perms = ch.permissions_for(ch.guild.me)
        if not isinstance(ch, discord.TextChannel):
            bad.append((f'non-text <{type(ch).__name__}>', ch))
        elif not perms.read_message_history:
            bad.append(('lack permissions', ch))
        else:
            good.append(ch)
    return good, bad


def channel_name(ch):
    if getattr(ch, 'name', None):
        return ch.name

    if isinstance(ch, discord.GroupChannel):
        return 'group-' + ch.owner.name

    return ch.recipient.name


def utc_ts(utc_naive_dt):
    return utc_naive_dt.replace(tzinfo=datetime.timezone.utc).timestamp()


def emoji_id(emoji):
    return emoji if isinstance(emoji, str) else emoji.id


def patch_http():

    async def email_login(self, email, password):
        payload = {
            'email': email,
            'password': password
        }

        try:
            data = await self.request(Route('POST', '/auth/login'), json=payload)
        except HTTPException as e:
            if e.response.status == 400:
                raise LoginFailure('Improper credentials have been passed.') from e
            raise

        self._token(data['token'], bot=False)
        return data

    HTTPClient.email_login = email_login


def load_messages(fnames):
    objects = {}
    for fname in fnames:
        with open(fname) as f:
            for l in f:
                record_type, data = l.split(',', 1)
                data = json.loads(data)
                if record_type in ['run_info', 'run_finished']:
                    continue
                elif record_type == 'reaction':
                    reactions = objects.setdefault('reactions', {})
                    reactions[(data['message'], data['emoji'])] = data
                    objects['message'][data['message']].setdefault('reactions', []).append(data)
                elif record_type == 'reaction_user':
                    reaction = objects['reactions'][(data['message'], data['emoji'])]
                    reaction.setdefault('users', []).append(data['user'])
                else:
                    objects.setdefault(record_type, {})[data['id']] = data

    # for i in objects['messages'].values():
    #     i['channel'] = objects['channel'][i['channel']]
    #     i[''] = objects['channel'][i['channel']]

