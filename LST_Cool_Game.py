import streamlit as st
import pandas as pd
import numpy as np
import rasterio
import plotly.graph_objects as go


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Can You Make Dhaka Cooler?",
    page_icon="🌡️",
    layout="wide"
)


# ============================================================
# GAME SETTINGS
# ============================================================

MAX_TURNS = 10

HEAT_THRESHOLD = 35.0

TARGET_REDUCTION = 0.30


# ============================================================
# CAMPAIGN LEVELS
# ============================================================

LEVELS = [
    {
        "level": 1,
        "year": 2025,
        "difficulty": "🟢 Easy",
        "budget": 20
    },
    {
        "level": 2,
        "year": 2017,
        "difficulty": "🟢 Easy",
        "budget": 20
    },
    {
        "level": 3,
        "year": 2018,
        "difficulty": "🟢 Easy",
        "budget": 20
    },
    {
        "level": 4,
        "year": 2016,
        "difficulty": "🟢 Easy",
        "budget": 20
    },
    {
        "level": 5,
        "year": 2022,
        "difficulty": "🟡 Medium",
        "budget": 25
    },
    {
        "level": 6,
        "year": 2019,
        "difficulty": "🟡 Medium",
        "budget": 25
    },
    {
        "level": 7,
        "year": 2024,
        "difficulty": "🟡 Medium",
        "budget": 25
    },
    {
        "level": 8,
        "year": 2015,
        "difficulty": "🟠 Hard",
        "budget": 35
    },
    {
        "level": 9,
        "year": 2021,
        "difficulty": "🟠 Hard",
        "budget": 35
    },
    {
        "level": 10,
        "year": 2023,
        "difficulty": "🔴 Very Hard",
        "budget": 50
    },
    {
        "level": 11,
        "year": 2020,
        "difficulty": "🔥 Final Challenge",
        "budget": 50
    }
]


# ============================================================
# INTERVENTIONS
# ============================================================

INTERVENTIONS = {

    "🌳 Tree": {
        "cost": 5,
        "radius": 2.0,
        "effect": 1.0,
        "description":
            "Low cost. Moderate cooling over a wider area."
    },

    "🌿 Green Space": {
        "cost": 15,
        "radius": 3.0,
        "effect": 1.5,
        "description":
            "Expensive, but creates a larger cooling zone."
    },

    "🏠 Cool Roof": {
        "cost": 10,
        "radius": 1.5,
        "effect": 1.2,
        "description":
            "Strong local cooling with a smaller influence area."
    }
}


# ============================================================
# FILE PATHS
# ============================================================

MASTER_CSV = (
    r"E:\Dhaka_Cool_Game\Dhaka_Cool_Game_Master.csv"
)

REFERENCE_RASTER = (
    r"E:\Dhaka_Cool_Game\Dhaka_LST_2020_Mar_Sep.tif"
)


# ============================================================
# LOAD MASTER CSV
# ============================================================

master_data = pd.read_csv(MASTER_CSV)


# ============================================================
# LOAD REFERENCE RASTER
#
# Used only for the spatial grid geometry.
# The actual LST values for each level come from the
# corresponding year column in the master CSV.
# ============================================================

with rasterio.open(REFERENCE_RASTER) as src:

    raster = src.read(1).astype(float)

    transform = src.transform

    nodata = src.nodata

    rows, cols = raster.shape


if nodata is not None:

    raster[raster == nodata] = np.nan


# ============================================================
# CREATE BASE SPATIAL GRID
# ============================================================

grid = []

cell_number = 0


for row in range(rows):

    for col in range(cols):

        lst = raster[row, col]

        if np.isnan(lst):
            continue

        if cell_number >= len(master_data):
            continue

        master_row = master_data.iloc[cell_number]

        x1 = transform.c + col * transform.a
        x2 = x1 + transform.a

        y1 = transform.f + row * transform.e
        y2 = y1 + transform.e

        grid.append(
            {
                "cell_id":
                    master_row["cell_id"],

                "latitude":
                    master_row["latitude"],

                "longitude":
                    master_row["longitude"],

                "min_lon":
                    min(x1, x2),

                "max_lon":
                    max(x1, x2),

                "min_lat":
                    min(y1, y2),

                "max_lat":
                    max(y1, y2)
            }
        )

        cell_number += 1


BASE_GRID = pd.DataFrame(grid)


# ============================================================
# PREPARE YEAR DATA
# ============================================================

YEAR_COLUMNS = [
    str(year)
    for year in range(2015, 2026)
]


