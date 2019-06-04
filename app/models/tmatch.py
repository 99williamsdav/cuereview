#!/usr/bin/env python
"""
tmatch.py: Model for database interactions related to tmatch, as well as file parsing.
"""
__author__ = "David Williams"
__maintainer__ = "David Williams"
__email__ = "99williamsdav@gmail.com"

import web
import sqlite3
import re
import os
import datetime

import csv
import StringIO

from config import db

from app.utils import log
from app.models import tplayer
from app.models import tframe
from app.models import breakpot


# Match parsing constants
MATCH_COLUMNS = {'PLAYER':'Player',
                'FRAME':'Game',
                'BREAK':'Break',
                'TYPE':'Type',
                'BALL':'Ball',
                'POINTS':'Points',
                'ISLONG':'IsLong'}


# Overview: Creates match from parsing csv
# Parameters: csv file (csv export output from snooker app), name of file if uploaded
# Returns: error, match_id
# Insert: tmatch, tframe, tbreak, tbreakpot
# Update: tplayerstats
# Delete: -
def parseCsvMatch(csv_content, date=''):
    func = "match.parseCsvMatch()"
    error = ""

    data = csv.reader(StringIO.StringIO(csv_content), delimiter=',')

    column_headers = []

    player_ids = {} # dictionary of names mapping to id

    shots = []

    # First pass to create array of shot dictionaries
    row_no = 0
    for shotrow in data:
        col_no = 0
        shot = {}

        # Check number of columns
        if len(shotrow) != len(MATCH_COLUMNS):
            error = "bad number of csv columns"
            return error, 0

        for colval in shotrow:
            if row_no == 0:
                # Reverse lookup column header code to create dictionaries with keys from MATCH_COLUMNS
                try:
                    column_header = (key for key,value in MATCH_COLUMNS.items() if value==colval).next()
                    column_headers.append(column_header)
                except StopIteration:
                    error = "invalid csv header: "+colval
                    return error, 0
            else:
                # Find which column we're looking at based on headers
                col_type = column_headers[col_no]

                # Add value to shot dictionary
                shot[col_type] = colval

                # Set player names if not known, create players if they don't exist, trim spaces from player names
                if col_type == "PLAYER":
                    colval = colval.replace(" ", "")
                    if colval not in player_ids:
                        if len(player_ids) < 2:
                            player_ids[colval] = tplayer.getOrCreatePlayer(colval)
                        else:
                            error = "More than two players detected"
                            return error, 0

            col_no += 1

        # Add shot dictionary to list of shots
        if shot != {}:
            shots.append(shot)

        row_no += 1

    # Errors from first pass - Known issue: Won't work if one player doesn't pot
    if len(player_ids) != 2:
        error = "Invalid number of players: "+str(len(player_ids))
        return error, 0

    # Check if match might already exist
    # select m.match_id, count(distinct p.name), count(*)
    # from tmatch m, tframe f, tbreak b, tbreakpot bp, tmatchscore ms, tplayer p 
    # where m.match_id=f.match_id and f.frame_id=b.frame_id and b.break_id=bp.break_id and 
    #           m.match_id=ms.match_id and ms.player_id=p.player_id and p.name in ("David", "Jimmy")
    #  group by 1 having count(distinct p.name)=2;

    # Second pass to populate database
    # FIXME BEGIN TRANSACTION
    match_id = 0
    t = db.transaction()
    try:
        match_id = createMatch(date)
        cur_player_id = 0
        cur_frame_id = 0
        cur_frame = 0
        cur_break_id = 0
        cur_break = 0

        for shot in shots:
            cur_player_id = player_ids[shot['PLAYER']]

            if shot['FRAME'] != cur_frame: # New frame
                if cur_break_id > 0:
                    breakpot.closeBreak(cur_break_id)
                    cur_break_id = 0
                if cur_frame_id > 0:
                    tframe.closeFrame(cur_frame_id)
                cur_frame = shot['FRAME']
                cur_frame_id = tframe.createFrame(match_id, cur_frame)


            if shot['BREAK'] != cur_break or shot['BREAK'] == '': # New break
                if cur_break_id > 0:
                    breakpot.closeBreak(cur_break_id)
                if shot['BREAK'] != '':
                    cur_break = shot['BREAK']
                cur_break_id = breakpot.createBreak(cur_frame_id, cur_break, cur_player_id)

            # Register shot
            breakpot.pot(cur_break_id, shot['BALL'], shot['POINTS'], shot['TYPE'])

        if cur_break_id > 0:
            breakpot.closeBreak(cur_break_id)

        if cur_frame_id > 0:
            tframe.closeFrame(cur_frame_id)

        closeMatch(match_id)
        commitMatch(match_id)
    except Exception, e:
        log.error('Failed to create match - '+str(e))
        error = 'Failed to create match'
        log.error('rollback()')
        t.rollback()
    else:
        t.commit()

    return error, match_id


