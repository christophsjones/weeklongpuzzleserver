from flask import Flask, request, render_template, redirect, url_for, abort, send_from_directory
app = Flask(__name__)

from flask_sqlalchemy import SQLAlchemy
app.config.from_object('mysql_config')
db = SQLAlchemy(app)
