from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
import os

import handlers

application = webapp.WSGIApplication([
  ('/', handlers.IndexHandler),
  ('/create', handlers.CreateHandler),
  ('/_ah/mail/(.+)%%40%s\.appspotmail\.com' % os.environ['APPLICATION_ID'],
   handlers.EmailHandler),
  ('/feed/([a-z0-9]+)', handlers.FeedHandler),
  ('/feed/([a-z0-9]+)/([1-9][0-9]*)', handlers.OriginalHandler),
])

def main():
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
