import sqlite3
import click
from pathlib import Path
from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def create_db():
    db = get_db()
    schema_paths = list(Path().glob('**/*.sql'))
    schema_paths.reverse()
    for schema_path in schema_paths:
        with schema_path.open() as f:
            db.executescript(f.read())


def create_admin(email, password):
    db = get_db()
    hashed_password = generate_password_hash(password)
    db.execute("""--sql
    INSERT INTO users (email, password, is_admin) VALUES (?, ?, 1)""", (email, hashed_password))
    db.commit()


@click.command('create-db')
@with_appcontext
def db_command():
    create_db()
    click.echo('Created database successfully!')


@click.command('create-admin')
@with_appcontext
def admin_command():
    email = click.prompt('Email', default='admin@localhost')
    password = click.prompt('Password', hide_input=True)
    create_admin(email, password)
    click.echo('Admin was created')


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(db_command)
    app.cli.add_command(admin_command)
