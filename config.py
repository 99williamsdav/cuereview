"""
config.py: Configuation file for CueReview 
"""
__author__ = "David Williams"
__maintainer__ = "David Williams"
__email__ = "99williamsdav@gmail.com"

import web

from app.utils import functions
from app.utils import formatting

name ='CueReview'
cgi_url = ''
version = '0.34'
bdate = '10/06/12'
log_file = '/home/dwilliam/projects/CueReview/logs/cuereview.log'

# connect to database
db = web.database(dbn='sqlite',
                  db='CueReview.sqlite')

# Debug Mode
web.config.debug = True
web.config.db_printing = web.config.debug

# Template Caching
cache = False


# template global functions
globals = functions.get_all_functions(formatting)

# Base Template
view = web.template.render('app/views', cache=cache, globals=globals)


# Error email address
web.config.email_errors = '99williamsdav@gmail.com'
web.config.email_errors_from = '99williamsdav@gmail.com'
