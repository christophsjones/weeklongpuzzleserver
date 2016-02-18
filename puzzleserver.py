import cherrypy
from cherrypy.lib.static import serve_file
from jinja2 import Environment, FileSystemLoader, Template
import MySQLdb
import MySQLdb.cursors

from contextlib import closing
from collections import OrderedDict
from os import getcwd
import sys

from mysql_config import mysqldb_config

HUNT_STATUS = 'open'
DATE_OFFSET = '2016-02-21 12:00:00'

def guess_autoescape(template_name):
    return True

templateLoader = FileSystemLoader(searchpath=getcwd() + '/templates')
env = Environment(autoescape=guess_autoescape, loader=templateLoader)

day_ids = {1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 4: 'Thursday', 5: 'Meta'}

def standardize_guess(guess):
    alpha_guess = ''.join(e for e in guess if e.isalnum())
    return alpha_guess.upper()

def handle_error(*args, **kwargs):
    cherrypy.response.status = 404
    error_tmpl = env.get_template('error.html')
    return error_tmpl.render(error='Page not found')

class Root(object):

    def sanitize_unicode(resource):
        error_tmpl = env.get_template('error.html')
        def safety_first(*args, **kwargs):
            for arg in args:
                if isinstance(arg, str) or isinstance(arg, unicode):
                    try:
                        arg.decode('utf-8')
                    except UnicodeEncodeError:
                        return error_tmpl.render(error='Input contains invalid characters')
            for kwarg in kwargs.values():
                if isinstance(kwarg, str) or isinstance(kwarg, unicode):
                    try:
                        kwarg.decode('utf-8')
                    except UnicodeEncodeError:
                        return error_tmpl.render(error='Input contains invalid characters')
            return resource(*args, **kwargs)
        return safety_first

    @cherrypy.expose
    def index(self):
        tmpl = env.get_template('home.html')
        return tmpl.render()
    
    @cherrypy.expose
    def home(self):
        tmpl = env.get_template('home.html')
        return tmpl.render()

    @cherrypy.expose
    @sanitize_unicode
    def solve(self, team_name=None, password=None, puzzle_name=None, guess=None):
        if HUNT_STATUS == 'closed':
            closed_tmpl = env.get_template('hunt_closed.html')
            return closed_tmpl.render()

        error_tmpl = env.get_template('error.html')
        try:
            with closing(MySQLdb.connect(**mysqldb_config)) as cnx:
                cursor = cnx.cursor()

                team_query = """SELECT team_name, password, time_created FROM teams ORDER BY time_created"""
                cursor.execute(team_query)
                teams = OrderedDict([(row['team_name'], row) for row in cursor])
                cursor.close()
                
                cursor = cnx.cursor()
                puzz_query = """SELECT 
                    puzzle_name, answer, release_date, number 
                    FROM puzzles WHERE TIMESTAMPDIFF(DAY, '{date}', NOW()) >= release_date 
                    ORDER BY release_date, number""".format(date=DATE_OFFSET)
                testing_puzz_query = """SELECT 
                    puzzle_name, answer, release_date, number 
                    FROM puzzles ORDER BY release_date, number"""
                cursor.execute(testing_puzz_query if HUNT_STATUS == 'testing' else puzz_query)
                puzzles = OrderedDict([(row['puzzle_name'], row) for row in cursor])
                cursor.close()
        except MySQLdb.Error as e:
            return error_tmpl.render(error="Could not fetch puzzle list")

        if not puzzles:
            tmpl = env.get_template('hunt_soon.html')
            return tmpl.render()

        if team_name is not None:
            if puzzle_name == "None":
                return error_tmpl.render(error='Gotta pick a puzzle')

            if team_name not in teams:
                return error_tmpl.render(error='Invalid team name')
            if password != teams[team_name]['password']:
                return error_tmpl.render(error='Invalid password for team ' + team_name)

            if puzzle_name not in puzzles:
                return error_tmpl.render(error='Invalid puzzle name')
            if not isinstance(guess, str) and not isinstance(guess, unicode):
                return error_tmpl.render(error='Invalid guess')

            guess = standardize_guess(guess)

            try:
                with closing(MySQLdb.connect(**mysqldb_config)) as cnx:
                    cursor = cnx.cursor()
                    submit_query = """INSERT INTO submissions (team_name, puzzle_name, guess) VALUES (%s, %s, %s)"""
                    cursor.execute(submit_query, (team_name, puzzle_name, guess))
                    cnx.commit()
                    cursor.close()
            except MySQLdb.Error as e:
                pass # fail to record submissions silently
            
            if guess == puzzles[puzzle_name]['answer']:
                try:
                    with closing(MySQLdb.connect(**mysqldb_config)) as cnx: 
                        cursor = cnx.cursor()
                        check_query = """SELECT team_name, puzzle_name, solved 
                            FROM solves WHERE team_name = %s AND puzzle_name = %s"""
                        cursor.execute(check_query, (team_name, puzzle_name,))
                        for row in cursor:
                            if row['solved']:
                                return error_tmpl.render(error='Answer is correct, but your team already solved this puzzle.')
                        cursor.close()

                        cursor = cnx.cursor()
                        solves_query = """UPDATE solves SET solved = 1 WHERE team_name = %s AND puzzle_name = %s"""
                        cursor.execute(solves_query, (team_name, puzzle_name,))
                        cnx.commit()
                        cursor.close()

                except MySQLdb.Error as e:
                    return error_tmpl.render(error='Could not update team solve stats. Please try submitting again.')

                tmpl = env.get_template('correct.html')
                return tmpl.render(
                    team_name=team_name, 
                    puzzle_name=puzzle_name, 
                    guess=guess, 
                )
            else:
                with closing(MySQLdb.connect(**mysqldb_config)) as cnx:
                    cursor = cnx.cursor()
                    response_query = """SELECT puzzle_name, guess, response 
                        FROM responses WHERE puzzle_name = %s AND guess = %s"""
                    cursor.execute(response_query, (puzzle_name, guess))

                    responses = cursor.fetchall()
                    cursor.close()

                tmpl = env.get_template('incorrect.html')
                return tmpl.render(
                    puzzle_name=puzzle_name,
                    guess=guess,
                    responses=responses,
                )
        else:
            tmpl = env.get_template('solve.html')
            return tmpl.render(puzzles=puzzles.keys())

    @cherrypy.expose
    @sanitize_unicode
    def teams(self, team=None):
        if team is not None:
            try:
                with closing(MySQLdb.connect(**mysqldb_config)) as cnx:
                    cursor = cnx.cursor()
                    solves_query = """SELECT 
                        solves.team_name AS team_name, 
                        puzzles.puzzle_name AS puzzle_name, 
                        IF(solves.solved = 1, solves.solve_time, "") AS solve_time, 
                        puzzles.pdf_name AS pdf_name, 
                        puzzles.release_date AS release_date, 
                        puzzles.number AS number
                        FROM puzzles JOIN solves ON puzzles.puzzle_name = solves.puzzle_name 
                        WHERE team_name = %s AND TIMESTAMPDIFF(DAY, '{date}', NOW()) >= release_date 
                        ORDER BY release_date, number""".format(date=DATE_OFFSET)
                    testing_solves_query = """SELECT 
                        solves.team_name AS team_name, 
                        puzzles.puzzle_name AS puzzle_name, 
                        IF(solves.solved = 1, solves.solve_time, "") AS solve_time, 
                        puzzles.pdf_name AS pdf_name, 
                        puzzles.release_date AS release_date, 
                        puzzles.number AS number 
                        FROM puzzles JOIN solves ON puzzles.puzzle_name = solves.puzzle_name 
                        WHERE team_name = %s ORDER BY release_date, number"""

                    cursor.execute(testing_solves_query if HUNT_STATUS == 'testing' else solves_query, (team,))
                    solves = cursor.fetchall()
                    cursor.close()
            except MySQLdb.Error as e:
                error_tmpl = env.get_template('error.html')
                return error_tmpl.render(error='Could not fetch team information for team ' + team)
            if not solves:
                soon_tmpl = env.get_template("team_soon.html")
                return soon_tmpl.render(team=team)

            days = set([row['release_date'] for row in solves])
            puzzdays = [(day, [row for row in solves if row['release_date'] == day]) for day in days]
            puzzdays = [(day_ids[day], ps) for (day, ps) in puzzdays]

            tmpl = env.get_template('team.html')
            return tmpl.render(team=team, puzzdays=puzzdays)
        else:
            try:
                with closing(MySQLdb.connect(**mysqldb_config)) as cnx:
                    cursor = cnx.cursor()
                    query = """SELECT 
                        teams.team_name AS team_name, 
                        SUM(solves.solved) AS total_solves, 
                        MAX(solves.solve_time) AS solve_time 
                        FROM teams JOIN solves ON teams.team_name = solves.team_name 
                        GROUP BY teams.team_name ORDER BY total_solves DESC, solve_time"""
                    cursor.execute(query)
                    teams = [row for row in cursor]
                    cursor.close()
            except MySQLdb.Error as e:
                error_tmpl = env.get_template('error.html')
                return error_tmpl.render(error='Could not fetch team names')

            tmpl = env.get_template('teams.html')
            return tmpl.render(teams=enumerate(teams))

    @cherrypy.expose
    def puzzles(self, *args):
        if len(args) != 0:
            error_tmpl = env.get_template('error.html')
            if len(args) != 2 or args[0] != 'hint':
                return error_tmpl.render(error="Page not found ")
            else:
                pname = args[1]
                try:
                    with closing(MySQLdb.connect(**mysqldb_config)) as cnx:
                        cursor = cnx.cursor()
                        hint_query = """SELECT puzzle_name, pdf_name, hint FROM puzzles WHERE pdf_name = %s
                            AND TIMESTAMPDIFF(DAY, '{date}', NOW()) > release_date""".format(date=DATE_OFFSET)
                        cursor.execute(hint_query, (pname,))
                        
                        res = cursor.fetchone()
                        cursor.close()
                except MySQLdb.Error as e:
                    return error_tmpl.render(error="Could not fetch hint for puzzle " + pname)
                if res is None:
                    return error_tmpl.render(error="Page not found")
                else:
                    tmpl = env.get_template('hint.html')
                    return tmpl.render(puzzle_name=res['puzzle_name'], hint=res['hint'])
            
        if HUNT_STATUS == "closed" or HUNT_STATUS == "testing":
            try:
                with closing(MySQLdb.connect(**mysqldb_config)) as cnx:
                    cursor = cnx.cursor()
                    testing_query = """SELECT 
                        puzzles.puzzle_name AS puzzle_name, 
                        puzzles.pdf_name AS pdf_name, 
                        puzzles.release_date AS release_date, 
                        puzzles.number AS number, 
                        SUM(solves.solved) AS total_solves
                        FROM puzzles JOIN solves on puzzles.puzzle_name = solves.puzzle_name 
                        GROUP BY solves.puzzle_name ORDER BY release_date, number"""
                    cursor.execute(testing_query)
                    
                    res = cursor.fetchall()
                    cursor.close()
            except MySQLdb.Error as e:
                error_tmpl = env.get_template('error.html')
                return error_tmpl.render(error='Could not fetch puzzles')

            days = set([row['release_date'] for row in res])
            puzzdays = [(day, [row for row in res if row['release_date'] == day]) for day in days]
            puzzdays = [(day_ids[day], ps) for (day, ps) in puzzdays]

            tmpl = env.get_template('solution_puzzles.html')
            return tmpl.render(puzzdays=puzzdays)

        else:
            try:
                with closing(MySQLdb.connect(**mysqldb_config)) as cnx:
                    cursor = cnx.cursor()
                    query = """SELECT 
                        puzzles.puzzle_name AS puzzle_name, 
                        puzzles.pdf_name AS pdf_name, 
                        puzzles.release_date AS release_date, 
                        puzzles.number AS number, 
                        SUM(solves.solved) AS total_solves,
                        TIMESTAMPDIFF(DAY, '{date}', NOW()) > release_date AS hint_avail
                        FROM puzzles JOIN solves ON puzzles.puzzle_name = solves.puzzle_name 
                        WHERE TIMESTAMPDIFF(DAY, '{date}', NOW()) - release_date >= 0
                        GROUP BY solves.puzzle_name ORDER BY release_date, number""".format(date=DATE_OFFSET)
                    cursor.execute(query)
                    res = cursor.fetchall()
                    cursor.close()
            except MySQLdb.Error as e:
                error_tmpl = env.get_template('error.html')
                return error_tmpl.render(error='Could not fetch puzzles')
            if not res:
                soon_tmpl = env.get_template("hunt_soon.html")
                return soon_tmpl.render()

            days = set([row['release_date'] for row in res])
            puzzdays = [(day, [row for row in res if row['release_date'] == day]) for day in days]
            puzzdays = [(day_ids[day], ps) for (day, ps) in puzzdays]

            tmpl = env.get_template('puzzles.html')
            return tmpl.render(puzzdays=puzzdays)

    @cherrypy.expose
    @sanitize_unicode
    def register(self, team_name=None, password=None, password2=None, email=None, name=None):
        if HUNT_STATUS == 'closed':
            closed_tmpl = env.get_template('hunt_closed.html')
            return closed_tmpl.render()

        if team_name is not None:
            error_tmpl = env.get_template('error.html')

            if password is None:
                return error_tmpl.render(error='Invalid password')
            if password == '':
                return error_tmpl.render(error='Password cannot be empty')
            if password != password2:
                return error_tmpl.render(error='Passwords do not match')

            try:
                with closing(MySQLdb.connect(**mysqldb_config)) as cnx:
                    cursor = cnx.cursor()
                    register_query = """INSERT INTO teams (team_name, password, contact_email, contact_name) VALUES (%s, %s, %s, %s)"""
                    cursor.execute(register_query, (team_name, password, email, name))
                    cnx.commit()
                    cursor.close()

                    cursor = cnx.cursor()
                    solves_query = """INSERT INTO solves (team_name, puzzle_name) SELECT %s, puzzle_name FROM puzzles"""
                    cursor.execute(solves_query, (team_name,))
                    cnx.commit()
                    cursor.close()
            
            except MySQLdb.Error as e:
                return error_tmpl.render(error="That team name is already taken. Please choose another.")

            tmpl = env.get_template('register_success.html')
            return tmpl.render(team_name=team_name)
        else:
            tmpl = env.get_template('register.html')
            return tmpl.render()
    
    @cherrypy.expose
    def whatis(self):
        tmpl = env.get_template('whatis.html')
        return tmpl.render()

if __name__ == "__main__":
    if 'prod' in sys.argv:
        cherrypy.config.update({'server.socket_host': '0.0.0.0'})
    cherrypy.config.update({'server.socket_port': 80, 'engine.autoreload.on': True, 'error_page.default': handle_error}) 
    root = Root()
    cherrypy.quickstart(root, '/', 
            {'/' : {'tools.staticdir.root': getcwd() + '/'}, 
             '/puzzles': {'tools.staticdir.on': True, 'tools.staticdir.dir': 'puzzles'}, 
             '/static': {'tools.staticdir.on': True, 'tools.staticdir.dir': 'static'}, 
             '/favicon.ico': {'tools.staticfile.on': True, 'tools.staticfile.filename': '/favicon.ico'}})
