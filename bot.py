import json
import asyncio
import random
import os
import io
import discord
import aiohttp
from selfbot import Selfbot
from discord.ext import commands

# ── config ─────────────────────────────────────────────────────────────────────

SELFBOT_TOKEN = "your token here" # replace with your token
LOADBOT_TOKEN = "your token here" # replace with a bot token

# dont edit anything past this line

# ── constants ──────────────────────────────────────────────────────────────────
MAX_OVERWRITES = 999

TEXT_CHANNEL   = 0
VOICE_CHANNEL  = 2
ANNOUNCEMENT   = 5
FORUM_CHANNEL  = 15
STAGE_CHANNEL  = 13
SAVEABLE_TYPES = {TEXT_CHANNEL, VOICE_CHANNEL, ANNOUNCEMENT, FORUM_CHANNEL, STAGE_CHANNEL}

# ── selfbot ────────────────────────────────────────────────────────────────────

selfbot = Selfbot(SELFBOT_TOKEN, prefix='!')

# queued restore — fired when loadbot joins any guild
_last_backup    = None   # path of most recent backup
_pending_confirm = {}    # channel_id -> {file, name, guild, user_id}

selfbot._extra_dispatch = None

@selfbot.event
async def on_ready():
    print(f'[selfbot] logged in as {selfbot.user["username"]}') if selfbot.user else None


@selfbot.event
async def on_message(message):
    channel_id = message.get('channel_id')
    if selfbot.user and channel_id in _pending_confirm and message.get('author', {}).get('id') == selfbot.user['id']:
        text    = message.get('content', '').strip().lower()
        pending = _pending_confirm[channel_id]
        if text == 'n':
            _pending_confirm.pop(channel_id)
            await selfbot.send(channel_id, 'restore cancelled')
        elif text == 'y':
            backup_file = pending['file']
            guild       = pending['guild']
            user_id     = pending['user_id']
            _pending_confirm.pop(channel_id)
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    restore_data = json.load(f)
            except Exception as e:
                await selfbot.send(channel_id, f'could not read backup: {e}')
                return
            await selfbot.send(channel_id, 'starting restore now')
            asyncio.create_task(do_restore(guild, restore_data, user_id))


