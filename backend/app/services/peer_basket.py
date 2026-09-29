"""CR247 Phase 1C — the same-4-digit-SIC peer basket behind the Fundamentals
lane's "Peer comparison" line.

The sheet always carried the company's own multiples and, since CR219 R37,
its multiples against its OWN history — but never a read across OTHER
companies, so "is 38x cheap for this industry" was not a question the sheet
could support (`_sector_line` says so itself). This module assembles the
basket:

  * **Membership** — same 4-digit SIC as the target. SIC is the SEC's own
    industry code, read from the submissions JSON `company_profile.py`
    already consumes (`edgar_submissions.fetch_company_submissions`). The
    candidate list below is a hand-maintained PROBE list, never a fact:
    every candidate's membership is verified live at resolve time against
    its own submissions JSON, and a candidate that does not file under the
    target's exact SIC (or cannot be read) is dropped. Nothing from the
    list is ever rendered — only live-verified membership is.
  * **Neighbourhood** — the `_BASKET_SIZE` verified peers whose market caps
    sit nearest the target's own (log-distance), market caps from yfinance
    `.info`, the same source the sheet's own `market_cap` comes from. No
    screener integration exists or is wanted: if the basket cannot be
    assembled from data in hand, the resolution is `None` with a reason
    and the renderer states it (CR040), never a fabricated or widened
    basket — the SIC is never fuzzy-matched to make up the count.
  * **Figures** — median trailing P/E, median EV/EBITDA, median net margin
    across the basket, computed here in code (CR179 Leg 4: the model never
    computes a figure). A peer missing a field is excluded from THAT
    median and the effective n is stated on the rendered line.

Refresh semantics: one resolution per target ticker per `_REFRESH_DAYS`,
lazy (seeded on the first convene that asks for the ticker, never bulk),
in-process. A failed resolution retries after `_FAILURE_RETRY`, not the
full week — a transient provider outage must not lock the line out for
seven days (the live/degraded TTL split `company_profile.py` makes).
Process restart cold-starts the store; that is the accepted cost of an
in-memory store, same tradeoff CR244's other caches make.

Live-only: peer quotes have no historical store, so an as-of profile build
gets `unavailable` with that reason rather than today's peers on a
past-dated sheet (the DEF334 lesson, same as `put_call.py`). The room
overlay also declines when the target's own market cap is not live: the
neighbourhood is defined by it, and an unanchored basket would not be the
basket the line names.

No feature flag is read here — the flag gates the render. Test seams:
`set_peer_fetchers` injects the two network calls; `clear_peer_basket_store`
drops every cached resolution (conftest pins both off, the
`liquidity_lookup` precedent, so no test reaches SEC or Yahoo by default).
"""

from __future__ import annotations

import math
import statistics
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.core.logging import logger
from app.services import edgar_submissions
from app.services.edgar_cik import CikResolutionUnavailable, resolve_cik

# ── Refresh semantics ────────────────────────────────────────────────────────

_REFRESH_DAYS = 7
_REFRESH_TTL = timedelta(days=_REFRESH_DAYS)
# A failed resolution retries after one hour, not the full week: an outage is
# transient by nature, and the weekly cadence is about paying for a successful
# re-resolution, not about caching a failure (the company_profile TTL split).
_FAILURE_RETRY = timedelta(hours=1)

# The rendered line states this; the SPEC example names 7.
_BASKET_SIZE = 7
# Fewer than this and a median is two points wearing a statistic's clothes —
# the SPEC's floor, and the reason the SIC is never widened to reach it.
_MIN_PEERS = 3

