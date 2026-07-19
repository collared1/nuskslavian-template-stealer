import aiohttp
import asyncio
import json
import random
import base64

class Context:
    def __init__(self, bot, message):
        self._bot = bot
        self._message = message
        self.channel_id = message['channel_id']
        self.guild_id = message.get('guild_id')
        self.author = message['author']
        self.content = message.get('content', '')
        self.message_id = message['id']

    async def send(self, content):
        return await self._bot._request('POST', f'/channels/{self.channel_id}/messages', json={'content': content})

    async def reply(self, content):
        return await self._bot._request('POST', f'/channels/{self.channel_id}/messages', json={
            'content': content,
            'message_reference': {
                'message_id': self.message_id,
                'channel_id': self.channel_id,
                'guild_id': self.guild_id,
            },
        })

    async def delete(self):
        return await self._bot._request('DELETE', f'/channels/{self.channel_id}/messages/{self.message_id}')


class Selfbot:
    def __init__(self, token, prefix='!'):
        self.token = token
        self.prefix = prefix
        self.base = 'https://discord.com/api/v9'
        self.headers = {
            'Authorization': token,
            'Content-Type': 'application/json',
        }
        self._session = None
        self._commands = {}
        self._events = {}
        self._cache = {}
        self.user = None

    # ── http ───────────────────────────────────────────────────────────────────

    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session

    async def _request(self, method, endpoint, **kwargs):
        session = await self._get_session()
        url = f'{self.base}{endpoint}'
        max_retries = 10
        for attempt in range(max_retries):
            async with session.request(method, url, **kwargs) as response:
                if response.status == 429:
                    try:
                        body = await response.json()
                        retry_after = float(response.headers.get('Retry-After') or body.get('retry_after', 1))
                    except Exception:
                        retry_after = 1.0
                    wait = min(retry_after + (0.5 * (2 ** attempt)), 60.0)
                    print(f'[429] rate limited on {method} {endpoint} — waiting {wait:.1f}s')
                    await asyncio.sleep(wait)
                    continue
                if response.status == 204:
                    return None
                response.raise_for_status()
                return await response.json()
        raise Exception(f'exceeded max retries for {endpoint}')

    # ── cache ──────────────────────────────────────────────────────────────────

    def cache_clear(self):
        self._cache.clear()

    def _cache_get(self, key):
        return self._cache.get(key)

    def _cache_set(self, key, value):
        self._cache[key] = value
        return value

    # ── decorators ─────────────────────────────────────────────────────────────

    def command(self, name=None):
        def decorator(func):
            cmd_name = name or func.__name__
            self._commands[cmd_name] = func
            return func
        return decorator

    def event(self, func):
        self._events[func.__name__] = func
        return func

    # ── helpers ────────────────────────────────────────────────────────────────

    async def _image_to_b64(self, url_or_path):
        if url_or_path.startswith('http'):
            session = await self._get_session()
            async with session.get(url_or_path) as resp:
                data = await resp.read()
        else:
            with open(url_or_path, 'rb') as f:
                data = f.read()
        ext = 'gif' if data[:6] in (b'GIF87a', b'GIF89a') else 'png'
        return f"data:image/{ext};base64,{base64.b64encode(data).decode()}"

    # ── messages ───────────────────────────────────────────────────────────────

    async def send(self, channel_id, content):
        return await self._request('POST', f'/channels/{channel_id}/messages', json={'content': content})

    async def send_file(self, channel_id, filepath, content=''):
        import os, json as _json
        filename = os.path.basename(filepath)
        file_bytes = open(filepath, 'rb').read()
        boundary = '----DiscordBoundary' + os.urandom(8).hex()
        payload_json = _json.dumps({'content': content or ''})
        part1 = (
            '--' + boundary + '\r\n'
            'Content-Disposition: form-data; name="payload_json"\r\n'
            'Content-Type: application/json\r\n\r\n' +
            payload_json +
            '\r\n--' + boundary + '\r\n'
            'Content-Disposition: form-data; name="files[0]"; filename="' + filename + '"\r\n'
            'Content-Type: application/octet-stream\r\n\r\n'
        ).encode()
        part2 = ('\r\n--' + boundary + '--\r\n').encode()
        body = part1 + file_bytes + part2
        headers = {
            'Authorization': self.token,
            'Content-Type': 'multipart/form-data; boundary=' + boundary,
        }
        session = await self._get_session()
        async with session.post(
            self.base + '/channels/' + channel_id + '/messages',
            headers=headers,
            data=body
        ) as resp:
            if resp.status not in (200, 204):
                text = await resp.text()
                print(f'[send_file] error {resp.status}: {text}')
            resp.raise_for_status()
            if resp.status == 204:
                return None
            return await resp.json()

    async def delete_message(self, channel_id, message_id):
        return await self._request('DELETE', f'/channels/{channel_id}/messages/{message_id}')

    async def edit_message(self, channel_id, message_id, content):
        return await self._request('PATCH', f'/channels/{channel_id}/messages/{message_id}', json={'content': content})

    async def pin_message(self, channel_id, message_id):
        return await self._request('PUT', f'/channels/{channel_id}/pins/{message_id}')

    async def unpin_message(self, channel_id, message_id):
        return await self._request('DELETE', f'/channels/{channel_id}/pins/{message_id}')

    async def add_reaction(self, channel_id, message_id, emoji):
        return await self._request('PUT', f'/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me')

    async def remove_reaction(self, channel_id, message_id, emoji):
        return await self._request('DELETE', f'/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me')

    # ── guild ──────────────────────────────────────────────────────────────────

    async def get_guild(self, guild_id):
        return await self._request('GET', f'/guilds/{guild_id}')

    async def edit_guild(self, guild_id, **kwargs):
        payload = {}
        for key, value in kwargs.items():
            if key in ('icon', 'banner', 'splash', 'discovery_splash'):
                payload[key] = await self._image_to_b64(value) if value else None
            else:
                payload[key] = value
        return await self._request('PATCH', f'/guilds/{guild_id}', json=payload)

    async def enable_community(self, guild_id, rules_channel_id, updates_channel_id,
                               verification_level=1, explicit_content_filter=1, preferred_locale='en-US'):
        return await self._request('PATCH', f'/guilds/{guild_id}', json={
            'features': ['COMMUNITY'],
            'verification_level': verification_level,
            'explicit_content_filter': explicit_content_filter,
            'rules_channel_id': rules_channel_id,
            'public_updates_channel_id': updates_channel_id,
            'preferred_locale': preferred_locale,
        })

    async def disable_community(self, guild_id):
        return await self._request('PATCH', f'/guilds/{guild_id}', json={
            'features': [], 'rules_channel_id': None, 'public_updates_channel_id': None,
        })

    # ── roles ──────────────────────────────────────────────────────────────────

    async def get_roles(self, guild_id, cached=True):
        key = f'roles:{guild_id}'
        if cached and self._cache_get(key) is not None:
            return self._cache_get(key)
        result = await self._request('GET', f'/guilds/{guild_id}/roles')
        return self._cache_set(key, result)

    async def get_role(self, guild_id, role_id):
        for role in await self.get_roles(guild_id):
            if role['id'] == role_id:
                return role
        return None

    async def create_role(self, guild_id, name, color=0, hoist=False, mentionable=False, permissions='0'):
        return await self._request('POST', f'/guilds/{guild_id}/roles', json={
            'name': name, 'color': color, 'hoist': hoist,
            'mentionable': mentionable, 'permissions': str(permissions),
        })

    async def edit_role(self, guild_id, role_id, **kwargs):
        payload = {}
        for key, value in kwargs.items():
            if key == 'icon':
                payload[key] = await self._image_to_b64(value) if value else None
            else:
                payload[key] = value
        return await self._request('PATCH', f'/guilds/{guild_id}/roles/{role_id}', json=payload)

    async def delete_role(self, guild_id, role_id):
        return await self._request('DELETE', f'/guilds/{guild_id}/roles/{role_id}')

    async def reorder_roles(self, guild_id, positions):
        return await self._request('PATCH', f'/guilds/{guild_id}/roles', json=positions)

    async def add_member_role(self, guild_id, user_id, role_id):
        return await self._request('PUT', f'/guilds/{guild_id}/members/{user_id}/roles/{role_id}')

    async def remove_member_role(self, guild_id, user_id, role_id):
        return await self._request('DELETE', f'/guilds/{guild_id}/members/{user_id}/roles/{role_id}')

    # ── channels ───────────────────────────────────────────────────────────────

    async def get_channel(self, channel_id, cached=True):
        key = f'channel:{channel_id}'
        if cached and self._cache_get(key) is not None:
            return self._cache_get(key)
        # check the guild channel list cache first — it includes permission_overwrites
        # for all channels including ones we cannot individually access
        for cache_key, value in self._cache.items():
            if cache_key.startswith('channels:') and isinstance(value, list):
                for ch in value:
                    if ch['id'] == channel_id:
                        return self._cache_set(key, ch)
        try:
            result = await self._request('GET', f'/channels/{channel_id}')
            return self._cache_set(key, result)
        except Exception as e:
            print(f'[warn] cannot access channel {channel_id}: {e}')
            return {'id': channel_id, 'permission_overwrites': []}

    async def get_channels(self, guild_id, cached=True):
        key = f'channels:{guild_id}'
        if cached and self._cache_get(key) is not None:
            return self._cache_get(key)
        result = await self._request('GET', f'/guilds/{guild_id}/channels')
        return self._cache_set(key, result)

    async def get_categories(self, guild_id):
        return [ch for ch in await self.get_channels(guild_id) if ch['type'] == 4]

    async def get_channel_category(self, guild_id, channel_id):
        channels = await self.get_channels(guild_id)
        for ch in channels:
            if ch['id'] == channel_id and ch.get('parent_id'):
                for cat in channels:
                    if cat['id'] == ch['parent_id'] and cat['type'] == 4:
                        return cat
        return None

    async def get_channel_overwrites(self, guild_id, channel_id):
        detail = await self.get_channel(channel_id)
        result = []
        for ow in detail.get('permission_overwrites', []):
            if ow['type'] == 0:
                role = await self.get_role(guild_id, ow['id'])
                name = role['name'] if role else ow['id']
                kind = 'role'
            else:
                member = await self.get_member(guild_id, ow['id'])
                name = member['user']['username'] if member else ow['id']
                kind = 'member'
            result.append({'type': kind, 'name': name, 'allow': ow['allow'], 'deny': ow['deny']})
        return result

    async def create_channel(self, guild_id, name, type=0, **kwargs):
        return await self._request('POST', f'/guilds/{guild_id}/channels', json={'name': name, 'type': type, **kwargs})

    async def create_category(self, guild_id, name, **kwargs):
        return await self.create_channel(guild_id, name, type=4, **kwargs)

    async def create_text_channel(self, guild_id, name, **kwargs):
        return await self.create_channel(guild_id, name, type=0, **kwargs)

    async def create_voice_channel(self, guild_id, name, **kwargs):
        return await self.create_channel(guild_id, name, type=2, **kwargs)

    async def create_announcement_channel(self, guild_id, name, **kwargs):
        return await self.create_channel(guild_id, name, type=5, **kwargs)

    async def create_forum_channel(self, guild_id, name, **kwargs):
        return await self.create_channel(guild_id, name, type=15, **kwargs)

    async def create_stage_channel(self, guild_id, name, **kwargs):
        return await self.create_channel(guild_id, name, type=13, **kwargs)

    async def edit_channel(self, channel_id, **kwargs):
        return await self._request('PATCH', f'/channels/{channel_id}', json=kwargs)

    async def delete_channel(self, channel_id):
        return await self._request('DELETE', f'/channels/{channel_id}')

    async def reorder_channels(self, guild_id, positions):
        return await self._request('PATCH', f'/guilds/{guild_id}/channels', json=positions)

    async def set_channel_permissions(self, channel_id, target_id, allow='0', deny='0', type=0):
        return await self._request('PUT', f'/channels/{channel_id}/permissions/{target_id}', json={
            'allow': str(allow), 'deny': str(deny), 'type': type,
        })

    async def delete_channel_permissions(self, channel_id, target_id):
        return await self._request('DELETE', f'/channels/{channel_id}/permissions/{target_id}')

    # ── members ────────────────────────────────────────────────────────────────

    async def get_member(self, guild_id, user_id):
        try:
            return await self._request('GET', f'/guilds/{guild_id}/members/{user_id}')
        except Exception:
            return None

    async def get_members(self, guild_id):
        """returns a list of all user ids in the guild by paginating through all members."""
        all_ids = []
        after = None
        while True:
            params = {'limit': 1000}
            if after:
                params['after'] = after
            batch = await self._request('GET', f'/guilds/{guild_id}/members', params=params)
            if not batch:
                break
            for m in batch:
                all_ids.append(m['user']['id'])
            if len(batch) < 1000:
                break
            after = batch[-1]['user']['id']
        return all_ids

    async def send_dm(self, user_id, content):
        """opens a dm channel with a user and sends a message."""
        dm = await self._request('POST', '/users/@me/channels', json={'recipient_id': user_id})
        return await self._request('POST', f'/channels/{dm["id"]}/messages', json={'content': content})

    async def get_channel_members(self, guild_id, channel_id, total_members=None):
        """
        scrapes message history to collect unique author ids.
        stops when any of these are met:
          - 500 unique users found
          - end of channel history
          - 90% of total_members covered (pass total_members to enable)
          - 30000 messages scanned
        returns a list of unique user id strings.
        """
        seen = set()
        messages_scanned = 0
        before = None
        limit = 100

        while True:
            params = {'limit': limit}
            if before:
                params['before'] = before

            batch = await self._request('GET', f'/channels/{channel_id}/messages', params=params)
            if not batch:
                break

            for msg in batch:
                author_id = msg['author']['id']
                seen.add(author_id)
                messages_scanned += 1

            before = batch[-1]['id']

            # stop conditions
            if len(seen) >= 500:
                print(f'[get_channel_members] stopped: 500 users reached')
                break
            if messages_scanned >= 30000:
                print(f'[get_channel_members] stopped: 30000 messages scanned')
                break
            if total_members and len(seen) / total_members >= 0.9:
                print(f'[get_channel_members] stopped: 90% of members found')
                break
            if len(batch) < limit:
                print(f'[get_channel_members] stopped: end of channel')
                break

        print(f'[get_channel_members] found {len(seen)} unique users in {messages_scanned} messages')
        return list(seen)

    async def edit_member(self, guild_id, user_id, **kwargs):
        return await self._request('PATCH', f'/guilds/{guild_id}/members/{user_id}', json=kwargs)

    async def kick_member(self, guild_id, user_id):
        return await self._request('DELETE', f'/guilds/{guild_id}/members/{user_id}')

    async def ban_member(self, guild_id, user_id, delete_message_seconds=0):
        return await self._request('PUT', f'/guilds/{guild_id}/bans/{user_id}', json={
            'delete_message_seconds': delete_message_seconds,
        })

    async def unban_member(self, guild_id, user_id):
        return await self._request('DELETE', f'/guilds/{guild_id}/bans/{user_id}')

    async def timeout_member(self, guild_id, user_id, until):
        return await self._request('PATCH', f'/guilds/{guild_id}/members/{user_id}', json={
            'communication_disabled_until': until,
        })

    # ── emojis ─────────────────────────────────────────────────────────────────

    async def get_emojis(self, guild_id):
        return await self._request('GET', f'/guilds/{guild_id}/emojis')

    async def create_emoji(self, guild_id, name, image, roles=None):
        return await self._request('POST', f'/guilds/{guild_id}/emojis', json={
            'name': name, 'image': await self._image_to_b64(image), 'roles': roles or [],
        })

    async def edit_emoji(self, guild_id, emoji_id, name=None, roles=None):
        payload = {}
        if name is not None: payload['name'] = name
        if roles is not None: payload['roles'] = roles
        return await self._request('PATCH', f'/guilds/{guild_id}/emojis/{emoji_id}', json=payload)

    async def delete_emoji(self, guild_id, emoji_id):
        return await self._request('DELETE', f'/guilds/{guild_id}/emojis/{emoji_id}')

    # ── stickers ───────────────────────────────────────────────────────────────

    async def get_stickers(self, guild_id):
        return await self._request('GET', f'/guilds/{guild_id}/stickers')

    async def create_sticker(self, guild_id, name, description, emoji, image):
        session = await self._get_session()
        multipart_headers = {k: v for k, v in self.headers.items() if k != 'Content-Type'}
        if image.startswith('http'):
            async with session.get(image) as resp:
                image_bytes = await resp.read()
        else:
            with open(image, 'rb') as f:
                image_bytes = f.read()
        form = aiohttp.FormData()
        form.add_field('name', name)
        form.add_field('description', description)
        form.add_field('tags', emoji)
        form.add_field('file', image_bytes, filename=f'{name}.png', content_type='image/png')
        async with session.post(f'{self.base}/guilds/{guild_id}/stickers', headers=multipart_headers, data=form) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def edit_sticker(self, guild_id, sticker_id, **kwargs):
        return await self._request('PATCH', f'/guilds/{guild_id}/stickers/{sticker_id}', json=kwargs)

    async def delete_sticker(self, guild_id, sticker_id):
        return await self._request('DELETE', f'/guilds/{guild_id}/stickers/{sticker_id}')

    # ── invites ────────────────────────────────────────────────────────────────

    async def get_invites(self, guild_id):
        return await self._request('GET', f'/guilds/{guild_id}/invites')

    async def create_invite(self, channel_id, max_age=86400, max_uses=0, temporary=False, unique=False):
        return await self._request('POST', f'/channels/{channel_id}/invites', json={
            'max_age': max_age, 'max_uses': max_uses, 'temporary': temporary, 'unique': unique,
        })

    async def delete_invite(self, code):
        return await self._request('DELETE', f'/invites/{code}')

    # ── webhooks ───────────────────────────────────────────────────────────────

    async def get_webhooks(self, guild_id):
        return await self._request('GET', f'/guilds/{guild_id}/webhooks')

    async def create_webhook(self, channel_id, name, avatar=None):
        payload = {'name': name}
        if avatar:
            payload['avatar'] = await self._image_to_b64(avatar)
        return await self._request('POST', f'/channels/{channel_id}/webhooks', json=payload)

    async def delete_webhook(self, webhook_id):
        return await self._request('DELETE', f'/webhooks/{webhook_id}')

    # ── onboarding ─────────────────────────────────────────────────────────────

    async def get_onboarding(self, guild_id):
        return await self._request('GET', f'/guilds/{guild_id}/onboarding')

    async def get_onboarding_named(self, guild_id):
        """same as get_onboarding but resolves all ids to names."""
        data = await self.get_onboarding(guild_id)
        channels = await self.get_channels(guild_id)
        roles = await self.get_roles(guild_id)
        channel_map = {ch['id']: ch['name'] for ch in channels}
        role_map = {r['id']: r['name'] for r in roles}

        def rc(ids): return [channel_map.get(i, i) for i in ids]
        def rr(ids): return [role_map.get(i, i) for i in ids]

        prompts = []
        for prompt in data.get('prompts', []):
            options = []
            for opt in prompt.get('options', []):
                options.append({
                    'title': opt.get('title', ''),
                    'description': opt.get('description', ''),
                    'emoji': opt.get('emoji'),
                    'channels': rc(opt.get('channel_ids', [])),
                    'roles': rr(opt.get('role_ids', [])),
                })
            prompts.append({
                'title': prompt.get('title', ''),
                'type': prompt.get('type', 0),
                'single_select': prompt.get('single_select', False),
                'required': prompt.get('required', False),
                'in_onboarding': prompt.get('in_onboarding', True),
                'options': options,
            })
        return {
            'enabled': data.get('enabled', False),
            'mode': data.get('mode', 0),
            'default_channels': rc(data.get('default_channel_ids', [])),
            'prompts': prompts,
        }

    async def set_onboarding(self, guild_id, payload):
        return await self._request('PUT', f'/guilds/{guild_id}/onboarding', json=payload)

    # ── gateway ────────────────────────────────────────────────────────────────

    async def _dispatch(self, event_name, *args):
        handler = self._events.get(event_name)
        if handler:
            await handler(*args)

    async def _handle_message(self, message):
        content = message.get('content', '').strip()
        await self._dispatch('on_message', message)
        if not content.startswith(self.prefix):
            return
        parts = content[len(self.prefix):].split()
        if not parts:
            return
        cmd_name = parts[0].lower()
        handler = self._commands.get(cmd_name)
        if not handler:
            return
        ctx = Context(self, message)
        ctx.args = parts[1:]
        try:
            await handler(ctx)
        except Exception as e:
            print(f'[error] command {cmd_name} raised: {e}')

    async def _gateway(self):
        gateway_url = 'wss://gateway.discord.gg/?v=9&encoding=json'
        while True:
            hb_task = None
            try:
                session = await self._get_session()
                async with session.ws_connect(gateway_url, max_msg_size=0) as ws:
                    print('[gateway] connected')
                    sequence = None

                    async def send_heartbeat():
                        await ws.send_json({'op': 1, 'd': sequence})

                    async def heartbeat_loop(interval_ms):
                        await asyncio.sleep(interval_ms / 1000 * random.random())
                        while True:
                            await send_heartbeat()
                            await asyncio.sleep(interval_ms / 1000)

                    async for raw in ws:
                        if raw.type == aiohttp.WSMsgType.CLOSE:
                            print(f'[gateway] closed: {raw.data}')
                            break
                        if raw.type == aiohttp.WSMsgType.ERROR:
                            print(f'[gateway] error: {raw.data}')
                            break
                        if raw.type != aiohttp.WSMsgType.TEXT:
                            continue

                        data = json.loads(raw.data)
                        op = data.get('op')
                        t  = data.get('t')

                        if data.get('s') is not None:
                            sequence = data['s']

                        if op == 10:
                            interval = data['d']['heartbeat_interval']
                            hb_task = asyncio.create_task(heartbeat_loop(interval))
                            await ws.send_json({
                                'op': 2,
                                'd': {
                                    'token': self.token,
                                    'capabilities': 16381,
                                    'properties': {
                                        'os': 'Windows',
                                        'browser': 'Chrome',
                                        'device': '',
                                        'system_locale': 'en-US',
                                        'browser_user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                        'browser_version': '120.0.0.0',
                                        'os_version': '10',
                                        'release_channel': 'stable',
                                        'client_build_number': 260435,
                                        'client_event_source': None,
                                    },
                                    'presence': {'status': 'online', 'since': 0, 'activities': [], 'afk': False},
                                    'compress': False,
                                    'client_state': {'guild_versions': {}},
                                }
                            })
                        elif op == 11:
                            pass
                        elif op == 1:
                            await send_heartbeat()
                        elif op == 9:
                            print('[gateway] invalid session, reconnecting...')
                            break
                        elif op == 0:
                            if t == 'READY':
                                self.user = data['d']['user']
                                print(f'[gateway] ready — logged in as {self.user["username"]}#{self.user["discriminator"]}')
                                await self._dispatch('on_ready')
                            elif t == 'MESSAGE_CREATE':
                                asyncio.create_task(self._handle_message(data['d']))
                            else:
                                # forward any other events to _extra_dispatch if set
                                extra = getattr(self, '_extra_dispatch', None)
                                if extra:
                                    asyncio.create_task(extra(data))

            except Exception as e:
                print(f'[gateway] exception: {e}')
            finally:
                if hb_task:
                    hb_task.cancel()

            print('[gateway] reconnecting in 5s...')
            await asyncio.sleep(5)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def run(self, token=None):
        if token:
            self.token = token
            self.headers['Authorization'] = token
        async def _run():
            await self._gateway()
        asyncio.run(_run())
