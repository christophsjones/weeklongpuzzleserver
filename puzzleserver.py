from imports import *
import models

import re
import sys
import datetime
from urllib import urlencode
from collections import OrderedDict
from functools import wraps

from sqlalchemy import exists, func, text
from passlib.apps import custom_app_context as pwd_context

#TODO describe better
HUNT_STATUS = 'open' # open, closed, or testing
DATE_OFFSET = datetime.datetime.strptime('2016-10-20 16:30:00', '%Y-%m-%d %H:%M:%S')
META_NUMBER = 10 # don't change this unless you have >10 puzzles/day

STAFF_CONTACT = 'csj@andrew.cmu.edu'

day_ids = {1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 4: 'Thursday', 5: 'Friday', 6: 'Saturday'}

banhammer = []

#TODO move to utility function file
def standardize_guess(guess):
    alpha_guess = ''.join(e for e in guess if e.isalnum())
    return alpha_guess.upper()

# all string arguments must be sanitized
def sanitize_unicode(resource):
    @wraps(resource)
    def safety_first(*args, **kwargs):
        for arg in request.form.values():
            if isinstance(arg, str) or isinstance(arg, unicode):
                try:
                    arg.decode('utf-8')
                except UnicodeEncodeError:
                    return render_template('error.html', error='Input contains invalid characters')
        for arg in request.args.values():
            if isinstance(arg, str) or isinstance(arg, unicode):
                try:
                    arg.decode('utf-8')
                except UnicodeEncodeError:
                    return render_template('error.html', error='Input contains invalid characters')
        return resource(*args, **kwargs)
    return safety_first
#####

# this should be redundant but whatever better safe than sorry
def secret_until_start(resource):
    @wraps(resource)
    def is_it_christmas_yet(*args, **kwargs):
        if HUNT_STATUS == "open" and (datetime.datetime.now() - DATE_OFFSET).days < 1:
            return render_template("hunt_soon.html")
        return resource(*args, **kwargs)
    return is_it_christmas_yet

def close_when_over(resource):
    @wraps(resource)
    def hunts_over_man(*args, **kwargs):
        if HUNT_STATUS == "closed":
            return render_template('hunt_closed.html')
        return resource(*args, **kwargs)
    return hunts_over_man

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/solve', methods=['GET', 'POST'])
@sanitize_unicode
@secret_until_start
@close_when_over
def solve():

    team_rows = db.session.query(models.Teams).order_by(models.Teams.time_created)
    teams = OrderedDict([(row.team_name, row) for row in team_rows])
    
    puzzle_rows = db.session.query(models.Puzzles).order_by(models.Puzzles.release_date, models.Puzzles.number)
    if HUNT_STATUS == "open":
        time_difference = func.timestampdiff(text('DAY'), DATE_OFFSET, func.now())
        puzzle_rows = puzzle_rows.filter(time_difference >= models.Puzzles.release_date)
    puzzles = OrderedDict([(row.puzzle_name, row) for row in puzzle_rows])

    # no puzzles yet, hunt hasn't started
    if not puzzles:
        return render_template('hunt_soon.html')

    if request.method != "POST": # not making a solve attempt
        return render_template('solve.html', puzzles=puzzles.keys())

    #else making a solve attempt
    team_name = request.form.get('team_name')
    puzzle_name = request.form.get('puzzle_name')
    password = request.form.get('password')
    guess = request.form.get('guess')

    if (
        puzzle_name is None or 
        team_name is None or 
        password is None or
        guess is None or 
        puzzle_name not in puzzles
    ):
        return render_template('error.html', error='Malformed request')

    if team_name in banhammer:
        return render_template('error.html', error="Your team has submitted too many times. Please contact " + STAFF_CONTACT)
    if team_name not in teams:
        return render_template('error.html', error='Invalid team name')
    if not pwd_context.verify(password, teams[team_name].password): 
        return render_template('error.html', error='Invalid password for team ' + team_name)

    guess = standardize_guess(guess)

    time_difference = func.timestampdiff(text('MINUTE'), models.Submissions.submit_time, func.now())
    recent_submissions = db.session.query(models.Submissions).filter_by(team_name=team_name).filter(time_difference <= 1).count()
    if recent_submissions >= 100:
        banhammer.append(team_name)

    submission = models.Submissions(team_name=team_name, guess=guess, puzzle_name=puzzle_name)
    db.session.add(submission)
    db.session.commit()
    
    template_kwargs = {'team_name': team_name, 'puzzle_name': puzzle_name, 'guess': guess}
    if guess == puzzles[puzzle_name].answer:
        if db.session.query(exists().where(models.Solves.team_name == team_name).where(models.Solves.puzzle_name == puzzle_name)).scalar():
            template_kwargs['response'] = "Answer is correct, but your team already soved this puzzle."
        else:
            solved = models.Solves(team_name=team_name, puzzle_name=puzzle_name)
            db.session.add(solved)
            if puzzles[puzzle_name].number == META_NUMBER:
                template_kwargs['meta_solved'] = True
                meta_solved = models.Teams(team_name=team_name, meta_solved=1)
                db.session.merge(meta_solved)
            db.session.commit()

        return render_template('correct.html', **template_kwargs)
    else:
        responses = db.session.query(models.Responses).filter_by(puzzle_name=puzzle_name, guess=guess)
        template_kwargs['responses'] = responses
        return render_template('incorrect.html', **template_kwargs)

