import web
import config

import datetime, string
import re

BALL_SIZES = {
    'white': '20',
    'red': '20',
    'yellow': '28',
    'green': '34',
    'brown': '40',
    'blue': '44',
    'pink': '48',
    'black': '52'
}

def cgi():
    return config.cgi_url

def match_url(match_id=0):
    return config.cgi_url+"/matches/"+str(match_id)

def player_url(player_name=''):
    return config.cgi_url+"/players/"+player_name.lower()

def ball_img(ball_name='red', size='30', title=''):
    #return '<img width="'+size+'" height="'+size+'" src="'+config.cgi_url+'/static/img/'+ball_name.lower()+'.jpg"></img>'
    if size is None:
        size = BALL_SIZES[ball_name.lower()]
    return '<canvas class="'+ball_name.lower()+' ball" width="'+size+'" height="'+size+'" title="'+str(title)+'"></canvas>'

def format_date(d):
    datex = datetime.datetime.strptime(d, '%Y-%m-%d')
    return datex.strftime('%d %B %Y')

def str_upper(s):
    return s.upper()

def get_name():
    return config.name

def get_version():
    return config.version

def get_builddate():
    return config.bdate

def format_minutes(m):
    hours, mins = divmod(int(m), 60)
    days, hours = divmod(int(hours), 24)

    if days > 0:
        return '%sd %sh %sm' % (days, hours, mins)
    elif hours > 0:
        return '%sh %sm' % (hours, mins)
    else:
        return '%sm' % (mins)
