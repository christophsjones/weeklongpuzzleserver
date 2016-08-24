import MySQLdb.cursors

mysqldb_config = {
    'user': 'pserver',
    'passwd': 'nohints',
    'db': 'puzzleserver',
    'cursorclass': MySQLdb.cursors.DictCursor,
    }
