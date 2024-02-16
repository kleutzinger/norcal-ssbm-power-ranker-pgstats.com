# Melee Rankings Scraper for PGStats

- This gets all melee sets from [a google sheet list of strong local players](https://docs.google.com/spreadsheets/d/1EQmk2ElCjlC6LiYrmqBcjxpAHL49PTgJRuOwcY1MlPY/edit#gid=0). Then we scrape all their data from pgstats.com within the ranking period.
- We parse the data and write to this [output sheet](https://docs.google.com/spreadsheets/d/1-rj-k-gLWUize_fYmlGVH0zFkBLa14U6nMMonNEkraE/edit#gid=715852685)
- This is currently hardcoded for the norcal super smash bros melee scene

It outputs a table in google sheets![](./img/2023-06-19-00-43-58.png)

## The way I run this

```sh
# make venv first
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt

# get data from pgstats, put write it to individual json files
python src/scrape.py
# analyze the jsons, write it to google sheets
python src/parse.py
```

## Other Notes

- All data is pulled from pgstats. If a tournament is missing from pgstats, you can request it to be added here: [data form](https://docs.google.com/forms/d/e/1FAIpQLScKXIoIBxnh0NmYtxto5_kkkuJybI9-Ipss2e-RdX4Bx2GHkg/viewform?usp=sf_link) . This is taken from the footer of [pgstats](https://pgstats.com).
- Only in-person tournaments are considered valid for rankings. This is an implementation detail that can be changed pretty easily to include online.
- I deploy this code to my Dokku instance and it re-scrapes every 6 hours. Pgstats usually updates pretty promptly, so new tournaments should be in my sheet the morning after the real event.

## Todo:

- [x] rewrite combined player ids when adding sets to the database
- [x] scrape player list from a google sheet
- [x] trim down player model by removing results data (keep the profile data, though (maybe rename to metadata))
- [x] write player data to redis
- [x] write badge data to redis
- [x] write data to google sheet
- [x] scrape on deploy
- [ ] scrape on request (button)
- [x] deploy something to dokku
- [x] scrape on cron on dokku
- [x] enforce better ordering of ranked players in sheets. i could try some heuristics like the order they appear in the google sheet. The ranking data from pgstats isn't too helpful.
- [ ] in main h2h comment header, also count number of uniquee tournaments between players
  - [ ] make it even better ordering. (clone a certain player's badge count -1?)
  - [ ] with rolling subtractive count for multi-copies
- [x] color code / format the h2h sheet
- [x] color code / format wins/losses sheet
- [x] ignore irrelevant tournaments (like side events). Taken from list of ids in the google sheet
- [x] show every tournament considered
- [x] make meta stats like
  - [ ] biggest win streak
  - [ ] bracket demons
  - [ ] number of ranked players played
  - [ ] record vs ranked players
  - [ ] unique players played
  - [ ] unique ranked players played
  - [ ] non-sheeted players with most wins
- [ ] figure out a way to globally order tournament sets
- [ ] turn players into links
- [ ] link to readme (or how to read sheet.md) in sheet
- [x] look into adding comments on cells to list when players played
  - [x] notes in h2h
  - [x] notes in wins/losses
  - [x] tournament set history
  - [x] total game count
