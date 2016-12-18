from flask import Flask, render_template, request, redirect
from flask import url_for, jsonify, flash
from flask import session as login_session
import random
import string
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from database_setup import Category, Item, Base

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Catalog app"

engine = create_engine("sqlite:///catalog.db")
Base.metadata.bind = engine


DBSession = sessionmaker(bind=engine)
session = DBSession()

# Create anti-forgery state token


@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps(
            'Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius:150px;'
    '-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output

    # DISCONNECT - Revoke a current user's token and reset their login_session


@app.route('/gdisconnect')
def gdisconnect():
    '''Logout view'''
    access_token = login_session['access_token']
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps(
            'Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/'
    'revoke?token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:

        response = make_response(json.dumps(
            'Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


@app.route('/')
@app.route('/catalog')
def Home():
    '''Default view'''
    categories = session.query(Category).all()
    recent_items = session.query(Item).order_by("date_added desc").all()[:10]
    if 'username' not in login_session:
        return render_template('home.html', categories=categories,
                               recent_items=recent_items)
    else:
        return render_template('home.html', login=True,
                               categories=categories,
                               recent_items=recent_items)


@app.route('/catalog/newcat/', methods=['GET', 'POST'])
def newCategory():
    '''Create a new category'''
    if 'username' not in login_session:
        return redirect('/login')
    else:
        if request.method == 'POST':
            newCategory = Category(name=request.form['name'])
            session.add(newCategory)
            session.commit()
            return redirect(url_for('Home'))
        else:
            return render_template('new_category.html')


@app.route('/catalog/newitem/', methods=['GET', 'POST'])
def newItem():
    '''Add new item to database'''
    if 'username' not in login_session:
        return redirect('/login')
    else:
        if request.method == 'POST':
            name = request.form['name']
            description = request.form['description']
            category = request.form['category']
            print category
            newItem = Item(name=name, description=description,
                           author=login_session['username'], category_id=int(category))
            session.add(newItem)
            session.commit()
            return redirect(url_for('Home'))
        else:
            categories = session.query(Category).all()
            return render_template('new_item.html', categories=categories)


@app.route('/catalog/<string:category>/items/')
def categoryView(category):
    ''' View with category and all its items'''
    categories = session.query(Category).all()
    cat_id = session.query(Category).filter_by(name=category).one().id
    items = session.query(Item).filter_by(category_id=cat_id)
    if 'username' not in login_session:
        return render_template('category.html',
                               items=items, categories=categories)
    else:
        return render_template('category.html',
                               login=True, items=items, categories=categories)


@app.route('/catalog/<string:category>/<string:item>/')
def itemView(category, item):
    '''A detailed item view'''
    cat_id = session.query(Category).filter_by(name=category).one().id
    item = session.query(Item).filter_by(category_id=cat_id, name=item).one()

    if 'username' not in login_session:
        return render_template('item.html', item=item, category=category)
    else:
        return render_template('item.html', login=True,
                               item=item, category=category)


@app.route('/catalog/<string:category>/<string:item>/edit',
           methods=['GET', 'POST'])
def editItem(category, item):
    '''Edit item in database'''
    if 'username' not in login_session:
        return redirect('/login')
    else:
        cat_id = session.query(Category).filter_by(name=category).one().id
        edit_item = session.query(Item).filter_by(
            category_id=cat_id, name=item).one()
        if request.method == 'POST' and edit_item.author == login_session['username']:
            name = request.form['name']
            description = request.form['description']
            category = request.form['category']

            edit_item.name = name
            edit_item.description = description
            edit_item.category_id = int(category)
            session.commit()
            return redirect(url_for('Home'))
        elif edit_item.author == login_session['username']:
            categories = session.query(Category).all()
            return render_template('edit_item.html', item=edit_item,
                                   categories=categories)
        else:
            return "You are not the author!"


@app.route('/catalog/<string:category>/<string:item>/delete',
           methods=['GET', 'POST'])
def deleteItem(category, item):
    '''Deletes a item from the database'''
    if 'username' not in login_session:
        return redirect('/login')
    else:
        cat_id = session.query(Category).filter_by(name=category).one().id
        item_del = session.query(Item).filter_by(
            name=item, category_id=cat_id).one()
        if request.method == 'POST' and item_del.author == login_session['username']:
            item_del = session.query(Item).filter_by(
                name=item, category_id=cat_id).delete()
            return redirect(url_for('Home'))

        elif item_del.author == login_session['username']:
            return render_template('delete.html', category=category, item=item)
        else:
            return "You are not the author!"


@app.route('/category/JSON')
def jsonData():
    '''Return JSON for all categories'''
    categories = session.query(Category).all()
    return jsonify(categories=[c.serialize for c in categories])


@app.route('/category/<string:category>/JSON')
def categoryItemData(category):
    '''Return JSON of all the items for a category'''
    cat_id = session.query(Category).filter_by(name=category).one().id
    items = session.query(Item).filter_by(category_id=cat_id).all()
    return jsonify(Items=[i.serialize for i in items])


@app.route('/category/<string:category>/<string:item>/JSON')
def itemJSON(category, item):
    '''Return JSON for an item'''
    cat_id = session.query(Category).filter_by(name=category).one().id
    item = session.query(Item).filter_by(name=item, category_id=cat_id).one()
    return jsonify(item=item.serialize)


if __name__ == '__main__':
    app.secret_key = 'akshay_dahiya'
    app.debug = True
app.run(host='0.0.0.0', port=5000)
