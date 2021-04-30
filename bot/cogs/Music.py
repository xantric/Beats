import discord
from discord.ext import commands
import wavelink
import typing as t
import asyncio
import re
import datetime as dt
import random
from enum import Enum
import math
import asyncio
from time import time
URL_REGEX = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"

OPTIONS = {
    "1️⃣": 0,
    "2⃣": 1,
    "3⃣": 2,
    "4⃣": 3,
    "5⃣": 4,
}

class PlayerIsAlreadyPaused(commands.CommandError):
    pass

class AlreadyConnectedToVoiceChannel(commands.CommandError):
    pass

class NoVoiceChannel(commands.CommandError):
    pass

class QueueIsEmpty(commands.CommandError):
    pass

class NoTracksFound(commands.CommandError):
    pass

class NoMoreTracks(commands.CommandError):
    pass

class NoPreviousTracks(commands.CommandError):
    pass

class RepeatMode(Enum):
    NONE=0
    SONG=1
    ALL=2

class Queue:
    def __init__(self):
        self._queue = []
        self.position = 0
        self.repeat_mode = RepeatMode.NONE
    

    @property
    def is_empty(self):
        return not self._queue
    @property
    def first_track(self):
        if not self._queue:
            raise QueueIsEmpty

        return self._queue[0]
    @property
    def current_track(self):
        if not self._queue:
            raise QueueIsEmpty
        if self.position <= len(self._queue) - 1:
            return self._queue[self.position]
    @property
    def queue_duration(self):
        if not self._queue:
            raise QueueIsEmpty
        du = 0
        for i in self._queue[self.position+1:]:
            du += i.duration
        return du
    @property
    def upcoming_track(self):
        if not self._queue:
            raise QueueIsEmpty
        new_queue = self._queue
        if self.repeat_mode == RepeatMode.ALL:
            if len(self._queue) == self.position+1:
                return self._queue[:self.position]
            else:
                new_l = new_queue[self.position+1:]
                new_l.extend(new_queue[:self.position])
                return new_l 

        return self._queue[self.position+1:]
    @property
    def previous_track(self):
        if not self._queue:
            raise QueueIsEmpty
        return self._queue[:self.position]
    @property
    def length(self):
        return len(self._queue)


    def empty_queue(self):
        self._queue.clear()
    
    def shuffle(self):
        if not self._queue:
            raise QueueIsEmpty
        upcoming = self.upcoming_track
        random.shuffle(upcoming)
        self._queue = self._queue[:self.position+1]
        self._queue.extend(upcoming)
    
    def set_repeat_mode(self,mode):
        if mode == "none":
            self.repeat_mode = RepeatMode.NONE
        elif mode == "song":
            self.repeat_mode = RepeatMode.SONG
        elif mode == "queue":
            self.repeat_mode = RepeatMode.ALL

    def add(self,*args):
        self._queue.extend(args)
    def get_next_track(self):
        if not self._queue:
            raise QueueIsEmpty
        
        self.position += 1

        if self.position < 0:
            return None
        elif self.position > len(self._queue) - 1:
            if self.repeat_mode == RepeatMode.ALL:
                self.position = 0
            else:
                return None
        

        return self._queue[self.position]    


