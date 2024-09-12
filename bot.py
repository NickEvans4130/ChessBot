import discord
from discord.ext import commands
from discord.ui import Button, View
import chess
import requests
import sqlite3

# Initialize the bot and chess game
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
game = chess.Board()

# Role management and state tracking
roles = {'white_hand': None, 'white_brain': None, 'black_hand': None, 'black_brain': None}
users = {}
piece_choices = {}  # Track user's chosen piece
pressed_users = set()  # Track users who have pressed a button

DATABASE = 'users.db'

@bot.tree.command(name="brainhand", description="Starts a Brain and Hand Game")
async def start_game(ctx: discord.Interaction):
    if any(role is None for role in roles.values()):
        embed = discord.Embed(title="Select Your Role")
        view = View()

        # Buttons for selecting roles
        buttons = {
            'White Hand': 'white_hand',
            'White Brain': 'white_brain',
            'Black Hand': 'black_hand',
            'Black Brain': 'black_brain',
        }

        for label, role_key in buttons.items():
            button = Button(label=label, style=discord.ButtonStyle.primary, custom_id=role_key)
            button.callback = role_callback
            view.add_item(button)

        await ctx.response.send_message(embed=embed, view=view)
    else:
        await ctx.response.send_message("The game has already started.", ephemeral=True)

# Handle role selection
async def role_callback(interaction: discord.Interaction):
    user = interaction.user
    role_key = interaction.data['custom_id']

    if user.id in pressed_users:
        await interaction.response.send_message("You have already selected a role.", ephemeral=True)
        return

    if role_key in roles and roles[role_key] is None:
        roles[role_key] = user
        users[user.id] = role_key
        pressed_users.add(user.id)  # Mark user as having pressed a button
        await interaction.response.send_message(f"You have been assigned as {role_key.replace('_', ' ').title()}.")
        
        # Check if all roles are assigned
        if all(role is not None for role in roles.values()):
            await display_board(interaction.channel)
    else:
        await interaction.response.send_message("This role is already taken or invalid.", ephemeral=True)

# Display the chess board
async def display_board(channel: discord.TextChannel):
    board_str = str(game)
    embed = discord.Embed(title="Chess Board", description="Here's the current state of the board:")
    embed.add_field(name="Board", value=f"```\n{board_str}\n```")
    await channel.send(embed=embed)

# Command to choose a piece
@bot.command()
async def piece(ctx, piece_name: str):
    user = ctx.author
    if user.id not in users:
        await ctx.send("You need to select a role first.")
        return

    role = users[user.id]
    if role.endswith('hand'):
        piece_name = piece_name.lower()
        valid_pieces = {
            'pawn': chess.PAWN,
            'knight': chess.KNIGHT,
            'bishop': chess.BISHOP,
            'rook': chess.ROOK,
            'queen': chess.QUEEN,
            'king': chess.KING
        }

        if piece_name in valid_pieces:
            piece_choices[user.id] = piece_name
            await ctx.send(f"You have selected the {piece_name}.")
        else:
            await ctx.send("Invalid piece name.")
    else:
        await ctx.send("Only players with 'hand' roles can select a piece.")

# Command to make a move
@bot.command()
async def move(ctx, move: str):
    user = ctx.author
    if user.id not in users:
        await ctx.send("You need to select a role first.")
        return

    role = users[user.id]
    if role.endswith('hand'):
        if user.id not in piece_choices:
            await ctx.send("You need to choose a piece first using the !piece command.")
            return

        piece_name = piece_choices[user.id]
        valid_pieces = {
            'pawn': chess.PAWN,
            'knight': chess.KNIGHT,
            'bishop': chess.BISHOP,
            'rook': chess.ROOK,
            'queen': chess.QUEEN,
            'king': chess.KING
        }

        piece_type = valid_pieces[piece_name]
        legal_moves = [m for m in game.legal_moves if game.piece_at(m.from_square).piece_type == piece_type]

        try:
            chess_move = chess.Move.from_uci(move)
            if chess_move in legal_moves:
                game.push(chess_move)
                await ctx.send(f"Move {move} made.")
            else:
                await ctx.send("Invalid move for the selected piece.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")
    else:
        await ctx.send("Only players with 'hand' roles can make a move.")

def create_table():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            discord_id TEXT PRIMARY KEY,
            chess_username TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_user(discord_id, chess_username):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO users (discord_id, chess_username)
        VALUES (?, ?)
    ''', (discord_id, chess_username))
    conn.commit()
    conn.close()

def get_chess_username(discord_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        SELECT chess_username FROM users WHERE discord_id = ?
    ''', (discord_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

@bot.tree.command(name='sync', description='Sync your Chess.com account with Discord')
async def sync(interaction: discord.Interaction, chess_username: str):
    # Get the author ID from the interaction context
    author_id = interaction.user.id

    add_user(author_id, chess_username)

    headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0"
    }   

    response = requests.get(f"https://api.chess.com/pub/player/{chess_username}/stats", headers=headers)

    if response.status_code == 200:
        data = response.json()

        # Check if the specific sections exist in the data before accessing them
        rapid_rating = data.get('chess_rapid', {}).get('last', {}).get('rating', 'N/A')
        bullet_rating = data.get('chess_bullet', {}).get('last', {}).get('rating', 'N/A')
        blitz_rating = data.get('chess_blitz', {}).get('last', {}).get('rating', 'N/A')

        await interaction.response.send_message(f'Successfully synced! Here are your ratings:\n'
                                                f'Rapid: {rapid_rating}\n'
                                                f'Bullet: {bullet_rating}\n'
                                                f'Blitz: {blitz_rating}')
    else:
        # Log the response content for further debugging
        print(f"Status Code: {response.status_code}, Content: {response.content}")
        await interaction.response.send_message('Error retrieving data from Chess.com. Please check your username and try again.')

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    create_table()
    await bot.tree.sync()

# Run the bot
bot.run('')
