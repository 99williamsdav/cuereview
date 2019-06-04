#!/usr/bin/env python
"""
tplayer.py: Model for database interactions related to tplayer and tplayerstats.
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
from app.models import tball

# ELO CONSTANTS
f=1000.0
k=32.0

# Overview: Creates player if name doesn't exist, returns existing player_id if does
# Parameters: player name
# Returns: player_id
# Insert: tplayer
def getOrCreatePlayer(name):
    player_id = 0

    entries = list(db.query("""
            SELECT player_id FROM tplayer WHERE name=$name
            """, vars={'name':name}))

    if len(entries) > 0:
        player_id = entries[0]['player_id']
    else:
        try:
            player_id = db.insert('tplayer',
                                    name=name)
        except sqlite3.IntegrityError, e:
            pass

    return player_id

# Overview: Returns basic player information
# Parameter: player_id
# Returns: {'player_id', 'name', 'elo'}
def getBasicPlayerInfo(player_id):
    player = list(db.query("""
                SELECT *
                FROM tplayer
                WHERE player_id=$player_id
            """, vars={'player_id':player_id}))[0]

    return player


# Overview: Returns all information about a player
# Parameter: name
# Returns: {'player_id', 'name', 'elo', 'matches_played', 'wins', 'losses', 'percentage', 
#            'frames_played', 'frame_wins', 'frame_losses', 'frame_percentage', 'highest_break':{*}, 'longest_break':{*}, 'best_score':{*}, 'most_fouls':{*}, 'ppf', 'fpf',
#            '[BALLNAME]*_avg', '[BALLNAME]*_avg_points'}
#       *: stat dicts contain {'date', 'match_id', ['frame_id' / 'break_id'], ['score' / 'length' / 'foul_points']}
def getPlayerStats(name, from_date="2000-01-01", to_date="9999-12-31"):

    qry = list(db.query("""
                SELECT p.player_id, p.name, p.elo, count(*) as matches_played
                FROM tmatchscore ms, tmatch m, tplayer p
                WHERE p.player_id=ms.player_id AND
                    m.match_id=ms.match_id AND
                    m.confirmed = "Y" AND
                    m.date >= $from_date AND
                    m.date <= $to_date AND
                    UPPER(p.name)=UPPER($name)
                GROUP BY 1,2
            """, vars={'name':name,'from_date':from_date,'to_date':to_date}))
    
    if len(qry) == 0:
        return None

    player = qry[0]

    player['elo'] = round(player['elo'], 2)

    player['wins'] = list(db.query("""
                SELECT count(*) as wins
                FROM tmatchscore ms, tmatch m
                WHERE player_id=$player_id AND
                    m.match_id=ms.match_id AND
                    m.confirmed = "Y" AND
                    m.date >= $from_date AND
                    m.date <= $to_date AND
                    ms.won=1
            """, vars={'player_id':player['player_id'],'from_date':from_date,'to_date':to_date}))[0]['wins']

    player['losses'] = player['matches_played'] - player['wins']
    player['percentage'] = int((float(player['wins']) / player['matches_played']) * 100)

    player['frames_played'] = list(db.query("""
                SELECT count(*) as frames_played
                FROM tframescore fs, tframe f, tmatch m
                WHERE fs.player_id=$player_id AND
                    fs.frame_id=f.frame_id AND
                    m.match_id=f.match_id AND
                    m.confirmed = "Y" AND
                    m.date >= $from_date AND
                    m.date <= $to_date
            """, vars={'player_id':player['player_id'],'from_date':from_date,'to_date':to_date}))[0]['frames_played']

    player['frame_wins'] = list(db.query("""
                SELECT count(*) as frame_wins
                FROM tframescore fs, tframe f, tmatch m
                WHERE fs.player_id=$player_id AND
                    fs.frame_id=f.frame_id AND
                    m.match_id=f.match_id AND
                    m.confirmed = "Y" AND
                    m.date >= $from_date AND
                    m.date <= $to_date AND
                    fs.won=1
            """, vars={'player_id':player['player_id'],'from_date':from_date,'to_date':to_date}))[0]['frame_wins']

    player['frame_losses'] = player['frames_played'] - player['frame_wins']
    player['frame_percentage'] = int((float(player['frame_wins']) / player['frames_played']) * 100)

    player['highest_break'] = list(db.query("""
                SELECT b.break_id, b.score, m.date, m.match_id
                FROM tbreak b, tframe f, tmatch m
                WHERE b.player_id=$player_id AND
                    b.frame_id=f.frame_id AND
                    m.match_id=f.match_id AND
                    m.confirmed = "Y" AND
                    m.date >= $from_date AND
                    m.date <= $to_date AND
                    b.foul_num IS NULL
                ORDER BY b.score DESC, b.length DESC
                LIMIT 1
            """, vars={'player_id':player['player_id'],'from_date':from_date,'to_date':to_date}))[0]

    player['longest_break'] = list(db.query("""
                SELECT b.break_id, b.length, m.date, m.match_id
                FROM tbreak b, tframe f, tmatch m
                WHERE b.player_id=$player_id AND
                    b.frame_id=f.frame_id AND
                    m.match_id=f.match_id AND
                    m.confirmed = "Y" AND
                    m.date >= $from_date AND
                    m.date <= $to_date AND
                    b.foul_num IS NULL
                ORDER BY b.length DESC
                LIMIT 1
            """, vars={'player_id':player['player_id'],'from_date':from_date,'to_date':to_date}))[0]

    player['best_score'] = list(db.query("""
                SELECT fs.frame_id, fs.score, m.date, m.match_id
                FROM tframescore fs, tframe f, tmatch m
                WHERE fs.player_id=$player_id AND
                    fs.frame_id=f.frame_id AND
                    m.match_id=f.match_id AND
                    m.confirmed = "Y" AND
                    m.date >= $from_date AND
                    m.date <= $to_date
                ORDER BY fs.score DESC
                limit 1
            """, vars={'player_id':player['player_id'],'from_date':from_date,'to_date':to_date}))[0]

    player['most_fouls'] = list(db.query("""
                SELECT fs.frame_id, fs.foul_points, m.date, m.match_id
                FROM tframescore fs, tframe f, tmatch m
                WHERE fs.player_id=$player_id AND
                    fs.frame_id=f.frame_id AND
                    m.match_id=f.match_id AND
                    m.confirmed = "Y" AND
                    m.date >= $from_date AND
                    m.date <= $to_date
                ORDER BY fs.foul_points DESC
                limit 1
            """, vars={'player_id':player['player_id'],'from_date':from_date,'to_date':to_date}))[0]

    # ppf = points per frame
    player['ppf'] = round(list(db.query("""
                SELECT avg(score) as ppf
                FROM tframescore fs, tframe f, tmatch m
                WHERE fs.player_id=$player_id AND
                    fs.frame_id=f.frame_id AND
                    m.match_id=f.match_id AND
                    m.confirmed = "Y" AND
                    m.date >= $from_date AND
                    m.date <= $to_date
            """, vars={'player_id':player['player_id'],'from_date':from_date,'to_date':to_date}))[0]['ppf'], 1)

    # fpf = fouls per frame
    player['fpf'] = round(list(db.query("""
                SELECT avg(fs.foul_points) as fpf
                FROM tframescore fs, tframe f, tmatch m
                WHERE fs.player_id=$player_id AND
                    fs.frame_id=f.frame_id AND
                    m.match_id=f.match_id AND
                    m.confirmed = "Y" AND
                    m.date >= $from_date AND
                    m.date <= $to_date
            """, vars={'player_id':player['player_id'],'from_date':from_date,'to_date':to_date}))[0]['fpf'], 1)

    for ball in tball.getAllBalls():
        player[ball['name']+'_total'] = list(db.query("""
                SELECT count(*) as num_pots
                FROM tbreakpot bp, tbreak b, tframe f, tmatch m
                WHERE b.break_id=bp.break_id AND
                    b.player_id=$player_id AND
                    f.frame_id=b.frame_id AND
                    m.match_id=f.match_id AND
                    m.confirmed = "Y" AND
                    m.date >= $from_date AND
                    m.date <= $to_date AND
                    ball_id=$ball_id
            """, vars={'player_id':player['player_id'],
                        'ball_id':ball['ball_id'],
                        'from_date':from_date,
                        'to_date':to_date}))[0]['num_pots']

        player[ball['name']+'_avg'] = round(float(player[ball['name']+'_total']) / player['frames_played'], 1)
        player[ball['name']+'_avg_points'] = round((float(player[ball['name']+'_total']) / player['frames_played']) * ball['points'], 1)

    return dict(player)


# Overview: Returns information about all players
# Parameters: date range (optional - defaults to all time)
# Returns: array of {'player_id', 'name', 'matches_played', 'wins', 'losses', 'percentage'}
def getAllPlayers(from_date="2000-01-01", to_date="9999-12-31"):

    player_names = list(db.query("""
                    SELECT p.name
                    FROM tplayer p, tmatchscore ms, tmatch m
                    WHERE p.player_id=ms.player_id AND
                        ms.match_id=m.match_id AND
                        m.date >= $from_date AND
                        m.date <= $to_date
                    GROUP BY 1
                    ORDER BY count(*) DESC
            """, vars={'from_date':from_date, 'to_date':to_date}))

    players = []
    for player_name in player_names:
        player = getPlayerStats(player_name['name'], from_date, to_date)
        if player is not None:
            players.append(player)

    return players

# Overview: Calculates elo rating changes and updates them
# Parameters: winner ID, loser ID, frame_id
# Update: tplayer
# Insert: telojrnl
def updateElo(winner_id, loser_id, frame_id):
    winner = getBasicPlayerInfo(winner_id)
    loser = getBasicPlayerInfo(loser_id)

    prob = getProbability(winner['elo'], loser['elo'])
    change = getEloChange(prob)

    changeElo(winner_id, change, frame_id, loser['elo'])
    changeElo(loser_id, -change, frame_id, winner['elo'])

    log.info(winner['name']+' elo: '+str(winner['elo'])+' + '+str(change), 'tplayer')
    log.info(loser['name']+' elo: '+str(loser['elo'])+' - '+str(change), 'tplayer')


# Overview: Calculates probability of one player beating another
# Parameters: ID of two players
# Returns: Decimal probability
def getContestProbability(player_id, opp_id):
    player = getBasicPlayerInfo(player_id)
    opponent = getBasicPlayerInfo(opp_id)

    return getProbability(player['elo'], opponent['elo'])


# Overview: Calculates probability of one elo beating another
# Parameters: elo of two players
# Returns: Decimal probability
def getProbability(player_elo, opp_elo):
    return 1 / (1 + 10 ** ((opp_elo - player_elo) / f))

# Overview: Calculates an elo change
# Parameter: Decimal probability
# Returns: elo change
def getEloChange(probability):
    return (k * (1 - probability))

# Overview: Updates a player's elo
# Parameters: player ID, elo change, frame ID (for jrnl), opponent's elo rating (for jrnl)
# Update: tPlayer.elo
# Insert: tEloJrnl
def changeElo(player_id, elo_change, frame_id, opp_elo):
    # update player elo
    db.query("""
                UPDATE tplayer
                SET elo = elo + $change
                WHERE player_id=$player_id
            """, vars={'player_id':player_id, 'change':elo_change})

    # add elo jrnl entry
    try:
        db.query("""
                INSERT INTO telojrnl (player_id, frame_id, elo_change, opp_elo, new_elo)
                VALUES ($player_id, $frame_id, $elo_change, $opp_elo, (SELECT elo FROM tplayer WHERE player_id=$player_id) )
            """, vars={'player_id':player_id, 'frame_id':frame_id, 'elo_change':elo_change, 'opp_elo':opp_elo})
    except sqlite3.IntegrityError, e:
        log.error('SQL error while inserting entry into tEloJrnl')
