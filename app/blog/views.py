from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app, abort

from app.blog.tags import create_tags, update_tags, get_tags
from app.blog.utils import slugify, pagination
from app.db import get_db
from app.users.views import login_required
from app.utils import form_errors, validate
from werkzeug.utils import secure_filename
from datetime import datetime
import markdown

bp = Blueprint('blog', __name__)


def save_image(file):
    filename = secure_filename(file.filename)
    image_url = current_app.config['UPLOAD_FOLDER'] / filename
    file.save(image_url)
    return filename


@bp.app_template_filter('markdown')
def convert_markdown(content):
    return markdown.markdown(content)


@bp.app_template_filter('dateformat')
def dateformat(date):
    return date.strftime('%a %d, %B %Y')


# @bp.route('/')
# def posts():
#     db = get_db()
#     q = request.args.get('q')  # get url params
#     search_query = f"""--sql
#             (title LIKE '%{q}%' OR body LIKE '%{q}%')"""
#
#     # Post queries
#     query = """--sql
#     SELECT * FROM posts WHERE publish <= '%s' AND publish != '' """ % datetime.now()
#     count_query = query.replace('*', 'COUNT(*)')
#
#     if q:  # modify queries for search
#         query += f"""--sql
#         AND {search_query}"""
#         count_query += f"""--sql
#         AND {search_query}"""
#
#     # Admin query: Retrive all posts
#     if g.user and g.user['is_admin']:
#         query = """--sql
#         SELECT * FROM posts """
#         count_query = query.replace('*', 'COUNT(*)')
#         if q:  # modify admin user post queries for search
#             query += f"""--sql
#             WHERE {search_query}"""
#             count_query += f"""--sql
#             WHERE {search_query}"""
#
#     # Pagination
#     page = request.args.get('page') or 1
#     count = db.execute(count_query).fetchone()[0]
#     paginate = pagination(count, int(page))
#
#     query += """--sql
#     ORDER BY id DESC LIMIT %s OFFSET %s""" % (paginate['per_page'], paginate['offset'])
#
#     posts_list = db.execute(query).fetchall()
#     return render_template('index.html', posts=posts_list, paginate=paginate, now=datetime.now().date())


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

    # Admin query: Retrieve all posts
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

    # Convert sqlite3.Row objects to dictionaries
    posts_list = [dict(post) for post in posts_list]

    # Fetch tags and comments count for each post
    for post in posts_list:
        post_id = post['id']
        post['tags'] = get_tags(post_id)
        post['comment_count'] = db.execute("""
            SELECT COUNT(*) 
            FROM comments 
            WHERE post_id = ?
        """, (post_id,)).fetchone()[0]

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


@bp.route('/<slug>', methods=['GET', 'POST'])
def post_detail(slug):
    db = get_db()
    post = db.execute("""--sql
    SELECT * FROM posts WHERE slug = ?""", (slug,)).fetchone()

    if post is None:
        abort(404)  # resource not found

    if request.method == 'POST' and g.user:
        comment_body = request.form['comment']
        print(comment_body)
        if comment_body:
            db.execute("INSERT INTO comments (body, user_id, post_id) VALUES (?, ?, ?)",
                       (comment_body, g.user['id'], post['id']))
            db.commit()
            flash('Your comment was created', category='success')
            return redirect(url_for('blog.post_detail', slug=slug))

    comments = db.execute("""SELECT comments.*, users.username FROM comments 
                                 JOIN users ON comments.user_id = users.id 
                                 WHERE post_id = ? ORDER BY created DESC""",
                          (post['id'],)).fetchall()

    tags = get_tags(post['id'])
    return render_template('blog/detail.html', post=post, tags=tags, comments=comments)


@bp.route('/edit_comment/<int:comment_id>', methods=['GET', 'POST'])
def edit_comment(comment_id):
    db = get_db()
    comment = db.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()

    if comment is None or (comment['user_id'] != g.user['id'] and not g.user['is_admin']):
        abort(403)  # permission denied

    if request.method == 'POST':
        new_body = request.form['comment']
        slug = request.form['slug']
        db.execute("UPDATE comments SET body = ?, updated = CURRENT_TIMESTAMP WHERE id = ?", (new_body, comment_id))
        db.commit()
        flash('Your comment was updated', category='success')
        return redirect(url_for('blog.post_detail', slug=slug))

    post = db.execute("SELECT slug FROM posts WHERE id = ?", (comment['post_id'],)).fetchone()
    return render_template('blog/edit_comment.html', comment=comment, slug=post['slug'])


@bp.route('/delete_comment/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    db = get_db()
    comment = db.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()

    if comment is None or (comment['user_id'] != g.user['id'] and not g.user['is_admin']):
        abort(403)  # permission denied

    db.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    db.commit()
    flash('Your comment was deleted', category='danger')
    return redirect(url_for('blog.post_detail', slug=request.form['slug']))


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
    db.commit()
    flash('Post was deleted', category='danger')
    return redirect(url_for('blog.posts'))
