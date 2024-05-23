from flask import render_template, jsonify, request
from app import app
from app.board import Board
import random

game = Board()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_game', methods=['POST'])
def start_game():
    global game
    game = Board()
    player = request.json['player']
    if player == -1:
        game.current_player = -1
        make_random_move()  # Computer starts
    return jsonify(success=True)

@app.route('/get_board', methods=['GET'])
def get_board():
    return jsonify(board=game.board)

@app.route('/make_move', methods=['POST'])
def make_move():
    move = request.json['move']
    if move in game.get_moves_list(game.current_player):
        game.push_move(move)
        if game.is_winning(game.current_player):
            return jsonify(winner=game.current_player)
        game.current_player = -game.current_player
        make_random_move()
        if game.is_winning(game.current_player):
            return jsonify(winner=-game.current_player)
    return jsonify(board=game.board)

def make_random_move():
    moves = game.get_moves_list(game.current_player)
    if moves:
        move = random.choice(moves)
        game.push_move(move)
        game.current_player = -game.current_player
