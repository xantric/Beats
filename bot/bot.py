from pathlib import Path 
import discord
from discord.ext import commands
import os
class MusicBot(commands.Bot):
    def __init__(self):
        self._cogs=[p.stem for p in Path(".").glob("./bot/cogs/*.py")]
        super().__init__(command_prefix=self.prefix, case_insensitive=True, intents=discord.Intents.all())
    def setup(self):
        print("Running Setup.....")

        for cog in self._cogs:
            self.load_extension(f"bot.cogs.{cog}")
            print(f"Loaded {cog} cog.")
        print("Setup Complete.")
    
    def run(self):
        self.setup()

##        with open("data/token.0","r", encoding="utf-8") as f:
##            TOKEN = f.read() 
        TOKEN = os.getenv("TOKEN")

        print("Running the bot")
        super().run(TOKEN,reconnect=True)
        
    async def on_ready(self):
        print(f"Bot ready.")
    async def prefix(self,bot,msg):
        return commands.when_mentioned_or("+")(bot,msg)
