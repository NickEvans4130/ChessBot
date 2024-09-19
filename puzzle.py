import requests
import chess.pgn
import io
import chess.engine


def fetch_games(username):
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    response = requests.get(url)
    archives = response.json()['archives']
    games = []
    for archive in archives:
        archive_response = requests.get(archive)
        games += archive_response.json()['games']
    return games


def parse_game_pgn(pgn):
    pgn_io = io.StringIO(pgn)
    game = chess.pgn.read_game(pgn_io)
    board = game.board()
    positions = []
    for move in game.mainline_moves():
        board.push(move)
        positions.append(board.fen())  # Save each position in FEN format
    return positions


def is_tactical_puzzle(board_fen):
    with chess.engine.SimpleEngine.popen_uci("/path/to/stockfish") as engine:
        board = chess.Board(board_fen)
        # Evaluate the current position
        info_before = engine.analyse(board, chess.engine.Limit(time=0.1))
        score_before = info_before['score'].relative.score()

        # Find the best move
        best_move = engine.play(board, chess.engine.Limit(time=0.1)).move
        board.push(best_move)

        # Evaluate after the best move
        info_after = engine.analyse(board, chess.engine.Limit(time=0.1))
        score_after = info_after['score'].relative.score()

        # Check if the position is a tactical puzzle (i.e., large eval change)
        if score_after - score_before > 300:  # Large swing in favor of one side
            return True, best_move
    return False, None

def generate_puzzles(games):
    puzzles = []
    for game in games:
        positions = parse_game_pgn(game['pgn'])
        for position in positions:
            is_puzzle, best_move = is_tactical_puzzle(position)
            if is_puzzle:
                puzzles.append({
                    'fen': position,
                    'solution': best_move
                })
    return puzzles
