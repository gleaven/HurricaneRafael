"""One table of outside networks for every stream that records an outside address together with its
network number (the aid portal and base logistics access logs, payments/aid_applications.csv, the vessel
remote-session table, the partner organisations' logs and their extracts).

The rule this module enforces: the same address always carries the same network number, in every stream.
Spelling is each system's own ("ASN 7018" in access logs, a bare number in the applications file).

Everything is deterministic and has no dependency on any other generator.
"""
import hashlib

# ---- access providers: households, phones, small businesses -------------------------------------------
_HOME = [24, 47, 66, 67, 68, 70, 72, 73, 75, 76, 97, 98, 99, 107, 174]
RES = [7018, 11427, 22773, 20057, 21928, 20115, 7922]
PREFIXES = {}                       # network number -> ["a.b", ...] (each a /16 of that network)
_seen = set()
for _i, _n in enumerate(RES):
    _pf, _k = [], 0
    while len(_pf) < 5:
        _c = f"{_HOME[(_i * 5 + _k * 3) % len(_HOME)]}.{(17 * _i + 41 * _k + 9) % 240 + 8}"
        _k += 1
        if _c not in _seen:
            _seen.add(_c)
            _pf.append(_c)
    PREFIXES[_n] = _pf
# a regional provider and two small ones; part of their address space lies in the ranges reserved for
# documentation, as several delivered streams use those ranges for local networks
PREFIXES[64500] = ["174.62", "98.203"]
PREFIXES[64512] = ["107.151"]
PREFIXES[64496] = ["68.119"]
DOC = {"198.51.100": 64500, "203.0.113": 64512, "192.0.2": 64496}        # whole /24s
# hosting and cloud networks: crawlers, scanners, scripts, monitoring services
HOSTING = [64501, 64502, 64503, 64504, 64505, 64506, 64507, 64508, 64509, 64510, 64511]
_HPFX = [13, 23, 34, 35, 40, 52, 54, 142, 151, 157, 185, 205, 216, 45, 91, 146]
_TAKEN16 = {"162.40", "104.190", "199.21", "64.134", "69.15", "96.88", "12.186", "185.220", "104.21", "69.48"}      # blocks registries and other logs use
for _i, _n in enumerate(HOSTING):
    _pf, _k = [], 0
    while len(_pf) < 4:
        _c = f"{_HPFX[(_i * 3 + _k * 5) % len(_HPFX)]}.{(29 * _i + 53 * _k + 31) % 230 + 12}"
        _k += 1
        if _c not in _seen and _c not in _TAKEN16:
            _seen.add(_c)
            _pf.append(_c)
    PREFIXES[_n] = _pf
_BY16 = {p: n for n, pf in PREFIXES.items() for p in pf}

# where people in the Coastal Bend get their internet access (weights), and Houston for the vendor's staff
WEIGHTS = {"local": [(7018, 29), (11427, 22), (22773, 18), (20057, 12), (21928, 8), (64500, 4.5), (64512, 3.4), (20115, 3), (7922, 2), (64496, 1.2)],
           "houston": [(7922, 33), (20115, 22), (7018, 18), (20057, 12), (21928, 9), (64512, 2.4), (11427, 1.5), (64500, 1.2), (64496, 0.9)]}
MOBILE = [(20057, 0.6), (21928, 0.4)]

# ---- addresses that are somebody's in particular -------------------------------------------------------
# The outside network several hidden stories share uses 66 addresses of 203.0.113.0/24. They are scattered
# over the whole /24 (the old layout .17-.80, .87, .112 is mapped one to one), and the provider's ordinary
# customers use the other addresses of the same /24, so no cut on the last octet separates the two.


def _h(*k):
    return int(hashlib.sha256("|".join(map(str, k)).encode()).hexdigest()[:12], 16)


_order = sorted(range(1, 255), key=lambda o: _h("scatter", o))
_OLD = list(range(17, 81)) + [87, 112]
_NEW = sorted(_order[:len(_OLD)])
_perm = sorted(range(len(_OLD)), key=lambda i: _h("assign", i))
STORY_OCTET = {_OLD[i]: _NEW[_perm[i]] for i in range(len(_OLD))}
STORY_SET = {f"203.0.113.{o}" for o in STORY_OCTET.values()}
STORY_POOL = [f"203.0.113.{STORY_OCTET[o]}" for o in range(17, 81)]          # the 64 addresses of the probe, the sign-in runs and the account changes


