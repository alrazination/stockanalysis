"""Stock universe: large, liquid companies that are tradable on Trade Republic.

Trade Republic routes orders to LS Exchange (Lang & Schwarz) in EUR. Every name
below is listed there. Prices are pulled from the most liquid home listing via
Yahoo Finance and converted to EUR, which tracks the LS quote closely.

Fields: (yahoo_ticker, name, ISIN, region)
"""

UNIVERSE = [
    # --- United States --------------------------------------------------------
    ("AAPL", "Apple", "US0378331005", "US"),
    ("MSFT", "Microsoft", "US5949181045", "US"),
    ("NVDA", "NVIDIA", "US67066G1040", "US"),
    ("AMZN", "Amazon", "US0231351067", "US"),
    ("GOOGL", "Alphabet (A)", "US02079K3059", "US"),
    ("META", "Meta Platforms", "US30303M1027", "US"),
    ("TSLA", "Tesla", "US88160R1014", "US"),
    ("AVGO", "Broadcom", "US11135F1012", "US"),
    ("BRK-B", "Berkshire Hathaway (B)", "US0846707026", "US"),
    ("JPM", "JPMorgan Chase", "US46625H1005", "US"),
    ("BAC", "Bank of America", "US0605051046", "US"),
    ("GS", "Goldman Sachs", "US38141G1040", "US"),
    ("V", "Visa", "US92826C8394", "US"),
    ("MA", "Mastercard", "US57636Q1040", "US"),
    ("PYPL", "PayPal", "US70450Y1038", "US"),
    ("LLY", "Eli Lilly", "US5324571083", "US"),
    ("UNH", "UnitedHealth", "US91324P1021", "US"),
    ("JNJ", "Johnson & Johnson", "US4781601046", "US"),
    ("ABBV", "AbbVie", "US00287Y1091", "US"),
    ("MRK", "Merck & Co.", "US58933Y1055", "US"),
    ("PFE", "Pfizer", "US7170811035", "US"),
    ("ISRG", "Intuitive Surgical", "US46120E6023", "US"),
    ("PG", "Procter & Gamble", "US7427181091", "US"),
    ("KO", "Coca-Cola", "US1912161007", "US"),
    ("PEP", "PepsiCo", "US7134481081", "US"),
    ("COST", "Costco", "US22160K1051", "US"),
    ("WMT", "Walmart", "US9311421039", "US"),
    ("HD", "Home Depot", "US4370761029", "US"),
    ("MCD", "McDonald's", "US5801351017", "US"),
    ("SBUX", "Starbucks", "US8552441094", "US"),
    ("NKE", "Nike", "US6541061031", "US"),
    ("DIS", "Walt Disney", "US2546871060", "US"),
    ("NFLX", "Netflix", "US64110L1061", "US"),
    ("BKNG", "Booking Holdings", "US09857L1089", "US"),
    ("UBER", "Uber", "US90353T1007", "US"),
    ("AMD", "Advanced Micro Devices", "US0079031078", "US"),
    ("INTC", "Intel", "US4581401001", "US"),
    ("QCOM", "Qualcomm", "US7475251036", "US"),
    ("TXN", "Texas Instruments", "US8825081040", "US"),
    ("MU", "Micron Technology", "US5951121038", "US"),
    ("TSM", "Taiwan Semiconductor (ADR)", "US8740391003", "US"),
    ("ORCL", "Oracle", "US68389X1054", "US"),
    ("CRM", "Salesforce", "US79466L3024", "US"),
    ("ADBE", "Adobe", "US00724F1012", "US"),
    ("NOW", "ServiceNow", "US81762P1021", "US"),
    ("PLTR", "Palantir", "US69608A1088", "US"),
    ("CRWD", "CrowdStrike", "US22788C1053", "US"),
    ("SHOP", "Shopify", "CA82509L1076", "US"),
    ("SPOT", "Spotify", "LU1778762911", "US"),
    ("XOM", "Exxon Mobil", "US30231G1022", "US"),
    ("CVX", "Chevron", "US1667641005", "US"),
    ("CAT", "Caterpillar", "US1491231015", "US"),
    # --- Germany --------------------------------------------------------------
    ("SAP.DE", "SAP", "DE0007164600", "DE"),
    ("SIE.DE", "Siemens", "DE0007236101", "DE"),
    ("ALV.DE", "Allianz", "DE0008404005", "DE"),
    ("MUV2.DE", "Munich Re", "DE0008430026", "DE"),
    ("DTE.DE", "Deutsche Telekom", "DE0005557508", "DE"),
    ("MBG.DE", "Mercedes-Benz Group", "DE0007100000", "DE"),
    ("BMW.DE", "BMW", "DE0005190003", "DE"),
    ("VOW3.DE", "Volkswagen (Vz.)", "DE0007664039", "DE"),
    ("BAS.DE", "BASF", "DE000BASF111", "DE"),
    ("BAYN.DE", "Bayer", "DE000BAY0017", "DE"),
    ("IFX.DE", "Infineon", "DE0006231004", "DE"),
    ("DBK.DE", "Deutsche Bank", "DE0005140008", "DE"),
    ("CBK.DE", "Commerzbank", "DE000CBK1001", "DE"),
    ("RHM.DE", "Rheinmetall", "DE0007030009", "DE"),
    ("HAG.DE", "Hensoldt", "DE000HAG0005", "DE"),
    ("MTX.DE", "MTU Aero Engines", "DE000A0D9PT0", "DE"),
    ("ADS.DE", "Adidas", "DE000A1EWWW0", "DE"),
    ("DHL.DE", "DHL Group", "DE0005552004", "DE"),
    ("ENR.DE", "Siemens Energy", "DE000ENER6Y0", "DE"),
    ("SHL.DE", "Siemens Healthineers", "DE000SHL1006", "DE"),
    ("ZAL.DE", "Zalando", "DE000ZAL1111", "DE"),
    # --- Rest of Europe -------------------------------------------------------
    ("ASML.AS", "ASML", "NL0010273215", "EU"),
    ("ADYEN.AS", "Adyen", "NL0012969182", "EU"),
    ("SHELL.AS", "Shell", "GB00BP6MXD84", "EU"),
    ("AIR.PA", "Airbus", "NL0000235190", "EU"),
    ("MC.PA", "LVMH", "FR0000121014", "EU"),
    ("RMS.PA", "Hermès", "FR0000052292", "EU"),
    ("OR.PA", "L'Oréal", "FR0000120321", "EU"),
    ("TTE.PA", "TotalEnergies", "FR0000120271", "EU"),
    ("SAN.PA", "Sanofi", "FR0000120578", "EU"),
    ("SU.PA", "Schneider Electric", "FR0000121972", "EU"),
    ("RACE.MI", "Ferrari", "NL0011585146", "EU"),
    ("UCG.MI", "UniCredit", "IT0005239360", "EU"),
    ("ITX.MC", "Inditex", "ES0148396007", "EU"),
    ("IBE.MC", "Iberdrola", "ES0144580Y14", "EU"),
    ("NOVO-B.CO", "Novo Nordisk (B)", "DK0062498333", "EU"),
    ("NESN.SW", "Nestlé", "CH0038863350", "EU"),
    ("NOVN.SW", "Novartis", "CH0012005267", "EU"),
    ("RO.SW", "Roche (bearer)", "CH0012032113", "EU"),
]

# Benchmark used to judge the simulator: iShares Core MSCI World (Xetra, EUR).
BENCHMARK = ("EUNL.DE", "iShares Core MSCI World UCITS ETF", "IE00B4L5Y983")

BY_TICKER = {t: {"ticker": t, "name": n, "isin": i, "region": r} for t, n, i, r in UNIVERSE}


def lookup(ticker: str) -> dict:
    """Return universe metadata for a ticker (case-insensitive); ad-hoc tickers allowed."""
    t = ticker.upper()
    return BY_TICKER.get(t, {"ticker": t, "name": t, "isin": "?", "region": "?"})