# ── The candidate probe list ─────────────────────────────────────────────────
#
# Hand-maintained, keyed by 4-digit SIC. THIS LIST IS NEVER RENDERED AND NEVER
# TAKEN ON TRUST: `refresh_peer_basket` verifies every candidate's SIC live
# against its own submissions JSON before it can enter a basket, so a stale
# entry (a company that changed SIC, a delisted ticker) can only cost
# coverage, never truth. Extend it with large US-listed names; the coverage
# escape hatch (not_available, "insufficient peer coverage") is the honest
# answer for SICs nobody has mapped yet.
_CANDIDATES_BY_SIC: dict[str, tuple[str, ...]] = {
    # Crude petroleum & natural gas / refining.
    "1311": ("XOM", "CVX", "COP", "EOG", "OXY", "MPC", "PSX", "VLO", "HES",
             "DVN", "FANG", "APA", "MRO", "CTRA", "EQT", "OVV"),
    "2911": ("XOM", "CVX", "COP", "VLO", "MPC", "PSX", "HFC", "DK", "PBF"),
    # Semiconductors & related devices.
    "3674": ("NVDA", "AVGO", "AMD", "TXN", "QCOM", "INTC", "MU", "ADI",
             "MCHP", "NXPI", "MRVL", "ON", "SWKS", "MPWR", "QRVO", "TER"),
    # Semiconductor/special-industry machinery (the equipment half).
    "3559": ("AMAT", "LRCX", "KLAC", "TER", "ASML", "UMC", "TSM"),
    # Electronic computers / storage / peripherals.
    "3571": ("HPE", "HPQ", "DELL", "SMCI", "IBM"),
    "3572": ("STX", "WDC", "SNDK"),
    "3577": ("LOGI", "CRUS"),
    # Prepackaged software / computer services / data processing.
    "7372": ("MSFT", "ORCL", "CRM", "ADBE", "NOW", "INTU", "PLTR", "SNOW",
             "WDAY", "TEAM", "PANW", "CRWD", "FTNT", "DDOG", "NET", "OKTA",
             "ZS", "APP", "HUBS", "ZM", "DOCU", "MDB", "TWLO"),
    "7370": ("GOOGL", "META", "IBM", "ACN", "CTSH", "EPAM", "IT", "DOX"),
    "7373": ("IBM", "ACN", "CTSH", "DXC", "EPAM", "GLOB", "NXT"),
    "7374": ("ADP", "PAYX", "BR", "FIS", "GPN", "TIXT", "PAYC", "WDAY"),
    "7375": ("GOOGL", "META", "SNAP", "PINS", "RDDT", "BIDU", "YELP"),
    # Mail-order / nonstore retail.
    "5961": ("AMZN", "EBAY", "ETSY", "W", "CHWY", "DASH", "CPNG", "MELI"),
    # Motor vehicles & parts.
    "3711": ("TSLA", "F", "GM", "RIVN", "LCID", "NIO", "XPEV", "LI", "FSR"),
    "3714": ("BWA", "LEA", "MGA", "DLPH", "GNTX", "ALV", "ADNT", "MREO"),
    # Truck & bus bodies / farm machinery / construction machinery.
    "3713": ("PCAR", "CMI", "NAV", "REV"),
    "3523": ("DE", "AGCO", "CNH", "TTC", "LNN", "ALG"),
    "3531": ("CAT", "CMI", "TEX", "OSK", "ALSN", "AGCO", "JCI", "CNHI"),
    "3533": ("NOV", "FTI", "SLB", "OII", "DRQ", "HP", "PTEN", "WFT"),
    # Aerospace / aircraft parts / missiles & space.
    "3721": ("BA", "TDG", "HWM", "TXT", "GD", "CW", "WWD", "TGI", "HXL",
             "SPR"),
    "3716": ("TDG", "HWM", "HEI", "SPR", "WWD", "CW", "TGI", "HXL", "LDI"),
    "3760": ("LMT", "NOC", "RTX", "GD", "TXT", "HII", "LDOS", "BAH", "SAIC",
             "KTOS", "RKLB", "AJRD"),
    # Electronic components / connectors / comms equipment.
    "3679": ("GLW", "APH", "TEL", "JBL", "FLEX", "SANM", "BHE", "PLXS",
             "VSH", "CTS"),
    "3678": ("APH", "TEL", "GLW", "JBL", "BDC", "RBC"),
    "3661": ("CSCO", "HRS", "MSI", "JNPR", "ANET", "EXTR", "CALX", "HLIT"),
    "3669": ("MSI", "PANW", "JNPR", "ANET", "CRWD", "FTNT", "VRNS", "OSUR"),
    "3613": ("ETN", "HUBB", "POWL", "ABB", "RBC", "GEV", "SPXC", "AOS"),
    # Instruments / medical.
    "3826": ("TMO", "DHR", "A", "MTD", "WAT", "BRKR", "PKI", "ITRI", "NOVT"),
    "3841": ("ABT", "MDT", "SYK", "BDX", "BSX", "EW", "ZBH", "DXCM", "HOLX",
             "BAX", "STE", "CNMD", "GMED"),
    "3845": ("ISRG", "HOLX", "NXTM", "PHG", "ICUI", "INFU"),
    "3844": ("GEHC", "PHG", "SIEM", "HOCPY", "HSM"),
    "3812": ("GD", "TDY", "LDOS", "HRS", "GRMN", "CUB", "MOG", "CW"),
    # Pharmaceuticals / biotech.
    "2834": ("JNJ", "PFE", "MRK", "LLY", "ABBV", "BMY", "AMGN", "GILD",
             "VRTX", "REGN", "ZTS", "SNY", "AZN", "NVS", "NVO", "WBA"),
    "2836": ("MRNA", "BIIB", "AMGN", "GILD", "VRTX", "REGN", "INCY", "SGEN",
             "EXEL", "CRSP", "NTLA", "BEAM", "ALNY", "IONS", "SRPT"),
    # Beverages / packaged food / tobacco.
    "2086": ("KO", "PEP", "MNST", "KDP", "CCEP", "FIZZ", "COTY", "STZ",
             "TAP", "SAM", "BF", "DEO"),
    "2080": ("KO", "PEP", "MNST", "KDP", "STZ", "TAP", "SAM", "FMX", "CCU"),
    "2000": ("GIS", "K", "HSY", "CAG", "SJM", "MDLZ", "KHC", "CPB", "HRL",
             "MKC", "CVT", "LW", "TSN", "PPC", "SJM", "FLO"),
    "2111": ("MO", "PM", "BTI", "UVV", "VGR", "TPB", "XXII"),
    # Household / personal products.
    "2840": ("PG", "CL", "CHD", "ECL", "EL", "CLX", "KMB", "COTY", "ELF",
             "UL", "UN", "ENR", "REV", "OUST"),
    "2841": ("PG", "CL", "CHD", "CLX", "KMB", "EL", "UL", "COTY", "ELF"),
    # Chemicals / specialty chemicals.
    "2800": ("DOW", "DD", "LYB", "EMN", "ASH", "ALB", "CE", "PPG", "SHW",
             "ECL", "IFF", "ALB", "CF", "MOS", "FMC", "NTR", "SMG", "WLK",
             "HUN", "KRO", "PQG"),
    "2870": ("CF", "MOS", "FMC", "NTR", "SMG", "UAN", "LXU", "IPI"),
    # Metals & mining.
    "3312": ("X", "NUE", "STLD", "CLF", "RS", "CMC", "TMST", "ASTL", "ATI",
             "KALU", "WOR", "SCHN", "CMC"),
    "3334": ("AA", "CENX", "ARNC", "HWM", "KALU", "RYI", "CSTM"),
    "1020": ("FCX", "SCCO", "TECK", "BHP", "RIO", "VALE", "NEM", "GOLD",
             "AEM", "KGC", "WPM"),
    # Rails / trucking / air transport.
    "4011": ("UNP", "CSX", "NSC", "CP", "CNI", "GWR", "WAB"),
    "4210": ("UPS", "FDX", "ODFL", "JBHT", "XPO", "CHRW", "SNDR", "KNX",
             "WERN", "SAIA", "HTLD", "USX"),
    "4512": ("DAL", "UAL", "AAL", "LUV", "ALK", "JBLU", "SAVE", "MESA",
             "SKYW"),
    "4481": ("RCL", "CCL", "NCLH", "VIK", "LIND"),
    # Telecom.
    "4812": ("VZ", "T", "TMUS", "USM", "CNSL", "CTL"),
    "4813": ("VZ", "T", "TDS", "CTL", "FTR", "WIN"),
    "4841": ("CMCSA", "CHTR", "DISH", "LBRDA", "LBRDK", "ATUS", "CABO"),
    "4833": ("FOXA", "NXST", "SBGI", "GTN", "SSP", "TEGNA", "TVR"),
    # Electric / gas / water utilities.
    "4911": ("NEE", "DUK", "SO", "AEP", "EXC", "SRE", "XEL", "ED", "WEC",
             "ES", "PEG", "FE", "CEG", "VST", "NRG", "D", "PPL", "AES",
             "EIX", "PCG", "DTE", "AEE", "ETR", "EVRG", "LNT", "MGEE",
             "PNW", "IDA", "OTTR", "ALE", "SR", "CWCO", "YORW", "CTWS"),
    "4922": ("WMB", "KMI", "OKE", "ET", "EPD", "MPLX", "PAA", "WES", "AM"),
    "4941": ("AWK", "CWT", "SJW", "YORW", "CTWS", "MSEX", "PNNW"),
    "4953": ("WM", "RSG", "SRCL", "CLH", "WCN", "CWST", "GFL"),
    "4950": ("WM", "RSG", "SRCL", "CLH", "WCN", "CWST", "GFL", "ECOL"),
    # Banks / brokers / insurers.
    "6021": ("JPM", "BAC", "WFC", "C", "USB", "PNC", "TFC", "COF", "FITB",
             "MTB", "KEY", "RF", "CFG", "HBAN", "ZION", "WAL", "SNV", "TCB"),
    "6022": ("JPM", "BAC", "WFC", "C", "USB", "PNC", "TFC", "COF", "FITB",
             "MTB", "KEY", "RF", "CFG", "HBAN", "ZION", "WAL", "NYCB"),
    "6211": ("GS", "MS", "SCHW", "IBKR", "RJF", "TW", "HOOD", "SOFI", "MC",
             "PJT", "LAZ", "EVR", "MCO", "SPGI"),
    "6231": ("ICE", "CME", "NDAQ", "MSCI", "CBOE", "MKTX", "NMR", "DB",
             "SCHW"),
    "6282": ("BLK", "STT", "BEN", "IVZ", "TROW", "APO", "KKR", "CG", "ARES",
             "OWL", "PAX", "VCTR", "HLNE", "SEIC", "FDS"),
    "6311": ("MET", "PRU", "AFL", "LNC", "UNM", "PFG", "CNO", "GCO", "AMIC"),
    "6321": ("UNH", "ELV", "CI", "HUM", "CNC", "MOH", "ALHC", "CLOV", "OSH"),
    "6324": ("UNH", "ELV", "CI", "HUM", "CNC", "MOH", "BTSG", "ACHC"),
    "6331": ("BRK.B", "CB", "AIG", "TRV", "ALL", "PGR", "CINF", "HIG",
             "CNA", "RLI", "MKL", "RGA", "RE", "AFG", "KMPR", "THG",
             "WRB", "CNA"),
    "6411": ("AON", "MMC", "BRO", "AJG", "WTW", "ACGL", "RGA", "EHTH"),
    # REITs / real estate.
    "6798": ("PLD", "AMT", "EQIX", "CCI", "PSA", "WELL", "O", "SPG",
             "VICI", "SBAC", "DLR", "AVB", "EQR", "BXP", "ARE", "VTR",
             "PEAK", "EXR", "CUBE", "IRM", "HST", "ESS", "CPT", "INVH",
             "MAA", "UDR", "AIV", "BRX", "KIM", "FRT", "REG", "NNN",
             "STAG", "ADC", "EPR", "SKT"),
    "6513": ("AVB", "EQR", "ESS", "CPT", "MAA", "UDR", "AIV", "INVH",
             "BRG", "IRT", "NXRT"),
    "6531": ("CBRE", "JLL", "CWK", "KRC", "BXP", "HPP", "VNO", "SLG",
             "ARE", "KIM", "FRT"),
    # Retail.
    "5331": ("WMT", "TGT", "DG", "DLTR", "FIVE", "BIG", "PSMT", "GO"),
    "5411": ("KR", "ACI", "SFM", "GO", "TFM", "WFM", "HFT", "UNFI"),
    "5311": ("M", "JWN", "KSS", "DDS", "BJ", "TGT", "KSS", "M", "DDS"),
    "5651": ("ROST", "TJX", "BURL", "GPS", "UAA", "CRI", "GIL", "LEVI"),
    "5661": ("FL", "DSW", "SCVL", "SHOO", "CAL", "SKX", "DECK", "CROX"),
    "5699": ("LULU", "DECK", "CROX", "UA", "UAA", "SKX", "FOSL", "MOV"),
    "5712": ("ETD", "HVT", "LZB", "SNBR", "TPX", "WH", "BC", "HOFT"),
    "5731": ("BBY", "HGG", "CON", "SPLS", "ODP"),
    "5912": ("CVS", "WBA", "RAD", "CNC", "MOH", "COR", "HSIC", "PETS"),
    "5812": ("MCD", "YUM", "QSR", "DRI", "CMG", "DPZ", "TXRH", "EAT",
             "WING", "SHAK", "BROS", "JACK", "WEN", "BKW", "DNUT", "PZZA"),
    "5810": ("SBUX", "MCD", "YUM", "QSR", "DRI", "CMG", "DPZ", "TXRH"),
    "5611": ("M", "JWN", "TJX", "ROST", "BURL", "GPS", "KSS", "DDS"),
    "5621": ("ROST", "TJX", "BURL", "GPS", "ANN", "CHS", "DSW"),
    "5941": ("DKS", "HIBB", "ASO", "BGFV", "VSTO", "JOUT", "SPWH"),
    "5944": ("SIG", "TIF", "ZLC", "BRGO", "MPWW"),
    "5945": ("HAS", "MAT", "FUN", "GOLF", "JAKK", "LF"),
    # Hospitality / leisure / media.
    "7011": ("MAR", "HLT", "H", "HYATT", "CHH", "WYN", "MGM", "LVS",
             "CZR", "BYD", "PNK", "ERI", "GDEN", "RRR", "BOYD"),
    "7812": ("DIS", "NFLX", "WBD", "PARA", "FOXA", "LYV", "AMCX", "ENT",
             "CNK", "IMAX", "RDI", "AMC"),
    "7832": ("AMC", "CNK", "IMAX", "RDI", "CINE", "MCS"),
    "7841": ("NFLX", "ROKU", "SPOT", "HBO", "PARA", "FOXA", "LYV"),
    "7990": ("DIS", "SEAS", "FUN", "SIX", "PLAY", "GOLF", "PENN", "CHDN",
             "BYD", "GDEN", "RRR", "IGT", "SGMS", "WYNN", "MGM"),
    "7996": ("FUN", "SIX", "SEAS", "EPC", "EAT"),
    "7941": ("MSGS", "BATRA", "FWONA", "MANU", "EPL", "MAD"),
    "7997": ("MSGS", "BATRA", "FWONA", "MANU", "MAD", "EPL"),
    # Health care providers.
    "8062": ("HCA", "THC", "UHS", "CYH", "SEM", "RHC", "ACHC", "LPNT",
             "QHC", "HMA"),
    "8071": ("DGX", "LH", "BIO", "XRAY", "HSIC", "ALR", "NEOG", "GKOS",
             "SNN"),
    "8092": ("DVA", "FMS", "BAX", "BIVV", "KDNY", "IRBT", "NXTM", "INFU"),
    "8093": ("HCA", "THC", "UHS", "SEM", "RHC", "ACHC", "BTSG", "AMN"),
    # Business services / data / advertising.
    "7321": ("TRU", "EFX", "EXPN", "FICO", "BR", "WK", "HURN"),
    "7311": ("OMC", "IPG", "WPP", "CCO", "LAMR", "CUK", "STZ"),
    "7371": ("ACN", "CTSH", "EPAM", "GLOB", "IT", "DOX", "LDOS", "BAH",
             "SAIC", "CACI", "VRSN"),
    "7389": ("FLT", "ADS", "WU", "GPN", "VNT", "FOUR", "EVTC", "PRTH",
             "ATIP"),
    "7341": ("ROL", "ECL", "SERV", "TRU", "VVI", "ABM", "TTC", "SCI"),
    "7200": ("SCI", "CSV", "STON", "MATW", "BCC", "HI", "BNY", "AWI"),
    # Education / other.
    "8211": ("BFAM", "LRN", "STRA", "APEI", "UTI", "EDMC", "CEC", "BPI"),
    "8221": ("CHGG", "TWOU", "LOPE", "STRA", "APEI", "EDU", "FEDU", "NEW"),
    "8299": ("CHGG", "TWOU", "LOPE", "STRA", "APEI", "UTI", "EDMC"),
    "8999": ("SPGI", "MCO", "FDS", "MSCI", "TRU", "EFX", "BR", "VRSN",
             "WLTW", "AJG", "MMC", "AON", "BRO"),
}

