#!/usr/bin/env python
"""
tball.py: Model for database interactions related to tball.
"""
__author__ = "David Williams"
__maintainer__ = "David Williams"
__email__ = "99williamsdav@gmail.com"

import web
import sqlite3
import re
import os

from config import db

# Overview: Creates ball if it doesn't exist, returns existing ball_id if does
# Parameters: ball name, points worth, foul
# Returns: ball_id
# Insert: tball
def getOrCreateBall(name, points, foul):
    ball_id = 0

    entries = list(db.query("""
            SELECT ball_id FROM tball WHERE name=$name AND foul=$foul
            """, vars={'name':name,'foul':foul}))

    if len(entries) > 0:
        ball_id = entries[0]['ball_id']
    else:
        try:
            ball_id = db.insert('tball',
                                    name=name,
                                    foul=foul,
                                    points=points)
        except sqlite3.IntegrityError, e:
            pass

    return ball_id

# Overview: Returns all ball types (not including fouls)
# Returns: [] of {'ball_id', 'name', 'points'}
def getAllBalls():
    balls = list(db.query("""
                    SELECT * FROM tball WHERE foul="N" ORDER BY points ASC
            """))

    return balls

# Overview: Returns stats for balls
# Returns: {'{BALL_NAME}_total', '{BALL_NAME}_avg', '{BALL_NAME}_avg_points'}
def getBallStats(from_date="2000-01-01", to_date="9999-12-31"):
    ball_stats = {}

    num_frames = list(db.query("""
                        SELECT count(*) as num_frames
                        FROM tframe f, tmatch m
                        WHERE m.match_id=f.match_id AND
                            m.date >= $from_date AND
                            m.date <= $to_date
            """, vars={'from_date':from_date,'to_date':to_date}))[0]['num_frames']

    num_frames = num_frames * 2 # stats per player per frame (remove multiplication if we want stats per whole frame)

    for ball in getAllBalls():
        ball_stats[ball['name']+'_total'] = list(db.query("""
                SELECT count(*) as num_pots
                FROM tbreakpot bp, tbreak b, tframe f, tmatch m
                WHERE b.break_id=bp.break_id AND
                    f.frame_id=b.frame_id AND
                    m.match_id=f.match_id AND
                    m.date >= $from_date AND
                    m.date <= $to_date AND
                    ball_id=$ball_id
            """, vars={'ball_id':ball['ball_id'],
                        'from_date':from_date,
                        'to_date':to_date}))[0]['num_pots']

        ball_stats[ball['name']+'_avg'] = 0
        ball_stats[ball['name']+'_avg_points'] = 0
        if num_frames > 0:
            ball_stats[ball['name']+'_avg'] = round(float(ball_stats[ball['name']+'_total']) / num_frames, 1)
            ball_stats[ball['name']+'_avg_points'] = round((float(ball_stats[ball['name']+'_total']) / num_frames) * ball['points'], 1)

    return ball_stats