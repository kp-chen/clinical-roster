"""Roster management blueprint"""
from flask import Blueprint

roster_bp = Blueprint('roster', __name__)

from . import routes