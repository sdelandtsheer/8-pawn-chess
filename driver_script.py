import numpy as np
import matplotlib.pyplot as plt

from app.board import Board

terminal_moves = []

for rep in range(1000):
    print(f'rep: {rep}')
    b = Board()
    n_moves = 100
    player = 1

    print(b)

    for move in range(n_moves):
        if b.is_winning(-player):
            print(f'player {-player} is winning')
            terminal_moves.append(move - 1)
            break
        else:
            print(f'move: {move}')
            moves = b.get_moves_list(player)
            rnd = np.random.randint(0, len(moves))
            b.push_move(moves[rnd])
            player = -player
            print(b)

n, bins, patches = plt.hist(x=terminal_moves, bins='auto', color='#0504aa',
                            alpha=0.7, rwidth=0.85)
plt.grid(axis='y', alpha=0.75)
plt.xlabel('Value')
plt.ylabel('Frequency')
plt.title('# moves')
maxfreq = n.max()
# Set a clean upper y-axis limit.
plt.ylim(ymax=np.ceil(maxfreq / 10) * 10 if maxfreq % 10 else maxfreq + 10)
plt.show()