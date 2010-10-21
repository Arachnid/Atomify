from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.ext.deferred import defer
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
import logging
import os
import time
import urllib

import models


class BaseHandler(webapp.RequestHandler):
  def initialize(self, request, response):
    super(BaseHandler, self).initialize(request, response)
    self.user = users.get_current_user()

  def render_template(self, name, template_args):
    if self.user:
      login_url = users.create_logout_url('/')
    else:
      login_url = users.create_login_url('/')
    template_args.update({
        'user': self.user,
        'login_url': login_url
    })
    path = os.path.join(os.path.dirname(__file__), 'templates', name)
    self.response.out.write(template.render(path, template_args))


class EmailHandler(webapp.RequestHandler):
  def post(self, name):
    alias = models.Alias.get_by_key_name(name)
    if alias:
      feed_key = models.Alias.feed.get_value_for_datastore(alias)
      message = models.EmailMessage.create(feed_key, self.request.body)
      # Delete any old messages
      defer(delete_old_messages, feed_key)
      # Schedule a hub ping
      defer(send_hubbub_ping, feed_key)
    else:
      self.error(404)


def delete_old_messages(feed_key):
  q = models.EmailMessage.all()
  q.ancestor(feed_key)
  q.order('-created')
  keys = q.fetch(10, 10)
  db.delete(keys)
  logging.debug("Deleted %d old messages from feed %s", len(keys),
                feed_key.name())


HUB_URL = 'http://pubsubhubbub.appspot.com/'

def send_hubbub_ping(feed_key):
  feed = models.Feed.get(feed_key)
  data = urllib.urlencode({
      'hub.url': feed.url,
      'hub.mode': 'publish',
  })
  response = urlfetch.fetch(HUB_URL, data, urlfetch.POST)
  if response.status_code / 100 != 2:
    raise Exception("Hub ping failed", response.status_code, response.content)


class FeedHandler(BaseHandler):
  def get(self, feed_name):
    feed = models.Feed.get_by_key_name(feed_name)
    q = models.Message.all().ancestor(feed).order('-created')
    entries = q.fetch(10)
    logging.warn(entries)
    self.render_template('feed.xml', {
        'feed': feed,
        'entries': entries,
        'self_url': self.request.url,
        'host_url': self.request.host_url,
        'updated': max(x.created for x in entries) if entries else feed.created,
    })


class OriginalHandler(BaseHandler):
  def get(self, feed_name, message_id):
    message_key = db.Key.from_path(
        models.Feed.kind(), feed_name,
        models.Message.kind(), int(message_id))
    message = db.get(message_key)
    if message:
      self.response.headers['Content-Type'] = message.original_content_type
      self.response.out.write(message.original)
    else:
      self.error(404)


class IndexHandler(BaseHandler):
  def get(self):
    user = users.get_current_user()
    if user:
      aliases = models.Alias.all().filter('owner =', user).fetch(100)
    else:
      aliases = None
    self.render_template('index.html', {
        'aliases': aliases,
    })


class CreateHandler(BaseHandler):
  def post(self):
    user = users.get_current_user()
    feed = models.Feed.create(owner=user)
    alias_name = self.request.POST.get('address')
    if alias_name:
      alias = models.Alias.create(alias_name, feed, user)
    else:
      alias = models.Alias.create_random(feed, user)
    if alias:
      feed.title = 'Atom feed for %s@atomify.appspotmail.com' % alias.name
      feed.put()
      self.render_template('created.html', {
          'alias': alias,
          'feed': feed,
      })
    else:
      self.render_template('already_exists.html', {
          'address': alias_name,
      })