@selfbot.command()
async def saveserver(ctx):
    if not ctx.guild_id:
        await ctx.send('commands only work inside a server')
        return
    await ctx.delete()
    await selfbot.send(ctx.channel_id, 'SLAVA MOTHER FUCKING NUSKSLAVIA! SAVING YOUR FUCKASS SERVER NOW!')

    selfbot.cache_clear()
    guild_id = ctx.guild_id

    await asyncio.sleep(random.uniform(0.5, 1))
    guild        = await selfbot.get_guild(guild_id)
    await asyncio.sleep(random.uniform(0.5, 1))
    all_channels = await selfbot.get_channels(guild_id)
    await asyncio.sleep(random.uniform(0.5, 1))
    roles_raw    = await selfbot.get_roles(guild_id)

    print(f'saving server: {guild["name"]}')

    # roles
    print('fetching roles')
    roles_data = sorted(
        [{'name': r['name'], 'color': r['color'], 'hoist': r['hoist'],
          'mentionable': r['mentionable'], 'position': r['position'], 'permissions': r['permissions']}
         for r in roles_raw if r['name'] != '@everyone'],
        key=lambda r: r['position'], reverse=True
    )
    print(f'saved {len(roles_data)} roles')

    # categories
    print('fetching categories')
    categories_data = []
    await asyncio.sleep(random.uniform(0.5, 1))
    for cat in sorted(await selfbot.get_categories(guild_id), key=lambda c: c['position']):
        print(f'category: {cat["name"]}')
        categories_data.append({
            'name': cat['name'], 'position': cat['position'],
            'permission_overwrites': await selfbot.get_channel_overwrites(guild_id, cat['id']),
        })

    print(f'saved {len(categories_data)} categories')

    # channels
    print('fetching channels')
    saveable = [ch for ch in all_channels if ch['type'] in SAVEABLE_TYPES]
    channels_by_category = {}
    for ch in saveable:
        pid = ch.get('parent_id') or '__none__'
        channels_by_category.setdefault(pid, []).append(ch)
    for pid in channels_by_category:
        channels_by_category[pid].sort(key=lambda c: c['position'])

    channels_data = []
    for i, ch in enumerate(saveable):
        print(f'channel {i+1}/{len(saveable)}: #{ch["name"]}')
        detail       = await selfbot.get_channel(ch['id'])
        cat          = await selfbot.get_channel_category(guild_id, ch['id'])
        pid          = ch.get('parent_id') or '__none__'
        cat_position = channels_by_category[pid].index(ch)
        no_access    = 'permission_overwrites' not in detail
        entry = {
            'name': ch['name'], 'type': ch['type'],
            'position': ch['position'], 'cat_position': cat_position,
            'category': cat['name'] if cat else None,
            'no_access': no_access,
            'topic': detail.get('topic'), 'nsfw': detail.get('nsfw', False),
            'slowmode_delay': detail.get('rate_limit_per_user', 0),
            'permission_overwrites': await selfbot.get_channel_overwrites(guild_id, ch['id']),
        }
        if ch['type'] == FORUM_CHANNEL:
            entry['available_tags']         = detail.get('available_tags', [])
            entry['default_reaction_emoji'] = detail.get('default_reaction_emoji')
            entry['default_sort_order']     = detail.get('default_sort_order')
        channels_data.append(entry)
    print(f'saved {len(channels_data)} channels')
    await asyncio.sleep(random.uniform(0.5, 1))

    # emojis
    print('fetching emojis')
    role_id_to_name = {r['id']: r['name'] for r in roles_raw}
    emojis_data = []
    for e in await selfbot.get_emojis(guild_id):
        ext = 'gif' if e.get('animated') else 'png'
        emojis_data.append({
            'name': e['name'], 'animated': e.get('animated', False),
            'url': f"https://cdn.discordapp.com/emojis/{e['id']}.{ext}",
            'roles': [role_id_to_name[r] for r in e.get('roles', []) if r in role_id_to_name],
        })
    print(f'saved {len(emojis_data)} emojis')
    await asyncio.sleep(random.uniform(0.5, 1))

    # stickers
    print('fetching stickers')
    stickers_data = [
        {'name': s['name'], 'description': s.get('description', ''),
         'emoji': s.get('tags', ''), 'url': f"https://cdn.discordapp.com/stickers/{s['id']}.png"}
        for s in await selfbot.get_stickers(guild_id)
    ]
    print(f'saved {len(stickers_data)} stickers')
    await asyncio.sleep(random.uniform(0.5, 1))

    # community + onboarding
    print('fetching community and onboarding')
    channel_id_to_name = {ch['id']: ch['name'] for ch in all_channels}
    community_data = {
        'features': guild.get('features', []),
        'verification_level': guild.get('verification_level', 0),
        'explicit_content_filter': guild.get('explicit_content_filter', 0),
        'default_message_notifications': guild.get('default_message_notifications', 0),
        'preferred_locale': guild.get('preferred_locale', 'en-US'),
        'rules_channel_name': channel_id_to_name.get(guild.get('rules_channel_id')),
        'updates_channel_name': channel_id_to_name.get(guild.get('public_updates_channel_id')),
    }
    await asyncio.sleep(random.uniform(0.5, 1))
    onboarding_data = await selfbot.get_onboarding_named(guild_id)

    SEND_MESSAGES = 0x800
    mod_only_channels = [
        ch['name'] for ch in channels_data
        for ow in ch.get('permission_overwrites', [])
        if ow['type'] == 'role' and ow['name'] == '@everyone' and int(ow['deny']) & SEND_MESSAGES
    ]

    guild_data = {
        'name': guild['name'], 'description': guild.get('description'),
        'icon_url': f"https://cdn.discordapp.com/icons/{guild_id}/{guild['icon']}.{'gif' if guild['icon'].startswith('a_') else 'png'}?size=1024"
                    if guild.get('icon') else None,
        'roles': roles_data, 'categories': categories_data, 'channels': channels_data,
        'emojis': emojis_data, 'stickers': stickers_data,
        'community': community_data, 'onboarding': onboarding_data,
        'mod_only_channels': mod_only_channels,
    }

    global _last_backup
    n = 1
    while os.path.exists(f'server_backup_{n}.json'):
        n += 1
    backup_file = f'server_backup_{n}.json'
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(guild_data, f, indent=4)
    _last_backup = backup_file
    print(f'backup written to {backup_file}')

    try:
        await selfbot.send_file(ctx.channel_id, backup_file, content=f'server backup complete! saved as {backup_file}')
    except Exception as e:
        print(f'could not send file: {e}')
        await selfbot.send(ctx.channel_id, f'backup saved as {backup_file}')

    await selfbot.send(ctx.channel_id,
        f'create a new server, add the loadbot with https://discord.com/oauth2/authorize?client_id=1474059989827063940&permissions=8&integration_type=0&scope=bot, then do `!restore {backup_file}`\n'
        f'or just do `!restore` to restore using this backup'
    )