# Fetcher shapes: the submissions JSON by CIK (the shared CR244 read) and the
# yfinance `.info` dict by ticker. Both return None on any failure — a fetch
# problem degrades its own resolution, never raises through the overlay.
SubmissionsFetcher = Callable[[int], dict | None]
InfoFetcher = Callable[[str], dict | None]


@dataclass(frozen=True)
class PeerRow:
    """One verified basket member, with every figure the medians draw on.

    `market_cap` is raw dollars (the `.info` convention); `net_margin_pct`
    is already a percent to match the sheet's own margin figures. None means
    the provider did not serve the field — excluded from that median, never
    zeroed (DEF053).
    """

    ticker: str
    cik: int | None
    sic: str
    market_cap: float | None
    trailing_pe: float | None
    ev_to_ebitda: float | None
    net_margin_pct: float | None


@dataclass(frozen=True)
class PeerMedians:
    """The three basket medians, each with its effective n.

    A peer missing a field is excluded from THAT median only, so each median
    carries its own count — the line states it whenever it differs from the
    basket size.
    """

    trailing_pe: float | None
    trailing_pe_n: int
    ev_ebitda: float | None
    ev_ebitda_n: int
    net_margin_pct: float | None
    net_margin_n: int


@dataclass(frozen=True)
class PeerBasket:
    """One weekly resolution for one target ticker."""

    ticker: str
    sic: str
    sic_description: str | None
    members: tuple[PeerRow, ...]
    as_of: date
    medians: PeerMedians


