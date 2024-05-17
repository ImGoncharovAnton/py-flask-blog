from flask import Blueprint, render_template

bp = Blueprint('page', __name__)


@bp.route('/about')
def about():
    return render_template('page/about.html')


@bp.route('/contact', methods=('GET', 'POST'))
def contact():
    return render_template('page/contact.html')