@selfbot.command()
async def restore(ctx):
    global _last_backup

    if len(ctx.args) >= 1:
        backup_file = ctx.args[0]
    else:
        if _last_backup is None:
            await ctx.send('no last restore found — run `!saveserver` first or specify a file')
            return
        backup_file = _last_backup

    if not os.path.exists(backup_file):
        await ctx.send(f'file not found: {backup_file}')
        return

    try:
        with open(backup_file, 'r', encoding='utf-8') as f:
            preview = json.load(f)
        server_name = preview.get('name', 'unknown')
    except Exception as e:
        await ctx.send(f'could not read backup: {e}')
        return

    guild = loadbot.get_guild(int(ctx.guild_id))
    if not guild:
        await ctx.send('loadbot is not in this server — add it first')
        return

    await ctx.delete()
    _pending_confirm[ctx.channel_id] = {
        'file':      backup_file,
        'name':      server_name,
        'guild':     guild,
        'user_id':   ctx.author['id'],
    }
    await selfbot.send(ctx.channel_id,
        f'restore **{server_name}** from `{backup_file}` into **{guild.name}**? reply `y` or `n`'
    )

# ── loadbot ────────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
loadbot = commands.Bot(command_prefix='!lb', intents=intents)

_skip = asyncio.Event()

def skipped():
    if _skip.is_set():
        _skip.clear()
        print('[skip] section skipped')
        return True
    return False

@loadbot.event
async def on_ready():
    print(f'[loadbot] logged in as {loadbot.user}')

async def removecommunitychannels(guild):
    converted = 0
    failed = 0
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel) and channel.is_news():
            try:
                await channel.edit(type=discord.ChannelType.text)
                converted += 1
                print(f'[removecommunitychannels] converted #{channel.name} to text')
            except discord.HTTPException as e:
                failed += 1
                print(f'[removecommunitychannels] failed #{channel.name}: {e}')
    print(f'converted {converted} announcement channels to text{f", {failed} failed" if failed else ""}')

async def reverseroles(ctx):
    guild = ctx.guild
    bot_top = guild.me.top_role
    roles = sorted(
        [r for r in guild.roles if r != guild.default_role and not r.managed and r < bot_top],
        key=lambda r: r.position
    )

    if not roles:
        await ctx.send('no roles to reverse')
        return
    positions = [(roles[i], roles[len(roles) - 1 - i].position) for i in range(len(roles))]

    try:
        await guild.edit_role_positions({role: pos for role, pos in positions})
        await ctx.send(f'reversed {len(roles)} roles')
        print(f'[reverseroles] reversed {len(roles)} roles in {guild.name}')
    except discord.HTTPException as e:
        await ctx.send(f'failed: {e}')
        print(f'[reverseroles] error: {e}')

@loadbot.command(name="reverseroles")
async def revroles(ctx):
    await reverseroles(ctx)


