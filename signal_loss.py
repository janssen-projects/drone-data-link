import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ==========================================
# KONFIGURATION: Spaltennamen
# ==========================================
COL_FLY_TIME = "OSD.flyTime"  # oder 'flyTime'
COL_LAT = "OSD.latitude"  # oder 'latitude'
COL_LON = "OSD.longitude"  # oder 'longitude'
COL_HEIGHT = "OSD.height [ft]"  # oder 'height'
COL_DOWNLINK = "RC.downlinkSignal"  # oder 'downlinkSignal'
COL_UPLINK = "RC.uplinkSignal"  # oder 'uplinkSignal'


def haversine_vectorized(lat1, lon1, lat2, lon2):
    """Berechnet die Entfernung (in Metern) zwischen zwei Punkten/Vektoren

    auf der Erde mit der Haversine-Formel (Vektorisiert für Pandas).
    """
    R = 6371000.0  # Erdradius in Metern

    # Konvertierung in Bogenmaß (Radiant)
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    )
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c


def analyze_csv_flight_log(csv_file_path):
    # 1. CSV einlesen
    df = pd.read_csv(csv_file_path, skiprows=1, sep=',') 

    # 2. FEHLERBEHEBUNG & Import-Validierung
    required_cols = [COL_FLY_TIME, COL_LAT, COL_LON, COL_HEIGHT, COL_DOWNLINK]
    for col in required_cols:
        if col not in df.columns:
            print(f"Fehler: Spalte '{col}' wurde in der CSV nicht gefunden!")
            print(f"Verfügbare Spalten: {list(df.columns)}")
            return
        # Konvertierung in Zahlen, falls Text
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 3. Grund-Filterung (Drohne fliegt, hat GPS)
    # df = df[df[COL_FLY_TIME] > 0].dropna(subset=[COL_LAT, COL_LON])

    if df.empty:
        print("Keine gültigen Flugdaten gefunden.")
        return

    # 4. Startpunkt (Home) definieren
    home_lat = df[COL_LAT].iloc[0]
    home_lon = df[COL_LON].iloc[0]
    print(f"Startpunkt (Home): Lat {home_lat}, Lon {home_lon}")

    # 5. 2D- und 3D-Entfernung berechnen
    # Umrechnung von Fuß (ft) in Meter (m) -> 1 ft = 0.3048 m
    df[COL_HEIGHT] = df[COL_HEIGHT] * 0.3048

    df["distance_2d"] = haversine_vectorized(
        home_lat, home_lon, df[COL_LAT], df[COL_LON]
    )
    df["distance_3d"] = np.sqrt(df["distance_2d"] ** 2 + df[COL_HEIGHT] ** 2)

    # --- HÖHENWINKEL BERECHNEN ---
    # arctan2(Gegenkathete [Höhe], Ankathete [2D-Distanz]) -> Ergebnis in Grad
    df["elevation_angle"] = np.degrees(
        np.arctan2(df[COL_HEIGHT], df["distance_2d"])
    )

    # 6. --- Logik: Hin- vs. Rückflug trennen ---
    # Wir suchen den Index, bei dem die 3D-Entfernung maximal war
    turn_point_index = df["distance_3d"].idxmax()
    print(
        f"Umdrehpunkt detektiert bei Index {turn_point_index} (Max Distanz: {df['distance_3d'].max():.1f}m)"
    )

    #  DataFrame am Umdrehpunkt splitten
    # .loc[:turn_point_index] nimmt alle Zeilen BIS zum Umdrehpunkt
    df_hinflug = df.loc[:turn_point_index].dropna(subset=[COL_DOWNLINK])
    # .loc[turn_point_index + 1:] nimmt alle Zeilen NACH dem Umdrehpunkt
    df_rueckflug = df.loc[turn_point_index + 1 :].dropna(subset=[COL_DOWNLINK])

    # --- SETUP PLOTS ---
    # Wir teilen uns NICHT die X-Achse (sharex=False), da Plot 1 die 3D-Distanz nutzt
    # und Plot 2 die echte 2D-Bodengeometrie benötigt.
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 9), gridspec_kw={"height_ratios": [1.2, 1]}
    )

    # Konstanten für das Hindernis
    x_haus_start = 55.0
    haus_breite = 10.0  # Annahme: Haus ist 10m tief
    y_haus_hoehe = 7.0

    # --------------------------------------------------
    # SUBPLOT 1: Signalstärkeverlauf (Über 3D-Sichtlinie)
    # --------------------------------------------------
    ax1.plot(
        df_hinflug["distance_3d"],
        df_hinflug[COL_DOWNLINK],
        label="Downlink Signal (outbound)",
        color="#1f77b4",
        linewidth=2.5,
    )
    ax1.plot(
        df_rueckflug["distance_3d"],
        df_rueckflug[COL_DOWNLINK],
        label="Downlink Signal (inbound)",
        color="#36d627",
        linewidth=1.5,
    )
    ax1.plot(
        df_hinflug["distance_3d"],
        df_hinflug[COL_UPLINK],
        label="Uplink Signal (outbound)",
        color="#ff7f0e",
        linewidth=1.5,
        linestyle=":",
    )
    ax1.plot(
        df_rueckflug["distance_3d"],    
        df_rueckflug[COL_UPLINK],
        label="Uplink Signal (inbound)",
        color="#ce3e3e",
        linewidth=1.5,
        linestyle=":",
    )    
    ax1.axvline(
        x=x_haus_start,
        color="gray",
        linestyle=":",
        alpha=0.5,
        label="Building (55m)",
    )
    # Gestrichelte Linie bei x=128m
    ax1.axvline(
        x=128.0,
        color="gray",
        linestyle="--",
        alpha=0.5,
        label="Signal recovery inbound (128m)",
    )
    ax1.axvline(
        x=354.0,
        color="gray",
        linestyle="--",
        alpha=0.5,
        label="Signal loss outbound(354m)",
    )
    ax1.set_title(
        "Signal Strength vs. Optical Shading",
        fontsize=13,
        fontweight="bold",
    )
    ax1.set_ylabel("Signal Strength / Quality", fontsize=11)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper right")

    # --------------------------------------------------
    # SUBPLOT 2: Geometric Cross-Section (Side View over 2D Ground Distance)
    # --------------------------------------------------
    max_2d_dist = df["distance_2d"].max()

    # 1. Real drone flight path (outbound is sufficient for geometry)
    ax2.plot(
        df_hinflug["distance_2d"],
        df_hinflug[COL_HEIGHT],
        color="black",
        linewidth=2,
        label="Drone Flight Path (Height)",
    )

    # 2. Draw the house as a box (rectangle)
    # patches.Rectangle((x, y), width, height)
    haus_kasten = patches.Rectangle(
        (x_haus_start, 0),
        haus_breite,
        y_haus_hoehe,
        edgecolor="darkred",
        facecolor="tomato",
        alpha=0.7,
        label="House (7m high)",
    )
    ax2.add_patch(haus_kasten)
    ax1.set_xlabel("Distance to UAV (Meter)", fontsize=11)

    # 3. Calculate and draw the critical line of sight
    # It starts at (0,0) and goes through the front roof edge (55, 7)
    x_sichtlinie = np.linspace(0, max_2d_dist, 500)
    # Slope m = House_Height / House_Distance
    m = y_haus_hoehe / x_haus_start
    y_sichtlinie = m * x_sichtlinie

    ax2.plot(
        x_sichtlinie,
        y_sichtlinie,
        color="darkgreen",
        linestyle="-.",
        linewidth=1.5,
        label="Critical line of sight (roof edge)",
    )

    # 4. Fill the dead zone area below the line of sight
    ax2.fill_between(
        x_sichtlinie,
        y_sichtlinie,
        0,
        where=(x_sichtlinie >= x_haus_start),
        color="gray",
        alpha=0.15,
        label="Theoretical dead zone (optical shading)",
    )
    # Gestrichelte Linie bei x=143 m
    ax2.axvline(
        x=143.0,
        color="gray",
        linestyle="--",
        alpha=0.5,
        label="UAV enters dead zone (143m)",        
    )
    ax2.set_title(
        "Geometric Cross-Section & Shadow Zone Validation",
        fontsize=13,
        fontweight="bold",
    )

    ax2.set_xlabel("Distance to UAV (Meter)", fontsize=11)
    ax2.set_ylabel("Flight Height / Object Height (Meter)", fontsize=11)
    ax2.set_xlim(0, max_2d_dist * 1.05)
    # Set Y-Limit slightly higher than the maximum drone height
    ax2.set_ylim(0, df[COL_HEIGHT].max() * 1.2)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="upper left")

    plt.tight_layout()
    plt.show()
 

# Call function to analyze the flight log CSV
analyze_csv_flight_log("data/f_log_bw1_linear.csv")