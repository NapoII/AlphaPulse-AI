from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import UserMixin, login_user, logout_user, login_required
import os

auth_bp = Blueprint('auth', __name__)

# Simple in-memory user store (for demo only)
USERS = {
    os.getenv('APP_USERNAME', 'admin'): {
        'password': os.getenv('APP_PASSWORD', 'admin123'),
        'id': '1',
        'name': 'Admin'
    }
}

class SimpleUser(UserMixin):
    def __init__(self, user_id, name):
        self.id = user_id
        self.name = name

def user_loader(user_id):
    for username, data in USERS.items():
        if data['id'] == user_id:
            return SimpleUser(data['id'], data['name'])
    return None

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        user = USERS.get(username)
        if user and user['password'] == password:
            login_user(SimpleUser(user['id'], user['name']))
            return redirect(url_for('main.index'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
