#!/usr/bin/env python
"""
tframe.py: Model for database interactions related to tframe and tframescore.
"""
__author__ = "David Williams"
__maintainer__ = "David Williams"
__email__ = "99williamsdav@gmail.com"

import web
import sqlite3
import re
import os

from app.utils import log
from config import db
from app.models import tplayer


# Overview: Creates empty frame (used during match parsing)
# Parameters: match_id, frame_num (to order frames in match)
# Returns: frame_id
# Insert: tframe
def createFrame(match_id, frame_num):
    log.info('createFrame('+str(match_id)+', '+str(frame_num)+')', 'tframe')

    player_id = 0
    try:
        player_id = db.insert('tframe',
                                match_id=match_id,
                                frame_num=frame_num)
    except sqlite3.IntegrityError, e:
        log.error('SQL error while inserting entry into tFrame')

    return player_id

# Overview: Closes frame in order to update stats
# Parameters: frame_id
# Returns: ?
# Insert: tframescore
# Update: tplayerstats
def closeFrame(frame_id):
    log.info('closeFrame('+str(frame_id)+') +', 'tframe')

    players = list(db.query("""
                    SELECT distinct player_id
                    FROM tbreak
                    WHERE frame_id=$frame_id
            """, vars={'frame_id':frame_id}))
    
    if len(players) != 2:
        log.error('Bad number of players returned ('+str(len(players))+') while closing frame')
        return

    for player in players:
        player['score'], player['foul_points'] = getCurrentFrameScore(frame_id, player['player_id'])

        #player['score'] = list(db.query("""
        #                SELECT IFNULL(sum(score), 0) as score
        #                FROM tbreak
        #                WHERE frame_id=$frame_id AND
        #                    player_id=$player_id AND
        #                    foul_num IS NULL
        #        """, vars={'frame_id':frame_id,
        #                    'player_id':player['player_id']}))[0]['score']

        #player['foul_points'] = list(db.query("""
        #                SELECT IFNULL(sum(score), 0) as foul_points
        #                FROM tbreak
        #                WHERE frame_id=$frame_id AND
        #                    player_id=$player_id AND
        #                    foul_num IS NOT NULL
        #        """, vars={'frame_id':frame_id,
        #                    'player_id':player['player_id']}))[0]['foul_points']

    # Add opponent fouls to score
    #players[0]['score'] += players[1]['foul_points']
    #players[1]['score'] += players[0]['foul_points']

    probability = tplayer.getContestProbability(players[0]['player_id'], players[1]['player_id'])

    players[0]['won'] = True # player 0 wins by default
    if players[1]['score'] > players[0]['score']:
        players[0]['won'] = False
        probability = tplayer.getContestProbability(players[1]['player_id'], players[0]['player_id'])

    players[1]['won'] = not players[0]['won']

    updateFrameProbability(frame_id, probability)

    for player in players:
        createFrameScore(frame_id,
                        player['player_id'],
                        player['won'],
                        player['score'],
                        player['foul_points'])


    if players[0]['won']:
        tplayer.updateElo(players[0]['player_id'], players[1]['player_id'], frame_id)
    else:
        tplayer.updateElo(players[1]['player_id'], players[0]['player_id'], frame_id)

    log.info('closeFrame -', 'tframe')

# Overview: Gets the frame score and foul points of a player up to and including a certain break
# Parameters: frame_id, player_id, 
#               break_num (defaults to 9999 to get overall frame score), 
#               opponent determines whether to get the player's opponent's score, 
#               foul_num (defaults to 99 to get all of current break_num)
# Returns: tuple of (player score, foul_points)
def getCurrentFrameScore(frame_id, player_id, break_num=9999, foul_num=None, opponent=False):
    # if break_num is specified but foul_num isn't, then we shouldn't include fouls for the current break_num
    # if break_num isn't specified, then we want every damn thing
    if not foul_num or foul_num == "":
        if break_num == 9999:
            foul_num = 99
        else:
            foul_num = 0

    # Reverse score query player clause if getting opponent's points
    player_qry = "player_id=$player_id"
    opp_qry = "player_id <> $player_id"
    if opponent:
        player_qry = "player_id <> $player_id"
        opp_qry = "player_id=$player_id"

    score = list(db.query("""
                        SELECT IFNULL(sum(score), 0) as score
                        FROM tbreak
                        WHERE frame_id=$frame_id AND
                            """+player_qry+""" AND
                            foul_num IS NULL AND
                            break_num <= $break_num
                """, vars={'frame_id':frame_id,
                            'player_id':player_id,
                            'break_num':break_num}))[0]['score']

    # break_num + foul_num ugly maths is to be able to ignore breaks with the same break_num but a higher foul_num
    opp_foul_points = list(db.query("""
                        SELECT IFNULL(sum(score), 0) as opp_foul_points
                        FROM tbreak
                        WHERE frame_id=$frame_id AND
                            """+opp_qry+""" AND
                            foul_num IS NOT NULL AND
                            break_num*100 + foul_num <= $break_num * 100 + $foul_num
                """, vars={'frame_id':frame_id,
                            'player_id':player_id,
                            'break_num':break_num,
                            'foul_num':foul_num}))[0]['opp_foul_points']

    score += opp_foul_points

    # break_num + foul_num ugly maths is to be able to ignore breaks with the same break_num but a higher foul_num
    foul_points = list(db.query("""
                        SELECT IFNULL(sum(score), 0) as foul_points
                        FROM tbreak
                        WHERE frame_id=$frame_id AND
                            """+player_qry+""" AND
                            foul_num IS NOT NULL AND
                            break_num*100 + foul_num <= $break_num * 100 + $foul_num
                """, vars={'frame_id':frame_id,
                            'player_id':player_id,
                            'break_num':break_num,
                            'foul_num':foul_num}))[0]['foul_points']

    log.debug('getCurrentFrameScore(frame_id='+str(frame_id)+', player_id='+str(player_id)+', break_num='+str(break_num)+', '+str(opponent)+') : '+str(score)+' , '+str(foul_points), 'tframe')
    return score, foul_points

