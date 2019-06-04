#!/usr/bin/env python
"""
homepage.py: RTron homepage.
"""
__author__ = "David Williams"
__maintainer__ = "David Williams"
__email__ = "david.williams@openbet.com"

import web
from config import view
from app.utils import render

class home:
	def GET(self):
		return render.wrap(view.home())