# Overview: Creates match
# Parameters: date (defaults to now, in case user doesn't specify)
# Returns: match_id
# Insert: tmatch
def createMatch(date=''):
    if date == '':
        date = datetime.date.today().strftime("%Y-%m-%d")

    match_id = 0
    try:
        match_id = db.insert('tmatch', date=date)
    except sqlite3.IntegrityError, e:
       pass

    return match_id

# Overview: Closes match in order to update stats
# Parameters: match_id
# Returns: ?
# Insert: tmatchscore
# Update: tplayerstats
def closeMatch(match_id):
    log.info('closeMatch('+str(match_id)+') +', 'tmatch')

    players = list(db.query("""
                    SELECT distinct fs.player_id
                    FROM tframe f, tframescore fs
                    WHERE f.match_id=$match_id AND
                        fs.frame_id=f.frame_id
            """, vars={'match_id':match_id}))

    if len(players) != 2:
        error = "uh oh"
        return

    for player in players:
        player['frames_won'] = list(db.query("""
                        SELECT count(*) as frames_won
                        FROM tframe f, tframescore fs
                        WHERE f.match_id=$match_id AND
                            fs.frame_id=f.frame_id AND
                            fs.player_id=$player_id AND
                            fs.won=1
                """, vars={'match_id':match_id,
                            'player_id':player['player_id']}))[0]['frames_won']

        player['total_points'] = list(db.query("""
                        SELECT IFNULL(sum(fs.score), 0) as total_points
                        FROM tframescore fs, tframe f
                        WHERE f.match_id=$match_id AND
                            fs.frame_id=f.frame_id AND
                            fs.player_id=$player_id
            """, vars={'match_id':match_id,
                        'player_id':player['player_id']}))[0]['total_points']

    players[0]['won'] = True # player 0 wins by default
    if players[1]['frames_won'] > players[0]['frames_won']:
        players[0]['won'] = False
    elif players[1]['frames_won'] == players[0]['frames_won']: # Tie, go by aggregate points
        if players[1]['total_points'] > players[0]['total_points']:
            players[0]['won'] = False

    players[1]['won'] = not players[0]['won']

    for player in players:
        createMatchScore(match_id,
                        player['player_id'],
                        player['won'],
                        player['frames_won'],
                        player['total_points'])

    log.info('closeMatch -', 'tmatch')

# Overview: Commits a match once the player has verified it
# Update: tmatch
def commitMatch(match_id):
    try:
        rowcount = db.update('tmatch',
                                where='match_id=$match_id',
                                vars={'match_id':match_id},
                                confirmed="Y")

        if rowcount != 1:
            error = "Bad number of rows deleted: "
            raise
    except:
        log.error('Failed to commit match '+str(match_id))
    

# FIXME
# Overview: Deletes tmatch entry and all related table entries
# Parameter: match_id
# Delete: tmatch, tmatchscore, tframe, tframescore, tbreak, tbreakpot
def deleteMatch(match_id):
    rowcount = db.delete('tmatch',
                where='match_id=$match_id',
                vars={'match_id':match_id})

    if rowcount != 1:
        error = "Bad number of rows deleted: "

# Overview: Creates a player match score when closing a match
# Parameters: frame_id, player_id, won, frames_won, total_points
# Returns: ?
# Insert: tmatchscore
def createMatchScore(match_id, player_id, won, frames_won, total_points):
    try:
        iid = db.insert('tmatchscore',
                            match_id=match_id,
                            player_id=player_id,
                            won=won,
                            frames_won=frames_won,
                            total_points=total_points)
    except sqlite3.IntegrityError, e:
        pass

