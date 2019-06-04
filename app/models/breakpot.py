#!/usr/bin/env python
"""
breakpot.py: Model for database interactions related to tbreak and tbreakpot.
"""
__author__ = "David Williams"
__maintainer__ = "David Williams"
__email__ = "99williamsdav@gmail.com"

import web
import sqlite3
import re
import os

from config import db
from app.models import player
from app.models import tball
from app.models import tframe

# Overview: Returns break
# Parameters: break_id
# Returns: Dictionary = {'player_id','player_name','score', 'frame_score', 'pots'}
#               pots = [] of {'ball_id', 'name', 'foul', 'points'}
def getBreak(break_id):
    entries = list(db.query("""
                SELECT p.name AS player_name,
                        b.*
                FROM tbreak b, tplayer p
                WHERE b.player_id=p.player_id AND
                        b.break_id=$break_id
            """, vars={'break_id':break_id}))

    vbreak = {}
    if len(entries) == 1:
        vbreak = entries[0]
    else:
        return {}

    vbreak['pots'] = list(db.query("""
                SELECT b.*
                FROM tball b, tbreakpot bp
                WHERE bp.ball_id=b.ball_id AND
                            bp.break_id=$break_id
                ORDER BY bp.pot_num
            """, vars={'break_id':break_id}))

    return vbreak

# Overview: Creates empty break (used during match parsing)
# Parameters: frame_id, break_num (to order breaks in frame)
# Returns: break_id
# Insert: tbreak
def createBreak(frame_id, break_num, player_id):
    break_id = 0
    try:
        break_id = db.insert('tbreak',
                                frame_id=frame_id,
                                break_num=break_num,
                                player_id=player_id)
    except sqlite3.IntegrityError, e:
        pass

    return break_id

# Overview: Closes break in order to update stats
# Parameters: break_id
# Returns: -
# Update: tbreak, tplayerstats
def closeBreak(break_id):
    # Find out if it's a foul break
    foul_entries = list(db.query("""
                SELECT count(*) as fouls
                FROM tball b, tbreakpot bp
                WHERE b.ball_id=bp.ball_id AND
                    bp.break_id=$break_id AND
                    b.foul='Y'
            """, vars={'break_id':break_id}))

    # Get break score
    score = list(db.query("""
                    SELECT IFNULL(SUM(b.points), 0) as score
                    FROM tball b, tbreakpot bp
                    WHERE b.ball_id=bp.ball_id AND bp.break_id=$break_id
            """, vars={'break_id':break_id}))[0]['score']

    # Get break length
    length = list(db.query("""
                    SELECT count(*) as length
                    FROM tbreakpot bp
                    WHERE bp.break_id=$break_id
            """, vars={'break_id':break_id}))[0]['length']

    # Get current frame score (doesn't make much sense for fouls, but oh well...)
    breakx = list(db.query("""
                    SELECT *
                    FROM tbreak
                    WHERE break_id=$break_id
            """, vars={'break_id':break_id}))[0]
    frame_score, foul_points = tframe.getCurrentFrameScore(breakx['frame_id'], breakx['player_id'])
    opp_frame_score, opp_foul_points = tframe.getCurrentFrameScore(breakx['frame_id'], breakx['player_id'], opponent=True)

    rowcount = 0
    if foul_entries[0]['fouls'] > 0:
        # Update tbreak entry with score and incremented foul_num

        foul_num = list(db.query("""
                    SELECT IFNULL(MAX(b2.foul_num)+1, 1) as foul_num
                    FROM tbreak b1, tbreak b2
                    WHERE b1.break_id=$break_id AND
                        b1.frame_id=b2.frame_id AND
                        b1.break_num=b2.break_num
            """, vars={'break_id':break_id}))[0]['foul_num']

        rowcount = db.update('tbreak',
                                where='break_id=$break_id',
                                vars={'break_id':break_id},
                                score=score,
                                foul_num=foul_num,
                                length=length,
                                frame_score=frame_score,
                                opp_frame_score=opp_frame_score)

    else:
        frame_score += score # add on score to frame score because it doesn't exist in tbreak yet

        # Update tbreak entry with score
        rowcount = db.update('tbreak',
                                where='break_id=$break_id',
                                vars={'break_id':break_id},
                                score=score,
                                length=length,
                                frame_score=frame_score,
                                opp_frame_score=opp_frame_score)
    
    if rowcount != 1:
        error = "Uh oh"

# Overview: Registers a potted ball or foul
# Parameters: break_id, ball_name ('Red', 'Yellow' etc.), points, type ('Foul' or 'Pot')
# Returns: ?
# Update: tbreakpot
def pot(break_id, ball_name, points, type='Pot'):
    foul = 'N'
    if type == 'Foul':
        foul = 'Y'

    ball_id = tball.getOrCreateBall(ball_name, points, foul)

    # Get pot_num
    pot_num = list(db.query("""
                    SELECT IFNULL(MAX(b.pot_num)+1, 1) as pot_num
                    FROM tbreakpot b
                    WHERE b.break_id=$break_id
            """, vars={'break_id':break_id}))[0]['pot_num']

    try:
        break_id = db.insert('tbreakpot',
                                break_id=break_id,
                                pot_num=pot_num,
                                ball_id=ball_id)
    except sqlite3.IntegrityError, e:
        pass

    return 0


# BACKPOPULATION FUNCTIONS (one run only, make idempotent)

# update tbreak.frame_score and tbreak.opp_frame_score for breaks created before functionality was added
def backpopulateCurrentFrameScores():
    t = db.transaction()

    try:
        breaks = list(db.query("""
                        SELECT * FROM tbreak
                    """))

        for breakx in breaks:
            frame_score, foul_points = tframe.getCurrentFrameScore(breakx['frame_id'], breakx['player_id'], break_num=breakx['break_num'], foul_num=breakx['foul_num'])

            rowcount = db.update('tbreak',
                                    where='break_id=$break_id',
                                    vars={'break_id':breakx['break_id']},
                                    frame_score=frame_score)

            opp_frame_score, opp_foul_points = tframe.getCurrentFrameScore(breakx['frame_id'], breakx['player_id'], break_num=breakx['break_num'], foul_num=breakx['foul_num'], opponent=True)

            rowcount += db.update('tbreak',
                                    where='break_id=$break_id',
                                    vars={'break_id':breakx['break_id']},
                                    opp_frame_score=opp_frame_score)

            if rowcount != 2:
                print "FUCKING HELL"
                raise
    except:
        t.rollback()
        raise
    else:
        t.commit()