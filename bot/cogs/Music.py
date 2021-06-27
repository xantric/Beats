import discord
from discord.ext.commands.errors import CommandInvokeError
import lavalink
from discord.ext import commands
import asyncio
import re
import datetime as dt
import random
import math
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from enum import Enum
import os

client_id = os.getenv('spotify_client_id')
client_secret = os.getenv('spotify_client_secret')
sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=client_id,client_secret=client_secret))

url_rx = re.compile(r'https?://(?:www\.)?.+')
OPTIONS = {
    "1️⃣": 0,
    "2️⃣": 1,
    "3️⃣": 2,
    "4️⃣": 3,
    "5️⃣": 4,
    "6️⃣": 5,
    "7️⃣": 6,
}
class RepeatMode(Enum):
    NONE=0
    SONG=1
    ALL=2

class Music(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        bot.lavalink = lavalink.Client(bot.user.id)
        bot.lavalink.add_node('lava.link', 80, 'anything as a password', 'us', 'alpha')
        bot.lavalink.add_node('lava.link', 80, 'anything as a password', 'us', 'beta')
        bot.lavalink.add_node('lava.link', 80, 'anything as a password', 'us', 'gamma')
        bot.lavalink.add_node('lava.link', 80, 'anything as a password', 'us', 'delta')
        bot.lavalink.add_node('lava.link', 80, 'anything as a password', 'us', 'eta')
        bot.lavalink.add_node('lava.link', 80, 'anything as a password', 'us', 'zeta')
        bot.lavalink.add_node('lava.link', 80, 'anything as a password', 'us', 'theta')# Host, Port, Password, Region, Name
        bot.add_listener(bot.lavalink.voice_update_handler, 'on_socket_response')
        lavalink.add_event_hook(self.track_hook)
        self.repeat_mode = RepeatMode.NONE
    async def cog_before_invoke(self, ctx):
        """ Command before-invoke handler. """
        guild_check = ctx.guild is not None
        #  This is essentially the same as `@commands.guild_only()`
        #  except it saves us repeating ourselves (and also a few lines).

        if guild_check:
            await self.ensure_voice(ctx)
            #  Ensure that the bot and command author share a mutual voicechannel.

        return guild_check

    # async def cog_command_error(self, ctx, error):
    #     if isinstance(error, commands.CommandInvokeError):
    #         em = discord.Embed(description=f"{error.original}",color=discord.Color.red())
    #         await ctx.send(embed=em)
            # The above handles errors thrown in this cog and shows them to the user.
            # This shouldn't be a problem as the only errors thrown in this cog are from `ensure_voice`
            # which contain a reason string, such as "Join a voicechannel" etc. You can modify the above
            # if you want to do things differently.

    async def ensure_voice(self, ctx):
        """ This check ensures that the bot and command author are in the same voicechannel. """
        player = self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))
        should_connect = ctx.command.name in ('play','ytsearch','connect')

        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandInvokeError('You are not in a voice channel')

        if not player.is_connected:
            if not should_connect:
                raise commands.CommandInvokeError('Not connected to any voice channel.')

            permissions = ctx.author.voice.channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:  # Check user limit too?
                raise commands.CommandInvokeError('I need the `CONNECT` and `SPEAK` permissions.')

            player.store('channel', ctx.channel.id)
            await ctx.guild.change_voice_state(channel=ctx.author.voice.channel,self_deaf=True)
            em = discord.Embed(description=f"Joined {ctx.author.voice.channel.mention}",color=discord.Color.blurple())
            await ctx.send(embed=em)
        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                raise commands.CommandInvokeError('You are not in the same voice channel.')

    @commands.command(aliases=['p'])
    async def play(self, ctx, *, query: str=None):
        """ Searches and plays a song from a given query. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        embed = discord.Embed(color=discord.Color.blurple())
        if query == None and player.paused:
            await player.set_pause(False)
            await ctx.message.add_reaction("⏯️")
        elif query is not None:
            query = query.strip('<>')
            if "https://open.spotify.com/playlist/" in query or "spotify:playlist:" in query:
                tracks = self.get_tracks_spotify(query)
                emoji = discord.utils.get(self.bot.emojis, name = "loadingd")
                embed = discord.Embed(title=f"{emoji} Loading Playlist",description="This might take some time but the playback should start right away.",color=discord.Color.random())
                await ctx.send(embed = embed)
                for track in tracks:
                    results = await player.node.get_tracks(track)
                    if not player.is_playing:
                        await player.play()
                    player.add(requester=ctx.author.id, track=results['tracks'][0])
                embed.title = 'Playlist Enqueued!'
                embed.description = f"Queued `{len(tracks)-1}` tracks"
            elif "https://open.spotify.com/track/" in query or "spotify:track:" in query:
                ID = self.getTrackID(query)
                track = self.getTrackFeatures(ID)
                results = await player.node.get_tracks(track)
                player.add(requester=ctx.author.id, track=results['tracks'][0])
                embed.title = "Track Enqueued"
                embed.description = track
            else:
                if not url_rx.match(query):
                    query = f'ytsearch:{query}'

                results = await player.node.get_tracks(query)

                if not results or not results['tracks']:
                    return await ctx.send('Nothing found!')

                
                # Valid loadTypes are:
                #   TRACK_LOADED    - single video/direct URL)
                #   PLAYLIST_LOADED - direct URL to playlist)
                #   SEARCH_RESULT   - query prefixed with either ytsearch: or scsearch:.
                #   NO_MATCHES      - query yielded no results
                #   LOAD_FAILED     - most likely, the video encountered an exception during loading.
                if results['loadType'] == 'PLAYLIST_LOADED':
                    tracks = results['tracks']

                    for track in tracks:
                        
                        player.add(requester=ctx.author.id, track=track)

                    embed.title = 'Playlist Enqueued!'
                    #print(results["playlistInfo"])
                    embed.description = f'{results["playlistInfo"]["name"]} - {len(tracks)} tracks'
                else:
                    track = results['tracks'][0]
                    #print(track)
                    embed.title = 'Track Enqueued'
                    embed.description = f'[{track["info"]["title"]}]({track["info"]["uri"]})'

                    # You can attach additional information to audiotracks through kwargs, however this involves
                    # constructing the AudioTrack class yourself.
                    track = lavalink.models.AudioTrack(track, ctx.author.id, recommended=True)
                    player.add(requester=ctx.author.id, track=track)

            await ctx.send(embed=embed)

            # We don't want to call .play() if the player is playing as that will effectively skip
            # the current track.
            if not player.is_playing:
                await player.play()
            
    def getTrackID(self, track):
        track = sp.track(track)
        return track["id"]
    def getTrackFeatures(self, id):
        meta = sp.track(id)
        features = sp.audio_features(id)
        name = meta['name']
        album = meta['album']['name']
        artist = meta['album']['artists'][0]['name']
        release_date = meta['album']['release_date']
        length = meta['duration_ms']
        popularity = meta['popularity']
        return f"ytsearch:{artist} - {album}"
    def get_tracks_spotify(self,url):
        x = sp.playlist_items(url,offset=0)
        temp = []
        for i in range(len(x['items'])):
            song = x['items'][i]['track']['artists'][0]['name']
            ar = x['items'][i]['track']['name']
            name_song = f"ytsearch:{song} - {ar}"
            temp.append(name_song)
        x = sp.playlist_items(url,offset=100)
        for i in range(len(x['items'])):
            song = x['items'][i]['track']['artists'][0]['name']
            ar = x['items'][i]['track']['name']
            name_song = f"ytsearch:{song} - {ar}"
            temp.append(name_song)
        return temp

    async def track_hook(self, event):
        
        if isinstance(event, lavalink.TrackStartEvent):
            guild_id = int(event.player.guild_id)
            player = self.bot.lavalink.player_manager.get(guild_id)
            channel = player.fetch('channel')
            #print(player.current.requester)
            requester = await self.bot.fetch_user(player.current.requester)
            embed = discord.Embed(title='Now Playing',description=f'[{player.current.title}]({player.current.uri}) [{requester.mention}]',color=discord.Color.blurple())
            if self.repeat_mode != RepeatMode.SONG:
                await self.bot.get_channel(channel).send(embed=embed)
        if isinstance(event, lavalink.TrackStuckEvent):
            guild_id = int(event.player.guild_id)
            player = self.bot.lavalink.player_manager.get(guild_id)
            await player.skip()
        if isinstance(event,lavalink.TrackExceptionEvent):
            guild_id = int(event.player.guild_id)
            player = self.bot.lavalink.player_manager.get(guild_id)
            channel = player.fetch('channel')
            em = discord.Embed(description=f"{event.exception}",color=discord.Color.random())
            await self.bot.get_channel(channel).send(embed=em)
        if isinstance(event, lavalink.NodeConnectedEvent):
            print(f"lavalink node: {event.node} ready")
        if isinstance(event, lavalink.TrackEndEvent):
            guild_id = int(event.player.guild_id)
            player = self.bot.lavalink.player_manager.get(guild_id)
            #x = player.fetch('requester')
            #print(x)
            #print(event.reason)
            #print(player.current.requester)
            #print(event.track)
            if self.repeat_mode == RepeatMode.ALL:
                player.add(requester=event.track.requester,track=event.track)
    @commands.command(name="connect",aliases=["join"])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def _connect(self,ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        embed=discord.Embed(description=f"Connected to voice channel",color=discord.Color.blurple())
        if player.is_connected:
            await ctx.send(embed=embed)
    @commands.command(aliases=['dc'])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def disconnect(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_connected:
            # We can't disconnect, if we're not connected.
            return await ctx.send('Not connected.')

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            # Abuse prevention. Users not in voice channels, or not in the same voice channel as the bot
            # may not disconnect the bot.
            return await ctx.send('You\'re not in my voicechannel!')

        # Clear the queue to ensure old tracks don't start playing
        # when someone else queues something.
        player.queue.clear()
        # Stop the current track so Lavalink consumes less resources.
        await player.stop()
        self.repeat_mode = RepeatMode.NONE
        # Disconnect from the voice channel.
        await ctx.guild.change_voice_state(channel=None)
        await ctx.send(':mailbox_with_no_mail: Disconnected.')

    @commands.command(name="queue",aliases=["q"])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def _queue(self,ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player.is_playing or len(player.queue) != 0:
            items_per_page = 6
            current_page = 1
            entries = len(player.queue)
            pages = math.ceil(entries / items_per_page)
            if pages == 0:
                pages=1
            em = discord.Embed(title="Current Queue",
            color=discord.Color.blurple(),
            timestamp=dt.datetime.utcnow()
            )
            if player.is_playing:
                em.add_field(
                    name="Currently Playing",
                    value=f"[{player.current.title}]({player.current.uri})",
                    inline=False
                )
            else:
                em.add_field(
                    name="Currently Playing",
                    value=f"Nothing playing right now",
                    inline=False
                )
            #print(dir(player.current))
            temp = 0
            for i in player.queue:
                temp += i.duration
            em.add_field(name=":hourglass: Queue Duration",value=f"`{lavalink.format_time(temp)}`")
            em.add_field(name=":pencil: Entries",value=f"`{len(player.queue)}`")
            if player.is_playing:
                requester = await self.bot.fetch_user(player.current.requester)
                em.add_field(name="Requested by:",value=f"{requester.mention}")
            else:
                em.add_field(name="Requested by:",value=f"--------")
            if self.repeat_mode == RepeatMode.ALL:
                em.add_field(name="Loop",value=":repeat: `Queue`")
            elif self.repeat_mode == RepeatMode.SONG:
                em.add_field(name="Loop",value=":repeat_one: `Song`")
            elif self.repeat_mode == RepeatMode.NONE:
                em.add_field(name="Loop",value=":x:")
            
            equaliser = [-0.075, 0.125, 0.125, 0.1, 0.1, 0.05, 0.075, 0.0, 0.0, 0.0, 0.0, 0.0, 0.125, 0.15, 0.05]
            if player.equalizer == equaliser:
                em.add_field(name="BassBoost",value=":white_check_mark:")
            else:
                em.add_field(name="BassBoost",value=":x:")
            if player.is_playing:
                if player.volume >= 100:
                    em.add_field(name=":loud_sound: Volume",value=f"`{player.volume}`")
                elif player.volume < 100:
                    em.add_field(name=":sound: Volume",value=f"`{player.volume}`")
            else:
                em.add_field(name=":mute: Volume",value="-------")
            if len(player.queue) != 0:
                em.add_field(
                    name="Up Next",
                    value="\n".join(f"{i+1}. [{t.title}]({t.uri}) ({int((t.duration/60000)%60)}:{str(int((t.duration/1000)%60)).zfill(2)})"
                    for i , t in enumerate(player.queue[:items_per_page])
                    ),
                    inline=False
                )
            else:
                em.add_field(
                    name="Up Next",
                    value="No more songs add some using `[p]play <name>`",
                    inline=False
                )
            
            em.set_thumbnail(url="https://cdn.discordapp.com/emojis/830772596538343506.gif?v=1")
            em.set_footer(text=f"Page : {current_page}/{pages}\nInvoked by {ctx.author.name}",icon_url=ctx.author.avatar_url)
            msg = await ctx.send(embed=em)
            start = (current_page-1)* items_per_page
            end = start + items_per_page
            buttons = ["⏪","⬅️","⏹️","➡️","⏩"]
            if pages > 1:
                for button in buttons:
                    await msg.add_reaction(button)
                while True:
                    try:
                        reaction, user = await self.bot.wait_for("reaction_add",check=lambda reaction, user: user == ctx.author and reaction.emoji in buttons, timeout=20.0)
                    except asyncio.TimeoutError:
                        await msg.clear_reactions()
                        break
                    else:
                        previous_pg = current_page
                        if reaction.emoji == "⬅️":
                            if current_page > 1:
                                current_page -= 1
                        elif reaction.emoji == "➡️":
                            if current_page < pages:
                                current_page += 1
                        elif reaction.emoji == "⏩":
                            if current_page < pages:
                                current_page = pages
                        elif reaction.emoji == "⏪":
                            if current_page > 1:
                                current_page = 1
                        elif reaction.emoji == "⏹️":
                            await msg.clear_reactions()
                            break
                        for button in buttons:
                            await msg.remove_reaction(button,ctx.author)
                        if previous_pg != current_page:
                            pages = math.ceil(entries / items_per_page)
                            start = (current_page - 1) * items_per_page
                            end = start + items_per_page
                            em.remove_field(7)
                            #em = discord.Embed(title=f"Search Results for: {query}",description="",color=discord.Color.random())
                            em.add_field(
                            name="Next up",
                            value="\n".join(f"{i+1+start}. [{t.title}]({t.uri}) ({int((t.duration/60000)%60)}:{str(int((t.duration/1000)%60)).zfill(2)})" 
                            for i, t in enumerate(player.queue[start:end])
                            ),
                            inline=False
                            )
                            #em.set_footer(text=f"Page : {current_page}/{pages}\nYou can use these as `:name:` to send emojis")
                            em.set_footer(text=f"Page : {current_page}/{pages}\nInvoked by {ctx.author.name}",icon_url=ctx.author.avatar_url)
                            await msg.edit(embed=em)
    @commands.command(name="skip",aliases=["next","n"])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def _skip(self,ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player.is_playing:
            if  ctx.author.guild_permissions.manage_guild or ctx.author.id == player.current.requester or ctx.author.guild_permissions.administrator:
                await ctx.message.add_reaction("⏭️")
                await player.skip()
            else:
                await ctx.send("You are missing the role or perms for this command or u are not the requester.")
    @commands.command(name="pause")
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def _pause(self,ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player.is_playing:
            if ctx.author.guild_permissions.manage_guild or ctx.author.id == player.current.requester or ctx.author.guild_permissions.administrator:
                await player.set_pause(True)
                await ctx.message.add_reaction("⏸️")
            else:
                await ctx.send("You are missing the role or perms for this command or u are not the requester.")
    @commands.command(name="resume")
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def _resume(self,ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if ctx.author.guild_permissions.manage_guild or ctx.author.id == player.current.requester or ctx.author.guild_permissions.administrator:
            if player.paused:
                await player.set_pause(False)
                await ctx.message.add_reaction("⏯️")
        else:
            await ctx.send("You are missing the required role or perms for this command or u are not the requester.")
    @commands.command(name="stop")
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def _stop(self,ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player.is_playing:
            if ctx.author.guild_permissions.manage_guild or ctx.author.id == player.current.requester or ctx.author.guild_permissions.administrator:
                await player.stop()
                await ctx.message.add_reaction("⏹️")
            else:
                await ctx.send("You are missing the required role or perms for this command or u are not the requester.")
    @commands.command(name="shuffle",aliases=['mix'])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def _shuffle(self,ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        random.shuffle(player.queue)
        await ctx.message.add_reaction("🔀")
    
    @commands.command(name="seek",aliases=["position","fastforward","ff"])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def seek_command(self,ctx,time:str):
        try:
            player = self.bot.lavalink.player_manager.get(ctx.guild.id)
            if ":" in time:
                a = time.split(":")
                x = len(a)
                if x == 2:
                    minutes = int(a[0])
                    seconds = int(a[1])
                    seconds += minutes*60
                elif x == 3:
                    hours  = int(a[0])
                    minutes = int(a[1])
                    seconds = int(a[2])
                    seconds += minutes*60+hours*3600
            else:
                seconds = int(time)
            await player.seek(seconds*1000)
            #em = discord.Embed(description=f"Seeked to the position `{time}`")
            await ctx.message.add_reaction("✅")
        except Exception as e:
            await ctx.send(str(e))
    
    @commands.command(name="move",aliases=["mv"])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def move_command(self,ctx,index1:int,index2:int):
        if index1 is None or index2 is None:
            raise commands.MissingRequiredArgument
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        x = player.queue.pop(index1-1)
        y = player.queue.pop(index2-1)
        player.queue.insert(index2-1, x)
        player.queue.insert(index1-1, y)
        await ctx.message.add_reaction("✅")
    
    @commands.command(name="removesong",aliases=["rs","remove","rm"])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def removesong(self,ctx,index:int):
        if index is None:
            await ctx.send("You need to specify the index of song to remove.")
        else:
            player = self.bot.lavalink.player_manager.get(ctx.guild.id)
            player.queue.pop(index-1)
            await ctx.message.add_reaction("✅")

    @commands.command(name="ytsearch",aliases=['songsearch'])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def _ytsearch(self,ctx,*,query:str):
        try:
            player = self.bot.lavalink.player_manager.get(ctx.guild.id)
            query = f'ytsearch:{query}'
            results = await player.node.get_tracks(query)
            tracks = results['tracks'][0:len(OPTIONS)]
            i = 0
            query_result = ''
            for track in tracks:
                i = i + 1
                query_result = query_result + f'{i}) [{track["info"]["title"]}]({track["info"]["uri"]})\n'
            embed = discord.Embed()
            embed.description = query_result

            msg = await ctx.channel.send(embed=embed)

            def _check(r,u):
                return (r.emoji in OPTIONS.keys()
                and u == ctx.author
                and r.message.id == msg.id
                )
            for emoji in list(OPTIONS.keys())[:min(len(tracks), len(OPTIONS))]:
                await msg.add_reaction(emoji)
            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=60.0, check=_check)
            except asyncio.TimeoutError:
                await msg.delete()
            else:
                await msg.delete()
                track = tracks[OPTIONS[reaction.emoji]]

                player.add(requester=ctx.author.id, track=track)
                embed = discord.Embed(color=discord.Color.blurple())
                embed.title = 'Track Enqueued'
                embed.description = f'[{track["info"]["title"]}]({track["info"]["uri"]})'
                if not player.is_playing:
                    await player.play()
                
                await ctx.send(embed=embed)

        except Exception as error:
            print(error)

    @commands.command(name="nowplaying",aliases=["now","np","song"])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def _nowplaying(self,ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player.is_playing:
            embed = discord.Embed(title="Now Playing",
            description=f"[**{player.current.title}**]({player.current.uri})",
            color=discord.Color.random(),
            timestamp=dt.datetime.utcnow()
            )
            #embed.set_thumbnail(url=player.queue.current_track.thumb)
            seconds=(player.position/1000)%60
            seconds = int(seconds)
            minutes=(player.position/(1000*60))%60
            minutes = int(minutes)
            hours=(player.position/(1000*60*60))%24
            hours = int(hours)
            #print(f"{h}")
            hrs = (player.current.duration//60000)//60
            x = (player.position/player.current.duration)*100
            string = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
            y = int((x/100)*len(string))
            #print(len(string))
            final = string[:y]+":blue_circle:"+string[y:]+f" `[{round(x,1)}%]`"
            embed.add_field(name=":bust_in_silhouette: Author",value=f"{player.current.author}",inline=True)
            requester = await self.bot.fetch_user(player.current.requester)
            embed.add_field(name="Requested by:",value=f"{requester.mention}",inline=False)
            if hrs > 0:
                embed.add_field(name=":hourglass: Duration",value=f"`{hours}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}/{lavalink.format_time(player.current.duration)}`\n{final}")
            else:
                embed.add_field(name=":hourglass: Duration",value=f"`{minutes}:{str(seconds).zfill(2)}/{int((player.current.duration/(1000*60))%60)}:{str(int((player.current.duration/1000)%60)).zfill(2)}`\n{final}")
            #embed.add_field(name="Duration",value=f"{player.queue.cuurrent_track.length//60000}:{str(track.length%60).zfill(2)}")
            
            await ctx.send(embed=embed)

    @commands.command(name='loop',aliases=["repeat"])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def _loop(self,ctx,loop:str="song"):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        loop = loop.lower()
        if loop =="song" or loop =="s":
            x = not player.repeat
            player.repeat = x
            self.repeat_mode = RepeatMode.SONG
            await ctx.message.add_reaction("🔂")
        elif loop == "q" or loop == "queue":
            self.repeat_mode = RepeatMode.ALL
            player.repeat = False
            await ctx.message.add_reaction("🔁")
        elif loop == "none" or loop == "n":
            self.repeat_mode = RepeatMode.NONE
            player.repeat = False
            em = discord.Embed(description="Looping set to: `None`",color=discord.Color.random())
            await ctx.send(embed=em)
        else:
            em = discord.Embed(description="Please specify a valid option: `song`, `queue`, `none` or (`s`,`q`,`n`)",color=discord.Color.random())
            await ctx.send(embed=em)
    @commands.command(name="bassboost",aliases=["boost","bass"])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def bassboost_command(self,ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        # print(type(player.equalizer.name))
        # print(player.equalizer.name)
        #print(player.equalizer)
        equaliser = [(0, -0.065), (1, .135), (2, .130), (3, .1), (4, .1),
                  (5, .05), (6, 0.075), (7, .0), (8, .0), (9, .0),
                  (10, .0), (11, .0), (12, .125), (13, .15), (14, .05)]
        eq = [-0.075, 0.125, 0.125, 0.1, 0.1, 0.05, 0.075, 0.0, 0.0, 0.0, 0.0, 0.0, 0.125, 0.15, 0.05]
        if player.equalizer != eq:
            await player.set_gains(*equaliser)
            await ctx.send("Bass boosted mode turned on.")
        elif player.equalizer == eq:
            await player.reset_equalizer()
            await ctx.send("Bass boosted mode turned off.")
    
    @commands.command(name="suggest",aliases=["sgst","trending"])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def _suggest(self,ctx,genre:str):
        #y = sp.recommendation_genre_seeds()
        #print(y)
        x = sp.recommendations(seed_genres=[genre],limit=10)
        embed = discord.Embed(title=f"Song suggestions for: {genre}",description="",color=discord.Color.random())
        #print(x['tracks'][0].keys())
        for i in range(len(x['tracks'])):
            song = x['tracks'][i]['name']
            ar = x['tracks'][i]['artists'][0]['name']
            if embed.description == "":
                embed.description += f"**{i+1}.** `{song} - {ar}`"
            else:
                embed.description += f"\n**{i+1}.** `{song} - {ar}`"
        await ctx.send(embed=embed)
    @commands.command(name="lyrics")
    async def ly(self,ctx):
        raise CommandInvokeError('This command does not work currently')
    @commands.command(name="playervolume",aliases=["v","vol","loudness"])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def _volume(self,ctx,amount:int):
        if 0 <= amount <= 200:
            player = self.bot.lavalink.player_manager.get(ctx.guild.id)
            if amount > player.volume:
                await ctx.message.add_reaction("🔊")
            elif amount <= player.volume:
                await ctx.message.add_reaction("🔉")
            await player.set_volume(amount)
        else:
            await ctx.send("The amount should be in between 0 and 200")
    @commands.command(name="clearqueue",aliases=["queueclear"])
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def _clearqueue(self,ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        player.queue.clear()
        await ctx.message.add_reaction("✅")

def setup(bot):
    bot.add_cog(Music(bot))
