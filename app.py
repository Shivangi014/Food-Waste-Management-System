"""
Local Food Wastage Management System — Streamlit App
Run: streamlit run app.py
"""
import os
import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st
import plotly.express as px

DB_PATH = "food_waste.db"
DATA_DIR = "data"

# ---------------- DB SETUP ----------------
@st.cache_resource
def get_conn():
    first_time = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    if first_time:
        seed_db(conn)
    return conn

def seed_db(conn):
    providers = pd.read_csv(f"{DATA_DIR}/providers_data.csv")
    receivers = pd.read_csv(f"{DATA_DIR}/receivers_data.csv")
    food = pd.read_csv(f"{DATA_DIR}/food_listings_data.csv")
    claims = pd.read_csv(f"{DATA_DIR}/claims_data.csv")
    food["Expiry_Date"] = pd.to_datetime(food["Expiry_Date"]).dt.strftime("%Y-%m-%d")
    claims["Timestamp"] = pd.to_datetime(claims["Timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    providers.to_sql("providers", conn, index=False, if_exists="replace")
    receivers.to_sql("receivers", conn, index=False, if_exists="replace")
    food.to_sql("food_listings", conn, index=False, if_exists="replace")
    claims.to_sql("claims", conn, index=False, if_exists="replace")
    conn.commit()

def q(sql, params=()):
    return pd.read_sql_query(sql, get_conn(), params=params)

def exec_sql(sql, params=()):
    cur = get_conn().cursor()
    cur.execute(sql, params)
    get_conn().commit()

# ---------------- UI ----------------
st.set_page_config(page_title="Local Food Wastage Management", page_icon="🍽️", layout="wide")
st.title("🍽️ Local Food Wastage Management System")

page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Browse & Filter Listings", "Providers & Receivers", "CRUD", "15 SQL Queries", "EDA"],
)

# ---------------- DASHBOARD ----------------
if page == "Dashboard":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Providers", int(q("SELECT COUNT(*) c FROM providers").c[0]))
    c2.metric("Receivers", int(q("SELECT COUNT(*) c FROM receivers").c[0]))
    c3.metric("Food Listings", int(q("SELECT COUNT(*) c FROM food_listings").c[0]))
    c4.metric("Total Claims", int(q("SELECT COUNT(*) c FROM claims").c[0]))

    a, b = st.columns(2)
    with a:
        st.subheader("Claims by Status")
        df = q("SELECT Status, COUNT(*) AS count FROM claims GROUP BY Status")
        st.plotly_chart(px.pie(df, names="Status", values="count", hole=0.4), use_container_width=True)
    with b:
        st.subheader("Food Type Distribution")
        df = q("SELECT Food_Type, COUNT(*) AS count FROM food_listings GROUP BY Food_Type")
        st.plotly_chart(px.bar(df, x="Food_Type", y="count", color="Food_Type"), use_container_width=True)

    st.subheader("Top 10 Cities by Listings")
    df = q("SELECT Location AS City, COUNT(*) AS listings FROM food_listings GROUP BY Location ORDER BY listings DESC LIMIT 10")
    st.plotly_chart(px.bar(df, x="City", y="listings"), use_container_width=True)

# ---------------- BROWSE / FILTER ----------------
elif page == "Browse & Filter Listings":
    st.subheader("Filter Food Listings")
    cities = ["All"] + sorted(q("SELECT DISTINCT Location FROM food_listings").Location.tolist())
    providers = ["All"] + sorted(q("SELECT DISTINCT Provider_Type FROM food_listings").Provider_Type.tolist())
    ftypes = ["All"] + sorted(q("SELECT DISTINCT Food_Type FROM food_listings").Food_Type.tolist())
    mtypes = ["All"] + sorted(q("SELECT DISTINCT Meal_Type FROM food_listings").Meal_Type.tolist())

    c1, c2, c3, c4 = st.columns(4)
    city = c1.selectbox("City", cities)
    pt = c2.selectbox("Provider Type", providers)
    ft = c3.selectbox("Food Type", ftypes)
    mt = c4.selectbox("Meal Type", mtypes)

    sql = """SELECT f.*, p.Name AS Provider_Name, p.Contact
             FROM food_listings f LEFT JOIN providers p ON f.Provider_ID = p.Provider_ID WHERE 1=1"""
    params = []
    for col, val in [("Location", city), ("Provider_Type", pt), ("Food_Type", ft), ("Meal_Type", mt)]:
        if val != "All":
            sql += f" AND f.{col} = ?"
            params.append(val)
    df = q(sql, tuple(params))
    st.write(f"**{len(df)} listings**")
    st.dataframe(df, use_container_width=True)

# ---------------- DIRECTORY ----------------
elif page == "Providers & Receivers":
    tab1, tab2 = st.tabs(["Providers", "Receivers"])
    with tab1:
        city = st.selectbox("Filter by City", ["All"] + sorted(q("SELECT DISTINCT City FROM providers").City.tolist()), key="pc")
        sql = "SELECT * FROM providers" + ("" if city == "All" else " WHERE City = ?")
        st.dataframe(q(sql, () if city == "All" else (city,)), use_container_width=True)
    with tab2:
        city = st.selectbox("Filter by City", ["All"] + sorted(q("SELECT DISTINCT City FROM receivers").City.tolist()), key="rc")
        sql = "SELECT * FROM receivers" + ("" if city == "All" else " WHERE City = ?")
        st.dataframe(q(sql, () if city == "All" else (city,)), use_container_width=True)

# ---------------- CRUD ----------------
elif page == "CRUD":
    table = st.selectbox("Table", ["food_listings", "providers", "receivers", "claims"])
    action = st.radio("Action", ["View", "Add", "Update", "Delete"], horizontal=True)
    df = q(f"SELECT * FROM {table} LIMIT 200")
    pk = {"food_listings": "Food_ID", "providers": "Provider_ID", "receivers": "Receiver_ID", "claims": "Claim_ID"}[table]

    if action == "View":
        st.dataframe(df, use_container_width=True)

    elif action == "Add":
        st.write("Enter new row values")
        vals = {c: st.text_input(c) for c in df.columns}
        if st.button("Add Row"):
            cols = ",".join(vals.keys())
            ph = ",".join(["?"] * len(vals))
            exec_sql(f"INSERT INTO {table} ({cols}) VALUES ({ph})", tuple(vals.values()))
            st.success("Row added"); st.rerun()

    elif action == "Update":
        rid = st.number_input(f"{pk} to update", step=1, value=int(df[pk].iloc[0]))
        row = q(f"SELECT * FROM {table} WHERE {pk}=?", (int(rid),))
        if row.empty:
            st.warning("Not found")
        else:
            new = {c: st.text_input(c, value=str(row[c].iloc[0])) for c in row.columns if c != pk}
            if st.button("Save"):
                sets = ",".join([f"{c}=?" for c in new])
                exec_sql(f"UPDATE {table} SET {sets} WHERE {pk}=?", tuple(new.values()) + (int(rid),))
                st.success("Updated"); st.rerun()

    elif action == "Delete":
        rid = st.number_input(f"{pk} to delete", step=1, value=int(df[pk].iloc[0]))
        if st.button("Delete", type="primary"):
            exec_sql(f"DELETE FROM {table} WHERE {pk}=?", (int(rid),))
            st.success("Deleted"); st.rerun()

# ---------------- 15 SQL QUERIES ----------------
elif page == "15 SQL Queries":
    QUERIES = {
        "1. Providers & Receivers per City": """
            SELECT COALESCE(p.City, r.City) AS City,
                   COUNT(DISTINCT p.Provider_ID) AS Providers,
                   COUNT(DISTINCT r.Receiver_ID) AS Receivers
            FROM providers p FULL OUTER JOIN receivers r ON p.City = r.City
            GROUP BY COALESCE(p.City, r.City) ORDER BY Providers DESC""",
        "2. Top Provider Type by Food Contributed": """
            SELECT Provider_Type, SUM(Quantity) AS Total_Quantity
            FROM food_listings GROUP BY Provider_Type ORDER BY Total_Quantity DESC""",
        "3. Provider Contacts in a Specific City": "SELECT Name, Type, Contact FROM providers WHERE City = :city",
        "4. Top Receivers by Claims": """
            SELECT r.Receiver_ID, r.Name, COUNT(c.Claim_ID) AS Total_Claims
            FROM receivers r JOIN claims c ON r.Receiver_ID = c.Receiver_ID
            GROUP BY r.Receiver_ID, r.Name ORDER BY Total_Claims DESC LIMIT 10""",
        "5. Total Quantity of Food Available": "SELECT SUM(Quantity) AS Total_Quantity_Available FROM food_listings",
        "6. City With Highest # of Food Listings": """
            SELECT Location AS City, COUNT(*) AS Listings FROM food_listings
            GROUP BY Location ORDER BY Listings DESC LIMIT 10""",
        "7. Most Common Food Types": """
            SELECT Food_Type, COUNT(*) AS Listings FROM food_listings
            GROUP BY Food_Type ORDER BY Listings DESC""",
        "8. Claims per Food Item": """
            SELECT f.Food_ID, f.Food_Name, COUNT(c.Claim_ID) AS Claims
            FROM food_listings f LEFT JOIN claims c ON f.Food_ID = c.Food_ID
            GROUP BY f.Food_ID, f.Food_Name ORDER BY Claims DESC LIMIT 20""",
        "9. Provider with Most Successful (Completed) Claims": """
            SELECT p.Provider_ID, p.Name, COUNT(*) AS Completed_Claims
            FROM claims c JOIN food_listings f ON c.Food_ID = f.Food_ID
            JOIN providers p ON f.Provider_ID = p.Provider_ID
            WHERE c.Status = 'Completed'
            GROUP BY p.Provider_ID, p.Name ORDER BY Completed_Claims DESC LIMIT 10""",
        "10. Claim Status Breakdown (%)": """
            SELECT Status, COUNT(*) AS Cnt,
                   ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM claims), 2) AS Percentage
            FROM claims GROUP BY Status""",
        "11. Avg Quantity Claimed per Receiver": """
            SELECT r.Receiver_ID, r.Name, AVG(f.Quantity) AS Avg_Qty
            FROM claims c JOIN receivers r ON c.Receiver_ID = r.Receiver_ID
            JOIN food_listings f ON c.Food_ID = f.Food_ID
            GROUP BY r.Receiver_ID, r.Name ORDER BY Avg_Qty DESC LIMIT 15""",
        "12. Most Claimed Meal Type": """
            SELECT f.Meal_Type, COUNT(*) AS Claims FROM claims c
            JOIN food_listings f ON c.Food_ID = f.Food_ID
            GROUP BY f.Meal_Type ORDER BY Claims DESC""",
        "13. Total Quantity Donated per Provider": """
            SELECT p.Provider_ID, p.Name, SUM(f.Quantity) AS Total_Donated
            FROM providers p JOIN food_listings f ON p.Provider_ID = f.Provider_ID
            GROUP BY p.Provider_ID, p.Name ORDER BY Total_Donated DESC LIMIT 15""",
        "14. Food Items Expiring in Next 7 Days": """
            SELECT Food_ID, Food_Name, Quantity, Expiry_Date, Location
            FROM food_listings WHERE DATE(Expiry_Date) BETWEEN DATE('now') AND DATE('now','+7 day')
            ORDER BY Expiry_Date""",
        "15. Most Active Cities by Claims": """
            SELECT f.Location AS City, COUNT(c.Claim_ID) AS Claims
            FROM claims c JOIN food_listings f ON c.Food_ID = f.Food_ID
            GROUP BY f.Location ORDER BY Claims DESC LIMIT 10""",
    }
    choice = st.selectbox("Pick a query", list(QUERIES.keys()))
    sql = QUERIES[choice]
    if ":city" in sql:
        city = st.selectbox("City", sorted(q("SELECT DISTINCT City FROM providers").City.tolist()))
        sql = sql.replace(":city", "?")
        df = q(sql, (city,))
    else:
        # SQLite doesn't support FULL OUTER JOIN — emulate for Q1
        if "FULL OUTER JOIN" in sql:
            sql = """
                SELECT City, SUM(Providers) AS Providers, SUM(Receivers) AS Receivers FROM (
                    SELECT City, COUNT(*) AS Providers, 0 AS Receivers FROM providers GROUP BY City
                    UNION ALL
                    SELECT City, 0, COUNT(*) FROM receivers GROUP BY City
                ) GROUP BY City ORDER BY Providers DESC"""
        df = q(sql)
    with st.expander("SQL"):
        st.code(sql, language="sql")
    st.dataframe(df, use_container_width=True)

# ---------------- EDA ----------------
elif page == "EDA":
    st.subheader("Exploratory Data Analysis")
    df = q("SELECT * FROM food_listings")
    df["Expiry_Date"] = pd.to_datetime(df["Expiry_Date"])
    st.write("**Food listings sample**"); st.dataframe(df.head())
    st.write("**Summary**"); st.dataframe(df.describe(include="all"))

    a, b = st.columns(2)
    with a:
        st.plotly_chart(px.histogram(df, x="Quantity", nbins=30, title="Quantity Distribution"), use_container_width=True)
    with b:
        st.plotly_chart(px.box(df, x="Food_Type", y="Quantity", title="Quantity by Food Type"), use_container_width=True)

    st.plotly_chart(
        px.histogram(df, x="Expiry_Date", title="Expiry Date Distribution", nbins=30),
        use_container_width=True,
    )

    claims = q("SELECT * FROM claims")
    claims["Timestamp"] = pd.to_datetime(claims["Timestamp"])
    claims["Day"] = claims["Timestamp"].dt.date
    daily = claims.groupby(["Day", "Status"]).size().reset_index(name="count")
    st.plotly_chart(px.line(daily, x="Day", y="count", color="Status", title="Daily Claims by Status"), use_container_width=True)
