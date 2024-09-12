from stockfish import Stockfish
import chess.pgn
import matplotlib.pyplot as plt
import numpy as np
import os
from scipy.interpolate import make_interp_spline

def loadGame(pgn):
    with open(pgn) as pgn:
        game = chess.pgn.read_game(pgn)
    return game

'''
Takes in pgn, uses stockfish to evaluate each move
Returns a list of evaluations by move order
(Not dictionary, so not associated with the corresponding move number)
Eval extends from -10 to +10
Notes:
- If either player has forced mate, the eval shows +-10
- If eval is greater than +10 or less than -10, still tops out at +-10
'''
def evalGame(game, stockfish):
    board = chess.Board()
    evals = []
    for move in game.mainline_moves():
        board.push(move)
        fen = board.fen()
        stockfish.set_fen_position(fen)
        evaluation = stockfish.get_evaluation()
        #print(evaluation)
        if evaluation['type'] == 'mate':
            if evaluation['value'] > 0:
                evals.append(10)
            elif evaluation['value'] < 0:
                evals.append(-10)
            else:
                evals.append(evals[-1]) # questionable logic, revisit
        else:
            evaluation = evaluation['value']/100
            evals.append(min(max(evaluation, -10), 10))
    return evals

'''
Calculates the number of moves based on the length of the eval list
(Maybe not necessary for the graph itself, but implemented in case x-axis
 move number labels are wanted)
Since chess notation goes 1. [white move] [black move],
this moves list represents '1. [white move]' as '1'
and '1. ... [black move]' as 1.5, etc.
'''
def numMoves(evals):
    moves = np.arange(1, len(evals)+1)
    moves = (moves+1)/2
    return moves

'''
Purely for aesthetics. Set k to 1 for default line graph,
k to 3 for slightly smoother graph
(done using spline so sometimes when the graph tops out at +-10
 it still draws a curve instead of laying flat)
'''
def smoothGraph(moves, evals, k):
    x = np.linspace(moves.min(), moves.max(), 500)
    spl = make_interp_spline(moves, evals, k=k) # make k=3 for smooth graph
    y = spl(x)
    return x, y

# MAIN #
stockfishPath = "C:/Users/.../stockfish/<stockfish>.exe"
stockfish = Stockfish(path=stockfishPath)

pgn = "game.pgn"
game = loadGame(pgn)
evals = evalGame(game, stockfish)
moves = numMoves(evals)
x, y = smoothGraph(moves, evals, 1) # make 3 for smoother graph

# PLOTTING #
plt.figure(figsize=(10,3))
plt.plot(x, y, color = 'green', linewidth = 2)

plt.axhline(y=0, color = '#a3a3a3') # y = 0 line

plt.fill_between(x, y, 10, color = '#333333')
plt.fill_between(x, y, -10, color = '#eeeeee')

# graph capped at +-10
plt.xlim(1, max(moves))
plt.ylim(-10, 10)

plt.axis('off')
#plt.xlabel('Move #')
#plt.ylabel('Eval (Stockfish 17)')

evalFolder = 'analysis' # folder to save eval graph
evalFile = 'eval.png' # eval graph name
path = os.path.join(evalFolder, evalFile)
os.makedirs(evalFolder, exist_ok = True)
plt.savefig(path, transparent = True, bbox_inches='tight', pad_inches=0)

plt.show()