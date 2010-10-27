from google.appengine.api import mail
from google.appengine.ext import db
from google.appengine.ext.db import polymodel

import base64
import os


def transactional(fun):
  def decorator(*args, **kwargs):
    return db.run_in_transaction(fun, *args, **kwargs)
  return decorator


class Feed(db.Model):
  """Represents a feed that accumulates received messages."""

  title = db.StringProperty()
  created = db.DateTimeProperty(required=True, auto_now_add=True)
  owner = db.UserProperty()

  @property
  def name(self):
    return self.key().name()

  @property
  def url(self):
    return "http://atomify.appspot.com/feed/%s" % self.name

  @classmethod
  def create(cls, owner=None):
    """Creates a new, randomly named, feed."""
    feed = cls(key_name=os.urandom(8).encode('hex'), owner=owner)
    return feed


class Alias(db.Model):
  """Represents an email alias that can accept incoming mail."""
  
  feed = db.ReferenceProperty(required=True)
  created = db.DateTimeProperty(required=True, auto_now_add=True)
  owner = db.UserProperty()

  @property
  def name(self):
    return self.key().name()

  @classmethod
  @transactional
  def create(cls, name, feed, owner=None):
    """Creates a new alias.
    
    If an aliaswith the provided name already exists, returns None.
    """
    alias = cls.get_by_key_name(name)
    if not alias:
      alias = cls(
          feed=feed,
          key_name=name,
          owner=owner)
      alias.put()
      return alias
    else:
      return None

  @classmethod
  def create_random(cls, feed, owner=None):
    """Creates a new randomly named alias."""
    mapping = None
    while not mapping:
      name = base64.b32encode(os.urandom(5)).lower()
      mapping = cls.create(name, feed, owner)
    return mapping


class Message(polymodel.PolyModel):
  """Represents a message received for a feed."""

  created = db.DateTimeProperty(required=True, auto_now_add=True)

  feed_name = property(lambda self: self.key().parent().name())
  message_id = property(lambda self: self.key().id())


class EmailMessage(Message):
  """Represents an email message."""

  body = db.BlobProperty(required=True)

  def __init__(self, *args, **kwargs):
    super(EmailMessage, self).__init__(*args, **kwargs)
    self.message = mail.InboundEmailMessage(self.body)

  @classmethod
  def create(cls, feed, body):
    ret = cls(parent=feed, body=body)
    ret.put()
    return ret

  title = property(lambda self:self.message.subject)
  author_email = property(lambda self:self.message.sender)
  
  @property
  def content_type(self):
    if list(self.message.bodies('text/html')):
      return 'html'
    else:
      return 'text'

  @property
  def content(self):
    for content_type, body in self.message.bodies('text/html'):
      return body.decode()
    for content_type, body in self.message.bodies('text/plain'):
      return body.decode()
    return ''

  original = property(lambda self:self.body)
  original_content_type = 'message/rfc822'
  published = property(lambda self:self.created)
