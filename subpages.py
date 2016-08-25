from puzzleserver import *

# so far only /puzzles is in its own subpage class because it's 
# the only one where the arguments/subdirectories need to be 
# checked programatically
class Puzzles(object):
   
    @cherrypy.expose
    def index(self):
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

            tmpl = env.get_template('solutions.html')
            return tmpl.render(puzzdays=puzzdays, meta_number=META_NUMBER)

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
            return tmpl.render(puzzdays=puzzdays, meta_number=META_NUMBER)

    @cherrypy.expose
    def stats(self, puzzle):
        try:
            with closing(MySQLdb.connect(**mysqldb_config)) as cnx:
                if HUNT_STATUS != "closed" and HUNT_STATUS != "test":
                    cursor = cnx.cursor()
                    check_puzzle_exists = """SELECT puzzle_name FROM puzzles WHERE pdf_name = %s AND TIMESTAMPDIFF(DAY, '{date}', NOW()) >= release_date""".format(date=DATE_OFFSET)
                    cursor.execute(check_puzzle_exists, (puzzle,))

                    res = cursor.fetchone()
                    cursor.close()

                    if res is None:
                        return handle_error()

                cursor = cnx.cursor()
                puzzle_query = """SELECT 
                    puzzles.puzzle_name AS puzzle_name, 
                    puzzles.pdf_name AS pdf_name,
                    solves.team_name AS team_name,
                    DATE_FORMAT(solves.solve_time, "%%W %%b %%e %%H:%%i:%%S") AS solve_time
                    FROM puzzles JOIN solves ON puzzles.puzzle_name = solves.puzzle_name 
                    WHERE puzzles.pdf_name = %s
                    AND solves.solved = 1
                    ORDER BY solve_time""".format(date=DATE_OFFSET)
                cursor.execute(puzzle_query, (puzzle,))
                
                teams = cursor.fetchall()
                cursor.close()
        except MySQLdb.Error as e:
            error_tmpl = env.get_template('error.html')
            return error_tmpl.render(error="Could not fetch data on puzzle " + puzzle)
        
        for team in teams:
            team['escaped_name'] = urlencode({'team': team['team_name']})

        tmpl = env.get_template('puzzle.html')
        return tmpl.render(puzzle=puzzle, solves=len(teams), teams=teams)
            

    @cherrypy.expose
    def hint(self, hint_puzzle=None):
        if hint_puzzle is None:
            return handle_error()
        try:
            with closing(MySQLdb.connect(**mysqldb_config)) as cnx:
                cursor = cnx.cursor()
                hint_query = """SELECT puzzle_name, pdf_name, hint FROM puzzles WHERE pdf_name = %s
                    AND TIMESTAMPDIFF(DAY, '{date}', NOW()) > release_date""".format(date=DATE_OFFSET)
                cursor.execute(hint_query, (hint_puzzle,))
                
                res = cursor.fetchone()
                cursor.close()
        except MySQLdb.Error as e:
            return error_tmpl.render(error="Could not fetch hint for puzzle " + hint_puzzle)
        if res is None:
            return handle_error()
        tmpl = env.get_template('hint.html')
        return tmpl.render(puzzle_name=res['puzzle_name'], hint=res['hint'])