class Player(wavelink.Player):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.queue = Queue()
    async def connect(self,ctx,channel=None):
        if self.is_connected:
            raise AlreadyConnectedToVoiceChannel

        if (channel := getattr(ctx.author.voice, "channel",channel)) is None:
            raise NoVoiceChannel

        await super().connect(channel.id)
        return channel
    async def set_volume(self, vol:int):
        if vol > 100:
            self.volume = 1000
        else:
            volume = vol*10
            self.volume = volume
    async def teardown(self):
        try:
            self.queue.repeat_mode = RepeatMode.NONE
            await self.destroy()
        except KeyError:
            pass
    
    async def add_tracks(self,ctx,tracks):
        if not tracks:
            raise NoTracksFound
        
        if isinstance(tracks, wavelink.TrackPlaylist):
            for i in range(len(tracks.tracks)):
                x = tracks.tracks[i]
                x.info["requester"] = ctx.author.mention
            embed = discord.Embed(description=f"Added `{len(tracks.tracks)}` tracks to your queue",color=discord.Color.random())
            await ctx.send(embed=embed)
            self.queue.add(*tracks.tracks)
        else:
            track = tracks[0]
            track.info["requester"] = ctx.author.mention
            requester = track.info["requester"]
            self.queue.add(track)
            if not self.is_playing and not self.queue.is_empty:
                
                embed = discord.Embed(title="Now Playing",
                description=f"[**{track.title}**]({track.uri})",
                color=discord.Color.random(),
                timestamp=dt.datetime.utcnow()
                )
                embed.set_thumbnail(url=track.thumb)
                embed.add_field(name="Duration",value=f"{track.length//60000}:{str(track.length%60).zfill(2)}")
                embed.add_field(name="Author",value=f"{track.author}")
                embed.add_field(name="Requested by:",value=f"{requester}")
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="Music Queue",
                description=f"Added [**{track.title}**]({track.uri}) to queue.",
                color=discord.Color.random()
                )
                await ctx.send(embed=embed)
        await ctx.message.add_reaction("✅")
        if not self.is_playing and not self.queue.is_empty:
            await self.start_playback()
        
    async def choose_track(self, ctx, tracks):
        def _check(r, u):
            return (
                r.emoji in OPTIONS.keys()
                and u == ctx.author
                and r.message.id == msg.id
            )

        embed = discord.Embed(
            title="Choose a song",
            description=(
                "\n".join(
                    f"**{i+1}.** `{t.title} ({t.length//60000}:{str(t.length%60).zfill(2)})`"
                    for i, t in enumerate(tracks[:5])
                )
            ),
            colour=ctx.author.colour,
            timestamp=dt.datetime.utcnow()
        )
        embed.set_author(name="Query Results")
        embed.set_footer(text=f"Invoked by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)

        msg = await ctx.send(embed=embed)
        for emoji in list(OPTIONS.keys())[:min(len(tracks), len(OPTIONS))]:
            await msg.add_reaction(emoji)

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=60.0, check=_check)
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.message.delete()
        else:
            await msg.delete()
            return tracks[OPTIONS[reaction.emoji]]

    async def start_playback(self):
        try:
            if not self.is_playing:
                try:
                    await self.play(self.queue.current_track)
                except:
                    await self.play(self.queue.upcoming_track)
        except:
            pass


    async def advance(self):
        try:
            if (track := self.queue.get_next_track()) is not None:
                await self.play(track)
        except QueueIsEmpty:
            pass

    async def repeat_track(self):
        await self.play(self.queue.current_track)
