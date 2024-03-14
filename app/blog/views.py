from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app, abort

from app.blog.tags import create_tags, update_tags, get_tags
from app.blog.utils import slugify, pagination
from app.db import get_db
from app.users.views import login_required
from app.utils import form_errors, validate
from werkzeug.utils import secure_filename
from datetime import datetime

bp = Blueprint('blog', __name__)


def save_image(file):
    filename = secure_filename(file.filename)
    image_url = current_app.config['UPLOAD_FOLDER'] / filename
    file.save(image_url)
    return filename


@bp.route('/')
def posts():
    db = get_db()
    q = request.args.get('q')  # get url params
    search_query = f"""--sql
            (title LIKE '%{q}%' OR body LIKE '%{q}%')"""

    # Post queries
    query = """--sql
    SELECT * FROM posts WHERE publish <= '%s' AND publish != '' """ % datetime.now()
    count_query = query.replace('*', 'COUNT(*)')

    if q:  # modify queries for search
        query += f"""--sql
        AND {search_query}"""
        count_query += f"""--sql
        AND {search_query}"""

    # Admin query: Retrive all posts
    if g.user and g.user['is_admin']:
        query = """--sql
        SELECT * FROM posts """
        count_query = query.replace('*', 'COUNT(*)')
        if q:  # modify admin user post queries for search
            query += f"""--sql
            WHERE {search_query}"""
            count_query += f"""--sql
            WHERE {search_query}"""

    # Pagination
    page = request.args.get('page') or 1
    count = db.execute(count_query).fetchone()[0]
    paginate = pagination(count, int(page))

    query += """--sql
    ORDER BY id DESC LIMIT %s OFFSET %s""" % (paginate['per_page'], paginate['offset'])

    posts_list = db.execute(query).fetchall()
    return render_template('index.html', posts=posts_list, paginate=paginate, now=datetime.now().date())


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def post_create():
    if not g.user['is_admin']:
        abort(403)
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

            post_id = db.execute("""--sql
            SELECT id FROM posts WHERE slug=?""", (slug,)).fetchone()['id']

            create_tags(tags.replace(' ', '').split(','), post_id)
            flash('Post was created', category='success')
            return redirect(url_for('blog.post_detail', slug=slug))

        return render_template('blog/form.html', errors=errors, post=None, title='Create Post')

    return render_template('blog/form.html', errors=None, post=None, title='Create Post')


@bp.route('/<slug>')
def post_detail(slug):
    db = get_db()
    post = db.execute("""--sql
    SELECT * FROM posts WHERE slug = ?""", (slug,)).fetchone()
    if post is None:
        abort(404)  # resource not found
    tags = get_tags(post['id'])
    return render_template('blog/detail.html', post=post, tags=tags)


@bp.route('/<slug>/update', methods=['GET', 'POST'])
@login_required
def post_update(slug):
    if not g.user['is_admin']:
        abort(403)
    db = get_db()
    post = db.execute("""--sql
    SELECT * FROM posts WHERE slug = ?""", (slug,)).fetchone()

    tags = get_tags(post['id'])

    if request.method == 'POST':
        title = request.form['title']
        new_slug = slugify(title)
        image = request.files['image']
        body = request.form['body']
        publish = request.form['publish']
        tags = request.form['tags']
        user_id = g.user['id']

        # handle errors
        error_fields = form_errors('title', 'body', 'tags')
        errors = validate(error_fields, title, body, tags)

        if title and body and tags:

            if image:
                filename = save_image(image)
                db.execute("""--sql
                UPDATE posts SET image = ? WHERE slug = ?""", (filename, slug))

            # update post
            query = """--sql
            UPDATE posts SET title = '%s', slug = '%s', body = '%s',  publish = '%s'
            WHERE slug = '%s'
            """ % (title, new_slug, body, publish, slug)
            db.execute(query)
            db.commit()

            update_tags(tags.replace(' ', '').split(','), post['id'])

            flash('Post was updated', category='success')
            return redirect(url_for('blog.post_detail', slug=new_slug))

        return render_template('blog/form.html', errors=errors, post=post, tags=tags, title='Edit Post')

    return render_template('blog/form.html', errors=None, post=post, tags=tags, title='Edit Post')


@bp.route('/<slug>/delete')
def delete_post(slug):
    if not g.user['is_admin']:
        abort(403)
    db = get_db()
    db.execute("""--sql
    DELETE FROM posts WHERE slug = ?""", (slug,))
    flash('Post was deleted', category='danger')
    return redirect(url_for('blog.posts'))
