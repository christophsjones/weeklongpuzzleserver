# weeklongpuzzleserver
Puzzlehunt server for SCS Day 2016.
Influenced by the design of Australian puzzlehunt websites such as http://www.maths.usyd.edu.au/ub/sums/puzzlehunt/2015/main

Short and (hopefully) easy to use and improve puzzlehunt site.

Things you need:
- MySQL (apt-get install mysql)
- Flask+SQLAlchemy (pip install -r requirements.txt)

### Initial Setup

Need a server? I had FREE student DigitalOcean credit and Namecheap credit from [Github](https://education.github.com/pack).

Install the packages above. When you install MySQL, make sure to set your own password for the “root” user (default is either ‘’ or ‘root’, I forget). 

Now,  navigate to the root of this repo. The database config has private password information you need to decide on. Remove the "PUBLIC_" prefix from PUBLIC_mysql_config.py and replace <username> and <password> with MySQL fields, either <username> = "root" or make a new one.

Start the server for the first time to set up the database:

```
python puzzleserver.py
```

You should now be able to access the page at http://localhost:5000. 

To set up the included test puzzles in the database, run
```
mysql -u root -p < db_examples
```

Change the contact_name in puzzleserver.py to your own email address!!

## Running a Hunt

If you want to get the signups going and add puzzles later go to 5. Hit start.

### 1. Add puzzles

Puzzles are expected to be a single PDF. For each puzzle, you'll need to insert into the "puzzles" table as in db_examples. Here's a decsription of each field: 
 - name: full puzzle name
 - pdf_name: short puzzle name, name of PDF at /puzzles/<pdf_name>.pdf. Advice: use puzzle name with spaces removed and camelcase
 - answer: puzzle answer, should only be CAPITAL ALPHANUMERICS (NO SPACES!). Submitted answers are converted to CAPITALS and all non-alphanum are removed.
 - release_date: which day to release on, 1 = Monday, 4 = Thursday
 - number: which number puzzle this is for the day. If two puzzles are released on Monday, the first should have number = 1, the second number = 2. THE META PUZZLE SHOULD HAVE NUMBER = 10 (= default META_NUMBER in puzzleserver.py)
 - hint: it's not in db_examples because there are no hints for those puzzles, but to add hints you insert the hint as a string into the "hint" column (leave the field null if no hint). Hints are released the next day. Make them **really** useful b/c this puzzlehunt is supposed to be fun

Move the puzzle PDF named <pdf_name>.pdf to /puzzles or /puzzleshidden. NOTE THAT BEING IN /puzzles MAKES THE FILE VISIBLE TO ANYONE WHO KNOWS/CAN GUESS THE PUZZLE PDF NAME. YES THIS MEANS YOU SHOULD MOVE THE PUZZLE PDFS FROM /puzzleshidden ONLY SHORTLY BEFORE THE DAY'S PUZZLE RELEASE. YES THIS IS A HACK AND IS IN THE TODO LIST.

### 2. Add responses

For some guesses you'll likely want custom responses. Insert all of these into the "responses" table.

### 3. Add plot

Plot is supported as a single PDF as /puzzles/<day>_plot.pdf e.g. /puzzles/Monday_plot.pdf. SEE ABOVE ABOUT NOT MOVING UNTIL RELEASE. If no plot is found no link will appear.

Add some meta solve congratulation text in /templates/correct.html sometime before meta release (this will appear after a correct meta solve). We also put this into an epilogue PDF at /puzzles/epilogue.pdf. This will be accessible to all after HUNT_STATUS = 'closed'.

### 4. Add solutions

Put solutions in /puzzles. AS ABOVE THEY WILL BE IMMEDIATELY VISIBLE TO ANYONE WHO KNOWS THE URL, SO DON'T PUT THEM THERE UNTIL HUNT_STATUS = 'closed'. Once HUNT_STATUS = 'closed' the solutions will be linked from the "Puzzles" page.

### 5. Hit start

In puzzleserver.py set the DATE_OFFSET to the Sunday before the hunt. Set HUNT_STATUS = 'open' (DON'T LEAVE IT IN TESTING!). No puzzles will be visible until that Monday.

You can run in production mode e.g. on port 80 and serving to Internet by 
```
python puzzleserver.py prod
```

In fact you probably want to run it in background (or use screen) so that it doesn't quit if you logout of server. Background method:
```
nohup python puzzleserver.py prod &
```

The server autoreloads if you save a file. (so ya know don't save a syntax error haha who would do that).

### 6. Hit stop

When the hunt is over, change HUNT_STATUS = 'closed'. THIS RELEASES SOLUTIONS SO DON'T PREEMPTIVELY DO IT. If you need to stop everything set DATE_OFFSET to sometime in the far future. Also this releases epilogue. 

### Miscellaneous: the banhammer

If a team tries to brute force solve by submitting over 100 queries in a minute, no more submissions from that team will be allowed (and team_name will be stored in "banhammer" list in puzzleserver.py). To free them up, just resave puzzleserver.py (this reloads the server and resets "banhammer = []"). Or manually add teams you don't like to this list.

## TODO
- hunt_soon.html should use DATE_OFFSET + 1 for start date
- If tables are empty there can be bugs
- Updating a row in “teams” table updates the meta_solve_time :(
- make it so that you don't have to manually move puzzle PDFs each day
- add SSL

## Things that would make your puzzlehunt more fun
- allow more customization of team info. E.g. a short blurb or a picture are displayed on your team page! :) (Flask sessions make this easy)
- add plot/pictures onto the puzzle page directly, or have a separate plot tab
- change the CSS/theme