@app.route('/teams', methods=['GET'])
@sanitize_unicode
def teams():
    team_name = request.args.get('team')
    if team_name is not None: # display stats for a specific team
        if not db.session.query(exists().where(models.Teams.team_name == team_name)).scalar():
            return render_template('error.html', error='No information found for team ' + team_name)

        team_solutions = db.session.query(models.Solves).filter_by(team_name=team_name).subquery()
        solved_rows = db.session.query(models.Puzzles, team_solutions).outerjoin(team_solutions).order_by(models.Puzzles.release_date, models.Puzzles.number)
        if HUNT_STATUS == 'open':
            time_difference = func.timestampdiff(text('DAY'), DATE_OFFSET, func.now())
            solved_rows = solved_rows.filter(time_difference >= models.Puzzles.release_date)

        if not solved_rows: # hunt hasn't started, but team exists
            return render_template("team_soon.html")

        days = set([row.Puzzles.release_date for row in solved_rows])
        puzzdays = [(day, [row for row in solved_rows if row.Puzzles.release_date == day]) for day in days]
        puzzdays = [(day_ids[day], ps) for (day, ps) in puzzdays]

        return render_template('team.html', team=team_name, puzzdays=puzzdays, meta_number=META_NUMBER)

    else: 
        time_difference = func.timestampdiff(text('SECOND'), func.timestampadd(text('DAY'), models.Puzzles.release_date, DATE_OFFSET), models.Solves.solve_time)
        total_solves = func.count(models.Solves).label('total_solves')
        avg_solve_time = func.avg(time_difference).label('avg_solve_time')
        team_rows = db.session.query(models.Teams, total_solves, avg_solve_time).outerjoin(models.Solves).outerjoin(models.Puzzles).group_by(models.Teams).order_by(total_solves.desc(), avg_solve_time)

        # TODO puzzle stats still include non-CMU teams
        # only rank teams with CMU email addresses
        cmu_email = re.compile(r'\A(\w|[-.+%])+@(\w|\.)*cmu.edu\Z')
        teams = [row for row in team_rows if row.Teams.contact_email is not None and cmu_email.match(row.Teams.contact_email)]

        for row in teams: # put team names in URLs properly
            row.Teams.escaped_name = urlencode({'team': row.Teams.team_name})

        return render_template('teams.html', teams=teams)

