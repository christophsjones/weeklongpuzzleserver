from imports import *
from sqlalchemy import ForeignKey, func

import datetime

db.Model.metadata.reflect(db.engine)

class Puzzles(db.Model):
    __tablename__ = 'puzzles'
    __table_args__ = {'extend_existing': True}

    puzzle_name = db.Column(db.String(50), primary_key=True)
    pdf_name = db.Column(db.String(50))
    answer = db.Column(db.String(50))
    release_date = db.Column(db.Integer)
    number = db.Column(db.Integer)
    hint = db.Column(db.String(1000))

class Responses(db.Model):
    __tablename__ = 'responses'
    __table_args__ = {'extend_existing': True}

    puzzle_name = db.Column(db.String(50), ForeignKey("puzzles.puzzle_name"), primary_key=True)
    guess = db.Column(db.String(50), primary_key=True)
    response = db.Column(db.String(1000))

class Solves(db.Model):
    __tablename__ = 'solves'
    __table_args__ = {'extend_existing': True}

    team_name = db.Column(db.String(50), ForeignKey("teams.team_name"), primary_key=True)
    puzzle_name = db.Column(db.String(50), ForeignKey("puzzles.puzzle_name"), primary_key=True)
    solve_time = db.Column(db.DateTime, default=func.now()) 

class Submissions(db.Model):
    __tablename__ = 'submissions'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True) #SQLAlchemy automatically autoincrements
    team_name = db.Column(db.String(50))
    guess = db.Column(db.String(50))
    puzzle_name = db.Column(db.String(50))
    submit_time = db.Column(db.DateTime, default=func.now())

class Teams(db.Model):
    __tablename__ = 'teams'
    __table_args__ = {'extend_existing': True}

    team_name = db.Column(db.String(50), primary_key=True)
    password = db.Column(db.String(256))
    time_created = db.Column(db.DateTime, default=func.now())
    contact_name = db.Column(db.String(50))
    contact_email = db.Column(db.String(50))
    meta_solved = db.Column(db.Integer, default=0)
    meta_solve_time = db.Column(db.DateTime, default=func.now(), onupdate=func.now()) 
