"""API v1 blueprint"""
from flask import Blueprint

api_v1_bp = Blueprint('api_v1', __name__)

from . import roster, auth