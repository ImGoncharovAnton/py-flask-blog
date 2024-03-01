from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE='db.sqlite3',
        SECRET_KEY='Development key',
        UPLOAD_FOLDER='uploads'
    )

    from app.users.views import bp as user_bp
    app.register_blueprint(user_bp)

    from app.blog.views import bp as blog_bp
    app.register_blueprint(blog_bp)

    from app import db
    db.init_app(app)

    return app
