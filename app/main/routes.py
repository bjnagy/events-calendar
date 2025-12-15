from flask import render_template, flash, redirect, url_for, request, current_app
from flask_login import current_user, login_required
from app import db
from app.main.forms import EditProfileForm, EmptyForm, EventForm
from app.models import User, Event
import sqlalchemy as sa
from datetime import datetime, timezone
from app.main import bp
from app.time import local_to_utc

@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()

@bp.route('/feed', methods=['GET', 'POST'])
@login_required
def feed():
    form = EventForm()
    if form.validate_on_submit():
        form_data_dict = form.data
        
        form_data_dict.pop('csrf_token', None)
        form_data_dict.pop('submit', None)

        # if hasattr(form, "coords"):
        #     form_data_dict['coords'] = form.coords

        # if not form_data_dict['starts_at_time']:
        #     form_data_dict['starts_at_time'] = datetime.min.time()
        # form_data_dict['starts_at'] = local_to_utc(datetime.combine(form_data_dict['starts_at_date'], form_data_dict['starts_at_time']), form_data_dict['timezone'])
        # form_data_dict.pop('starts_at_date')
        # form_data_dict.pop('starts_at_time')

        # if form_data_dict['ends_at_date']:
        #     if not form_data_dict['ends_at_time']:
        #         form_data_dict['ends_at_time'] = datetime.max.time()
        #     form_data_dict['ends_at'] = local_to_utc(datetime.combine(form_data_dict['ends_at_date'], form_data_dict['ends_at_time']), form_data_dict['timezone'])
        # form_data_dict.pop('ends_at_date')
        # form_data_dict.pop('ends_at_time')
        # form_data_dict.pop('timezone')

        event = Event(owner=current_user)
        event.from_dict(form_data_dict)
        db.session.add(event)
        db.session.commit()
        flash('Your event is now live!')
        return redirect(url_for('main.feed'))
    page = request.args.get('page', 1, type=int)
    events = db.paginate(current_user.following_events(), page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('main.feed', page=events.next_num) \
        if events.has_next else None
    prev_url = url_for('main.feed', page=events.prev_num) \
        if events.has_prev else None
    return render_template('feed.html', title='Feed', form=form,
                        events=events.items, next_url=next_url,
                        prev_url=prev_url)

@bp.route('/user/<username>')
#@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    page = request.args.get('page', 1, type=int)
    query = user.events.select().order_by(Event.timestamp.asc())
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
            return redirect(url_for('main.explore'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(url_for('main.user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(f'You are following {username}!')
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.explore'))


@bp.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('main.feed'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(url_for('main.user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f'You are not following {username}.')
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.feed'))

@bp.route('/', methods=['GET'])
@bp.route('/explore', methods=['GET'])
#@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Event).order_by(Event.starts_at.asc())
    events = db.paginate(query, page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('main.explore', page=events.next_num) \
        if events.has_next else None
    prev_url = url_for('main.explore', page=events.prev_num) \
        if events.has_prev else None
    return render_template("feed.html", title='Explore', events=events.items, next_url=next_url, prev_url=prev_url)
