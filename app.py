#!/usr/bin/env python
 
import sys, os

#home = os.path.dirname(__file__)
#if not home in sys.path:
#   sys.path.insert(0, home)
#os.chdir(home)


import web
import config
import app.controllers

#from app.helpers import error

urls = (        
    # front page
    '/*',                               'app.controllers.cuereview.Stats',

    '/upload',                          'app.controllers.cuereview.Upload',

    '/stats',                          'app.controllers.cuereview.Stats',

    '/matches/([0-9]*)',                'app.controllers.cuereview.Match',
    '/matches',                         'app.controllers.cuereview.Matches',

    '/players/([a-z]*)',                  'app.controllers.cuereview.Player',
    '/players',                         'app.controllers.cuereview.Players',

    '/breaks/([0-9]*)',                  'app.controllers.cuereview.Break',
    '/frames/([0-9]*)',                  'app.controllers.cuereview.FrameSummary',
    
#    '/settings/teams',                  'app.controllers.settings.settings_teams',
 #   '/settings/teams/([A-Z]*)',         'app.controllers.settings.settings_team',
)

app = web.application(urls, globals())
#application = web.application(urls, globals()).wsgifunc()

# Handle errors and 404's
#if not web.config.debug:
#    error.add(app)

if __name__ == "__main__":
    app.run()
