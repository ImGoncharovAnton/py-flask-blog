from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app

from app.blog.utils import slugify
from app.db import get_db
from app.users.views import login_required
from app.utils import form_errors, validate
from werkzeug.utils import secure_filename

bp = Blueprint('blog', __name__)


def save_image(file):
    filename = secure_filename(file.filename)
    image_url = current_app.config['UPLOAD_FOLDER'] / filename
    file.save(image_url)
    return filename


@bp.route('/')
def posts():
    db = get_db()
    posts_list = db.execute("""--sql
    SELECT * FROM posts""").fetchall()
    return render_template('index.html', posts=posts_list)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def post_create():
    if request.method == 'POST':
        title = request.form['title']
        slug = slugify(title)
        image = request.files['image']
        body = request.form['body']
        publish = request.form['publish']
        tags = request.form['tags']
        user_id = g.user['id']

        # handle errors
        error_fields = form_errors('title', 'body', 'image', 'tags')
        errors = validate(error_fields, title, body, image, tags)

        if title and body and tags and image:
            db = get_db()
            filename = save_image(image)
            # create post
            query = """--sql
                      INSERT INTO posts (title, image, slug, body, publish, user_id) 
                      VALUES ('%s', '%s', '%s', '%s', '%s', %s)""" % (
                title, filename, slug, body, publish, user_id)
            db.execute(query)
            db.commit()
            flash('Post was created', category='success')
            return redirect(url_for('blog.post_detail', slug=slug))

        return render_template('blog/form.html', errors=errors, post=None, title='Create Post')

    return render_template('blog/form.html', errors=None, post=None, title='Create Post')


@bp.route('/<slug>')
def post_detail(slug):
    db = get_db()
    post = db.execute("""--sql
    SELECT * FROM posts WHERE slug = ?""", (slug,)).fetchone()
    return render_template('blog/detail.html', post=post)


@bp.route('/<slug>/update', methods=['GET', 'POST'])
@login_required
def post_update(slug):
    db = get_db()
    post = db.execute("""--sql
    SELECT * FROM posts WHERE slug = ?""", (slug,)).fetchone()
    if request.method == 'POST':
        title = request.form['title']
        slug = slugify(title)
        image = request.files['image']
        body = request.form['body']
        publish = request.form['publish']
        tags = request.form['tags']
        user_id = g.user['id']

        # handle errors
        error_fields = form_errors('title', 'body', 'image', 'tags')
        errors = validate(error_fields, title, body, image, tags)

        if title and body and tags:

            if image:
                filename = save_image(image)
                db.execute("""--sql
                UPDATE posts SET image = ? WHERE slug = ?""", (filename, slug))

            # update post
            query = """--sql
            UPDATE posts SET title = '%s', slug = '%s', body = '%s',  publish = '%s'
            WHERE slug = '%s'
            """ % (title, slug, body, publish, user_id)
            db.execute(query)
            db.commit()
            flash('Post was updated', category='success')
            return redirect(url_for('blog.detail'))

        return render_template('blog/form.html', errors=errors, title='Edit Post')

    return render_template('blog/form.html', errors=None, post=post, title='Edit Post')


@bp.route('/<slug>/delete')
def delete_post(slug):
    db = get_db()
    db.execute("""--sql
    DELETE FROM posts WHERE slug = ?""", (slug,))
    flash('Post was deleted', category='danger')
    return redirect(url_for('blog.posts'))
