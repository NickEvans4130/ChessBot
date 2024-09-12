import discord
from discord.ext import commands
from discord.ui import Button, View

# Initialize the bot and chess game
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

@bot.event()
async def on_ready():
    print(f"Logged in as {bot.user.name}")

bot.run("TOKEN")