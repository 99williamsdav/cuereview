import web
import config
import datetime

from config import view

#from app.models import customers


def wrap(page='', title=config.name, error='', **kwargs):

        return view.wrapper(page=page, title=title, error=error, **kwargs)
