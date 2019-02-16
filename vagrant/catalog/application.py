from flask import Flask, render_template, request
from flask import redirect, jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, PawnShop, Valuable, User
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)
CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Pawn Shop Application"

# Connect to Database and create database session
engine = create_engine('sqlite:///pawnshopvaluables.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()


@app.route('/login')
def showLogin():
    # Create anti-forgery state token
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


# Connect with Google Oauth #
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
        print ("Token's client ID does not match applications.")
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200)
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

    # see if user exists, if not create new user
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius:' \
              '150px;-webkit-border-radius: 150px;-moz-border-radius:' \
              '150px;"> '
    flash("You are now logged in! Hello %s!" % login_session['username'],
          'success')
    return output


# DISCONNECT - Revoke a current user's token and reset their login_session
@app.route('/gdisconnect')
def gdisconnect():
        # Only disconnect a connected user.
    access_token = login_session.get('access_token')
    print(access_token)
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' \
          % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        # Reset the user's sesson.
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']

        response = make_response(json.dumps(
            'Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        flash("You have logged out.", 'success')
        return redirect(url_for('showPawnShops'))
    else:
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


# USER Functions
def createUser(login_session):
    "Create a new user"
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    "Get user inforamtion by `user_id`"
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    "Get user user_id by an email"
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# JSON APIs
@app.route('/pawnshops/<int:pawnshop_id>/valuables/JSON')
def pawnShopValuablesJSON(pawnshop_id):
    """Return JSON for each valuable in Pawn Shop"""
    items = session.query(Valuable).filter_by(
        pawnshop_id=pawnshop_id).all()
    return jsonify(valuables=[i.serialize for i in items])


@app.route('/pawnshops/<int:pawnshop_id>/valuables/<int:valuable_id>/JSON')
def valuableJSON(pawnshop_id, valuable_id):
    """Return JSON of a valuable in Pawn Shop"""
    valuable = session.query(Valuable).filter_by(id=valuable_id).one()
    return jsonify(valuable=valuable.serialize)


@app.route('/pawnshops/JSON')
def pawnshopsJSON():
    """return JSON of all Pawn Shop"""
    pawnshops = session.query(PawnShop).all()
    return jsonify(pawnshops=[r.serialize for r in pawnshops])


#  CREATE
@app.route('/pawnshops/new/', methods=['GET', 'POST'])
def newPawnShop():
    "Function for logged in user to create a new pawn shop"
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        newPawnShop = PawnShop(
            name=request.form['name'], user_id=login_session['user_id'])
        session.add(newPawnShop)
        flash('New Pawn Shop %s Successfully Created' % newPawnShop.name)
        session.commit()
        return redirect(url_for('showPawnShops'))
    else:
        return render_template('newpawnshop.html')


@app.route('/pawnshops/<int:pawnshop_id>/valuables/new/',
           methods=['GET', 'POST'])
def newValuable(pawnshop_id):
    if 'username' not in login_session:
        return redirect('/login')
    pawnshop = session.query(PawnShop).filter_by(id=pawnshop_id).one()
    if login_session['user_id'] != pawnshop.user_id:
        return "<script>function myFunction() {alert(" \
               "'You are not authorized to add to this pawn shop. " \
               "Please create your own pawn shop in order to add valuable.')" \
               ";}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        newValuable = Valuable(name=request.form['name'],
                               description=request.form['description'],
                               price=request.form['price'],
                               pawnshop_id=pawnshop_id,
                               user_id=pawnshop.user_id)
        session.add(newValuable)
        session.commit()
        flash('New Valuable %s Successfully Created' % (newValuable.name))
        return redirect(url_for('showValuables', pawnshop_id=pawnshop_id))
    else:
        return render_template('newvaluable.html', pawnshop_id=pawnshop_id)


# READ
@app.route('/')
@app.route('/pawnshops/')
def showPawnShops():
    """Returns JSON of all pawnshops"""
    pawnshops = session.query(PawnShop).order_by(asc(PawnShop.name))
    return render_template('pawnshops.html', pawnshops=pawnshops)


@app.route('/pawnshops/<int:pawnshop_id>/')
@app.route('/pawnshops/<int:pawnshop_id>/valuables/')
def showValuables(pawnshop_id):
    "show all valuables of pawn shop"
    pawnshop = session.query(PawnShop).filter_by(
        id=pawnshop_id).one()
    creator = getUserInfo(pawnshop.user_id)
    valuables = session.query(Valuable).filter_by(
        pawnshop_id=pawnshop_id).all()
    return render_template('valuables.html', valuables=valuables,
                           pawnshop=pawnshop, creator=creator)


# UPDATE
@app.route('/pawnshops/<int:pawnshop_id>/edit/', methods=['GET', 'POST'])
def editPawnShop(pawnshop_id):
    "edit the name of pawn shop with `pawn_shop`"
    editedPawnShop = session.query(
        PawnShop).filter_by(id=pawnshop_id).one()
    if 'username' not in login_session:
        return redirect('/login')
    if editedPawnShop.user_id != login_session['user_id']:
        return "<script>function myFunction() {" \
               "alert('You are not authorized to edit this pawnshop. " \
               "Please create your own pawnshop in order to edit.');}" \
               "</script><body onload='myFunction()''>"
    if request.method == 'POST':
        editedPawnShop.name = request.form['name']
        flash('Pawn Shop Successfully Edited %s' % editedPawnShop.name)
        return redirect(url_for('showPawnShops'))
    else:
        return render_template('editpawnshop.html', pawnshop=editedPawnShop)


@app.route('/pawnshops/<int:pawnshop_id>/valuables/<int:valuable_id>/edit',
           methods=['GET', 'POST'])
def editValuable(pawnshop_id, valuable_id):
    "edit valuable "
    if 'username' not in login_session:
        return redirect('/login')
    editedValuable = session.query(Valuable).filter_by(id=valuable_id).one()
    pawnshop = session.query(PawnShop).filter_by(id=pawnshop_id).one()
    if login_session['user_id'] != pawnshop.user_id:
        return "<script>function myFunction() {alert(" \
               "'You are not authorized to edit this pawnshop."\
               "Please create your own pawnshop in order to edit.');}"\
               "</script><body onload='myFunction()''>"

    if request.method == 'POST':
        if request.form['name']:
            editedValuable.name = request.form['name']
        if request.form['description']:
            editedValuable.description = request.form['description']
        if request.form['price']:
            editedValuable.price = request.form['price']
        session.add(editedValuable)
        session.commit()
        flash('Valuable Successfully Edited')
        return redirect(url_for('showValuables', pawnshop_id=pawnshop_id))
    else:
        return render_template('editvaluable.html', pawnshop_id=pawnshop_id,
                               valuable_id=valuable_id, valuable=editedValuable)


# DELETE
@app.route('/pawnshops/<int:pawnshop_id>/delete/',
           methods=['GET', 'POST'])
def deletePawnShop(pawnshop_id):
    "Delete a pawn shop with `pawnshop_id`"
    pawnshopToDelete = session.query(PawnShop).filter_by(
        id=pawnshop_id).one()
    if 'username' not in login_session:
        return redirect('/login')
    if pawnshopToDelete.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert(" \
               "'You are not authorized to delete this pawnshop. "\
               "Please create your own pawnshop to delete from.'" \
               ");}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        session.delete(pawnshopToDelete)
        flash('%s Successfully Deleted' % pawnshopToDelete.name)
        session.commit()
        return redirect(url_for('showPawnShops'))
    else:
        return render_template('deletepawnshop.html',
                               pawnshop=pawnshopToDelete)


@app.route('/pawnshops/<int:pawnshop_id>/valuables/<int:valuable_id>/delete',
           methods=['GET', 'POST'])
def deleteValuable(pawnshop_id, valuable_id):
    "Delete a valuable with `valuable_id` from pawn shop `panwshop_id`"
    if 'username' not in login_session:
        return redirect('/login')
    pawnshop = session.query(PawnShop).filter_by(id=pawnshop_id).one()
    valuableToDelete = session.query(Valuable).filter_by(
        id=valuable_id).one()
    if login_session['user_id'] != pawnshop.user_id:
        return "<script>function myFunction() {alert(" \
               "'You are not authorized to delete from this pawnshop."\
               "Please create your own pawnshop to delete from.'" \
               ");} </script><body onload='myFunction()''>"
    if request.method == 'POST':
        session.delete(valuableToDelete)
        session.commit()
        flash('Menu Item Successfully Deleted')
        return redirect(url_for('showValuables',
                                pawnshop_id=pawnshop_id))
    else:
        return render_template('deletevaluable.html',
                               valuable=valuableToDelete)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000, threaded=False)