# ── loadbot helpers ────────────────────────────────────────────────────────────

def _fake_id(n):
    return str(1000000000000000000 + n)

async def enable_onboarding(guild, onboarding):
    role_map    = {r.name: r.id for r in guild.roles}
    channel_map = {c.name: c.id for c in guild.channels}
    def resolve_roles(names):
        return [role_map[n] for n in names if n in role_map]
    def resolve_channels(names):
        return [channel_map[n] for n in names if n in channel_map]
    counter = 0
    prompts = []
    for prompt in onboarding.get('prompts', []):
        options = []
        for opt in prompt.get('options', []):
            counter += 1
            options.append({
                'id': _fake_id(counter), 'title': opt['title'],
                'description': opt.get('description', ''), 'emoji': opt.get('emoji'),
                'role_ids': resolve_roles(opt.get('roles', [])),
                'channel_ids': resolve_channels(opt.get('channels', [])),
            })
        counter += 1
        prompts.append({
            'id': _fake_id(counter), 'title': prompt['title'],
            'type': prompt.get('type', 0), 'single_select': prompt.get('single_select', False),
            'required': prompt.get('required', False), 'in_onboarding': prompt.get('in_onboarding', True),
            'options': options,
        })
    payload = {
        'enabled': onboarding.get('enabled', True), 'mode': onboarding.get('mode', 0),
        'default_channel_ids': resolve_channels(onboarding.get('default_channels', [])),
        'prompts': prompts,
    }
    await guild._state.http.request(
        discord.http.Route('PUT', '/guilds/{guild_id}/onboarding', guild_id=guild.id),
        json=payload
    )

def build_overwrites(overwrites_data, role_map, guild, overwrite_counter):
    """
    builds discord.py overwrite dict.
    returns (overwrites, new_counter).
    if adding these overwrites would exceed MAX_OVERWRITES, returns empty dict.
    """
    if overwrite_counter >= MAX_OVERWRITES:
        return {}, overwrite_counter
    overwrites = {}
    for ow in overwrites_data:
        if overwrite_counter >= MAX_OVERWRITES:
            print(f'[load] overwrite limit ({MAX_OVERWRITES}) reached — skipping remaining overwrites')
            break
        target = None
        if ow['type'] == 'role':
            target = guild.default_role if ow['name'] == '@everyone' else role_map.get(ow['name'])
        elif ow['type'] == 'member':
            target = guild.get_member_named(ow['name'])
        if target is None:
            continue
        allow = discord.Permissions(int(ow['allow']))
        deny  = discord.Permissions(int(ow['deny']))
        overwrites[target] = discord.PermissionOverwrite.from_pair(allow, deny)
        overwrite_counter += 1
    return overwrites, overwrite_counter

# ── do_restore ─────────────────────────────────────────────────────────────────

