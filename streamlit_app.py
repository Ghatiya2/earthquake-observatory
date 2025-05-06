import streamlit as st
import pandas as pd
import requests
import altair as alt
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
import pytz
from datetime import datetime
import re

st.set_page_config(page_title="Earthquake Observatory", layout="wide")

st.title("🌍 Real-Time Earthquake Observatory")
st.markdown("Visualizing earthquake patterns from the last 30 days. Powered by [USGS Earthquake API](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php)")

# ------------- Load and Process Data ------------------ #
@st.cache_data(ttl=180)
def load_data():
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson"
    r = requests.get(url)
    data = r.json()["features"]
    
    records = []
    for d in data:
        p = d["properties"]
        c = d["geometry"]["coordinates"]
        if p["mag"] is None or c[2] is None: continue
        records.append({
            "Place": p["place"],
            "Magnitude": p["mag"],
            "Time_UTC": pd.to_datetime(p["time"], unit="ms"),
            "Depth (km)": c[2],
            "Longitude": c[0],
            "Latitude": c[1]
        })

    df = pd.DataFrame(records)
    df["Time_Central"] = df["Time_UTC"].dt.tz_localize("UTC").dt.tz_convert("America/Chicago")
    df["Hour"] = df["Time_Central"].dt.hour
    df["Date"] = df["Time_Central"].dt.date
    df["Year"] = df["Time_Central"].dt.year
    df["Country"] = df["Place"].apply(lambda x: re.search(r",\s*(.*)$", x).group(1) if "," in x else "Unknown")
    return df

df = load_data()

# Sidebar Filters
st.sidebar.header("🔎 Filter")
year_filter = st.sidebar.selectbox("Select Year", sorted(df["Year"].unique(), reverse=True))
country_filter = st.sidebar.multiselect("Select Country", sorted(df["Country"].unique()), default=["Japan", "Indonesia", "Chile"])

filtered_df = df[df["Year"] == year_filter]
if country_filter:
    filtered_df = filtered_df[filtered_df["Country"].isin(country_filter)]

# ------------- Section 1: Live Earthquake Map ------------------ #
st.subheader("1️⃣ Global Earthquake Map (Last 30 Days)")

map = folium.Map(location=[0, 0], zoom_start=2)
marker_cluster = MarkerCluster().add_to(map)

for _, row in filtered_df.iterrows():
    folium.CircleMarker(
        location=[row["Latitude"], row["Longitude"]],
        radius=2 + row["Magnitude"],
        color="crimson",
        fill=True,
        fill_opacity=0.6,
        popup=f"{row['Place']}<br>Mag: {row['Magnitude']}<br>Depth: {row['Depth (km)']} km"
    ).add_to(marker_cluster)

st_data = st_folium(map, width=1000)

# ------------- Section 2: Country-Wise Chart ------------------ #
st.subheader("2️⃣ Earthquakes by Country")
country_chart = (
    alt.Chart(filtered_df)
    .mark_bar()
    .encode(
        y=alt.Y("Country:N", sort='-x'),
        x=alt.X("count():Q", title="Count"),
        color=alt.Color("Country:N", legend=None)
    )
    .properties(height=500, width=700)
)
st.altair_chart(country_chart, use_container_width=True)

# ------------- Section 3: Heatmap (Hour vs Day) ------------------ #
st.subheader("3️⃣ Earthquake Frequency Heatmap (Hour vs Date)")
heat_df = filtered_df.groupby(["Date", "Hour"]).size().reset_index(name="Count")
heatmap = alt.Chart(heat_df).mark_rect().encode(
    x=alt.X("Hour:O"),
    y=alt.Y("Date:T"),
    color=alt.Color("Count:Q", scale=alt.Scale(scheme="reds")),
    tooltip=["Date", "Hour", "Count"]
).properties(width=800, height=500)
st.altair_chart(heatmap, use_container_width=True)

# ------------- Section 4: Depth vs Magnitude ------------------ #
st.subheader("4️⃣ Depth vs Magnitude")
scatter = alt.Chart(filtered_df).mark_circle(size=60).encode(
    x=alt.X("Depth (km):Q"),
    y=alt.Y("Magnitude:Q"),
    color=alt.Color("Magnitude:Q", scale=alt.Scale(scheme="plasma")),
    tooltip=["Place", "Magnitude", "Depth (km)", "Time_Central"]
).interactive().properties(height=400)
st.altair_chart(scatter, use_container_width=True)

# ------------- Section 5: Time Series of Earthquake Count ------------------ #
st.subheader("5️⃣ Earthquake Trend (Hourly Frequency)")
df_ts = filtered_df.set_index("Time_Central").resample("1H").size().reset_index(name="Count")
line = alt.Chart(df_ts).mark_line().encode(
    x=alt.X("Time_Central:T", title="Time"),
    y=alt.Y("Count:Q", title="Earthquake Count")
).properties(height=400)
st.altair_chart(line, use_container_width=True)

# ------------- Final Summary ------------------ #
st.markdown("---")
st.success(f"Total earthquakes shown: {len(filtered_df)} | Max magnitude: {filtered_df['Magnitude'].max():.2f} | Avg depth: {filtered_df['Depth (km)'].mean():.2f} km")