LST_LOOKUP = master_data[
    ["cell_id"] + YEAR_COLUMNS
].copy()


# ============================================================
# GET LEVEL INFORMATION
# ============================================================

def get_level_info(level_index):

    return LEVELS[level_index]


# ============================================================
# CREATE GAME FOR A LEVEL
# ============================================================

def create_level(level_index):

    level_info = get_level_info(level_index)

    year = level_info["year"]

    budget = level_info["budget"]


    # --------------------------------------------------------
    # Merge the year's LST values with the spatial grid
    # --------------------------------------------------------

    game = BASE_GRID.copy()

    year_values = LST_LOOKUP[
        ["cell_id", str(year)]
    ].copy()

    year_values = year_values.rename(
        columns={
            str(year): "observed_lst"
        }
    )


    game = game.merge(
        year_values,
        on="cell_id",
        how="left"
    )


    # --------------------------------------------------------
    # Game variables
    # --------------------------------------------------------

    game["cooling"] = 0.0

    game["simulated_lst"] = (
        game["observed_lst"]
    )

    game["tree"] = False

    game["green_space"] = False

    game["cool_roof"] = False


    # --------------------------------------------------------
    # Initial extreme heat
    # --------------------------------------------------------

    extreme_cells = int(
        (
            game["observed_lst"]
            >= HEAT_THRESHOLD
        ).sum()
    )


    # --------------------------------------------------------
    # Target
    # --------------------------------------------------------

    target = int(
        extreme_cells
        * (1 - TARGET_REDUCTION)
    )


    return {
        "game": game,

        "level_index": level_index,

        "level": level_info["level"],

        "year": year,

        "difficulty":
            level_info["difficulty"],

        "budget": budget,

        "starting_budget": budget,

        "turn": 1,

        "selected_cell": None,

        "selected_action": None,

        "extreme_before":
            extreme_cells,

        "target":
            target,

        "history": [],

        "finished": False,

        "won": False
    }


# ============================================================
# SESSION STATE
# ============================================================

if "game_state" not in st.session_state:

    st.session_state.game_state = create_level(0)


state = st.session_state.game_state

game = state["game"]


# ============================================================
# RESET CURRENT LEVEL
# ============================================================

def reset_level():

    level_index = state["level_index"]

    st.session_state.game_state = (
        create_level(level_index)
    )

    st.rerun()


# ============================================================
# START NEXT LEVEL
# ============================================================

def next_level():

    current_index = state["level_index"]

    next_index = current_index + 1

    if next_index < len(LEVELS):

        st.session_state.game_state = (
            create_level(next_index)
        )

        st.rerun()


# ============================================================
# APPLY INTERVENTION
# ============================================================

def apply_intervention(
    cell_id,
    intervention_name
):

    settings = INTERVENTIONS[
        intervention_name
    ]

    cost = settings["cost"]

    radius = settings["radius"]

    max_effect = settings["effect"]


    # --------------------------------------------------------
    # Check budget
    # --------------------------------------------------------

    if state["budget"] < cost:

        return (
            False,
            "You do not have enough Cooling Points."
        )


    # --------------------------------------------------------
    # Find selected cell
    # --------------------------------------------------------

    selected = game[
        game["cell_id"] == cell_id
    ].iloc[0]


    target_lat = selected["latitude"]

    target_lon = selected["longitude"]


    # --------------------------------------------------------
    # Approximate distance in kilometres
    # --------------------------------------------------------

    lat_km = 111.0

    lon_km = (
        111.0
        * np.cos(
            np.radians(target_lat)
        )
    )


    distance = np.sqrt(

        (
            (
                game["latitude"]
                - target_lat
            )
            * lat_km
        ) ** 2

        +

        (
            (
                game["longitude"]
                - target_lon
            )
            * lon_km
        ) ** 2
    )


    # --------------------------------------------------------
    # Calculate cooling effect
    # --------------------------------------------------------

    effect = np.where(

        distance <= radius,

        max_effect
        * (
            1
            - distance / radius
        ),

        0
    )


    # --------------------------------------------------------
    # Apply cooling
    # --------------------------------------------------------

    game["cooling"] += effect

    game["simulated_lst"] = (
        game["observed_lst"]
        - game["cooling"]
    )


    # --------------------------------------------------------
    # Record intervention
    # --------------------------------------------------------

    selected_index = game.index[
        game["cell_id"] == cell_id
    ][0]


    if intervention_name == "🌳 Tree":

        game.loc[
            selected_index,
            "tree"
        ] = True


    elif intervention_name == "🌿 Green Space":

        game.loc[
            selected_index,
            "green_space"
        ] = True


    elif intervention_name == "🏠 Cool Roof":

        game.loc[
            selected_index,
            "cool_roof"
        ] = True


    # --------------------------------------------------------
    # Calculate consequences
    # --------------------------------------------------------

    before_heat = int(
        (
            game["simulated_lst"]
            + effect
            >= HEAT_THRESHOLD
        ).sum()
    )


    after_heat = int(
        (
            game["simulated_lst"]
            >= HEAT_THRESHOLD
        ).sum()
    )


    cells_affected = int(
        (effect > 0).sum()
    )


    total_cooling = float(
        effect.sum()
    )


    # --------------------------------------------------------
    # Spend points
    # --------------------------------------------------------

    state["budget"] -= cost


    # --------------------------------------------------------
    # Record move
    # --------------------------------------------------------

    state["history"].append(
        {
            "Turn":
                state["turn"],

            "Cell":
                cell_id,

            "Action":
                intervention_name,

            "Cost":
                cost,

            "Cells affected":
                cells_affected,

            "Cooling added":
                round(
                    total_cooling,
                    2
                ),

            "Extreme heat":
                after_heat
        }
    )


    # --------------------------------------------------------
    # Advance turn
    # --------------------------------------------------------

    state["turn"] += 1


    # --------------------------------------------------------
    # Check victory
    # --------------------------------------------------------

    if after_heat <= state["target"]:

        state["finished"] = True

        state["won"] = True


    elif state["turn"] > MAX_TURNS:

        state["finished"] = True

        state["won"] = False


    return (
        True,
        f"{intervention_name} successfully placed."
    )