async def do_restore(guild, data, notify_user_id):
    _skip.clear()
    overwrite_counter = 0
    print(f'[load] starting restore for {guild.name}')

    # name and icon
    icon_bytes = None
    if data.get('icon_url'):
        async with aiohttp.ClientSession() as session:
            async with session.get(data['icon_url']) as resp:
                if resp.status == 200:
                    b = await resp.read()
                    icon_bytes = b if len(b) <= 10240 * 1024 else None
    try:
        await guild.edit(name=data['name'], icon=icon_bytes)
        print('[load] name and icon set')
    except Exception as e:
        print(f'[load] could not set name/icon: {e}')
        try:
            await guild.edit(name=data['name'])
        except: pass

    # disable community
    if 'COMMUNITY' in guild.features:
        await guild.edit(community=False)
        print('[load] community disabled')

    # delete channels
    print('[load] deleting channels')
    for channel in list(guild.channels):
        if skipped(): break
        try:
            await channel.delete()
        except Exception as e:
            print(f'[load] could not delete channel {channel.name}: {e}')

    # delete roles
    print('[load] deleting roles')
    for role in list(guild.roles):
        if skipped(): break
        if role.name != '@everyone' and not role.managed:
            try:
                await role.delete()
            except Exception as e:
                print(f'[load] could not delete role {role.name}: {e}')

    # enable community with temp channels
    community    = data.get('community', {})
    is_community = 'COMMUNITY' in community.get('features', [])
    tmp_rules = tmp_updates = None
    if is_community and not skipped():
        print('[load] enabling community')
        tmp_rules   = await guild.create_text_channel('temp-rules')
        tmp_updates = await guild.create_text_channel('temp-updates')
        await guild.edit(
            community=True, rules_channel=tmp_rules, public_updates_channel=tmp_updates,
            verification_level=discord.VerificationLevel(community.get('verification_level', 1)),
            explicit_content_filter=discord.ContentFilter(community.get('explicit_content_filter', 1)),
            preferred_locale=discord.Locale(community.get('preferred_locale', 'en-US')),
        )
        print('[load] community enabled with temp channels')

    # create roles
    print('[load] creating roles')
    role_map = {}
    for role_data in data.get('roles', []):
        if skipped(): break
        try:
            role = await guild.create_role(
                name=role_data['name'], color=discord.Color(role_data['color']),
                hoist=role_data['hoist'], mentionable=role_data['mentionable'],
                permissions=discord.Permissions(int(role_data['permissions'])),
            )
            role_map[role_data['name']] = role
            print(f'[load] created role: {role_data["name"]}')
        except discord.HTTPException as e:
            if e.status == 429:
                print(f'[load] role rate limit — retrying after {e.retry_after:.0f}s')  # ty:ignore[unresolved-attribute]
                await asyncio.sleep(e.retry_after + 1)  # ty:ignore[unresolved-attribute]
                try:
                    role = await guild.create_role(
                        name=role_data['name'], color=discord.Color(role_data['color']),
                        hoist=role_data['hoist'], mentionable=role_data['mentionable'],
                        permissions=discord.Permissions(int(role_data['permissions'])),
                    )
                    role_map[role_data['name']] = role
                except Exception as e2:
                    print(f'[load] still could not create role {role_data["name"]}: {e2}')
            else:
                print(f'[load] could not create role {role_data["name"]}: {e}')
        except Exception as e:
            print(f'[load] could not create role {role_data["name"]}: {e}')

    # create categories
    print('[load] creating categories')
    category_map = {}
    for cat in sorted(data.get('categories', []), key=lambda c: c.get('position', 0)):
        if skipped(): break
        try:
            overwrites, overwrite_counter = build_overwrites(
                cat.get('permission_overwrites', []), role_map, guild, overwrite_counter)
            new_cat = await guild.create_category(cat['name'], overwrites=overwrites)
            category_map[cat['name']] = new_cat
            print(f'[load] created category: {cat["name"]}')
        except Exception as e:
            print(f'[load] could not create category {cat["name"]}: {e}')

    # create channels
    print('[load] creating channels')
    channel_map = {}
    cat_pos_lookup = {cat['name']: cat.get('position', 0) for cat in data.get('categories', [])}

    def channel_sort_key(ch):
        cat_name = ch.get('category')
        cat_pos  = cat_pos_lookup.get(cat_name, -1) if cat_name else -1
        return (cat_pos, ch.get('cat_position', ch.get('position', 0)))

    for ch in sorted(data.get('channels', []), key=channel_sort_key):
        if skipped(): break
        category   = category_map.get(ch.get('category')) if ch.get('category') else None
        overwrites, overwrite_counter = build_overwrites(
            ch.get('permission_overwrites', []), role_map, guild, overwrite_counter)
        try:
            ch_type = ch['type']
            kwargs  = dict(category=category, overwrites=overwrites,
                           topic=ch.get('topic') or '', nsfw=ch.get('nsfw', False),
                           slowmode_delay=ch.get('slowmode_delay', 0))
            if ch_type == 0:
                new_ch = await guild.create_text_channel(ch['name'], **kwargs)
            elif ch_type == 2:
                [kwargs.pop(k) for k in ('topic', 'nsfw', 'slowmode_delay')]
                new_ch = await guild.create_voice_channel(ch['name'], **kwargs)
            elif ch_type == 5:
                new_ch = await guild.create_text_channel(ch['name'], news=True, **kwargs)
            elif ch_type == 13:
                [kwargs.pop(k) for k in ('topic', 'nsfw', 'slowmode_delay')]
                new_ch = await guild.create_stage_channel(ch['name'], **kwargs)
            elif ch_type == 15:
                kwargs.pop('nsfw', None)
                new_ch = await guild.create_forum(ch['name'], **kwargs)
            else:
                continue
            channel_map[ch['name']] = new_ch
            print(f'[load] created channel: #{ch["name"]}')
        except discord.HTTPException as e:
            if e.status == 429:
                await asyncio.sleep(e.retry_after + 1)  # ty:ignore[unresolved-attribute]
            print(f'[load] could not create channel {ch["name"]}: {e}')
        except Exception as e:
            print(f'[load] could not create channel {ch["name"]}: {e}')

    # reorder channels
    if not skipped() and channel_map:
        try:
            sorted_cats = sorted(data.get('categories', []), key=lambda c: c.get('position', 0))
            cat_order   = [c['name'] for c in sorted_cats]
            by_cat = {}
            for ch in data.get('channels', []):
                key = ch.get('category') or '__none__'
                by_cat.setdefault(key, []).append(ch)
            for key in by_cat:
                by_cat[key].sort(key=lambda c: c.get('position', 0))
            positions  = []
            global_pos = 0
            for ch in by_cat.get('__none__', []):
                if ch['name'] not in channel_map: continue
                positions.append({'id': channel_map[ch['name']].id, 'position': global_pos, 'parent_id': None})
                global_pos += 1
            for cat_name in cat_order:
                cat = category_map.get(cat_name)
                if not cat: continue
                positions.append({'id': cat.id, 'position': global_pos, 'parent_id': None})
                global_pos += 1
                for ch in by_cat.get(cat_name, []):
                    if ch['name'] not in channel_map: continue
                    positions.append({'id': channel_map[ch['name']].id, 'position': global_pos, 'parent_id': cat.id})
                    global_pos += 1
            for i in range(0, len(positions), 20):
                await guild._state.http.bulk_channel_update(guild.id, positions[i:i+20])
                await asyncio.sleep(1)
            print('[load] channels reordered')
        except Exception as e:
            print(f'[load] could not reorder channels: {e}')

    # wire community
    if is_community and not skipped():
        print('[load] wiring community channels')
        for ch in [tmp_rules, tmp_updates]:
            if ch:
                try: await ch.delete()
                except: pass
        rules_ch   = channel_map.get(community.get('rules_channel_name'))
        updates_ch = channel_map.get(community.get('updates_channel_name'))
        if not rules_ch:
            rules_ch = next((c for c in channel_map.values() if isinstance(c, (discord.TextChannel, discord.ForumChannel))), None)
        if not updates_ch:
            updates_ch = next((c for c in channel_map.values() if isinstance(c, (discord.TextChannel, discord.ForumChannel)) and c != rules_ch), rules_ch)
        await guild.edit(rules_channel=rules_ch, public_updates_channel=updates_ch)
        print('[load] community wired')

    # delete old emojis/stickers
    print('[load] deleting emojis and stickers')
    for emoji in list(guild.emojis):
        if skipped(): break
        try: await emoji.delete()
        except Exception as e: print(f'[load] could not delete emoji {emoji.name}: {e}')
    for sticker in list(guild.stickers):
        if skipped(): break
        try: await sticker.delete()
        except Exception as e: print(f'[load] could not delete sticker {sticker.name}: {e}')

    # upload emojis
    print('[load] uploading emojis')
    emoji_count = 0
    async with aiohttp.ClientSession() as session:
        for emoji_data in data.get('emojis', []):
            if skipped(): break
            if emoji_count >= 49:
                print('[load] emoji limit reached (49)')
                break
            try:
                async with session.get(emoji_data['url']) as resp:
                    if resp.status == 200:
                        image_bytes = await resp.read()
                        roles = [role_map[n] for n in emoji_data.get('roles', []) if n in role_map]
                        await guild.create_custom_emoji(name=emoji_data['name'], image=image_bytes, roles=roles)
                        emoji_count += 1
                        print(f'[load] created emoji: {emoji_data["name"]} ({emoji_count}/49)')
            except discord.HTTPException as e:
                if e.status == 429:
                    print('[load] emoji rate limit — moving on to stickers')
                    break
                print(f'[load] could not create emoji {emoji_data["name"]}: {e}')
            except Exception as e:
                print(f'[load] could not create emoji {emoji_data["name"]}: {e}')

    # upload stickers
    print('[load] uploading stickers')
    sticker_count = 0
    async with aiohttp.ClientSession() as session:
        for sticker_data in data.get('stickers', []):
            if skipped(): break
            if sticker_count >= 49:
                print('[load] sticker limit reached (49)')
                break
            try:
                async with session.get(sticker_data['url']) as resp:
                    if resp.status == 200:
                        image_bytes = await resp.read()
                        await guild.create_sticker(
                            name=sticker_data['name'],
                            description=sticker_data.get('description', ''),
                            emoji=sticker_data.get('emoji', '⭐'),
                            file=discord.File(fp=io.BytesIO(image_bytes), filename=f"{sticker_data['name']}.png"),
                        )
                        sticker_count += 1
                        print(f'[load] created sticker: {sticker_data["name"]} ({sticker_count}/49)')
            except discord.HTTPException as e:
                if e.status == 429:
                    print('[load] sticker rate limit — moving on to onboarding')
                    break
                print(f'[load] could not create sticker {sticker_data["name"]}: {e}')
            except Exception as e:
                print(f'[load] could not create sticker {sticker_data["name"]}: {e}')

    # restore onboarding
    if is_community and not skipped() and data.get('onboarding', {}).get('enabled'):
        print('[load] restoring onboarding')
        try:
            await enable_onboarding(guild, data['onboarding'])
            print('[load] onboarding restored')
        except Exception as e:
            print(f'[load] could not restore onboarding: {e}')

    # make sure data is valid first
    name = data.get('name', 'restored server') if data else 'restored server'

    # disable community
    if 'COMMUNITY' in guild.features:
        await guild.edit(community=False)
        
    await removecommunitychannels(guild)

    # delete temp rules and temp updates
    for ch in [tmp_rules, tmp_updates]:
        if ch:
            try:
                await ch.delete()
            except:
                pass

    # Ensure we can always create a template by clearing overwrites if needed
    template_url = None
    max_retries = 200
    for attempt in range(max_retries):
        try:
            templates = await guild.templates()
            if templates:
                await templates[0].delete()
            template = await guild.create_template(name=name, description='Made by c0llared_')
            template_url = f'https://discord.new/{template.code}'
            print(f'[load] template: {template_url}')
            break
        except discord.HTTPException as e:
            if e.code == 30060: # Maximum number of channel permission overwrites reached
                print('[load] overwrite limit reached for template, clearing some overwrites...')
                # Try to clear overwrites from the first few channels to make room
                for channel in guild.channels[:1]:
                    try:
                        await channel.edit(overwrites={})
                    except:
                        pass
                await asyncio.sleep(2)
                continue

            print(f'[attempt {attempt+1}] could not create template: {e}')
        except Exception as e:
            print(f'[attempt {attempt+1}] unexpected error creating template: {e}')
            break

    # only try to DM if template creation succeeded
    if template_url:
        try:
            user = await loadbot.fetch_user(int(notify_user_id))
            await user.send(f'restore complete! template: {template_url}')
            print('[load] template DM sent')
        except Exception as e:
            print(f'[load] could not DM template: {e}')

    print('[load] done')

# ── run both bots concurrently ─────────────────────────────────────────────────

async def main():
    await asyncio.gather(
        selfbot._gateway(),
        loadbot.start(LOADBOT_TOKEN),
    )

if __name__ == '__main__':
    asyncio.run(main())
