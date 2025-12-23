import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Load your dataset
df = pd.read_csv("data/insurance_data.csv")

# ----------------------------
# Helpers
# ----------------------------
def _rng_for_row(row):
    # Deterministic RNG per row, based on TRANSACTION_ID (fallback to index)
    key = str(row.get("TRANSACTION_ID", "")) + "|" + str(row.name)
    seed = abs(hash(key)) % (2**32)
    return np.random.default_rng(seed)

def _safe_str(x):
    return "" if pd.isna(x) else str(x)

# ----------------------------
# Generators (deterministic)
# ----------------------------
def generate_life_claim_fields(row):
    rng = _rng_for_row(row)
    cause_options = ["Natural Causes", "Accident", "Illness", "Heart Attack", "Stroke"]
    beneficiary_names = ["John Doe", "Jane Smith", "Robert Brown", "Emily Davis", "Michael Johnson"]
    return pd.Series({
        "DATE_OF_DEATH": _safe_str(row.get("LOSS_DT", "")),
        "CAUSE_OF_DEATH": rng.choice(cause_options),
        "BENEFICIARY_NAME": rng.choice(beneficiary_names),
        "BENEFICIARY_RELATION": rng.choice(["Spouse", "Child", "Parent", "Sibling"]),
        "PAYOUT_METHOD": "Bank Transfer",
    })

def generate_travel_claim_fields(row):
    rng = _rng_for_row(row)
    base_date = pd.to_datetime(row.get("POLICY_EFF_DT", pd.NaT), errors="coerce")
    if pd.isna(base_date):
        base_date = pd.Timestamp.today().normalize()
    trip_len = int(rng.integers(5, 15))
    return pd.Series({
        "TRIP_START_DT": base_date.strftime("%Y-%m-%d"),
        "TRIP_END_DT": (base_date + timedelta(days=trip_len)).strftime("%Y-%m-%d"),
        "DESTINATION": rng.choice(["Paris", "London", "Tokyo", "New York", "Toronto"]),
        "COVERED_PERILS": "Trip Cancellation / Baggage Loss / Medical Emergency",
        "LOSS_TYPE": rng.choice(["Baggage Loss", "Flight Delay", "Medical Emergency", "Trip Cancellation"]),
        "FLIGHT_REF": f"FL{int(rng.integers(1000, 9999))}",
    })

def generate_property_claim_fields(row):
    rng = _rng_for_row(row)
    damage_types = ["Fire", "Flood", "Theft", "Storm", "Vandalism"]
    claim_amt = float(row.get("CLAIM_AMOUNT", 0) or 0)
    est_mult = rng.uniform(0.8, 1.2)
    addr = ", ".join([_safe_str(row.get("ADDRESS_LINE1", "")),
                      _safe_str(row.get("CITY", "")),
                      _safe_str(row.get("STATE", ""))]).strip(", ")
    return pd.Series({
        "PROPERTY_TYPE": rng.choice(["Residential", "Commercial"]),
        "DAMAGE_TYPE": rng.choice(damage_types),
        "PROPERTY_ADDRESS": addr,
        "EST_REPAIR_COST": round(claim_amt * est_mult, 2),
    })

def generate_mobile_claim_fields(row):
    rng = _rng_for_row(row)
    brands = ["Apple iPhone 13", "Samsung Galaxy S22", "Google Pixel 7",
              "OnePlus 10 Pro", "Xiaomi 12T"]
    incident_types = ["Screen Damage", "Theft", "Liquid Damage", "Lost Device"]
    # 15-digit IMEI-like number
    imei = "".join(str(int(d)) for d in rng.integers(0, 10, size=15))
    return pd.Series({
        "DEVICE_MODEL": rng.choice(brands),
        "IMEI": imei,
        "LOSS_TYPE": rng.choice(incident_types),
        "PROOF_OF_PURCHASE": "Receipt Attached",
    })

