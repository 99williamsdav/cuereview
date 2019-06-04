from config import log_file
from datetime import datetime

def debug(msg='', module='CueReview'):
    log(msg, module, 'DEBUG')

def error(msg='', module='CueReview'):
    log(msg, module, 'ERROR')

def info(msg='', module='CueReview'):
    log(msg, module, 'INFO')

def log(msg='', module='CueReview', type='DEBUG'):
    with open(log_file, "a") as f:
        f.write(str(datetime.now())+" ["+type+"] - "+module+": "+msg+"\n")