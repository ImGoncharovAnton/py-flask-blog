from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE='db.sqlite3',
        SECRET_KEY='Development key',
        UPLOAD_FOLDER='uploads'
    )

    from app import db
    db.init_app(app)

    return app
