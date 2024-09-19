import discord
from discord.ext import commands
from discord.ui import Button, View, Select
import chess
import chess.svg
import io
from cairosvg import svg2png
import requests
import sqlite3
import statistics
from dotenv import load_dotenv
import os

load_dotenv
TOKEN=os.getenv("TOKEN")

# Initialize the bot and chess game
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix='?', intents=intents)
game = chess.Board()

# Brain Hand Role management and state tracking
brain_hand_roles = {'white_hand': None, 'white_brain': None, 'black_hand': None, 'black_brain': None}
brain_hand_users = {}
brain_hand_piece_choices = {}  # Track user's chosen piece
brain_hand_pressed_users = set()  # Track users who have pressed a button

# (St)andard game variables
st_game_board = chess.Board()
st_move_history = []
st_current_message = None  # To store the message object

DATABASE = 'users.db'

@bot.tree.command(name="brainhand", description="Starts a Brain and Hand Game")
async def start_game(ctx: discord.Interaction):
    if any(role is None for role in brain_hand_roles.values()):
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

    if user.id in brain_hand_pressed_users:
        await interaction.response.send_message("You have already selected a role.", ephemeral=True)
        return

    if role_key in brain_hand_roles and brain_hand_roles[role_key] is None:
        brain_hand_roles[role_key] = user
        brain_hand_users[user.id] = role_key
        brain_hand_pressed_users.add(user.id)  # Mark user as having pressed a button
        await interaction.response.send_message(f"You have been assigned as {role_key.replace('_', ' ').title()}.")
        
        # Check if all roles are assigned
        if all(role is not None for role in brain_hand_roles.values()):
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
    if user.id not in brain_hand_users:
        await ctx.send("You need to select a role first.")
        return

    role = brain_hand_users[user.id]
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
            brain_hand_piece_choices[user.id] = piece_name
            await ctx.send(f"You have selected the {piece_name}.")
        else:
            await ctx.send("Invalid piece name.")
    else:
        await ctx.send("Only players with 'hand' roles can select a piece.")

# Command to make a move
@bot.command()
async def bh_move(ctx, move: str):
    user = ctx.author
    if user.id not in brain_hand_users:
        await ctx.send("You need to select a role first.")
        return

    role = brain_hand_users[user.id]
    if role.endswith('hand'):
        if user.id not in brain_hand_piece_choices:
            await ctx.send("You need to choose a piece first using the !piece command.")
            return

        piece_name = brain_hand_piece_choices[user.id]
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
            chess_elo TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_user(discord_id, chess_elo):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO users (discord_id, chess_elo)
        VALUES (?, ?)
    ''', (discord_id, chess_elo))
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

        add_user(author_id, (statistics.median([rapid_rating, bullet_rating, blitz_rating])))

class SkillSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Beginner", description="Elo range: 400-800", value="beginner"),
            discord.SelectOption(label="Intermediate", description="Elo range: 800-1200", value="intermediate"),
            discord.SelectOption(label="Experienced", description="Elo range: 1200+", value="experienced"),
        ]
        super().__init__(placeholder="Select your skill level...", options=options)

    async def callback(self, interaction: discord.Interaction):
        skill = self.values[0]
        elo_ranges = {
            "beginner": "400-800",
            "intermediate": "800-1200",
            "experienced": "1200+"
        }
        elo_range = elo_ranges.get(skill, "Unknown")
        await interaction.response.send_message(f"Your skill level: {skill.title()} ({elo_range})", ephemeral=True)
        if elo_range == elo_ranges['beginner']:
            elo = 600
        elif elo_range == elo_ranges['intermediate']:
            elo = 1000
        elif elo_range == elo_ranges['experienced']:
            elo = 1300
        else:
            print("Invalid elo range")

        add_user(interaction.user.id, elo)
        print(f"User {interaction.user.id} selected {elo_range} Elo range.")

class SkillView(View):
    def __init__(self):
        super().__init__()
        self.add_item(SkillSelect())

@bot.tree.command(name='skill', description='Select your skill level!')
async def skill(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Select Your Skill Level",
        description="If you do not have a chess.com rating, please select your skill level from below! \n If you do have a chess.com rating please run `/sync` to link your account.",
        color=discord.Color.blue()
    )
    view = SkillView()
    await interaction.response.send_message(embed=embed, view=view)

def generate_chessboard_image(board):
    """Generates a PNG image of the current chessboard."""
    svg_board = chess.svg.board(board)
    png_image = svg2png(bytestring=svg_board)
    return png_image


class ChessView(discord.ui.View):
    def __init__(self, board):
        super().__init__(timeout=None)
        self.board = board

    @discord.ui.button(label="Resign", style=discord.ButtonStyle.danger)
    async def resign_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"{interaction.user.mention} has resigned.", ephemeral=False)
        self.stop()

    @discord.ui.button(label="Offer Draw", style=discord.ButtonStyle.secondary)
    async def offer_draw_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"{interaction.user.mention} has offered a draw.", ephemeral=False)


@bot.tree.command(name="start_game", description="Starts a new chess game")
async def start_game(interaction: discord.Interaction):
    """Starts a new game and sends the initial board."""
    global st_game_board, st_current_message
    st_game_board = chess.Board()
    view = ChessView(st_game_board)

    # Generate the initial board
    image_data = generate_chessboard_image(st_game_board)
    file = discord.File(io.BytesIO(image_data), filename="chessboard.png")

    # Create an embed with the initial board and moves
    embed = discord.Embed(title="Chess Game", description="White to move.")
    embed.set_image(url="attachment://chessboard.png")
    embed.add_field(name="Move History", value="No moves yet.", inline=False)

    # Defer the response, indicating you'll send a follow-up message
    await interaction.response.defer()

    # Send the follow-up message and store the message object
    st_current_message = await interaction.followup.send(embed=embed, file=file, view=view)



@bot.tree.command(name="game_move", description="Make a chess move")
async def st_move(interaction: discord.Interaction, piece: str, start_square: str, end_square: str):
    """
    Processes a move based on the given piece, starting square, and ending square.
    Updates the same embed rather than sending a new one each time.
    """
    global st_game_board, st_move_history, st_current_message

    # Combine start and end squares into a UCI move string (e.g., e2e4)
    uci_move = start_square + end_square

    try:
        chess_move = chess.Move.from_uci(uci_move)
        if chess_move in st_game_board.legal_moves:
            st_game_board.push(chess_move)
            st_move_history.append(uci_move)

            # Update the board image
            image_data = generate_chessboard_image(st_game_board)
            file = discord.File(io.BytesIO(image_data), filename="chessboard.png")

            # Format move history
            move_list = " ".join([f"{i//2 + 1}. {st_move_history[i]} {st_move_history[i+1] if i+1 < len(st_move_history) else ''}"
                                  for i in range(0, len(st_move_history), 2)])

            # Update the embed with the new board and move history
            embed = discord.Embed(title="Chess Game", description="Move made.")
            embed.set_image(url="attachment://chessboard.png")
            embed.add_field(name="Move History", value=move_list, inline=False)

            # Edit the existing message rather than sending a new one
            await st_current_message.edit(embed=embed, attachments=[file])
            await interaction.response.send_message("Move made successfully!", ephemeral=True)
        else:
            await interaction.response.send_message("Illegal move. Try again.", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("Invalid move format. Please check the input.", ephemeral=True)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    create_table()
    await bot.tree.sync()

# Run the bot
bot.run(TOKEN)
