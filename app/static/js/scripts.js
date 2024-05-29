let currentPlayer = 1;
let sourceRow = -1;
let sourceCol = -1;

function startGame(player) {
    currentPlayer = player;
    fetch('/start_game', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ player }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadBoard();
        }
    });
}

function loadBoard() {
    fetch('/get_board')
    .then(response => response.json())
    .then(data => {
        renderBoard(data);
    });
}

function renderBoard(data) {
    const board = document.getElementById('board');
    board.innerHTML = '';
    data.board.forEach((row, rowIndex) => {
        row.forEach((square, colIndex) => {
            const div = document.createElement('div');
            div.className = `square ${((rowIndex + colIndex) % 2 === 0) ? 'white' : 'black'}`;
            div.innerHTML = square === 1 ? '♙' : (square === -1 ? '♟︎' : '');
            div.onclick = () => selectSquare(rowIndex, colIndex);
            board.appendChild(div);
        });
    });
}

function selectSquare(row, col) {
    // Handle square selection and move logic
    if (sourceRow == -1) {
        sourceRow = row;
        sourceCol = col;
        return;
    }

    const move = { from_row: sourceRow, from_col: sourceCol, to_row: row, to_col: col };
    fetch('/make_move', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ move }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.winner !== undefined) {
            document.getElementById('status').innerText = `Player ${data.winner === 1 ? 'White' : 'Black'} wins!`;
        } else {
            renderBoard(data);
        }
    });
}
