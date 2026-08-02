import pandas as pd

flags = pd.read_csv("outputs/screening_v3/tisp_v3_flags.csv", low_memory=False)
ready = pd.read_csv("outputs/screening_v3/tisp_v3_analysis_ready.csv", low_memory=False)

veto = flags[flags["veto_any"] == 1]
vr = ready[ready["row_id"].isin(veto["row_id"])]

print(f"Vetoed rows in flags:    {len(veto)}")
print(f"Of which in analysis_ready: {len(vr)}")
print()

# Check trigger_reason for these rows
if "trigger_reason" in vr.columns:
    print("trigger_reason distribution:")
    print(vr["trigger_reason"].value_counts().to_string())
print()

# Show decisions
print("final_decision distribution:")
print(vr["final_decision"].value_counts().to_string())

# Save list of vetoed row ids that are in analysis_ready
vr[["row_id", "COUNTRY_CODE", "final_decision", "veto_any", "veto_gibberish", "veto_all_missing"]].to_csv(
    "veto_status_check.csv", index=False, encoding="utf-8-sig"
)
print("\nDetailed list saved to veto_status_check.csv")
