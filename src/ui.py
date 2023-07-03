# make a streamlit site
import streamlit as st
from main import refresh_db, all_ids, get_player_results

input_player = st.text_input(
    "input player", "https://www.pgstats.com/melee/player/Kevbot?id=S12293"
)
st.write("Current PGStats link is", input_player)

operation = st.radio("What's your favorite movie genre", ("add", "remove", "combine"))


if st.button("refresh db"):
    st.write("refreshing db")
    refresh_db()
else:
    st.write("Goodbye")

for id in all_ids():
    print(id)
    # st.json(get_player_results(id))
    res = get_player_results(id)
    st.write(id)
