from flask import render_template, flash, redirect, url_for, request, current_app
from flask_login import current_user, login_required
from app import db
from app.main.forms import EditProfileForm, EmptyForm, EventForm
from app.models import User, Event
import sqlalchemy as sa
from datetime import datetime, timezone
from app.main import bp

@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = EventForm()
    #print(request.form)
    if form.validate_on_submit():
        event = Event(title=form.title.data, description=form.description.data, start_date=form.start_date.data, start_time=form.start_time.data, end_date=form.end_date.data, end_time=form.end_time.data, author=current_user)
        db.session.add(event)
        db.session.commit()
        flash('Your event is now live!')
        return redirect(url_for('main.index'))
    page = request.args.get('page', 1, type=int)
    events = db.paginate(current_user.following_events(), page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('main.index', page=events.next_num) \
        if events.has_next else None
    prev_url = url_for('main.index', page=events.prev_num) \
        if events.has_prev else None
    return render_template('index.html', title='Home', form=form,
                        events=events.items, next_url=next_url,
                        prev_url=prev_url)

@bp.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    page = request.args.get('page', 1, type=int)
    query = user.events.select().order_by(Event.timestamp.desc())
    events = db.paginate(query, page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'],
                        error_out=False)
    next_url = url_for('main.user', username=user.username, page=events.next_num) \
        if events.has_next else None
    prev_url = url_for('main.user', username=user.username, page=events.prev_num) \
        if events.has_prev else None
    form = EmptyForm()
    return render_template('user.html', user=user, events=events.items,
                           next_url=next_url, prev_url=prev_url, form=form)


@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile',
                           form=form)


@bp.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('main.index'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(url_for('main.user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(f'You are following {username}!')
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))


@bp.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('main.index'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(url_for('main.user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f'You are not following {username}.')
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))
    
@bp.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Event).order_by(Event.timestamp.desc())
    events = db.paginate(query, page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    return render_template("index.html", title='Explore', events=events.items)
