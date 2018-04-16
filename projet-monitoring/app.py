#! /usr/bin/python3.5
# -*- coding:utf-8 -*-

########## Importation ##########

from flask import Flask, render_template, url_for, redirect, request, g, session
from apscheduler.schedulers.background import BackgroundScheduler 
from apscheduler.triggers.interval import IntervalTrigger 
from passlib.hash import argon2 
import atexit 
import requests 
import datetime
import mysql.connector 

########## Def ##########

app = Flask(__name__)
app.config.from_object('config')
app.config.from_object('secret_config')

def connect_db():
    g.mysql_connection = mysql.connector.connect(
        host = app.config['DATABASE_HOST'],
        user = app.config['DATABASE_USER'],
        password = app.config['DATABASE_PASSWORD'],
        database = app.config['DATABASE_NAME']
    ) 
    g.mysql_cursor = g.mysql_connection.cursor()
    return g.mysql_cursor

def get_db():
    if not hasattr(g, 'db'):
        g.db = connect_db()
    return g.db 

def commit():
    g.mysql_connection.commit()
    

def all_status():
    with app.app_context():
        db = get_db()
        db.execute('SELECT id, url_web FROM link')
        link = db.fetchall()
        f = '%Y-%m-%d %H:%M:%S'
        for links in link:
            id = links[0]
            url_web = links[1]
            status = know_status(url_web)
            test_date = datetime.datetime.now()
            date = test_date.strftime(f)
            db = get_db()
            db.execute('INSERT INTO history (id_web, request_response, date_last_request) VALUES (%(id)s, %(status)s, %(date_request)s)', {'id':id, 'status': status, 'date_request':date})
        commit()

def know_status(url_web):
    status_code = 999
    try:
        r = requests.get(url_web, timeout=2)
        r.raise_for_status()
        status_code = r.status_code
    except requests.exceptions.HTTPError as errh:
        status_code = r.status_code
    except requests.exceptions.ConnectionError as errc:
        pass
    except requests.exceptions.Timeout as errt:
        pass
    except requests.exceptions.RequestException as err:
        pass
    return str(status_code)


########## Scheduler ##########

scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(
    func = all_status,
    trigger = IntervalTrigger(seconds=60),
    id='all_status',
    name='Ajout du satus',
    replace_existing = True)
atexit.register(lambda: scheduler.shutdown())

########## Routes ##########

@app.route('/')
def index():
    db = get_db()
    db.execute('SELECT l.id, l.url_web, h.request_response FROM link l, history h WHERE l.id = h.id_web and h.date_last_request=(SELECT MAX(date_last_request) FROM history hi WHERE hi.id_web = l.id) GROUP BY l.id, l.url_web, h.request_response')
    link = db.fetchall()
    return render_template("index.html", link=link)

@app.route('/login/', methods=['GET', 'POST'])
def login():
    email = str(request.form.get('email'))
    password = str(request.form.get('password'))

    db = get_db()
    db.execute('SELECT email, password, is_admin FROM user WHERE email = %(email)s', {'email': email})
    users = db.fetchall()

    valid_user = False
    for user in users:
        if argon2.verify(password, user[1]):
            valid_user = user

    if valid_user:
        session['user'] = valid_user
        return redirect(url_for('admin'))

    return render_template('login.html')

@app.route('/admin/')
def admin():
    db = get_db()
    db.execute('SELECT id, url_web FROM link')
    link = db.fetchall
    if not session.get('user') or not session.get('user')[2]:
        return redirect(url_for('login'))
    return render_template('admin.html', user=session['user'], link=link)

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if not session.get('user') or not session.get('user')[2]:
        return redirect(url_for('login'))
    db = get_db()

    if request.method == 'POST':
        page = str(request.form.get('Page'))
        db.execute('UPDATE link SET url_web = %(page)s WHERE id = %(id)s', {'page': page, 'id': id})
        commit()
        return render_template('admin.html', user=session['user'])

    else:
        db.execute('SELECT id, url_web FROM link WHERE id = %(id)s', {'id': id})
        link = db.fetchone()
        return render_template('admin_edit.html', user=session['user'], link=link)


@app.route('/history/<int:id>')
def history (id):
    db = get_db()
    db.execute('SELECT l.url_web, h.request_response, h.date_last_request FROM link l, history h WHERE l.id = h.id_web AND l.id = %(id)s ORDER BY date_last_request DESC', {'id': id})
    history=db.fetchall()
    return render_template("history.html", history = history)

@app.route('/admin/add', methods=['GET', 'POST'])
def admin_add():
    if not session.get('user') or not session.get('user')[2]:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        page = str(request.form.get('Page'))
        db = get_db()
        db.execute('INSERT INTO link (url_web) VALUES (%(page)s)', {'page': page})
        commit()
        return redirect(url_for('admin'))

    return render_template('admin_add.html')

@app.route('/admin/delete/<int:id>', methods=['GET', 'POST'])
def delete(id):
    if not session.get('user') or not session.get('user')[2]:
        return redirect(url_for('login'))
    db = get_db()

    if request.method == 'POST':
        db.execute('DELETE FROM link WHERE id = %(id)s', {'id': id})
        commit()
        return redirect(url_for('admin'))

    else:
        db.execute('SELECT id, url_web FROM link WHERE id = %(id)s', {'id': id})
        link = db.fetchone()
        return render_template('admin_del.html', user=session['user'], link=link)
    
@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