class Music(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot):
        self.bot = bot
        self.wavelink = wavelink.Client(bot=bot)
        self.bot.loop.create_task(self.start_nodes())
    # @commands.Cog.listener()
    # async def on_voice_state_update(self,member,before,after):
    #     if not member.bot and after.channel is None:
    #         if not [m for m in before.channel.members if not m.bot]:
    #             await asyncio.sleep(90)
    #             await self.get_player(member.guild).teardown()
    
    @wavelink.WavelinkMixin.listener()
    async def on_node_ready(self, node):
        print(f"Wavelink node {node.identifier} ready.")
    
    @wavelink.WavelinkMixin.listener("on_track_stuck")
    @wavelink.WavelinkMixin.listener("on_track_end")
    @wavelink.WavelinkMixin.listener("on_track_exception")
    async def on_player_stop(self,node,payload):
        if payload.player.queue.repeat_mode == RepeatMode.SONG:
            await payload.player.repeat_track()
        else:
            await payload.player.advance()


    async def cog_check(self,ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("Music commands are not available in DMs.")
            return False
        return True
    
    async def start_nodes(self):
        await self.bot.wait_until_ready()
        nodes = {
            "MAIN": {
                "host":"lava.link",
                "port":80,
                "rest_uri":"http://lava.link:80",
                "password":"anything as a password",
                "identifier":"MAIN",
                "region":"us-central"
            }
        }

        for node in nodes.values():
            await self.wavelink.initiate_node(**node)

    def get_player(self,obj):
        if isinstance(obj, commands.Context):
            return self.wavelink.get_player(obj.guild.id,cls=Player, context=obj)

        elif isinstance(obj, discord.Guild):
            return self.wavelink.get_player(obj.id,cls=Player)

    @commands.command(name="connect",aliases=["join"])
    async def _connect(self,ctx,*,channel:t.Optional[discord.VoiceChannel]):
        player = self.get_player(ctx)
        channel = await player.connect(ctx,channel)

        await ctx.send(f"Connected to {channel.name}.")

    @_connect.error
    async def connect_error(self,ctx,exc):
        if isinstance(exc, AlreadyConnectedToVoiceChannel):
            await ctx.send("Already connected to a voice channel.")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("You are not connected to any voice channel.")
    
    @commands.command(name="disconnect",aliases=["leave","dc"])
    async def _disconnect(self,ctx):
        player = self.get_player(ctx)
        await ctx.message.add_reaction("👋")
        await player.teardown()
        #await ctx.send("Disconnected.")

    @commands.command(name="play",aliases=["p"])
    async def _play(self,ctx,*,query:t.Optional[str]):
        player = self.get_player(ctx)

        if not player.is_connected:
            channel = await player.connect(ctx)
            await ctx.guild.change_voice_state(channel=channel,self_deaf=True)
        if query is None:
            pass
        else:
            query = query.strip("<>")
            if not re.match(URL_REGEX, query):
                query = f"ytsearch:{query}"
            
            
            await player.add_tracks(ctx, await self.wavelink.get_tracks(query))
            
    @commands.command(name="queue",aliases=["q"])
    async def queue_command(self,ctx):
        player = self.get_player(ctx)
        show = 5
        items_per_page = 5
        current_page = 1
        #entries = player.queue.length-1
        entries = len(player.queue.upcoming_track)
        pages = math.ceil(entries / items_per_page)
        if pages == 0:
            pages=1
        #print(pages)
        if player.queue.is_empty:
            raise QueueIsEmpty
        
        embed = discord.Embed(
            title="Current Queue",
            color=discord.Color.random(),
            timestamp=dt.datetime.utcnow()
        )
        
        if player.queue.current_track:
            embed.add_field(
            name="Currently playing",
            value=f"**[{player.queue.current_track.title}]({player.queue.current_track.uri})**",
            inline=False
            )
            #embed.add_field(name="Length",value=f"({player.queue.current_track.length//60000}:{str(player.queue.current_track.length%60).zfill(2)})",inline=True)
            if player.queue.queue_duration//60000 > 59:
                hrs = (player.queue.queue_duration//60000)//60
                embed.add_field(name=":hourglass: Queue Duration",value=f"{hrs}:{(player.queue.queue_duration//60000)-(60*hrs)}:{str(player.queue.queue_duration%60).zfill(2)}")
            else:
                embed.add_field(name=":hourglass: Queue Duration",value=f"{player.queue.queue_duration//60000}:{str(player.queue.queue_duration%60).zfill(2)}")
            embed.add_field(name=":pencil: Entries",value=f"{len(player.queue.upcoming_track)}")
            if player.queue.repeat_mode == RepeatMode.ALL:
                embed.add_field(name="Looping:",value=f"🔁`Queue`")
            elif player.queue.repeat_mode == RepeatMode.SONG:
                embed.add_field(name="Looping:",value=f"🔂`Song`")
            else:
                embed.add_field(name="Looping:",value=f"`None`")
            if player.equalizer.name == "Boost":
                embed.add_field(name="Bass Booster",value=":white_check_mark:")
            else:
                embed.add_field(name="Bass Booster",value=":x:")
            embed.add_field(name="Requested by:",value=player.queue.current_track.info["requester"])
        elif not player.queue.current_track:
            embed.add_field(
            name="Currently playing",
            value="No Tracks currently playing",
            inline=False
            )
        try:
            if upcoming_track := player.queue.upcoming_track:
                
                embed.add_field(
                    name="Next up",
                    value="\n".join(f"**{i+1}. [{t.title}]({t.uri}) ({t.length//60000}:{str(t.length%60).zfill(2)})**" 
                    for i, t in enumerate(player.queue.upcoming_track[:show])
                    ),
                    inline=False
                )
        except:
            if upcoming_track := player.queue.upcoming_track:
                embed.add_field(
                    name="Next up",
                    value="\n".join(f"**[{t.title}]({t.uri}) ({t.length//60000}:{str(t.length%60).zfill(2)})**" 
                    for t in player.queue.upcoming_track[:show]
                    ),
                    inline=False
                )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/830772596538343506.gif?v=1")
        embed.set_footer(text=f"Page : {current_page}/{pages}\nInvoked by {ctx.author.name}",icon_url=ctx.author.avatar_url)
        msg = await ctx.send(embed=embed)
        start = (current_page-1)* items_per_page
        end = start + items_per_page
        buttons = ["⬅️","➡️"]
        if pages > 1:
            for button in buttons:
                await msg.add_reaction(button)
            while True:
                try:
                    reaction, user = await self.bot.wait_for("reaction_add",check=lambda reaction, user: user == ctx.author and reaction.emoji in buttons, timeout=20.0)
                except asyncio.TimeoutError:
                    await msg.clear_reactions()
                else:
                    previous_pg = current_page
                    if reaction.emoji == "⬅️":
                        if current_page > 1:
                            current_page -= 1
                    elif reaction.emoji == "➡️":
                        if current_page < pages:
                            current_page += 1
                    for button in buttons:
                        await msg.remove_reaction(button,ctx.author)
                    if previous_pg != current_page:
                        pages = math.ceil(entries / items_per_page)
                        start = (current_page - 1) * items_per_page
                        end = start + items_per_page
                        embed.remove_field(6)
                        #em = discord.Embed(title=f"Search Results for: {query}",description="",color=discord.Color.random())
                        embed.add_field(
                        name="Next up",
                        value="\n".join(f"**{i+1+start}. [{t.title}]({t.uri}) ({t.length//60000}:{str(t.length%60).zfill(2)})**" 
                        for i, t in enumerate(player.queue.upcoming_track[start:end])
                        ),
                        inline=False
                        )
                        #em.set_footer(text=f"Page : {current_page}/{pages}\nYou can use these as `:name:` to send emojis")
                        embed.set_footer(text=f"Page : {current_page}/{pages}\nInvoked by {ctx.author.name}",icon_url=ctx.author.avatar_url)
                        await msg.edit(embed=embed)
    @queue_command.error
    async def queue_error(self,ctx,exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("Queue is currently empty. Add some songs using `[p]play <song_name>`.")
        else:
            print(str(exc))
    
    @commands.command(name="pause")
    async def pause_command(self,ctx):
        player = self.get_player(ctx)
        if player.is_paused:
            raise PlayerIsAlreadyPaused
        await ctx.message.add_reaction("⏸️")
        await player.set_pause(True)
    @pause_command.error
    async def pause_error(self,ctx,exc):
        if isinstance(exc, PlayerIsAlreadyPaused):
            pass

    @commands.command(name="resume")
    async def resume_command(self,ctx):
        player = self.get_player(ctx)
        if player.is_paused:
            await ctx.message.add_reaction("⏯️")
            await player.set_pause(False)
        else:
            return

    @commands.command(name="stop")
    async def stop_command(self,ctx):
        player = self.get_player(ctx)
        player.queue.empty_queue()
        player.queue.repeat_mode = RepeatMode.NONE
        await player.stop()
        await ctx.message.add_reaction("⏹️")

    @commands.command(name="next",aliases=["skip"])
    async def next_command(self,ctx):
        player = self.get_player(ctx)
        if not player.queue.upcoming_track:
            raise NoMoreTracks
        await ctx.message.add_reaction("⏭️")
        await player.stop()
    @next_command.error
    async def next_error(self,ctx,exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("`Queue is empty. ;-;`")
        if isinstance(exc, NoMoreTracks):
            await ctx.send("`No More tracks in queue.`")
        else:
            print(str(exc))
    
    @commands.command(name="previous",aliases=["back"])
    async def previous_command(self,ctx):
        player = self.get_player(ctx)
        if not player.queue.previous_track:
            raise NoPreviousTracks
        player.queue.position -= 2
        await ctx.message.add_reaction("⏮️")
        await player.stop()
    @previous_command.error
    async def previous_error(self,ctx,exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("`Queue is empty. ;-;`")
        if isinstance(exc, NoPreviousTracks):
            await ctx.send("`No Previous Track in queue.`")
    @commands.command(name="shuffle")
    async def shuffle_command(self,ctx):
        player = self.get_player(ctx)
        await ctx.message.add_reaction("🔀")
        player.queue.shuffle()
    @shuffle_command.error
    async def shuffle_error(self,ctx,exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("Queue is Empty. ;-; use `[p]play <song_name>` to start playing songs.")
    
    @commands.command(name="repeat",aliases=["loop"])
    async def repeat_command(self,ctx,mode:str="song"):
        if mode not in ("song","queue","none"):
            await ctx.send("Invalid repeat mode specified. These are valid inputs: `Song`, `Queue`, `None`")
        else:
            player = self.get_player(ctx)
            await ctx.message.add_reaction("🔁")
            player.queue.set_repeat_mode(mode.lower())
            embed = discord.Embed(description=f"Looping set to: `{mode}`",color=discord.Color.random())
            await ctx.send(embed=embed)

    @commands.command(name="nowplaying",aliases=["now","np","song"])
    async def nowplaying_command(self,ctx):
        player = self.get_player(ctx)
        if player.is_playing:
            embed = discord.Embed(title="Now Playing",
            description=f"[**{player.queue.current_track.title}**]({player.queue.current_track.uri})",
            color=discord.Color.random(),
            timestamp=dt.datetime.utcnow()
            )
            requester = player.queue.current_track.info["requester"]
            embed.set_thumbnail(url=player.queue.current_track.thumb)
            hrs = (player.queue.current_track.duration//60000)//60
            embed.add_field(name=":hourglass: Duration",value=f"{hrs}:{(player.queue.current_track.duration//60000)-(60*hrs)}:{str(player.queue.current_track.duration%60).zfill(2)}")
            #embed.add_field(name="Duration",value=f"{player.queue.cuurrent_track.length//60000}:{str(track.length%60).zfill(2)}")
            embed.add_field(name=":bust_in_silhouette: Author",value=f"{player.queue.current_track.author}")
            embed.add_field(name="Requested by:",value=f"{requester}",inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Nothing playing right now. Use `[p]play <song/url>` to start streaming.")
    @commands.command(name="removesong",aliases=["rs"])
    async def removesong(self,ctx,index:int):
        if index is None:
            await ctx.send("You need to specify the index of song to remove.")
        else:
            player = self.get_player(ctx)
            player.queue._queue.pop(index+player.queue.position)
            await ctx.message.add_reaction("✅")

    @commands.command(name="move")
    async def move_command(self,ctx,index1:int,index2:int):
        if index1 is None or index2 is None:
            raise commands.MissingRequiredArgument
        player = self.get_player(ctx)
        x = player.queue._queue.pop(index1+player.queue.position)
        y = player.queue._queue.pop(index2+player.queue.position)
        player.queue._queue.insert(index2+player.queue.position, x)
        player.queue._queue.insert(index1+player.queue.position, y)
        await ctx.message.add_reaction("✅")
    
    # @commands.command(name="volume",aliases=["setvolume","loudness"])
    # async def volume_command(self,ctx,vol:int):
    #     player = self.get_player(ctx)
    #     if 0 <= vol <=100:
    #         player.volume = vol
    #         await ctx.send(f"Volume of the player set to: {vol}%")
    #     else:
    #         await ctx.send("Volume must be between 0 and 100.")
    
    @commands.command(name="bassboost",aliases=["boost","bass"])
    async def bassboost_command(self,ctx):
        player = self.get_player(ctx)
        print(type(player.equalizer.name))
        print(player.equalizer.name)
        if player.equalizer.name != "Boost":
            # equaliser = [(0, -0.075), (1, .125), (2, .125), (3, .1), (4, .1),
            #       (5, .05), (6, 0.075), (7, .0), (8, .0), (9, .0),
            #       (10, .0), (11, .0), (12, .125), (13, .15), (14, .05)]
            await player.set_eq(wavelink.eqs.Equalizer.boost())
            await ctx.send("Bass boosted mode turned on.")
        elif player.equalizer.name == "Boost":
            await player.set_eq(wavelink.eqs.Equalizer.flat())
            await ctx.send("Bass boosted mode turned off.")
def setup(bot):
    bot.add_cog(Music(bot))