# Overview: Returns high-level information about a match
# Parameters: match_id
# Returns: {'match_id', 'date', 'confirmed', 'match_scores', 'headline'}
#               match_scores: [] of {'player_id', 'name', 'won', 'frames_won', 'total_points'}
def getBasicMatchInfo(match_id):
    log.debug('getBasicMatchInfo('+str(match_id)+')', 'tmatch')

    match_info = list(db.query("""
                            SELECT match_id, date, strftime("%d/%m/%Y", date) as pretty_date, confirmed
                            FROM tmatch
                            WHERE match_id = $match_id
                    """, vars={'match_id':match_id}))[0]

    match_info['match_scores'] = list(db.query("""
                    SELECT p.player_id, p.name, ms.won, ms.frames_won, ms.total_points
                    FROM tmatchscore ms, tplayer p
                    WHERE ms.match_id = $match_id AND
                        ms.player_id=p.player_id
                    ORDER BY p.player_id
            """, vars={'match_id':match_id}))


    # if match_info['winner_frame_count'] == match_info['loser_frame_count']:
    #     match_info['headline'] = match_info['winner_name']+' beats '+match_info['loser_name']+' on points scored'
    # else:
    #     match_info['headline'] = match_info['winner_name']+' beats '+match_info['loser_name']+' '+str(match_info['winner_frame_count'])+'-'+str(match_info['loser_frame_count'])

    match_info['headline'] = ''

    return match_info

# Overview: Returns full match information
# Parameters: match_id
# Returns: {'match_id', 'date', 'match_scores', 'headline', 'stats':[], 'frames'}
#       match_scores: [] of {'player_id', 'name', 'won', 'frames_won', 'total_points'}}
#       frames: [] of {'frame_id', 'frame_scores'}
#       frame_scores: [] of {'player_id', 'name', 'won', 'score', 'foul_points'}
def getMatch(match_id):
    log.debug('getMatch('+str(match_id)+')', 'tmatch')
    
    match_info = getBasicMatchInfo(match_id)

    frames = list(db.query("""
                    SELECT frame_id
                    FROM tframe
                    WHERE match_id = $match_id
            """, vars={'match_id':match_id}))

    frames_info = []
    for frame in frames:
        frames_info.append(tframe.getBasicFrameInfo(frame['frame_id']))

    match_info['frames'] = frames_info

    match_info['stats'] = createMatchStats(match_info)

    return match_info

# Overview: Works out various stats based on the info provided (used by getMatch)
# Parameter: match_info (based on what's created in getMatch)
# Returns: [] of stat strings
def createMatchStats(match_info):
    stats = []

    # Set up previous stats
    previous_best_score_in_frame = list(db.query("""
                    SELECT IFNULL(max(fs.score), 0) as best_score
                    FROM tframe f, tframescore fs, tmatch m
                    WHERE m.match_id=f.match_id and f.frame_id=fs.frame_id and m.date < $date
            """, vars={'date':match_info['date']}))[0]['best_score']

    previous_most_fouls_in_frame = list(db.query("""
                    SELECT IFNULL(max(fs.foul_points), 0) as most_foul_points
                    FROM tframe f, tframescore fs, tmatch m
                    WHERE m.match_id=f.match_id and f.frame_id=fs.frame_id and m.date < $date
            """, vars={'date':match_info['date']}))[0]['most_foul_points']

    # Pass for each player
    for frame in match_info['frames']:
        for frame_score in frame['frame_scores']:
            if frame_score['score'] > previous_best_score_in_frame:
                stats.append(frame_score['name']+" beat the previous best frame score of "+
                                    str(previous_best_score_in_frame)+" with "+str(frame_score['score'])+" points")
                previous_best_score_in_frame = frame_score['score']

            if frame_score['foul_points'] > previous_most_fouls_in_frame:
                stats.append(frame_score['name']+" broke the record for most fouls in a frame with "+
                                    str(frame_score['foul_points']))
                previous_most_fouls_in_frame = frame_score['foul_points']


    return stats

# Overview: Returns basic information for all matches
def getAllMatches():
    match_ids = list(db.query("""
                    SELECT match_id
                    FROM tmatch
                    ORDER BY date
            """))

    matches = []
    for match_id in match_ids:
        matches.append(getBasicMatchInfo(match_id['match_id']))

    return matches

# Overview: Returns basic information for all matches a player has played
# Parameter: player name
def getAllMatchesForPlayer(name):
    match_ids = list(db.query("""
                    SELECT distinct ms.match_id
                    FROM tmatchscore ms, tplayer p, tmatch m
                    WHERE ms.player_id=p.player_id AND
                        ms.match_id=m.match_id AND
                        UPPER(p.name)=UPPER($name)
                    ORDER BY m.date
            """, vars={'name':name}))

    matches = []
    for match_id in match_ids:
        matches.append(getBasicMatchInfo(match_id['match_id']))

    return matches