# Overview: Sets the probability of the result
# Parameters: frame_id, probability (decimal)
# Update: tframe
def updateFrameProbability(frame_id, probability):
    log.info('updateFrameProbability('+str(frame_id)+', '+str(probability)+')', 'tframe')

    db.update('tframe',
                    where='frame_id=$frame_id',
                    vars={'frame_id':frame_id},
                    result_probability=probability)
        

# Overview: Creates a player frame score when closing a frame
# Parameters: frame_id, player_id, won, score, foul_points
# Returns: ?
# Insert: tframescore
def createFrameScore(frame_id, player_id, won, score, foul_points):
    log.info('createFrameScore(frame_id='+str(frame_id)+', player_id='+str(player_id)+', won='+str(won)+', score='+str(score)+', foul_points='+str(foul_points)+')', 'tframe')

    try:
        iid = db.insert('tframescore',
                            frame_id=frame_id,
                            player_id=player_id,
                            won=won,
                            score=score,
                            foul_points=foul_points)
    except sqlite3.IntegrityError, e:
        log.error('SQL error while inserting entry into tFrameScore')


# Overview: Returns high-level information about a frame
# Parameters: frame_id
# Returns: Dictionary = {'frame_id', 'match_id', 'frame_num', 'frame_scores'}
#               frame_scores = [] of {'player_id', 'name', 'won', 'score', 'foul_points'}
def getBasicFrameInfo(frame_id):
    log.debug('getBasicFrameInfo('+str(frame_id)+')', 'tframe')

    entries = list(db.query("""
                    SELECT * FROM tframe
                    WHERE frame_id = $frame_id
            """, vars={'frame_id':frame_id}))

    frame_info = {}
    if len(entries) == 1:
        frame_info = entries[0]
    else:
        log.error('Bad number of frames found for frame_id='+str(frame_id), 'tframe.getBasicFrameInfo')
        return {}

    frame_info['frame_scores'] = list(db.query("""
                    SELECT p.player_id, p.name, fs.won, fs.score, fs.foul_points
                    FROM tframescore fs, tplayer p
                    WHERE fs.frame_id = $frame_id AND
                        fs.player_id=p.player_id
                    ORDER BY p.player_id
            """, vars={'frame_id':frame_id}))

    return frame_info

# Overview: Returns all information about a frame
# Parameters: frame_id
# Returns: Dictionary = {'frame_id', 'match_id', 'frame_num', 'frame_scores', 'breaks'}
#               frame_scores = [] of {'player_id', 'name', 'won', 'score', 'foul_points'}
#               breaks = [] of {'break_id'}    ----- {'player_id','player_name','score', 'pots'}   
#                                              ----- pots = [] of {'ball_id', 'name', 'foul', 'points'}
def getFrame(frame_id):
    log.debug('getFrame('+str(frame_id)+')', 'tframe')

    frame = getBasicFrameInfo(frame_id)

    frame['breaks'] = list(db.query("""
                    SELECT break_id FROM tbreak
                    WHERE frame_id = $frame_id
                    ORDER BY break_num, foul_num
            """, vars={'frame_id':frame_id}))

    log.debug('len(frame[\'breaks\']) = '+str(len(frame['breaks'])), 'tframe')

    #for vbreak in breaks:
    #    frame['breaks'].append(breakpot.getBreak(vbreak['break_id']))

    return frame

# Overview: Returns frame_id of all frames within a date range
# Parameters: date range (optional - defaults to all time)
# Returns: array of frame_id
def getAllFrameIDs(from_date="2000-01-01", to_date="9999-12-31"):
    frame_ids = list(db.query("""
                    SELECT f.frame_id
                    FROM tframe f, tmatch m
                    WHERE f.match_id=m.match_id AND
                        m.date >= $from_date AND
                        m.date <= $to_date
            """, vars={'from_date':from_date, 'to_date':to_date}))

    ids = []
    for frame_id in frame_ids:
        ids.append(frame_id['frame_id'])

    return ids

# Temporary function to backpopulate elo
def updateMissedElos():
    frame_ids = getAllFrameIDs()

    for frame_id in frame_ids:
        updateFrameElo(frame_id)

# Temporary function to backpopulate elo
def updateFrameElo(frame_id):
    frame = getBasicFrameInfo(frame_id)

    winner_id = 0
    loser_id = 0

    for frame_score in frame['frame_scores']:
        if frame_score['won']:
            winner_id = frame_score['player_id']
        else:
            loser_id = frame_score['player_id']

    tplayer.updateElo(winner_id, loser_id, frame_id)
