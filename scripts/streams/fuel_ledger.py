"""One ledger for the emergency generator-fuel contract at NAS Corpus Christi (N6883627C0075).

Read by gen_ot_records.py (delivery tickets in supply/fuel_deliveries.csv) and gen_finance.py (contract invoices), so
ticket numbers, dates and gallons agree in both. Deliveries start on D+33 (2027-10-17), the day after the supplier's
terminal receives its barge lot, and stop before the suspension on D+75."""
from common import rng

DELIVERY_DAYS = [33, 35, 38, 41, 45, 49, 54, 59, 64, 69]


def deliveries():
    """[(k, day, ticket_no, gallons, unit_price)] in delivery order."""
    r = rng("fuel-inv")
    out = []
    for k, dday in enumerate(DELIVERY_DAYS):
        gal = int(r.integers(21, 39)) * 1000
        price = round(float(r.uniform(5.62, 5.94)), 3)
        gal += int(rng("fuel-ledger", k).integers(-460, 470))          # metered gallons, not round truckloads
        out.append((k, dday, f"QF-{2100 + k}", gal, price))
    return out
