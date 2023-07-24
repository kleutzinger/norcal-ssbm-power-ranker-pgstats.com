# Melee Rankings Scraper for PGStats

- This gets all melee sets from the [a google sheet of strong local players](https://docs.google.com/spreadsheets/d/1EQmk2ElCjlC6LiYrmqBcjxpAHL49PTgJRuOwcY1MlPY/edit#gid=0) then from pgstats.com within the ranking period.
- This is currently hardcoded for the norcal super smash bros melee scene

It outputs a table in google sheets![](./img/2023-06-19-00-43-58.png)

## The way I run this

```sh
# make venv first
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt

# get data from pgstats, put it in our db (redis)
python src/scrape.py
# analyze the data in redis, write it to google sheets
python src/parse.py
```

## Other Notes

- If a tournament is missing from pgstats, you can request it to be added here: [data form](https://docs.google.com/forms/d/e/1FAIpQLScKXIoIBxnh0NmYtxto5_kkkuJybI9-Ipss2e-RdX4Bx2GHkg/viewform?usp=sf_link) . This is taken from the footer of [pgstats](https://pgstats.com).
- Only in-person tournaments are considered valid for rankings. This is an implementation detail that can be changed pretty easily. This is rankings currently work, however.

## Todo:

- [x] rewrite combined player ids when adding sets to the database
- [x] scrape player list from a google sheet
- [x] trim down player model by removing results data (keep the profile data, though (maybe rename to metadata))
- [x] write player data to redis
- [x] write badge data to redis
- [x] write data to google sheet
- [ ] parse data to web ui
- [x] scrape on deploy
- [ ] scrape on request (button)
- [x] deploy something to dokku
- [x] scrape on cron on dokku
- [ ] enforce better ordering of ranked players in sheets. i could try some heuristics like the order they appear in the google sheet. The ranking data from pgstats isn't too helpful.
- [x] color code / format the h2h sheet
