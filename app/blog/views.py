from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app, abort

from app.blog.tags import create_tags, update_tags, get_tags, get_all_tags
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


@bp.route('/')
def posts():
    db = get_db()
    q = request.args.get('q')
    tag_name = request.args.get('tag')

    # Base query
    query = "SELECT * FROM posts WHERE publish <= ? AND publish != ''"
    count_query = query.replace('*', 'COUNT(*)')

    # Add search query
    if q:
        search_query = "(title LIKE ? OR body LIKE ?)"
        query += f" AND {search_query}"
        count_query += f" AND {search_query}"

    # Add tag filter query
    if tag_name:
        tag_filter_query = "id IN (SELECT post_id FROM tagged_items INNER JOIN tags ON tags.id = tag_id WHERE tags.name = ?)"
        query += f" AND {tag_filter_query}"
        count_query += f" AND {tag_filter_query}"

    # Query parameters
    now = datetime.now()
    params = [now]
    if q:
        params.extend([f"%{q}%", f"%{q}%"])
    if tag_name:
        params.append(tag_name)

    # Pagination
    page = int(request.args.get('page', 1))
    per_page = 2
    total_count = db.execute(count_query, params).fetchone()[0]
    paginate = pagination(total_count, page, per_page)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([paginate['per_page'], paginate['offset']])

    # Fetch posts
    posts_list = db.execute(query, params).fetchall()
    posts_list = [dict(post) for post in posts_list]

    # Fetch tags and comment counts for each post
    for post in posts_list:
        post_id = post['id']
        post['tags'] = get_tags(post_id)
        post['comment_count'] = db.execute(
            "SELECT COUNT(*) FROM comments WHERE post_id = ?", (post_id,)
        ).fetchone()[0]

    # Fetch all tags for display
    all_tags = db.execute("SELECT name FROM tags").fetchall()
    all_tags = [tag['name'] for tag in all_tags]

    return render_template('index.html', posts=posts_list, paginate=paginate, now=datetime.now().date(), all_tags=all_tags)


@bp.route('/tag/<tag_name>')
def posts_by_tag(tag_name):
    db = get_db()

    # Base query
    query = "SELECT * FROM posts WHERE publish <= ? AND publish != ''"
    count_query = query.replace('*', 'COUNT(*)')

    # Add tag filter query
    tag_filter_query = "id IN (SELECT post_id FROM tagged_items INNER JOIN tags ON tags.id = tag_id WHERE tags.name = ?)"
    query += f" AND {tag_filter_query}"
    count_query += f" AND {tag_filter_query}"

    # Query parameters
    now = datetime.now()
    params = [now, tag_name]

    # Pagination
    page = int(request.args.get('page', 1))
    per_page = 2
    total_count = db.execute(count_query, params).fetchone()[0]
    paginate = pagination(total_count, page, per_page)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([paginate['per_page'], paginate['offset']])

    # Fetch posts
    posts_list = db.execute(query, params).fetchall()
    posts_list = [dict(post) for post in posts_list]

    # Fetch tags and comment counts for each post
    for post in posts_list:
        post_id = post['id']
        post['tags'] = get_tags(post_id)
        post['comment_count'] = db.execute(
            "SELECT COUNT(*) FROM comments WHERE post_id = ?", (post_id,)
        ).fetchone()[0]

    # Fetch all tags for display
    all_tags = db.execute("SELECT name FROM tags").fetchall()
    all_tags = [tag['name'] for tag in all_tags]

    return render_template('index.html', posts=posts_list, paginate=paginate, now=datetime.now().date(), all_tags=all_tags)



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