def generate_motor_claim_fields(row):
    rng = _rng_for_row(row)
    # Generate realistic-looking VIN (17 chars)
    vin_chars = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
    vin = "".join(rng.choice(list(vin_chars)) for _ in range(17))
    
    # Generate License Plate (ABC-1234 style)
    letters = "".join(rng.choice(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")) for _ in range(3))
    nums = "".join(rng.choice(list("0123456789")) for _ in range(4))
    plate = f"{letters}-{nums}"
    
    return pd.Series({
        "VEHICLE_TYPE": rng.choice(["Sedan", "SUV", "Truck", "Motorcycle", "Van"]),
        "LICENSE_PLATE": plate,
        "VIN": vin,
    })

def generate_health_claim_fields(row):
    rng = _rng_for_row(row)
    # Common ICD-10 Codes
    diagnoses = ["J01.90", "M54.5", "E11.9", "I10", "J20.9", "S82.801A", "K21.9"]
    # Common CPT Codes
    procedures = ["99213", "99214", "71045", "80053", "85025", "97110"]
    
    return pd.Series({
        "DIAGNOSIS_CODE": rng.choice(diagnoses),
        "PROCEDURE_CODE": rng.choice(procedures),
        "PROVIDER_NAME": rng.choice(["General Hospital", "City Clinic", "Dr. Smith Practice", "Urgent Care Plus"]),
    })

# ----------------------------
# Enrichment without join()
# ----------------------------
df["INSURANCE_TYPE"] = df["INSURANCE_TYPE"].str.title()

life_mask     = df["INSURANCE_TYPE"].eq("Life")
travel_mask   = df["INSURANCE_TYPE"].eq("Travel")
property_mask = df["INSURANCE_TYPE"].eq("Property")
mobile_mask   = df["INSURANCE_TYPE"].eq("Mobile")
motor_mask    = df["INSURANCE_TYPE"].eq("Motor")
health_mask   = df["INSURANCE_TYPE"].eq("Health")

# Prepare target columns (so assignment works even if some masks are empty)
target_cols = [
    "DATE_OF_DEATH", "CAUSE_OF_DEATH", "BENEFICIARY_NAME", "BENEFICIARY_RELATION", "PAYOUT_METHOD",
    "TRIP_START_DT", "TRIP_END_DT", "DESTINATION", "COVERED_PERILS", "LOSS_TYPE", "FLIGHT_REF",
    "PROPERTY_TYPE", "DAMAGE_TYPE", "PROPERTY_ADDRESS", "EST_REPAIR_COST",
    "DEVICE_MODEL", "IMEI", "PROOF_OF_PURCHASE",
    "VEHICLE_TYPE", "LICENSE_PLATE", "VIN",
    "DIAGNOSIS_CODE", "PROCEDURE_CODE", "PROVIDER_NAME"
]
for col in target_cols:
    if col not in df.columns:
        df[col] = pd.NA

# Generate per type, then assign only to masked rows
if life_mask.any():
    gen = df.loc[life_mask].apply(generate_life_claim_fields, axis=1)
    for col in gen.columns:
        df.loc[life_mask, col] = gen[col].values

if travel_mask.any():
    gen = df.loc[travel_mask].apply(generate_travel_claim_fields, axis=1)
    for col in gen.columns:
        df.loc[travel_mask, col] = gen[col].values

if property_mask.any():
    gen = df.loc[property_mask].apply(generate_property_claim_fields, axis=1)
    for col in gen.columns:
        df.loc[property_mask, col] = gen[col].values

if mobile_mask.any():
    gen = df.loc[mobile_mask].apply(generate_mobile_claim_fields, axis=1)
    for col in gen.columns:
        df.loc[mobile_mask, col] = gen[col].values

if motor_mask.any():
    gen = df.loc[motor_mask].apply(generate_motor_claim_fields, axis=1)
    for col in gen.columns:
        df.loc[motor_mask, col] = gen[col].values

if health_mask.any():
    gen = df.loc[health_mask].apply(generate_health_claim_fields, axis=1)
    for col in gen.columns:
        df.loc[health_mask, col] = gen[col].values

# ----------------------------
# SCALED FRAUD INJECTION (Target: ~5-10%)
# ----------------------------
print("💉 Injecting SCALED Fraud Patterns...")

# 1. Shared PII Rings (Identity Fraud) - Target: 50 claims
# Create 3 distinct rings
rings = [
    {"ssn": "999-01-1111", "size": 20, "name": "Ring A"},
    {"ssn": "999-02-2222", "size": 15, "name": "Ring B"},
    {"ssn": "999-03-3333", "size": 15, "name": "Ring C"},
]
for ring in rings:
    indices = df.sample(ring["size"], random_state=hash(ring["name"]) % 1000).index
    df.loc[indices, "SSN"] = ring["ssn"]
    print(f"   -> Injected Shared PII {ring['name']} (SSN={ring['ssn']}) into {len(indices)} rows.")

# 2. Collusive Provider Rings - Target: 200 claims
# Ring 1: Bad Agent + Bad Vendor
indices_1 = df.sample(100, random_state=101).index
df.loc[indices_1, "AGENT_ID"] = "AGENT_BAD_007"
df.loc[indices_1, "VENDOR_ID"] = "VNDR_BAD_666"
df.loc[indices_1, "CLAIM_AMOUNT"] *= 1.8 # Inflate
print(f"   -> Injected Collusive Ring 1 (AGENT_BAD_007) into {len(indices_1)} rows.")

# Ring 2: Another Bad Pair
indices_2 = df.drop(indices_1).sample(100, random_state=102).index
df.loc[indices_2, "AGENT_ID"] = "AGENT_SHADY_99"
df.loc[indices_2, "VENDOR_ID"] = "VNDR_SKETCHY_88"
df.loc[indices_2, "CLAIM_AMOUNT"] *= 1.5
print(f"   -> Injected Collusive Ring 2 (AGENT_SHADY_99) into {len(indices_2)} rows.")

# 3. Asset Recycling - Target: ~60 claims
# Motor VIN Recycling
motor_indices = df[df["INSURANCE_TYPE"] == "Motor"].index
if len(motor_indices) > 20:
    # 4 VINs, 5 claims each
    for i in range(4):
        idxs = np.random.choice(motor_indices, 5, replace=False)
        fake_vin = f"RECYCLEDVIN000{i}"
        df.loc[idxs, "VIN"] = fake_vin
        print(f"   -> Injected Recycled VIN {fake_vin} into 5 Motor claims.")

# Mobile IMEI Recycling
mobile_indices = df[df["INSURANCE_TYPE"] == "Mobile"].index
if len(mobile_indices) > 20:
    for i in range(4):
        idxs = np.random.choice(mobile_indices, 5, replace=False)
        fake_imei = f"99000000000000{i}"
        df.loc[idxs, "IMEI"] = fake_imei
        print(f"   -> Injected Recycled IMEI {fake_imei} into 5 Mobile claims.")

# Property Address Recycling (New)
prop_indices = df[df["INSURANCE_TYPE"] == "Property"].index
if len(prop_indices) > 20:
    idxs = np.random.choice(prop_indices, 20, replace=False)
    fake_addr = "123 Fake St, Fraudtown, CA"
    df.loc[idxs, "PROPERTY_ADDRESS"] = fake_addr
    print(f"   -> Injected Recycled Property Address into {len(idxs)} Property claims.")

# 4. Velocity Fraud (Burst Claims) - Target: ~80 claims
# 20 customers, 4 claims each
customers = df["CUSTOMER_ID"].sample(20, random_state=200).values
for cust in customers:
    # Find or assign 4 rows to this customer
    cust_idxs = df[df["CUSTOMER_ID"] == cust].index
    if len(cust_idxs) < 4:
        cust_idxs = df.sample(4, random_state=hash(cust) % 1000).index
        df.loc[cust_idxs, "CUSTOMER_ID"] = cust
    
    # Burst dates
    base_date = datetime(2022, 1, 1)
    for i, idx in enumerate(cust_idxs[:4]):
        d = base_date + timedelta(days=i*7)
        df.loc[idx, "LOSS_DT"] = d.strftime("%Y-%m-%d")
        df.loc[idx, "REPORT_DT"] = (d + timedelta(days=1)).strftime("%Y-%m-%d")

print(f"   -> Injected Velocity Fraud for 20 customers (~80 claims).")

# 5. Double Dipping - Target: 100 claims (50 pairs)
# Pick 50 source claims
src_indices = df.sample(50, random_state=300).index
# Pick 50 dest claims (different customers)
dest_indices = df.drop(src_indices).sample(50, random_state=301).index

cols_to_copy = ["CLAIM_AMOUNT", "LOSS_DT", "INSURANCE_TYPE", "INCIDENT_CITY", "INCIDENT_STATE", "DESCRIPTION"] # Description might not exist, check cols
cols_to_copy = [c for c in cols_to_copy if c in df.columns]

for src, dest in zip(src_indices, dest_indices):
    for col in cols_to_copy:
        df.loc[dest, col] = df.loc[src, col]

print(f"   -> Injected Double Dipping into 50 pairs (100 claims).")

# Save
out_path = "insurance_data_enriched.csv"
df.to_csv(out_path, index=False)

print(f"✅ Enriched dataset saved as '{out_path}'")
print("Added/updated columns:", sorted(set(target_cols) & set(df.columns)))