@dataclass(frozen=True)
class PeerBasketResult:
    """What `refresh_peer_basket` returned: the basket, or WHY there is none.

    `reason` is renderer-facing copy: it lands on the sheet's not-available
    line, so it states the fact ("insufficient peer coverage — …") and never
    an internal detail.
    """

    basket: PeerBasket | None
    reason: str | None = None


def _num(d: dict, key: str) -> float | None:
    v = d.get(key)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def compute_medians(members: tuple[PeerRow, ...] | list[PeerRow]) -> PeerMedians:
    """Median trailing P/E, EV/EBITDA and net margin across the basket.

    Per-field exclusion with the effective n, and medians computed in Python
    (CR179 Leg 4 — the model is never handed operands and an instruction).
    Multiples to one decimal to match the sheet's own multiple figures; the
    margin to a whole percent, matching `ratio_to_pct(decimals=0)`.
    """

    def _median(values: list[float], digits: int) -> tuple[float | None, int]:
        if not values:
            return None, 0
        return round(statistics.median(values), digits), len(values)

    pe, n_pe = _median([m.trailing_pe for m in members if m.trailing_pe is not None], 1)
    ev, n_ev = _median([m.ev_to_ebitda for m in members if m.ev_to_ebitda is not None], 1)
    nm, n_nm = _median([m.net_margin_pct for m in members if m.net_margin_pct is not None], 0)
    return PeerMedians(
        trailing_pe=pe, trailing_pe_n=n_pe,
        ev_ebitda=ev, ev_ebitda_n=n_ev,
        net_margin_pct=nm, net_margin_n=n_nm,
    )