# ============================================================
# HEADER
# ============================================================

st.title("🌡️ Can You Make Dhaka Cooler?")


st.markdown(
    f"## Level {state['level']} — "
    f"Dhaka {state['year']}"
)


st.markdown(
    f"### {state['difficulty']}"
)


st.write(
    "Dhaka is getting hotter, and urban heat is becoming "
    "an increasing challenge for city life. This game aims "
    "to raise awareness about rising temperatures and help "
    "you explore how urban cooling strategies can make a difference."
)


st.caption(
    "Use limited resources to place trees, green spaces, "
    "and cool roofs across the city. Make strategic choices "
    "and see how your decisions affect urban heat."
)


# ============================================================
# SCIENTIFIC NOTE
# ============================================================

with st.expander("ℹ️ About the data and simulation"):

    st.write(
        "Each level uses observed real MODIS land surface mean temperature "
        "for March–September of a different year from 2015–2025. "
        "The cooling effects of your interventions are simulated "
        "for gameplay and are not physical climate-model predictions."
    )


# ============================================================
# CAMPAIGN PROGRESS
# ============================================================

progress_value = (
    state["level"]
    / len(LEVELS)
)


st.progress(
    progress_value
)


st.caption(
    f"Campaign Progress: "
    f"Level {state['level']} of {len(LEVELS)}"
)


# ============================================================
# MISSION PANEL
# ============================================================

col1, col2, col3, col4 = st.columns(4)


current_extreme = int(
    (
        game["simulated_lst"]
        >= HEAT_THRESHOLD
    ).sum()
)


mean_temperature = float(
    game["simulated_lst"].mean()
)


with col1:

    st.metric(
        "💰 Cooling Points",
        state["budget"]
    )


with col2:

    st.metric(
        "🔥 Extreme Heat Cells",
        current_extreme
    )


with col3:

    st.metric(
        "🎯 Target",
        f"≤ {state['target']}"
    )


with col4:

    turns_used = min(
        state["turn"] - 1,
        MAX_TURNS
    )

    st.metric(
        "🎮 Turn",
        f"{turns_used}/{MAX_TURNS}"
    )


# ============================================================
# MISSION MESSAGE
# ============================================================

if not state["finished"]:

    st.info(
        f"🎯 **Mission:** Reduce extreme-heat cells "
        f"from {state['extreme_before']} to "
        f"**{state['target']} or fewer** "
        f"within {MAX_TURNS} turns."
    )


# ============================================================
# LEVEL FINISHED
#
# This section appears before the map so the player
# immediately sees the result and next-level controls.
# ============================================================

