import discord

from .util import utc_ts, emoji_id


channel_types = {
    discord.TextChannel: 'text',
    discord.VoiceChannel: 'voice',
    discord.DMChannel: 'private',
    discord.CategoryChannel: 'category',
    discord.GroupChannel: 'group',
}


def serialize_user(model):
    obj = {}
    for k in ['name', 'id', 'discriminator', 'avatar', 'bot',
              'avatar_url', 'default_avatar', 'default_avatar_url',
              'display_name']:
        obj[k] = getattr(model, k)

    obj['created_at'] = utc_ts(model.created_at)
    obj['default_avatar'] = str(model.default_avatar)
    if isinstance(model, discord.Member):
        obj['roles'] = [e.id for e in model.roles]
        obj['joined_at'] = utc_ts(model.joined_at)
        obj['top_role'] = model.top_role.id
        obj['server'] = model.guild.id
        obj['nick'] = model.nick
        obj['color'] = model.color.value
    return obj


def serialize_channel(model):
    if isinstance(model, discord.abc.PrivateChannel):
        return _serialize_private_channel(model)

    obj = {}
    for k in ['name', 'id', 'position']:
        obj[k] = getattr(model, k)

    for k in ['category_id', 'bitrate', 'topic', 'nsfw', 'user_limit']:
        if hasattr(model, k):
            obj[k] = getattr(model, k)

    obj['overwrites'] = [(a.id, [p.value for p in b.pair()]) for a, b in model.overwrites]
    obj['created_at'] = utc_ts(model.created_at)
    obj['server'] = model.guild.id
    cls = type(model)
    obj['type'] = channel_types.get(cls, cls.__name__)
    return obj


def _serialize_private_channel(model):
    obj = {}

    for k in ['id']:
        obj[k] = getattr(model, k)

    for k in ['name', 'icon', 'icon_url']:
        if hasattr(model, k):
            obj[k] = getattr(model, k)

    for k in ['recipient', 'owner', 'me']:
        if hasattr(model, k):
            obj[k] = model.id

    if hasattr(model, 'recipients'):
        obj[k] = [e.id for e in model.recipients]

    obj['created_at'] = utc_ts(model.created_at)
    cls = type(model)
    obj['type'] = channel_types.get(cls, cls.__name__)
    return obj


def serialize_emoji(model):
    obj = {}
    for k in ['animated', 'name', 'id']:
        obj[k] = getattr(model, k)

    if not isinstance(model, discord.PartialEmoji):
        for k in ['require_colons', 'managed', 'url']:
            obj[k] = getattr(model, k)

        obj['created_at'] = utc_ts(model.created_at)
        obj['roles'] = [e.id for e in model.roles]
        obj['server'] = model.guild.id
    return obj


def serialize_message(model):
    obj = {}
    for k in ['content', 'id', 'tts', 'mention_everyone', 'pinned']:
        obj[k] = getattr(model, k)

    obj['edited_timestamp'] = utc_ts(model.edited_at) if model.edited_at else None
    obj['timestamp'] = utc_ts(model.created_at)
    obj['author'] = model.author.id
    obj['channel'] = model.channel.id
    obj['mentions'] = [e.id for e in model.mentions]
    obj['embeds'] = [e.to_dict() for e in model.embeds]
    obj['attachments'] = [serialize_attachment(e) for e in model.attachments]
    obj['channel_mentions'] = [e.id for e in model.channel_mentions]
    obj['role_mentions'] = [e.id for e in model.role_mentions]
    return obj


def serialize_attachment(model):
    obj = {}
    for k in ['id', 'size', 'height', 'width',
              'filename', 'url', 'proxy_url']:
        obj[k] = getattr(model, k)
    return obj


def serialize_role(model):
    obj = {}
    for k in ['name', 'id', 'mentionable',
              'managed', 'position', 'hoist']:
        obj[k] = getattr(model, k)

    obj['server'] = model.guild.id
    obj['color'] = model.color.value
    obj['created_at'] = utc_ts(model.created_at)
    obj['permissions'] = model.permissions.value
    return obj


def serialize_reaction(model):
    obj = {}
    for k in ['count', 'me']:
        obj[k] = getattr(model, k)

    obj['message'] = model.message.id
    obj['emoji'] = emoji_id(model.emoji)
    return obj


def serialize_server(model):
    obj = {}
    for k in ['name', 'id', 'afk_timeout', 'icon',
              'large', 'mfa_level', 'features', 'splash',
              'icon_url', 'splash_url', 'member_count']:
        obj[k] = getattr(model, k)

    obj['roles'] = [serialize_role(e) for e in model.roles]
    obj['region'] = str(model.region)
    obj['members'] = [e.id for e in model.members]
    obj['channels'] = [e.id for e in model.channels]
    obj['emojis'] = [e.id for e in model.emojis]
    obj['created_at'] = utc_ts(model.created_at)
    obj['afk_channel'] = model.afk_channel.id if model.afk_channel else None
    obj['owner'] = model.owner.id
    obj['verification_level'] = str(model.verification_level)
    return obj
