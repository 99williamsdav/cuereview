#!/usr/bin/env python
"""
cuereview.py: CueReview controller for handling requests.
"""
__author__ = "David Williams"
__maintainer__ = "David Williams"
__email__ = "99williamsdav@gmail.com"


import web
import config
import datetime
import re

from config import view
from app.utils import render
from app.utils import formatting
from app.utils import log
from app.utils import tools

from app.models import tmatch
from app.models import tframe
from app.models import tplayer
from app.models import tball
from app.models import breakpot

class Upload:
    def GET(self):
        error = ""

        title = "Upload"

        return render.wrap(view.cr_upload(), title=title, error=error)

    def POST(self):
        error = ""

        webdata = web.input(action="", matchcsv="", matchfile={})
        action = webdata.action
        matchcsv = webdata.matchcsv
        matchfile = webdata.matchfile
        date = ''

        match_id = 0

        if action == "uploadmatch":
            log.info('uploadmatch +', 'Controller')

            if matchcsv == "" and matchfile != {}:
                matchcsv = matchfile.value

                filename = matchfile.filename
                if 'match' in filename:
                    date = re.findall('([0-9]*-[0-9]*-[0-9]*)', filename)[0]

            error, match_id = tmatch.parseCsvMatch(matchcsv, date)

            log.info('uploadmatch -', 'Controller')
        else:
            error = "Unknown action"

        title = "Upload"

        # Stay on upload page if error
        if error == "":
            raise web.seeother('/matches/'+str(match_id))
        else:
            return render.wrap(view.cr_upload(defaultcsv=matchcsv), title=title, error=error)

class Stats:
    def GET(self):
        error = ""

        webdata = web.input(f="2000-01-01", t=tools.subtractFromDate(), d="")
        from_date = webdata.f
        to_date = webdata.t
        duration = webdata.d

        if duration == "week":
            from_date = tools.subtractFromDate(weeks=1)
        elif duration == "month":
            from_date = tools.subtractFromDate(months=1)
        elif duration == "threemonths":
            from_date = tools.subtractFromDate(months=3)
        elif duration == "sixmonths":
            from_date = tools.subtractFromDate(months=6)
        elif duration == "year":
            from_date = tools.subtractFromDate(years=1)

        players = tplayer.getAllPlayers(from_date, to_date)
        ball_stats = tball.getBallStats(from_date, to_date)
        balls = tball.getAllBalls()


        title = "Stats"
        breadcrumbs = [('stats', 'Stats'), ('stats/players', 'Players')]
        return render.wrap(view.cr_stats(players=players, ball_stats=ball_stats, balls=balls, d=duration), title=title, breadcrumbs=breadcrumbs, error=error)

class Matches:
    def GET(self):
        error = ""

        matches = tmatch.getAllMatches()

        title = "Matches"
        return render.wrap(view.cr_matches(matches=matches), title=title, error=error)

class Match:
    def GET(self, match_id):
        error = ""

        match = tmatch.getMatch(match_id)

        htmlframes = []
        for frame in match['frames']:
            vframe = tframe.getFrame(frame['frame_id'])
            player1id = vframe['frame_scores'][0]['player_id']

            htmlbreaks = []
            for vbreak_id in vframe['breaks']:
                vbreak = breakpot.getBreak(vbreak_id['break_id'])
                left = ( vbreak['player_id'] == player1id ) # Pull to the left if it's player 1, pull to right if it's player 2
                htmlbreaks.append(view.cr_break(vbreak=vbreak, left=left))

            htmlframes.append(view.cr_frame(frame=vframe, htmlbreaks=htmlbreaks))

        title = match['headline']
        return render.wrap(view.cr_match(match=match, htmlframes=htmlframes), title=title, error=error)

class Players:
    def GET(self):
        error = ""

        webdata = web.input(f="2000-01-01", t="9999-12-31")
        from_date = webdata.f
        to_date = webdata.t

        players = tplayer.getAllPlayers(from_date, to_date)
        balls = tball.getAllBalls()

        title = "Players"
        return render.wrap(view.cr_players(players=players, balls=balls), title=title, error=error)

class Player:
    def GET(self, name):
        error = ""

        player = tplayer.getPlayerStats(name)
        matches = tmatch.getAllMatchesForPlayer(name)
        balls = tball.getAllBalls()

        title = name
        return render.wrap(view.cr_player(player=player, balls=balls, matches=matches), title=title, error=error)


# AJAX HANDLERS

# class Frame:
#     def GET(self, frame_id):
#         frame = tframe.getFrame(frame_id)
#         player1id = frame['frame_scores'][0]['player_id']
#         #log.debug('player1id = '+str(player1id))

#         htmlbreaks = []
#         for vbreak_id in frame['breaks']:
#             vbreak = breakpot.getBreak(vbreak_id['break_id'])
#             left = ( vbreak['player_id'] == player1id ) # Pull to the left if it's player 1, pull to right if it's player 2
#             htmlbreaks.append(view.cr_break(vbreak=vbreak, left=left))

#         return view.cr_frame(frame=frame, htmlbreaks=htmlbreaks)

class FrameSummary:
    def GET(self, frame_id):
        frame = tframe.getFrame(frame_id)

        return view.cr_frame_summary(frame=frame)

class Break:
    def GET(self, break_id):
        return view.cr_break(vbreak=breakpot.getBreak(break_id))
