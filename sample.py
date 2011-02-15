#!/usr/bin/python

import cgi
import logging
import urllib2

from django.utils import simplejson

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
            
# prod
config = {'server':'https://foursquare.com',
          'api_server':'https://api.foursquare.com',
          'redirect_uri': 'http://4sq-push-api-sample.appspot.com/oauth',
          'client_id': 'YOUR ID HERE',
          'client_secret': 'YOUR SECRET'}

class UserToken(db.Model):
  """Contains the user to foursquare_id + oauth token mapping."""
  user = db.UserProperty()
  fs_id = db.StringProperty()
  token = db.StringProperty()

class Checkin(db.Model):
  """A very simple checkin object, with a denormalized userid for querying."""
  fs_id = db.StringProperty()
  checkin_json = db.TextProperty()

def fetchJson(url):
  """Does a GET to the specified URL and returns a dict representing its reply."""
  logging.info('fetching url: ' + url)
  result = urllib2.urlopen(url).read()
  logging.info('got back: ' + result)
  return simplejson.loads(result)

class OAuth(webapp.RequestHandler):
  """Handle the OAuth redirect back to the service."""
  def post(self):
    self.get()

  def get(self):
    code = self.request.get('code')
    args = dict(config)
    args['code'] = code
    url = ('%(server)s/oauth2/access_token?client_id=%(client_id)s&client_secret=%(client_secret)s&grant_type=authorization_code&redirect_uri=%(redirect_uri)s&code=%(code)s' % args)
  
    json = fetchJson(url)

    token = UserToken()
    token.token = json['access_token']
    token.user = users.get_current_user()

    self_response = fetchJson('%s/v2/users/self?oauth_token=%s' % (config['api_server'], token.token))

    token.fs_id = self_response['response']['user']['id']
    token.put()

    self.redirect("/")

class ReceiveCheckin(webapp.RequestHandler):
  """Received a pushed checkin and store it in the datastore."""
  def post(self):
    json = simplejson.loads(self.request.body)
    checkin_json = json['checkin']
    user_json = json['user']
    checkin = Checkin()
    checkin.fs_id = user_json['id']
    checkin.checkin_json = simplejson.dumps(checkin_json)
    checkin.put()

class FetchCheckins(webapp.RequestHandler):
  """Fetch the checkins we've received via push for the current user."""
  def get(self):
    user = UserToken.all().filter("user = ", users.get_current_user()).get()
    ret = []
    if user:
      checkins = Checkin.all().filter("fs_id = ", user.fs_id).fetch(1000)
      ret = [c.checkin_json for c in checkins]
    self.response.out.write('['+ (','.join(ret)) +']')

class GetConfig(webapp.RequestHandler):
  """Returns the OAuth URI as JSON so the constants aren't in two places."""
  def get(self):
    uri = '%(server)s/oauth2/authenticate?client_id=%(client_id)s&response_type=code&redirect_uri=%(redirect_uri)s' % config
    self.response.out.write(simplejson.dumps({'auth_uri': uri}))

application = webapp.WSGIApplication([('/oauth', OAuth), 
                                      ('/checkin', ReceiveCheckin),
                                      ('/fetch', FetchCheckins),
                                      ('/config', GetConfig)],
                                     debug=True)

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
