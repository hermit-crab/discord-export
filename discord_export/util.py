import datetime

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
