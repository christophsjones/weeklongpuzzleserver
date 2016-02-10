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

def guess_autoescape(template_name):
    return True

templateLoader = FileSystemLoader(searchpath=getcwd() + '/templates')
env = Environment(autoescape=guess_autoescape, loader=templateLoader)

day_ids = {2: 'Monday', 3: 'Tuesday', 4: 'Wednesday', 5: 'Meta'}

class Root(object):
    cnx = MySQLdb.connect(**mysqldb_config) 

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
        error_tmpl = env.get_template('error.html')

        try:
            with closing(self.cnx.cursor()) as cursor:
                team_query = """SELECT team_name, password, time_created FROM teams ORDER BY time_created"""
                cursor.execute(team_query)
                teams = OrderedDict([(row['team_name'], row) for row in cursor])
                
                puzz_query = """SELECT puzzle_name, answer, release_date, number FROM puzzles ORDER BY release_date, number"""
                cursor.execute(puzz_query)
                puzzles = OrderedDict([(row['puzzle_name'], row) for row in cursor])
        except MySQLdb.Error as e:
            return error_tmpl.render(error="Could not fetch puzzle list")

        if team_name is not None:
            if team_name == "None":
                return error_tmpl.render(error='Gotta pick a team')
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

            guess = guess.upper()

            try:
                with closing(self.cnx.cursor()) as cursor:
                    submit_query = """INSERT INTO submissions (team_name, puzzle_name, guess) VALUES (%s, %s, %s)"""
                    cursor.execute(submit_query, (team_name, puzzle_name, guess))
                    self.cnx.commit()
            except MySQLdb.Error as e:
                pass # fail to record submissions silently
            
            if guess == puzzles[puzzle_name]['answer']:
                try:
                    with closing(self.cnx.cursor()) as cursor: 
                        check_query = """SELECT team_name, puzzle_name, solved FROM solves WHERE team_name = %s AND puzzle_name = %s"""
                        cursor.execute(check_query, (team_name, puzzle_name,))
                        for row in cursor:
                            if row['solved']:
                                return error_tmpl.render(error='Answer is correct, but your team already solved this puzzle.')

                        solves_query = """UPDATE solves SET solved = 1 WHERE team_name = %s AND puzzle_name = %s"""
                        cursor.execute(solves_query, (team_name, puzzle_name,))
                        self.cnx.commit()

                except MySQLdb.Error as e:
                    return error_tmpl.render(error='Could not update team solve stats. Please try submitting again.')

                tmpl = env.get_template('correct.html')
                return tmpl.render(
                    team_name=team_name, 
                    puzzle_name=puzzle_name, 
                    guess=guess, 
                )
            else:
                tmpl = env.get_template('incorrect.html')
                return tmpl.render(
                    puzzle_name=puzzle_name,
                    guess=guess
                )
        else:
            tmpl = env.get_template('solve.html')
            return tmpl.render(puzzles=puzzles.keys(), teams=teams.keys())

    @cherrypy.expose
    def teams(self):
        try:
            with closing(self.cnx.cursor()) as cursor:
                query = """SELECT teams.team_name AS team_name, SUM(solves.solved) AS total_solves, teams.time_last_solve AS time_last_solve FROM teams JOIN solves ON teams.team_name = solves.team_name GROUP BY teams.team_name ORDER BY total_solves DESC, time_last_solve"""
                cursor.execute(query)
                teams = [(row['team_name'], row['total_solves']) for row in cursor]
        except MySQLdb.Error as e:
            error_tmpl = env.get_template('error.html')
            return error_tmpl.render('Could not fetch team names')

        tmpl = env.get_template('teams.html')
        return tmpl.render(teams=enumerate(teams))

    @cherrypy.expose
    def puzzles(self):
        try:
            with closing(self.cnx.cursor()) as cursor:
                query = """SELECT puzzle_name, release_date FROM puzzles"""
                cursor.execute(query)
                
                res = cursor.fetchall()
        except MySQLdb.Error as e:
            error_tmpl = env.get_template('error.html')
            return error_tmpl.render('Could not fetch puzzles')

        days = set([row['release_date'] for row in res])
        puzzdays = [(day, [row['puzzle_name'] for row in res if row['release_date'] == day]) for day in days]
        puzzdays = [(day_ids[day], ps) for (day, ps) in puzzdays]

        tmpl = env.get_template('puzzles.html')
        return tmpl.render(puzzdays=puzzdays)

    @cherrypy.expose
    @sanitize_unicode
    def register(self, team_name=None, password=None, password2=None):
        if team_name is not None:
            error_tmpl = env.get_template('error.html')

            if password is None:
                return error_tmpl.render(error='Invalid password')
            if password == '':
                return error_tmpl.render(error='Password cannot be empty')
            if password != password2:
                return error_tmpl.render(error='Passwords do not match')

            try:
                with closing(self.cnx.cursor()) as cursor:
                    register_query = """INSERT INTO teams (team_name, password) VALUES (%s, %s)"""
                    cursor.execute(register_query, (team_name, password,))
                    self.cnx.commit()
                    solves_query = """INSERT INTO solves (team_name, puzzle_name) SELECT %s, puzzle_name FROM puzzles"""
                    cursor.execute(solves_query, (team_name,))
                    self.cnx.commit()
            
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
    cherrypy.config.update({'server.socket_port': 5104, 'engine.autoreload.on': True }) 
    root = Root()
    cherrypy.quickstart(root, '/', {'/' : {'tools.staticdir.root': getcwd() + '/'}, '/puzzles': {'tools.staticdir.on': True, 'tools.staticdir.dir': 'puzzles'}, '/static': {'tools.staticdir.on': True, 'tools.staticdir.dir': 'static'}})
