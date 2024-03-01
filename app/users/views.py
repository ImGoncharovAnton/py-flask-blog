from flask import render_template, url_for, session, Blueprint, redirect, request, flash, g
from app.db import get_db
from werkzeug.security import generate_password_hash, check_password_hash
import functools

from app.utils import form_errors, validate

bp = Blueprint('users', __name__)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if username and email and password:
            hashed_password = generate_password_hash(password)
            db = get_db()
            query = ("""--sql
            INSERT INTO users (username, email, password) 
            VALUES ('%s', '%s', '%s')""" % (username, email, hashed_password))
            db.execute(query)
            db.commit()
            flash('Account was created', category='success')
            return redirect(url_for('users.login'))

        # handle errors
        error_fields = form_errors('username', 'email', 'password')
        errors = validate(error_fields, username, email, password)
        return render_template('users/register.html', errors=errors)
    return render_template('users/register.html', errors=None)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute("""--sql
        SELECT * FROM users WHERE username = ? OR email = ?""",
                          (username, username)).fetchone()
        if user is None or not check_password_hash(user['password'], password):
            flash('Email or password incorrect', category='danger')
            return render_template('users/login.html')
        session.clear()
        session['user_id'] = user['id']
        return redirect(url_for('blog.posts'))
    return render_template('users/login.html')


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('users.login'))


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        db = get_db()
        user = db.execute("""--sql
        SELECT * FROM users WHERE id = ?""", (user_id,)).fetchone()
        g.user = user


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('users.login'))
        return view(**kwargs)

    return wrapped_view
