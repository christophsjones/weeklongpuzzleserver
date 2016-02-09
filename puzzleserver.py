import cherrypy
from cherrypy.lib.static import serve_file
from jinja2 import Environment, FileSystemLoader, Template
import MySQLdb
import MySQLdb.cursors

from contextlib import closing
from collections import OrderedDict
from os import getcwd

mysqldb_config = {
        'user': 'pserver',
        'passwd': 'nohints',
        'db': 'puzzleserver',
        'cursorclass': MySQLdb.cursors.DictCursor,
        }

def guess_autoescape(template_name):
    return True

templateLoader = FileSystemLoader(searchpath=getcwd() + '/templates')
env = Environment(autoescape=guess_autoescape, loader=templateLoader)

day_ids = {2: 'Monday', 3: 'Tuesday', 4: 'Wednesday', 5: 'Meta'}

class Root(object):
    cnx = MySQLdb.connect(**mysqldb_config) 

    @cherrypy.expose
    def index(self):
        tmpl = env.get_template('home.html')
        return tmpl.render()
    
    @cherrypy.expose
    def home(self):
        tmpl = env.get_template('home.html')
        return tmpl.render()

    @cherrypy.expose
    def solve(self, team_name=None, password=None, puzzle_name=None, guess=None):
        with closing(self.cnx.cursor()) as cursor:
            team_query = """SELECT team_name, password, total_solves, time_created FROM teams ORDER BY time_created"""
            cursor.execute(team_query)
            teams = OrderedDict([(row['team_name'], row) for row in cursor])
            
            puzz_query = """SELECT puzzle_name, answer, release_date, number FROM puzzles ORDER BY release_date, number"""
            cursor.execute(puzz_query)
            puzzles = OrderedDict([(row['puzzle_name'], row) for row in cursor])

        if team_name is not None:
            error_tmpl = env.get_template('error.html')
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
            
            with closing(self.cnx.cursor()) as cursor:
                already_query = """SELECT team_name, puzzle_name, solved FROM solves WHERE team_name = %s AND puzzle_name = %s"""
                cursor.execute(already_query, (team_name, puzzle_name))
                for row in cursor:
                    if row['solved'] == 1:
                        return error_tmpl.render(error='Your team already solved this puzzle!')

            with closing(self.cnx.cursor()) as cursor:
                submit_query = """INSERT INTO submissions (team_name, puzzle_name, guess) VALUES (%s, %s, %s)"""
                cursor.execute(submit_query, (team_name, puzzle_name, guess))
                self.cnx.commit()
            
            guess = guess.upper()
            if guess == puzzles[puzzle_name]['answer']:
                with closing(self.cnx.cursor()) as cursor: 
                    total_solves_query = """UPDATE teams SET total_solves = total_solves + 1 WHERE team_name = %s"""
                    cursor.execute(total_solves_query, (team_name))
                    solves_query = """UPDATE solves SET solved = 1 WHERE team_name = %s AND puzzle_name = %s"""
                    cursor.execute(solves_query, (team_name, puzzle_name))
                    self.cnx.commit()

                tmpl = env.get_template('correct.html')
                return tmpl.render(
                    team_name=team_name, 
                    puzzle_name=puzzle_name, 
                    guess=guess, 
                    total_solves=teams[team_name]['total_solves'] + 1
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
        with closing(self.cnx.cursor()) as cursor:
            query = """SELECT team_name, total_solves, time_last_solve FROM teams ORDER BY total_solves DESC, time_last_solve"""
            cursor.execute(query)
            teams = [(row['team_name'], row['total_solves']) for row in cursor]

        tmpl = env.get_template('teams.html')
        return tmpl.render(teams=enumerate(teams))

    @cherrypy.expose
    def puzzles(self):
        with closing(self.cnx.cursor()) as cursor:
            query = """SELECT puzzle_name, release_date FROM puzzles"""
            cursor.execute(query)
            
            res = cursor.fetchall()

        days = set([row['release_date'] for row in res])
        puzzdays = [(day, [row['puzzle_name'] for row in res if row['release_date'] == day]) for day in days]
        puzzdays = [(day_ids[day], ps) for (day, ps) in puzzdays]

        tmpl = env.get_template('puzzles.html')
        return tmpl.render(puzzdays=puzzdays)

    @cherrypy.expose
    def register(self, team_name=None, password=None, password2=None):
        if team_name is not None:
            error_tmpl = env.get_template('error.html')
            with closing(self.cnx.cursor()) as cursor:
                query = """SELECT team_name FROM teams WHERE team_name = %s"""
                cursor.execute(query, (team_name,))
                if any(True for _ in cursor):
                    return error_tmpl.render(error='Team name already taken')

            if password is None:
                return error_tmpl.render(error='Invalid password')
            if password == '':
                return error_tmpl.render(error='Password cannot be empty')
            if password != password2:
                return error_tmpl.render(error='Passwords do not match')

            with closing(self.cnx.cursor()) as cursor:
                register_query = """INSERT INTO teams (team_name, password) VALUES (%s, %s)"""
                cursor.execute(register_query, (team_name, password,))
                solves_query = """INSERT INTO solves (team_name, puzzle_name) SELECT %s, puzzle_name FROM puzzles"""
                cursor.execute(solves_query, (team_name,))
                self.cnx.commit()

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
    cherrypy.config.update({'server.socket_port': 8000, 'engine.autoreload.on': True }) 
    root = Root()
    cherrypy.quickstart(root, '/', {'/' : {'tools.staticdir.root': getcwd() + '/'}, '/puzzles': {'tools.staticdir.on': True, 'tools.staticdir.dir': 'puzzles'}, '/static': {'tools.staticdir.on': True, 'tools.staticdir.dir': 'static'}})