if state["finished"]:

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    if state["won"]:

        st.success(
            "🎉 **LEVEL COMPLETE!** "
            "You successfully cooled Dhaka."
        )

    else:

        st.error(
            "🔥 **LEVEL FAILED!** "
            "Dhaka is still too hot."
        )


    # --------------------------------------------------------
    # Final statistics
    # --------------------------------------------------------

    final_extreme = int(
        (
            game["simulated_lst"]
            >= HEAT_THRESHOLD
        ).sum()
    )


    reduction = (
        state["extreme_before"]
        - final_extreme
    )


    if state["extreme_before"] > 0:

        reduction_percent = (
            reduction
            / state["extreme_before"]
            * 100
        )

    else:

        reduction_percent = 0.0


    mean_reduction = (
        game["observed_lst"].mean()
        -
        game["simulated_lst"].mean()
    )


    trees = int(
        game["tree"].sum()
    )


    green_spaces = int(
        game["green_space"].sum()
    )


    cool_roofs = int(
        game["cool_roof"].sum()
    )


    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    st.write("## 📊 Level Results")


    r1, r2, r3, r4 = st.columns(4)


    with r1:

        st.metric(
            "Heat Cells",
            f"{state['extreme_before']} → "
            f"{final_extreme}"
        )


    with r2:

        st.metric(
            "Reduction",
            f"{reduction_percent:.1f}%"
        )


    with r3:

        st.metric(
            "Mean Cooling",
            f"{mean_reduction:.2f}°C"
        )


    with r4:

        st.metric(
            "Points Remaining",
            state["budget"]
        )


    st.write(
        "### 🏗️ Your Cooling Strategy"
    )


    a1, a2, a3 = st.columns(3)


    with a1:

        st.metric(
            "🌳 Trees",
            trees
        )


    with a2:

        st.metric(
            "🌿 Green Spaces",
            green_spaces
        )


    with a3:

        st.metric(
            "🏠 Cool Roofs",
            cool_roofs
        )


    st.write("")


    # --------------------------------------------------------
    # Level controls
    # --------------------------------------------------------

    if state["won"]:

        if state["level"] < len(LEVELS):

            c1, c2 = st.columns(2)


            with c1:

                if st.button(
                    "🔄 Replay Level",
                    use_container_width=True
                ):

                    reset_level()


            with c2:

                if st.button(
                    "➡️ Next Level",
                    use_container_width=True,
                    type="primary"
                ):

                    next_level()

        else:

            st.success(
                "🏆 **CAMPAIGN COMPLETE!** "
                "You have cooled every level of Dhaka."
            )


            if st.button(
                "🔄 Restart Campaign",
                use_container_width=True
            ):

                st.session_state.game_state = (
                    create_level(0)
                )

                st.rerun()


    else:

        if st.button(
            "🔄 Retry Level",
            use_container_width=True,
            type="primary"
        ):

            reset_level()


    st.stop()


# ============================================================
# MAP SECTION
# ============================================================

st.write("## 🗺️ Make Your Move")


st.write(
    "Click a location on the map. "
    "Then choose an intervention."
)


fig = go.Figure()


# ============================================================
# DRAW HEAT CELLS
# ============================================================

for _, cell in game.iterrows():

    value = cell["simulated_lst"]


    # --------------------------------------------------------
    # Heat colours
    # --------------------------------------------------------

    if value < 30:

        color = "rgb(40,90,220)"

    elif value < 32:

        color = "rgb(40,180,120)"

    elif value < 34:

        color = "rgb(240,210,50)"

    elif value < 35:

        color = "rgb(245,150,40)"

    elif value < 36:

        color = "rgb(230,80,35)"

    else:

        color = "rgb(190,35,35)"


    fig.add_trace(
        go.Scatter(

            x=[
                cell["min_lon"],
                cell["max_lon"],
                cell["max_lon"],
                cell["min_lon"],
                cell["min_lon"]
            ],

            y=[
                cell["min_lat"],
                cell["min_lat"],
                cell["max_lat"],
                cell["max_lat"],
                cell["min_lat"]
            ],

            mode="lines",

            fill="toself",

            fillcolor=color,

            line=dict(
                color="white",
                width=0.5
            ),

            hoverinfo="skip",

            showlegend=False
        )
    )


# ============================================================
# CLICKABLE CELL CENTRES
# ============================================================

