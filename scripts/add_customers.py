"""Append more mock customers (and the cities they live in) to the JSON data.

Run from the project root:

    python scripts/add_customers.py              # adds 40 customers
    python scripts/add_customers.py --count 90   # adds 90 customers

Existing records are never changed. New IDs continue after the highest existing
CUSTxxxx. Running the script twice adds more customers each time.
"""

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
IST = timezone(timedelta(hours=5, minutes=30))

FIRST_NAMES = [
    "Aditya", "Akash", "Amit", "Anjali", "Arjun", "Bhavna", "Chetan", "Deepak", "Divya",
    "Farhan", "Gauri", "Harsh", "Isha", "Jatin", "Kavya", "Lakshmi", "Manish", "Nikhil",
    "Pooja", "Rakesh", "Riya", "Sanjay", "Shreya", "Tanvi", "Uday", "Varun", "Yash",
    "Zoya", "Imran", "Simran", "Gurpreet", "Fatima", "Suresh", "Pallavi", "Ritu", "Dev",
]
LAST_NAMES = [
    "Sharma", "Patel", "Reddy", "Khan", "Gupta", "Bose", "Menon", "Chopra", "Desai",
    "Pillai", "Banerjee", "Shah", "Agarwal", "Bhatt", "Rao", "Saxena", "Thakur",
    "Mishra", "Ghosh", "Kaur", "Yadav", "Naidu", "Jain", "Sethi", "Pandey", "Hegde",
]
PLANS = [
    "Combo Voice+Data 349", "Family Max 999", "Postpaid Lite 499", "Postpaid Plus 799",
    "Smart Prepaid 299", "Student Saver 249", "Unlimited 4G 499", "Unlimited 5G 599",
    "Weekend Data 399", "Work Pro 1199",
]

# (recent_ticket, sim_status, account_status, weight): kept consistent on purpose.
PROFILES = [
    ("No recent tickets", "Active", "Good Standing", 8),
    ("Intermittent call drops during evening hours", "Active", "Good Standing", 2),
    ("Recharge successful but data balance not updated", "Active", "Good Standing", 2),
    ("SIM blocked after suspected fraudulent activity", "Blocked", "Under Review", 1),
    ("New SIM not activated after KYC submission", "Pending Activation", "Verification Pending", 2),
    ("International roaming not working", "Active", "Good Standing", 2),
    ("Unable to send SMS to banking short codes", "Active", "Good Standing", 2),
    ("Frequent no-service indicator indoors", "Active", "Good Standing", 2),
    ("Port-in request pending beyond committed date", "Pending Activation", "Verification Pending", 2),
    ("Incorrect late fee applied on latest bill", "Active", "Good Standing", 2),
    ("SIM replacement requested after phone loss", "Blocked", "Temporarily Suspended", 1),
    ("Bill payment overdue, reminder sent", "Active", "Past Due", 2),
    ("Services suspended due to unpaid dues", "Blocked", "Temporarily Suspended", 1),
    ("Slow mobile data speeds reported", "Active", "Good Standing", 2),
]

# New cities, added to network.json only if missing: (city, status, outage, hours_to_fix, signal)
NEW_CITIES = [
    ("Surat", "Operational", False, 0, "Strong"),
    ("Nagpur", "Operational", False, 0, "Moderate"),
    ("Indore", "Degraded", True, 5, "Weak"),
    ("Bhopal", "Operational", False, 0, "Strong"),
    ("Kochi", "Operational", False, 0, "Strong"),
    ("Chandigarh", "Operational", False, 0, "Strong"),
    ("Visakhapatnam", "Partial Outage", True, 3, "Weak"),
    ("Coimbatore", "Operational", False, 0, "Moderate"),
    ("Patna", "Operational", False, 0, "Moderate"),
    ("Thane", "Degraded", True, 4, "Weak"),
]


def load(name: str) -> list:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def save(name: str, records: list) -> None:
    (DATA_DIR / name).write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Add mock customers.")
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    customers, network = load("customers.json"), load("network.json")

    # 1) new cities
    known_cities = {r["city"] for r in network}
    now = datetime.now(IST)
    for city, status, outage, hours, signal in NEW_CITIES:
        if city not in known_cities:
            eta = (now + timedelta(hours=hours)).isoformat(timespec="seconds") if outage else "N/A"
            network.append(
                {"city": city, "network_status": status, "outage": outage,
                 "estimated_resolution": eta, "signal_strength": signal}
            )
    cities = [r["city"] for r in network]

    # 2) new customers
    next_id = max(int(c["customer_id"][4:]) for c in customers) + 1
    used_names = {c["name"] for c in customers}
    used_numbers = {c["mobile_number"] for c in customers}
    weights = [p[3] for p in PROFILES]

    for _ in range(args.count):
        while True:
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if name not in used_names:
                break
        while True:
            number = f"+91{rng.choice(['98', '97', '99', '96', '88', '70', '63'])}{rng.randint(10**7, 10**8 - 1)}"
            if number not in used_numbers:
                break
        ticket, sim, account, _w = rng.choices(PROFILES, weights=weights)[0]
        used_names.add(name)
        used_numbers.add(number)
        customers.append(
            {
                "customer_id": f"CUST{next_id}",
                "name": name,
                "mobile_number": number,
                "city": rng.choice(cities),
                "active_plan": rng.choice(PLANS),
                "sim_status": sim,
                "recent_ticket": ticket,
                "account_status": account,
            }
        )
        next_id += 1

    save("customers.json", customers)
    save("network.json", network)
    print(f"customers: {len(customers)} (last id CUST{next_id - 1}), cities: {len(network)}")


if __name__ == "__main__":
    main()