# ── Fetcher seams (tests) ────────────────────────────────────────────────────


def _default_submissions_fetcher(cik: int) -> dict | None:
    return edgar_submissions.fetch_company_submissions(cik)


def _default_info_fetcher(ticker: str) -> dict | None:
    try:
        import yfinance as yf

        info = yf.Ticker(ticker.upper()).info
    except Exception as exc:  # pragma: no cover - defensive, mirrors fundamentals.py
        logger.warn("peer_basket_info_error", ticker=ticker.upper(), error=str(exc)[:200])
        return None
    return info if isinstance(info, dict) and info else None


_submissions_fetcher: SubmissionsFetcher = _default_submissions_fetcher
_info_fetcher: InfoFetcher = _default_info_fetcher


def set_peer_fetchers(
    *, submissions: SubmissionsFetcher | None = None, info: InfoFetcher | None = None
) -> None:
    """Test seam: replace either network fetcher (conftest pins both off, the
    `liquidity_lookup` precedent, so no test reaches SEC or Yahoo by default)."""
    global _submissions_fetcher, _info_fetcher
    if submissions is not None:
        _submissions_fetcher = submissions
    if info is not None:
        _info_fetcher = info


def reset_peer_fetchers() -> None:
    """Restore the real fetchers (live probes, operational escape hatch)."""
    global _submissions_fetcher, _info_fetcher
    _submissions_fetcher = _default_submissions_fetcher
    _info_fetcher = _default_info_fetcher


