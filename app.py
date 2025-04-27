from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'

# Correct Database Setup:
if 'RENDER' in os.environ:
    print("Running on Render: Using /tmp/site.db database")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/site.db'
else:
    print("Running Locally: Using site.db in project folder")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

db = SQLAlchemy(app)

# Setup login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# MLB CSV File
CSV_FILENAME = 'mlb_2025_schedule.csv'

##########################################
# Database Models
##########################################

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.String(50), nullable=False)
    stars = db.Column(db.Integer, nullable=False)
    content = db.Column(db.String(280), nullable=False)

##########################################
# User loader
##########################################

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

##########################################
# Helper to Load Games
##########################################

def load_completed_games():
    df = pd.read_csv(CSV_FILENAME, dtype=str)

    completed_statuses = ['Final', 'Game Over', 'Completed Early', 'Completed Early: Rain']

    completed_games = df[df['status'].isin(completed_statuses)]
    completed_games = completed_games.sort_values(by='date', ascending=False)
    return completed_games

##########################################
# Routes
##########################################

@app.route('/')
@login_required
def index():
    games = load_completed_games()
    return render_template('index.html', games=games)

@app.route('/game/<game_id>', methods=['GET', 'POST'])
@login_required
def game_page(game_id):
    if request.method == 'POST':
        stars = int(request.form.get('stars', 0))
        content = request.form.get('content', '').strip()

        if stars <= 0 or stars > 5:
            flash('Invalid star rating.', 'danger')
            return redirect(url_for('game_page', game_id=game_id))
        if len(content) > 280:
            flash('Text is too long!', 'danger')
            return redirect(url_for('game_page', game_id=game_id))

        review = Review(user_id=current_user.id, game_id=game_id, stars=stars, content=content)
        db.session.add(review)
        db.session.commit()
        flash('Review Submitted!', 'success')
        return redirect(url_for('index'))

    all_reviews = Review.query.filter_by(game_id=game_id).all()
    return render_template('game.html', game_id=game_id, reviews=all_reviews)

##########################################
# Authentication
##########################################

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()

        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login Failed: Invalid username or password', 'danger')

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()

        if not username or not password:
            flash('Missing username or password', 'danger')
            return redirect(url_for('signup'))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists', 'danger')
            return redirect(url_for('signup'))

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

##########################################
# Main Runner
##########################################

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Properly inside context
    app.run(host='0.0.0.0', port=5000, debug=True)
