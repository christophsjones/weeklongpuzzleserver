import MySQLdb.cursors

mysqldb_config = {
    'user': 'pserver',
    'passwd': 'YOUR_PASSWORD_HERE',
    'db': 'puzzleserver',
    'cursorclass': MySQLdb.cursors.DictCursor,
    }