# ── The store ────────────────────────────────────────────────────────────────

_store: dict[str, tuple[PeerBasket | None, str | None, datetime]] = {}
_store_lock = threading.RLock()


def clear_peer_basket_store() -> None:
    """Drop every cached resolution. Test seam and operational escape hatch."""
    with _store_lock:
        _store.clear()


def _fail(reason: str) -> PeerBasketResult:
    logger.info("peer_basket_unavailable", reason=reason)
    return PeerBasketResult(basket=None, reason=reason)


def _resolve(sym: str, target_market_cap: float, day: date) -> PeerBasketResult:
    try:
        cik = resolve_cik(sym)
    except CikResolutionUnavailable:
        return _fail("SEC's ticker map is unreachable, so the company's SIC cannot be resolved")
    if cik is None:
        return _fail("no SEC registrant was found for this symbol, so no SIC is on file")
    submissions = _submissions_fetcher(cik)
    if not submissions:
        return _fail("the company's SEC submissions could not be read, so its SIC is unknown this call")
    sic_raw = str(submissions.get("sic") or "").strip()
    if len(sic_raw) != 4 or not sic_raw.isdigit():
        return _fail("the company's SEC filings carry no usable 4-digit SIC code")
    sic_description = submissions.get("sicDescription")
    candidates = _CANDIDATES_BY_SIC.get(sic_raw, ())
    if not candidates:
        return _fail(f"insufficient peer coverage — no candidate universe is maintained for SIC {sic_raw}")

    # Verify membership live: a candidate enters the basket only if its OWN
    # submissions JSON files under the target's exact SIC. The probe list is
    # never trusted and never rendered. A candidate whose submissions could
    # not be READ is counted separately from one that read back a different
    # SIC: below the floor, throttling ("unverified") and genuine lack of
    # coverage ("0 same-SIC peers") are different facts and must not blur.
    verified: list[tuple[str, int]] = []
    unverified_fetch_failures = 0
    for cand in candidates:
        if cand == sym:
            continue
        try:
            c_cik = resolve_cik(cand)
        except CikResolutionUnavailable:
            c_cik = None
        if c_cik is None:
            continue
        c_sub = _submissions_fetcher(c_cik)
        if not c_sub:
            unverified_fetch_failures += 1
            continue
        if str(c_sub.get("sic") or "").strip() == sic_raw:
            verified.append((cand, c_cik))
    if len(verified) < _MIN_PEERS:
        if unverified_fetch_failures:
            return _fail(
                f"insufficient peer coverage — {unverified_fetch_failures} candidate "
                "submissions could not be read this call, so their same-SIC "
                f"membership is unverified (only {len(verified)} verified, "
                f"{_MIN_PEERS} needed)"
            )
        return _fail(
            f"insufficient peer coverage — {len(verified)} same-SIC peers "
            f"from data in hand, {_MIN_PEERS} needed"
        )

    rows: list[PeerRow] = []
    for cand, c_cik in verified:
        info = _info_fetcher(cand)
        if not info:
            logger.info("peer_quote_unserved", peer=cand, ticker=sym)
            continue
        margins = _num(info, "profitMargins")
        rows.append(PeerRow(
            ticker=cand,
            cik=c_cik,
            sic=sic_raw,
            market_cap=_num(info, "marketCap"),
            trailing_pe=_num(info, "trailingPE"),
            ev_to_ebitda=_num(info, "enterpriseToEbitda"),
            net_margin_pct=round(margins * 100) if margins is not None else None,
        ))
    with_caps = [r for r in rows if r.market_cap is not None and r.market_cap > 0]
    if len(with_caps) < _MIN_PEERS:
        return _fail(
            f"insufficient peer coverage — fewer than {_MIN_PEERS} same-SIC "
            "peers served market caps this call"
        )

    # Market-cap neighbours: nearest by log-distance, so a 2x-bigger and a
    # 2x-smaller peer score the same.
    members = sorted(with_caps, key=lambda r: abs(math.log(r.market_cap / target_market_cap)))
    members = members[:_BASKET_SIZE]
    medians = compute_medians(members)
    if (
        medians.trailing_pe is None
        and medians.ev_ebitda is None
        and medians.net_margin_pct is None
    ):
        return _fail("the provider served no multiples for any peer in the basket")
    return PeerBasketResult(PeerBasket(
        ticker=sym,
        sic=sic_raw,
        sic_description=str(sic_description) if sic_description else None,
        members=tuple(members),
        as_of=day,
        medians=medians,
    ))


def refresh_peer_basket(
    ticker: str,
    *,
    target_market_cap: float,
    now: datetime | None = None,
) -> PeerBasketResult:
    """The basket for `ticker`, re-resolving at most once per `_REFRESH_DAYS`.

    Lazy per ticker: the first convene that asks pays the resolution; the
    next week of convenes serves the cached snapshot ("basket as of" states
    its date on the line). A failed resolution retries after `_FAILURE_RETRY`
    instead — an outage is transient, and caching it for a week would make the
    failure case the sticky one. `now` is a test seam for the clock.
    """
    sym = ticker.upper().strip()
    if target_market_cap <= 0:
        return _fail("the company's own market cap is not live, so market-cap neighbours cannot be chosen")
    moment = now or datetime.now(UTC)
    with _store_lock:
        entry = _store.get(sym)
        if entry is not None:
            basket, reason, resolved_at = entry
            ttl = _REFRESH_TTL if basket is not None else _FAILURE_RETRY
            if moment - resolved_at < ttl:
                return PeerBasketResult(basket=basket, reason=reason)
    result = _resolve(sym, target_market_cap, moment.date())
    with _store_lock:
        _store[sym] = (result.basket, result.reason, moment)
    return result
