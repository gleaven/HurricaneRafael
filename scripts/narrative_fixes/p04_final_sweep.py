"""Final consistency sweep, 2026-11-11: residues of narrative-audit defects D02, D04, D07, D10 found when the
closure table (07_validation/reports/audit_closure.md) was verified against the files, and the MSEL copy of D38."""

STORIES = {
    # D02: one address for the recovery centre (Oveal Williams Senior Center, Martin Luther King Drive): the wording is
    # set in p01_audit_blockers.py (NWS-P057-04)
    # D04: the charging document is a criminal complaint (PUB-210), not an indictment
    "NWS-P090-05": {"replace": [("according to an indictment unsealed Monday", "according to a criminal complaint unsealed Monday"),
                                ("The indictment alleges", "The complaint alleges"),
                                ("in connection with 128 fraudulent water-damage remediation claims", "in connection with fraudulent water-damage remediation claims")]},
    "NWS-P090-06": {"replace": [("According to an indictment unsealed Monday", "According to a criminal complaint unsealed Monday"),
                                # no public fact carries a count of the restoration firm's claims
                                ("faces separate charges arising from 128 fraudulent water-damage claims", "faces separate charges arising from fraudulent water-damage claims")]},
    "NWS-P090-07": {"replace": [("unsealed an indictment against", "unsealed a criminal complaint naming")]},
    # D07: the citywide notice has been in force since Sept. 18; the districts' notice is not the largest action since 2008
    "NWS-P012-06": {"replace": [(" and is the most significant water quality action in the city since Hurricane Dolly in 2008", "")]},
    # D10: helicopters flew from 1:22 a.m. Tuesday and rescues continued until Sunday (702 on Thursday evening, 1,427 on Sunday)
    "NWS-P005-06": {"replace": [
        ("Some areas remained inaccessible for the first 48 hours because surge water depth and debris made boat or foot access impossible and wind conditions prevented helicopter operations. Those areas have since been cleared.",
         "Some streets could not be reached by boat or on foot for the first 48 hours because of surge depth and debris, and there the helicopter crews did the work. Those areas have since been cleared."),
        ("She noted that the last confirmed living survivor rescue occurred at approximately 2200 Thursday, more than 60 hours after landfall.",
         "She noted that the pace had slowed since Thursday evening, when the count stood at 702, and that the last rescues were logged Sunday afternoon."),
    ]},
}

FILES = [
    ("00_scenario/msel.json", "consistent with 24-hour behavioral lag from notification delay", "consistent with the behavioral lag from the 12-hour 33-minute notification delay"),
]
