# make a streamlit site
import streamlit as st

input_player = st.text_input(
    "input player", "https://www.pgstats.com/melee/player/Kevbot?id=S12293"
)
st.write("Current PGStats link is", input_player)

operation = st.radio("What's your favorite movie genre", ("add", "remove", "combine"))

st.table([1, 2, 3, 4])