@app.route('/registerteam', methods=['POST'])
@sanitize_unicode
@close_when_over
def registerteam():
    team_name = request.form.get('team_name')
    password = request.form.get('password')
    password2 = request.form.get('password2')
    email = request.form.get('email')
    name = request.form.get('name')

    if team_name is None or password is None or password2 is None:
        return render_template('error.html', error="Malformed registration")

    if password == '':
        return render_template('error.html', error='Password cannot be empty')
    if password != password2:
        return render_template('error.html', error='Passwords do not match')
    
    if db.session.query(exists().where(models.Teams.team_name==team_name)).scalar():
        return render_template('error.html', error="That team name is already taken. Please choose another")

    new_team = models.Teams(team_name=team_name, password=pwd_context.encrypt(password), contact_email=email, contact_name=name)
    db.session.merge(new_team)
    db.session.commit()
    return render_template('register_success.html')

@app.route('/register')
@sanitize_unicode
@close_when_over
def register(): 
    return render_template('register.html')

@app.route('/whatis')
def whatis():
    return render_template('whatis.html')

@app.route('/puzzles')
@secret_until_start
def puzzles():
    #TODO count only CMU teams?
    puzzle_rows = db.session.query(models.Puzzles, func.count(models.Solves).label('solves')).join(models.Solves).group_by(models.Puzzles).order_by(models.Puzzles.release_date, models.Puzzles.number)
    if HUNT_STATUS == "open":
        time_difference = func.timestampdiff(text('DAY'), DATE_OFFSET, func.now())
        puzzle_rows = puzzle_rows.filter(time_difference >= models.Puzzles.release_date)

    if not puzzle_rows:
        return render_template("hunt_soon.html")

    days = set([row.Puzzles.release_date for row in puzzle_rows])
    puzzdays = [(day, [row for row in puzzle_rows if row.Puzzles.release_date == day]) for day in days]
    puzzdays = [(day_ids[day], ps) for (day, ps) in puzzdays]

    if HUNT_STATUS == "open":
        return render_template('puzzles.html', puzzdays=puzzdays, meta_number=META_NUMBER)

    return render_template('solutions.html', puzzdays=puzzdays, meta_number=META_NUMBER)

@app.route('/puzzles/stats/<string:pdf_name>')
@secret_until_start
def stats(pdf_name):
    puzzle_rows = db.session.query(models.Puzzles).filter_by(pdf_name=pdf_name)
    if HUNT_STATUS == "open":
        time_difference = func.timestampdiff(text('DAY'), DATE_OFFSET, func.now())
        puzzle_rows = puzzle_rows.filter(time_difference >= models.Puzzles.release_date)
    puzzle = puzzle_rows.first()
    
    if puzzle is None:
        return render_template('error.html', error='Unknown puzzle name')
    puzzle_name = puzzle.puzzle_name

    solve_rows = db.session.query(models.Solves).filter_by(puzzle_name=puzzle_name).order_by(models.Solves.solve_time)

    for row in solve_rows:
        row.escaped_name = urlencode({'team': row.team_name})
        
    return render_template('puzzle.html', puzzle=puzzle_name, solves=solve_rows.count(), teams=solve_rows) 

@app.route('/puzzles/hint/<string:pdf_name>')
@secret_until_start
def hint(pdf_name):
    puzzle_rows = db.session.query(models.Puzzles).filter_by(pdf_name=pdf_name)
    if HUNT_STATUS == "open":
        time_difference = func.timestampdiff(text('DAY'), DATE_OFFSET, func.now())
        puzzle_rows = puzzle_rows.filter(time_difference > models.Puzzles.release_date)
    puzzle = puzzle_rows.first()

    if not puzzle:
        return render_template('error.html', error='Unknown puzzle name')
    return render_template('hint.html', puzzle_name=puzzle.puzzle_name, hint=puzzle.hint)


if __name__ == "__main__":
    if 'prod' in sys.argv:
        app.run(host='0.0.0.0', port=8080, debug=False)
    else:
        app.run(debug=True)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', errpr='Page not found'), 404