fig.add_trace(
    go.Scatter(

        x=game["longitude"],

        y=game["latitude"],

        mode="markers",

        marker=dict(
            size=18,
            color="rgba(0,0,0,0.01)"
        ),

        customdata=np.column_stack(
            (
                game["cell_id"],
                game["observed_lst"],
                game["simulated_lst"],
                game["cooling"]
            )
        ),

        hovertemplate=(

            "<b>Cell:</b> %{customdata[0]}<br>"

            "<b>Observed:</b> "
            "%{customdata[1]:.2f} °C<br>"

            "<b>Current:</b> "
            "%{customdata[2]:.2f} °C<br>"

            "<b>Cooling:</b> "
            "%{customdata[3]:.2f} °C"

            "<extra></extra>"
        ),

        showlegend=False
    )
)


# ============================================================
# HIGHLIGHT SELECTED CELL
# ============================================================

if state["selected_cell"] is not None:

    selected = game[
        game["cell_id"]
        == state["selected_cell"]
    ]


    if len(selected) > 0:

        selected = selected.iloc[0]


        fig.add_trace(
            go.Scatter(

                x=[
                    selected["longitude"]
                ],

                y=[
                    selected["latitude"]
                ],

                mode="markers",

                marker=dict(
                    size=24,
                    color="rgba(0,0,0,0)",
                    line=dict(
                        color="black",
                        width=3
                    )
                ),

                showlegend=False,

                hoverinfo="skip"
            )
        )


# ============================================================
# MAP LAYOUT
# ============================================================

fig.update_layout(

    height=650,

    margin=dict(
        l=10,
        r=10,
        t=10,
        b=10
    ),

    showlegend=False,

    dragmode=False
)


fig.update_xaxes(

    title="Longitude",

    scaleanchor="y",

    scaleratio=1,

    showgrid=False
)


fig.update_yaxes(

    title="Latitude",

    showgrid=False
)


# ============================================================
# DISPLAY MAP
# ============================================================

event = st.plotly_chart(

    fig,

    use_container_width=True,

    on_select="rerun",

    selection_mode="points"
)


# ============================================================
# PROCESS CELL SELECTION
# ============================================================

if (

    event
    and event.selection
    and event.selection.points
):

    point = event.selection.points[0]


    if "customdata" in point:

        clicked_cell = (
            point["customdata"][0]
        )


        state["selected_cell"] = (
            clicked_cell
        )


        st.rerun()


# ============================================================
# SELECTED LOCATION
# ============================================================

if state["selected_cell"] is not None:

    selected = game[
        game["cell_id"]
        == state["selected_cell"]
    ]


    if len(selected) > 0:

        selected = selected.iloc[0]


        st.write(
            "## 📍 Selected Location"
        )


        s1, s2, s3, s4 = st.columns(4)


        with s1:

            st.metric(
                "Cell",
                selected["cell_id"]
            )


        with s2:

            st.metric(
                "Observed LST",
                f"{selected['observed_lst']:.2f}°C"
            )


        with s3:

            st.metric(
                "Current LST",
                f"{selected['simulated_lst']:.2f}°C"
            )


        with s4:

            cooling = (
                selected["observed_lst"]
                -
                selected["simulated_lst"]
            )


            st.metric(
                "Cooling",
                f"{cooling:.2f}°C"
            )


        # ====================================================
        # ACTION SELECTION
        # ====================================================

        st.write(
            "### 🛠️ Choose your intervention"
        )


        action_cols = st.columns(3)


        for i, (
            name,
            settings
        ) in enumerate(
            INTERVENTIONS.items()
        ):

            with action_cols[i]:

                st.write(
                    f"### {name}"
                )


                st.write(
                    f"**Cost:** "
                    f"{settings['cost']} points"
                )


                st.write(
                    settings["description"]
                )


                if st.button(
                    f"Deploy {name}",
                    key=f"action_{name}",
                    use_container_width=True
                ):

                    success, message = (
                        apply_intervention(
                            state["selected_cell"],
                            name
                        )
                    )


                    if success:

                        st.rerun()

                    else:

                        st.error(message)


else:

    st.warning(
        "👆 Select a cell on the map "
        "to make your first move."
    )


# ============================================================
# GAME HISTORY
# ============================================================

if len(state["history"]) > 0:

    st.write("## 📜 Your Moves")


    history_df = pd.DataFrame(
        state["history"]
    )


    st.dataframe(
        history_df,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# RESET CURRENT LEVEL
# ============================================================

st.write("")


if st.button(
    "🔄 Restart Level"
):

    reset_level()


# ============================================================
# FOOTNOTE
# ============================================================

st.caption(
    "MODIS LST represents the observed baseline "
    "for March–September of the selected year. "
    "Intervention effects are simulated game mechanics "
    "for gameplay and portfolio purposes and are not "
    "physically validated cooling predictions."
)