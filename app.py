import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# ---------------------------
# LOAD DATA
# ---------------------------

SHEET_ID = "1n1gqHl9jO9wO9DQYnxoKerfKLsqvUWs5a7Uo8NnG8zc"


def google_sheet_csv_url(gid: int) -> str:
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"

def get_current_period(today):
    if today.day <= 15:
        start = datetime(today.year, today.month, 1)
        end = datetime(today.year, today.month, 15)
    else:
        start = datetime(today.year, today.month, 16)

        if today.month == 12:
            end = datetime(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = datetime(today.year, today.month + 1, 1) - timedelta(days=1)

    return start, end


def get_next_period(today):
    current_start, current_end = get_current_period(today)
    next_day = current_end + timedelta(days=1)
    return get_current_period(next_day)

def generate_paydays(start, end, income_df):
    paydays = []

    for _, row in income_df.iterrows():

        name = row["name"]
        amount = row["amount"]
        schedule = row["schedule"]

        # YOUR PAY (1st & 15th)
        if schedule == "semi-monthly":
            for day in [1, 15]:
                try:
                    d = datetime(start.year, start.month, day)
                    if start <= d <= end:
                        paydays.append((d, name, amount / 2))
                except:
                    pass

        # WIFE BIWEEKLY
        elif schedule == "biweekly":
            wife_date = datetime(2026, 4, 2)

            while wife_date <= end:
                if wife_date >= start:
                    paydays.append((wife_date, name, amount))
                wife_date += timedelta(days=14)

    return paydays

def build_timeline(bills_df, income_df, start_date, end_date):
    events = []

    # Add paydays
    paydays = generate_paydays(start_date, end_date, income_df)

    for d, name, amt in paydays:
        events.append({
            "date": d,
            "name": f"{name} Paycheck",
            "amount": amt
        })

    # Add bills
    for _, row in bills_df.iterrows():
        bill_date = datetime(start_date.year, start_date.month, int(row["due_day"]))

        if start_date <= bill_date <= end_date:
            events.append({
                "date": bill_date,
                "name": row["name"],
                "amount": -row["amount"]
            })

    df = pd.DataFrame(events).sort_values("date")

    balance = 0
    timeline = []

    for _, row in df.iterrows():
        balance += row["amount"]

        timeline.append({
            "Date": row["date"].strftime("%b %d"),
            "Event": row["name"],
            "Change": row["amount"],
            "Balance": balance
        })

    result = pd.DataFrame(timeline)

    lowest = result["Balance"].min()
    lowest_row = result.loc[result["Balance"].idxmin()]

    return result, balance, lowest, lowest_row
   
def get_numeric_total(
    df: pd.DataFrame, sheet_name: str, expected_columns: list[str]
) -> float:
    for column in expected_columns:
        if column in df.columns:
            values = (
                df[column]
                .astype(str)
                .str.replace("$", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            return pd.to_numeric(values, errors="coerce").fillna(0).sum()

    st.error(
        f"{sheet_name} sheet is missing one of these columns: "
        f"{', '.join(expected_columns)}. Found: {', '.join(df.columns)}"
    )
    st.stop()

debts = pd.read_csv(google_sheet_csv_url(0))
bills = pd.read_csv(google_sheet_csv_url(1039347119))
income = pd.read_csv(google_sheet_csv_url(425398108))

debts.columns = debts.columns.str.strip().str.lower()
bills.columns = bills.columns.str.strip().str.lower()
income.columns = income.columns.str.strip().str.lower()

debts = debts.loc[:, ~debts.columns.str.startswith("unnamed:")]
bills = bills.loc[:, ~bills.columns.str.startswith("unnamed:")]
income = income.loc[:, ~income.columns.str.startswith("unnamed:")]

# ---------------------------
# SIMPLE CALCULATIONS
# ---------------------------

total_debt = get_numeric_total(debts, "Debts", ["balance", "amount"])
total_bills = get_numeric_total(bills, "Bills", ["amount", "balance"])
total_income = get_numeric_total(income, "Income", ["amount", "income"])

today = datetime.today()

current_start, current_end = get_current_period(today)
next_start, next_end = get_next_period(today)

current_df, current_balance, current_low, current_low_row = build_timeline(
    bills, income, current_start, current_end
)

next_df, next_balance, next_low, next_low_row = build_timeline(
    bills, income, next_start, next_end
)

st.header("📅 Bill Timeline")

view = st.selectbox(
    "Select View",
    ["Next 7 Days", "Next 14 Days", "This Month"]
)

if view == "Next 7 Days":
    timeline_start = today
    timeline_end = today + timedelta(days=7)

elif view == "Next 14 Days":
    timeline_start = today
    timeline_end = today + timedelta(days=14)

elif view == "This Month":
    timeline_start = datetime(today.year, today.month, 1)

    if today.month == 12:
        timeline_end = datetime(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        timeline_end = datetime(today.year, today.month + 1, 1) - timedelta(days=1)

filtered_bills = []

for _, row in bills.iterrows():
    due_day = int(row["due_day"])

    try:
        bill_date = datetime(timeline_start.year, timeline_start.month, due_day)
    except:
        continue

    if timeline_start <= bill_date <= timeline_end:
        filtered_bills.append({
            "date": bill_date,
            "name": row["name"],
            "amount": row["amount"]
        })

filtered_df = pd.DataFrame(filtered_bills).sort_values("date")

st.subheader("🧾 Upcoming Bills")

for _, row in filtered_df.iterrows():
    st.markdown(f"""
    **{row['date'].strftime('%b %d')}**  
    {row['name']} — ${row['amount']}
    """)

st.header("Current Pay Period")

st.write(f"{current_start.strftime('%b %d')} to {current_end.strftime('%b %d')}")

st.metric("Ending Balance", f"${current_balance:,.0f}")

if current_low < 0:
    st.error(f"You will go negative around {current_low_row['Date']}")
elif current_low < 300:
    st.warning(f"Tight around {current_low_row['Date']}")
else:
    st.success("You're safe this period")

st.header("Next Pay Period")

st.write(f"{next_start.strftime('%b %d')} to {next_end.strftime('%b %d')}")

st.metric("Projected Balance", f"${next_balance:,.0f}")

if next_low < 0:
    st.error(f"Risk next period around {next_low_row['Date']}")
elif next_low < 300:
    st.warning("Next period will be tight")
else:
    st.success("Next period looks good")

with st.expander("View Current Period Details"):
    st.dataframe(current_df)
# ---------------------------
# DISPLAY
# ---------------------------

st.header("Where We Stand")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Debt", f"${total_debt:,.0f}")

with col2:
    st.metric("Monthly Bills", f"${total_bills:,.0f}")

with col3:
    st.metric("Monthly Income", f"${total_income:,.0f}")

st.header("Quick Check")

remaining = total_income - total_bills

if remaining < 0:
    st.error("You're spending more than you make")
else:
    st.success(f"You have ${remaining:,.0f} left after bills")

st.header("💳 Debt Snowball")

debts_sorted = debts.sort_values("balance")

original_total = total_debt  # placeholder

paid = original_total - total_debt
progress = paid / original_total if original_total else 0

st.progress(progress)
st.write(f"{progress*100:.1f}% paid off")

for _, row in debts_sorted.iterrows():
    st.markdown(f"""
    **{row['name']}**  
    Balance: ${row['balance']:,.0f}  
    Min: ${row['min']}
    """)

next_debt = debts_sorted.iloc[0]

st.success(f"🎯 Next target: {next_debt['name']} (${next_debt['balance']})")

with st.expander("View Debts"):
    st.dataframe(debts)

with st.expander("View Bills"):
    st.dataframe(bills)

with st.expander("View Income"):
    st.dataframe(income)