def story_ip(old_octet):
    """Address that takes the place of 203.0.113.<old_octet> of the earlier layout."""
    return f"203.0.113.{STORY_OCTET[old_octet]}"


# single addresses other streams and registries give a fixed meaning; ordinary customers are never drawn from them
RESERVED = {"198.51.100.44",                                             # canon: one office's address
            "192.0.2.61", "192.0.2.62", "192.0.2.63", "192.0.2.90",       # recovery-centre kiosks and field tablets (aid applications)
            "192.0.2.130", "192.0.2.14", "192.0.2.150", "192.0.2.200", "192.0.2.210", "192.0.2.220"} | STORY_SET
VENDOR_BLOCK = range(64, 128)        # 192.0.2.64/26: the cargo-system vendor's published services and egress (see partner_it_registry)
VENDOR_OFFICE = [f"192.0.2.{n}" for n in range(96, 112)]                 # office egress pool
VENDOR_VPN = [f"192.0.2.{n}" for n in range(112, 127)]                   # staff VPN egress pool


def _doc_customers(base):
    out = []
    for o in range(1, 255):
        ip = f"{base}.{o}"
        if ip in RESERVED or (base == "192.0.2" and o in VENDOR_BLOCK):
            continue
        out.append(ip)
    return out


_DOC_POOL = {n: _doc_customers(b) for b, n in DOC.items()}
_DOC_SHARE = {64500: 0.3, 64512: 0.62, 64496: 0.75}                      # share of a provider's customers on its documentation-range /24


def asn_of(ip):
    """Network number of any address (None for private space)."""
    a = ip.split(".")
    if a[0] == "10" or ip.startswith("192.168.") or (a[0] == "172" and 16 <= int(a[1]) < 32) or (a[0] == "100" and 64 <= int(a[1]) < 128):
        return None
    b3 = ".".join(a[:3])
    if b3 in DOC:
        return DOC[b3]
    b2 = ".".join(a[:2])
    if b2 in _BY16:
        return _BY16[b2]
    return HOSTING[_h("net16", b2) % len(HOSTING)]


def label(ip, style="ASN {}"):
    n = asn_of(ip)
    return style.format(n) if n is not None else ""


def addr_in(n, h):
    """An ordinary customer address of network n chosen by the integer h (never a reserved or story address)."""
    if n in _DOC_POOL and (h % 1000) / 1000.0 < _DOC_SHARE[n]:
        pool = _DOC_POOL[n]
        return pool[(h >> 10) % len(pool)]
    pf = PREFIXES[n]
    return f"{pf[h % len(pf)]}.{1 + (h >> 5) % 249}.{2 + (h >> 14) % 248}"


def pick(pairs, x):
    tot = sum(w for _, w in pairs)
    acc = 0.0
    for v, w in pairs:
        acc += w / tot
        if x < acc:
            return v
    return pairs[-1][0]


def home(key, region="local", epoch=0):
    """(address, network number) of a household or small office. The provider is fixed per key; pass a
    slowly changing `epoch` to let the address change now and then, as residential addresses do."""
    n = pick(WEIGHTS[region], (_h("prov", region, key) % 10 ** 6) / 10.0 ** 6)
    if n in _DOC_POOL and (_h("docside", key) % 1000) / 1000.0 < _DOC_SHARE[n]:
        return addr_in(n, (_h("addr", key) << 10) | 0), n            # small providers share few addresses: stable
    h = _h("addr", key, epoch)
    pf = PREFIXES[n]
    return f"{pf[h % len(pf)]}.{1 + (h >> 5) % 249}.{2 + (h >> 14) % 248}", n


def mobile(key):
    n = pick(MOBILE, (_h("mob", key) % 10 ** 6) / 10.0 ** 6)
    h = _h("mobaddr", key)
    pf = PREFIXES[n]
    return f"{pf[h % len(pf)]}.{1 + (h >> 5) % 249}.{2 + (h >> 14) % 248}", n


def hosted(key):
    """(address, network number) of a server-side client: crawler, scanner, script, monitoring probe."""
    r = _h("hostkind", key) % 100
    if r < 6:                                         # some run from small providers, including the documentation ranges
        n = (64512, 64496, 64500)[_h("hk", key) % 3]
        return addr_in(n, _h("ha", key)), n
    n = HOSTING[_h("hn", key) % len(HOSTING)]
    h = _h("ha", key)
    pf = PREFIXES[n]
    return f"{pf[h % len(pf)]}.{1 + (h >> 5) % 249}.{2 + (h >> 14) % 248}", n
