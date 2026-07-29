"""Export full context for 9 unsure cases: closed-end patterns + signals + open-ends."""
import pandas as pd
import numpy as np

BASE = r"D:\开山\收集数据\D081_TISP"
UNSURE_IDS = [35055, 43310, 43438, 43508, 43550, 43647, 43734, 44090, 43796]

# Scale definitions (from 04_screen_tisp_v3.py)
SCIINFO = ["SCIINFO_newspapersmags","SCIINFO_tvradio","SCIINFO_newswebsitesapps","SCIINFO_videospodcasts","SCIINFO_filmsseries","SCIINFO_books","SCIINFO_socialmedia","SCIINFO_messengers","SCIINFO_museumszoos","SCIINFO_rlconversations"]
NORMPERC = ["NORMPERC_integrate","NORMPERC_advocate","NORMPERC_communicate","NORMPERC_involved","NORMPERC_outreach","NORMPERC_independent"]
TRUST_SCI = ["TRUST_SCI_expert","TRUST_SCI_honest","TRUST_SCI_concerned","TRUST_SCI_open","TRUST_SCI_intellig","TRUST_SCI_ethical","TRUST_SCI_improve","TRUST_SCI_trans","TRUST_SCI_qualified","TRUST_SCI_sincere","TRUST_SCI_otherint","TRUST_SCI_otherviews"]
SCIPOP = ["SCIPOP_common","SCIPOP_good","SCIPOP_advantage","SCIPOP_cahoots","SCIPOP_influence","SCIPOP_involved","SCIPOP_lifeexp","SCIPOP_rely"]
CLIM_EMO = ["CLIM_EMO_helpless","CLIM_EMO_anxious","CLIM_EMO_optimistic","CLIM_EMO_angry","CLIM_EMO_guilty","CLIM_EMO_ashamed","CLIM_EMO_depressed","CLIM_EMO_pessimistic","CLIM_EMO_indifferent"]
CLIM_GOV = ["CLIM_GOV_concerns","CLIM_GOV_doingenough","CLIM_GOV_dismisspeople","CLIM_GOV_science","CLIM_GOV_futuregens","CLIM_GOV_trustworthy","CLIM_GOV_lying"]
CLIM_WEATHERPAST = ["CLIM_WEATHERPAST_floods","CLIM_WEATHERPAST_heatwaves","CLIM_WEATHERPAST_heavystorms","CLIM_WEATHERPAST_wildfires","CLIM_WEATHERPAST_heavyrain","CLIM_WEATHERPAST_droughts"]
CLIM_WEATHERFUTU = ["CLIM_WEATHERFUTU_floods","CLIM_WEATHERFUTU_heatwaves","CLIM_WEATHERFUTU_heavystorms","CLIM_WEATHERFUTU_wildfires","CLIM_WEATHERFUTU_heavyrain","CLIM_WEATHERFUTU_droughts"]
OUTSPOKEN = ["OUTSPOKEN_othersthink","OUTSPOKEN_isolate","OUTSPOKEN_against"]
SDO = ["SDO_allgroupsconsider","SDO_notpushequality","SDO_equalityideal","SDO_superiordominate"]

ALL_SCALES = [
    ("SCIINFO", SCIINFO, "1-7"),
    ("NORMPERC", NORMPERC, "1-5"),
    ("TRUST_SCI", TRUST_SCI, "1-5"),
    ("SCIPOP", SCIPOP, "1-5"),
    ("CLIM_EMO", CLIM_EMO, "1-5"),
    ("CLIM_GOV", CLIM_GOV, "1-5"),
    ("CLIM_WEATHERPAST", CLIM_WEATHERPAST, "1-5"),
    ("CLIM_WEATHERFUTU", CLIM_WEATHERFUTU, "1-5"),
    ("OUTSPOKEN", OUTSPOKEN, "1-5"),
    ("SDO", SDO, "1-5"),
]

# Load flags (has ALL columns + signals)
flags = pd.read_csv(f"{BASE}\\outputs\\screening_v3\\tisp_v3_flags.csv",
                    dtype=str, keep_default_na=False, encoding="utf-8")

all_cols = ["row_id","COUNTRY_CODE","COUNTRY_NAME","COUNTRY_CONT",
            "ATTCHECK_NUMBER","ATTCHECK_RES",
            "DEM_AGE","DEM_GENDER","DEM_EDU","DEM_AGEGRP",
            "BENEFIT_OPEN","TRUST_OPEN",
            "ls_max_run","md_score","oe_r",
            "signal_attention","signal_longstring","signal_mahalanobis","signal_odd_even",
            "screening_tier","trigger_reason","veto_any"]

# Add all scale columns
for _, cols, _ in ALL_SCALES:
    all_cols.extend(cols)
all_cols = list(dict.fromkeys(all_cols))  # deduplicate preserving order

sub = flags.loc[flags["row_id"].astype(int).isin(UNSURE_IDS), all_cols].copy()
sub["row_id"] = sub["row_id"].astype(int)

# Sort by row_id
sub = sub.sort_values("row_id")

# Build output
out_lines = []
for _, r in sub.iterrows():
    rid = r["row_id"]
    country = r["COUNTRY_CODE"]
    tier = r["screening_tier"]
    reason = r["trigger_reason"]
    ls = r["ls_max_run"]
    md = r["md_score"]
    oe = r["oe_r"]

    out_lines.append(f"=== row_id={rid} | {country} | {tier} | {reason} ===")
    out_lines.append(f"信号值: ls_max_run={ls} | md_score={md} | oe_r={oe}")
    out_lines.append(f"注意力: ATTCHECK_NUMBER={r['ATTCHECK_NUMBER']} | ATTCHECK_RES={r['ATTCHECK_RES']}")
    out_lines.append(f"人口学: AGE={r['DEM_AGE']} | GENDER={r['DEM_GENDER']} | EDU={r['DEM_EDU']} | AGEGRP={r['DEM_AGEGRP']}")

    # Scale-by-scale answer sequence
    for scale_name, cols, scale_range in ALL_SCALES:
        seq = " ".join(r.get(c, "") for c in cols)
        out_lines.append(f"  [{scale_name}] ({scale_range}): {seq}")

    # Open-ends
    benefit = r.get("BENEFIT_OPEN", "")
    trust = r.get("TRUST_OPEN", "")
    out_lines.append(f"  BENEFIT_OPEN: {benefit}")
    out_lines.append(f"  TRUST_OPEN: {trust}")
    out_lines.append("")

result = "\n".join(out_lines)
print(result)

# Also save to file
out_path = f"{BASE}\\analysis\\unsure_context.txt"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(result)
print(f"\nSaved to {out_path}")
