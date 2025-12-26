"""
Known Corruption Cases in Macedonian Public Procurement

This file contains confirmed corruption cases from public sources (court verdicts,
prosecution announcements, investigative journalism) that can be used as ground truth
for training and validating ML corruption detection models.

Sources:
- Macedonian prosecution (jorm.gov.mk)
- Balkan Insight investigative reports
- Center for Civil Communications (ccc.org.mk) research
- US Treasury sanctions
- Macedonian news outlets (Makfax, Slobodna Evropa, 360stepeni, etc.)

Last updated: December 2025
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CorruptionCase:
    """Represents a known corruption case in public procurement."""
    case_id: str
    case_name: str
    case_name_mk: Optional[str]  # Macedonian name
    year: int
    status: str  # 'convicted', 'investigation', 'prosecution', 'fled'

    # Entities involved
    institution: Optional[str]
    institution_mk: Optional[str]
    companies: List[str]
    individuals: List[str]

    # Financial details
    estimated_damage_eur: Optional[float]
    contract_value_eur: Optional[float]

    # Procurement details
    tender_ids: List[str]  # Format: XXXXX/YYYY if known
    tender_type: Optional[str]  # goods, services, works
    sector: Optional[str]

    # Case description
    description: str
    corruption_type: List[str]  # bid_rigging, kickback, embezzlement, etc.

    # Source information
    sources: List[str]
    conviction_date: Optional[str]
    sentence_years: Optional[float]

    # Keywords for matching
    keywords_en: List[str]
    keywords_mk: List[str]


# =============================================================================
# CONFIRMED CONVICTED CASES (Court verdicts)
# =============================================================================

CONVICTED_CASES: List[CorruptionCase] = [

    CorruptionCase(
        case_id="MK-2023-001",
        case_name="Tank Case",
        case_name_mk="Случај Тенк",
        year=2012,
        status="convicted",
        institution="Ministry of Internal Affairs",
        institution_mk="Министерство за внатрешни работи",
        companies=["Mercedes-Benz"],
        individuals=[
            "Gordana Jankuloska",  # Former Interior Minister - 6 years (reduced to 4)
            "Nikola Gruevski",     # Former PM - 2 years
            "Gjoko Popovski"       # Ex-assistant minister - 4.5 years
        ],
        estimated_damage_eur=600000,
        contract_value_eur=600000,
        tender_ids=[],  # Tender ID not public
        tender_type="goods",
        sector="security",
        description="""
        Rigged tender for procurement of armored Mercedes S-600 Guard vehicle.
        Former PM Gruevski influenced Interior Minister Jankuloska to conduct
        a public procurement where the ministry would purchase a luxury armored
        vehicle worth 600,000 EUR for his personal use with police funds.
        """,
        corruption_type=["bid_rigging", "abuse_of_office", "kickback"],
        sources=[
            "https://meta.mk/jankuloska-osudena-na-6-godini-zatvor-za-nabavka-na-mertsedesot/",
            "https://lider.com.mk/makedonija/video-gordana-jankulovska-osudena-na-6-godini-zatvor/"
        ],
        conviction_date="2019",
        sentence_years=4.0,  # Reduced from 6 on appeal
        keywords_en=["armored vehicle", "mercedes", "tank", "interior ministry", "gruevski"],
        keywords_mk=["оклопено возило", "мерцедес", "тенк", "МВР", "груевски", "јанкулоска"]
    ),

    CorruptionCase(
        case_id="MK-2021-001",
        case_name="Software Case (Biometric)",
        case_name_mk="Случај Софтвери",
        year=2017,
        status="convicted",
        institution="General Secretariat of the Government",
        institution_mk="Генерален секретаријат на Владата",
        companies=["Gamma International", "Finzi"],
        individuals=[
            "Dragi Rashkovski",   # Former General Secretary - 8 years
            "Ivica Dimitrovski",  # 5 years
            "Igor Hristov",       # 5.5 years
            "Daniel Stanchev",    # 4 years
            "Irena Ivanovska",    # 3.5 years
            "Igor Ivanovski",     # 3 years
            "Maja Siljanovska"    # 3 years
        ],
        estimated_damage_eur=192000,  # Total 6.4M + 5M MKD
        contract_value_eur=None,
        tender_ids=["OT-d6600950cd56/2020"],  # Verified: 72B MKD State Election Commission tender
        tender_type="services",
        sector="IT/software",
        description="""
        Rigged tenders for biometric identification software and traffic speed
        detection software. The General Secretariat procured software that the
        Ministry of Internal Affairs never requested and never planned to use.
        Money was laundered through intermediary company Finzi.
        Note: Verified tender ID OT-d6600950cd56/2020 is a 72 billion MKD tender
        from State Election Commission for biometric systems.
        """,
        corruption_type=["bid_rigging", "money_laundering", "abuse_of_office"],
        sources=[
            "https://faktor.mk/dragi-rashkovski-dobi-osum-godini-zatvorska-kazna-za-softveri",
            "https://press24.mk/presuda-za-softveri-osum-godini-zatvor-za-dragi-rashkovski"
        ],
        conviction_date="2023-07",
        sentence_years=8.0,
        keywords_en=["biometric", "software", "general secretariat", "rashkovski", "surveillance", "election"],
        keywords_mk=["биометрија", "софтвер", "генерален секретаријат", "рашковски", "прислушување", "избори"]
    ),

    CorruptionCase(
        case_id="MK-2021-002",
        case_name="Trezor Case (Surveillance Equipment)",
        case_name_mk="Случај Трезор",
        year=2012,
        status="convicted",
        institution="Administration for Security and Counterintelligence (UBK)",
        institution_mk="Управа за безбедност и контраразузнавање (УБК)",
        companies=["Gamma International", "Finzi"],
        individuals=[
            "Saso Mijalkov",      # Former UBK chief - 8 years
            "Goran Grujevski",    # 15 years (in absentia, fled)
            "Nebojsa Stajkovic", # 5 years
            "Toni Jakimovski"     # 5 years
        ],
        estimated_damage_eur=None,
        contract_value_eur=None,
        tender_ids=[],
        tender_type="goods",
        sector="security/surveillance",
        description="""
        Illicit procurement of telecommunications surveillance equipment for UBK.
        Equipment was purchased from British company Gamma International through
        intermediary Finzi instead of direct procurement, inflating costs.
        """,
        corruption_type=["bid_rigging", "abuse_of_office", "intermediary_fraud"],
        sources=[
            "https://balkaninsight.com/2021/04/13/north-macedonia-convicts-ex-secret-police-chief-of-procurement-scam/",
            "https://prizma.mk/bogatiot-osudenik-mijalkov-i-kilavata-pravda/"
        ],
        conviction_date="2021-04",
        sentence_years=8.0,
        keywords_en=["surveillance", "UBK", "mijalkov", "wiretapping", "gamma"],
        keywords_mk=["прислушување", "УБК", "мијалков", "опрема", "разузнавање"]
    ),

    CorruptionCase(
        case_id="MK-2021-003",
        case_name="Target-Tvrdina (Mass Surveillance)",
        case_name_mk="Таргет-Тврдина",
        year=2015,
        status="convicted",
        institution="Administration for Security and Counterintelligence (UBK)",
        institution_mk="Управа за безбедност и контраразузнавање (УБК)",
        companies=[],
        individuals=[
            "Saso Mijalkov",      # Former UBK chief - 12 years
            "Goran Grujevski",    # 15 years (fled to Greece)
            "Nikola Boskoski",    # 15 years (fled)
            "Toni Jakimovski"     # 6 years
        ],
        estimated_damage_eur=None,
        contract_value_eur=None,
        tender_ids=[],
        tender_type=None,
        sector="security",
        description="""
        Mass illegal wiretapping from 2008 to 2015 organized by UBK chief Mijalkov
        to maintain control over all of society. Related to various procurement
        frauds exposed through the wiretaps.
        """,
        corruption_type=["abuse_of_office", "illegal_surveillance"],
        sources=[
            "https://www.slobodnaevropa.mk/a/31123388.html"
        ],
        conviction_date="2022",
        sentence_years=12.0,
        keywords_en=["wiretapping", "surveillance", "UBK", "mijalkov", "target"],
        keywords_mk=["прислушување", "УБК", "мијалков", "таргет", "тврдина"]
    ),

    CorruptionCase(
        case_id="MK-2023-002",
        case_name="Muhamed Zekiri Consulting Contracts",
        case_name_mk="Случај Зекири",
        year=2021,
        status="convicted",  # First instance, appeal ongoing
        institution="Government of North Macedonia",
        institution_mk="Влада на Република Северна Македонија",
        companies=["Croatian consulting firms (unnamed)"],
        individuals=[
            "Muhamed Zekiri"  # Former General Secretary - 2.5 years
        ],
        estimated_damage_eur=1152000,
        contract_value_eur=1567400,  # 795000 + 772400 EUR
        tender_ids=[],
        tender_type="services",
        sector="consulting",
        description="""
        Former Government Secretary General concluded two consulting contracts
        worth nearly 1 million EUR without proper public procurement procedures.
        First contract (795,000 EUR) with a Croatian firm founded just 20 days before.
        Second contract (772,400 EUR) for railway privatization consulting.
        """,
        corruption_type=["procurement_bypass", "abuse_of_office"],
        sources=[
            "https://sdk.mk/index.php/makedonija/muhamed-zekiri-osuden-da-vrati-1-152-000-evra-na-drzhavniot-budhet/",
            "https://jorm.gov.mk/obvinitelen-predlog-za-zloupotreba-na-sluzhbena-polozhba-i-ovlastuvane/"
        ],
        conviction_date="2023-12",
        sentence_years=2.5,
        keywords_en=["consulting", "railways", "zekiri", "government secretary", "croatia"],
        keywords_mk=["консултантски", "железници", "зекири", "генерален секретар", "хрватска"]
    ),

    CorruptionCase(
        case_id="MK-2022-001",
        case_name="Orce Kamcev - Vodno Land Parcels",
        case_name_mk="Случај Плацеви на Водно",
        year=2020,
        status="convicted",
        institution=None,
        institution_mk=None,
        companies=["Orka Holding", "Various Kamcev companies"],
        individuals=[
            "Jordan 'Orce' Kamcev"  # Businessman
        ],
        estimated_damage_eur=None,
        contract_value_eur=None,
        tender_ids=[],
        tender_type=None,
        sector="real_estate",
        description="""
        Money laundering scheme linked to illicit purchase of land on Vodno mountain.
        Part of broader pattern of corruption involving state capture.
        """,
        corruption_type=["money_laundering", "fraud"],
        sources=[
            "https://home.treasury.gov/news/press-releases/jy1628",
            "https://fokus.mk/arhiva-portret-jordan-ortse-kamchev-neuspeshen-politichar-do-milioner-so-biznis-imperija-i-spogodbeno-osuden-sorabotnik-na-pravdata/"
        ],
        conviction_date="2022",
        sentence_years=None,  # Plea deal
        keywords_en=["kamcev", "orce", "land", "vodno", "money laundering"],
        keywords_mk=["камчев", "орце", "плацеви", "водно", "перење пари"]
    ),
]

# =============================================================================
# ACTIVE INVESTIGATIONS / PROSECUTION (Not yet convicted)
# =============================================================================

INVESTIGATION_CASES: List[CorruptionCase] = [

    CorruptionCase(
        case_id="MK-2025-001",
        case_name="ESM District Heating Tender Fraud",
        case_name_mk="ЕСМ Дистрибуција на топлина",
        year=2023,
        status="investigation",
        institution="ESM Distribucija na Toplina DOEL Skopje",
        institution_mk="ЕСМ Дистрибуција на топлина ДООЕЛ Скопје",
        companies=["Unnamed Skopje company", "Unnamed Kumanovo company"],
        individuals=[
            "Bujar Dardishta",  # Former ESM director (33 total suspects)
            # 32 other individuals under investigation
        ],
        estimated_damage_eur=2041576,  # Money laundered
        contract_value_eur=7682445,    # Contract value
        tender_ids=[],  # SKAD equipment tender
        tender_type="goods",
        sector="energy/heating",
        description="""
        In 2023, ESM officials and private company managers created an organized
        group to rig public procurement for SCADA monitoring cabinets with GSM
        controllers for heating stations. A Kumanovo company submitted incomplete
        documentation at higher prices as fake competition while a Skopje company
        won with a bid matching the undisclosed estimated value. From 2023-2025,
        approximately 2 million EUR was laundered.
        """,
        corruption_type=["bid_rigging", "money_laundering", "fake_competition"],
        sources=[
            "https://makfax.com.mk/makedonija/uapseni-11-lica-za-mestenje-tender-vreden",
            "https://republika.mk/vesti/hronika/uapseni-11-licza-za-mestene-tender-vreden-nad-76-milioni-evra-vo-esm-distribuczija-na-toplina/",
            "https://www.slobodnaevropa.mk/a/33627944.html"
        ],
        conviction_date=None,
        sentence_years=None,
        keywords_en=["ESM", "heating", "SCADA", "district heating", "tender rigging"],
        keywords_mk=["ЕСМ", "топлина", "СКАД", "дистрибуција", "наместен тендер"]
    ),

    CorruptionCase(
        case_id="MK-2024-001",
        case_name="TEC Negotino Fuel Oil Procurement",
        case_name_mk="ТЕЦ Неготино мазут",
        year=2021,
        status="investigation",
        institution="ESM - Elektrani na Severna Makedonija",
        institution_mk="АД Електрани на Северна Македонија",
        companies=["RKM", "Pucko Petrol"],
        individuals=[
            "Ratko Kapushevski",  # RKM owner - 30 days detention
            "Erdzan Sulkoski",    # RKM - 30 days detention
            "Adrijan Mucha",      # Former ESM director - 30 days detention
            "Asmir Jahoski",      # Pucko Petrol - 30 days detention
            "Vasko Kovachevski", # Former ESM director (fled)
            # 8 other suspects
        ],
        estimated_damage_eur=167549985,  # 212M EUR RKM mazut case
        contract_value_eur=212000000,
        tender_ids=[
            # Note: The 212M EUR RKM mazut case is NOT in e-nabavki DB
            # These are related ESM energy tenders (partial matches):
            "14987/2019",   # ESM electricity tender
            "18928/2020",   # ESM electricity tender
            "17600/2024",   # JP Komunalna higiena fuels (Pucko Petrol winner)
        ],
        tender_type="goods",
        sector="energy",
        description="""
        Investigation into fuel oil (mazut) procurement for TEC Negotino thermal
        power plant from 2021-2023. Company founders and ESM employees allegedly
        conducted illegal procurements causing damage of over 167 million EUR
        to state budget. Environmental concerns (ecocide) also being investigated.
        IMPORTANT: The main 212M EUR RKM mazut case is NOT in e-nabavki database -
        may have been classified or conducted through different procurement channel.
        The tender_ids listed are related energy sector tenders from same entities.
        """,
        corruption_type=["bid_rigging", "embezzlement", "abuse_of_office"],
        sources=[
            "https://novamakedonija.com.mk/makedonija/hronika/asmir-jahoski-sproveden-vo-istrazhniot-zatvor-skopje/",
            "https://lider.mk/javnoto-obvinitelstvo-otvori-istraga-za-nabavkite-na-mazut-za-tets-negotino/",
            "https://www.slobodnaevropa.mk/a/istraga-koruocija-lotarija-sozr-pucko-petrol-/33629724.html"
        ],
        conviction_date=None,
        sentence_years=None,
        keywords_en=["TEC Negotino", "fuel oil", "mazut", "power plant", "RKM"],
        keywords_mk=["ТЕЦ Неготино", "мазут", "горива", "електрана", "РКМ"]
    ),

    CorruptionCase(
        case_id="MK-2024-002",
        case_name="State Lottery Embezzlement",
        case_name_mk="Државна лотарија",
        year=2023,
        status="investigation",
        institution="AD Drzavna Lotarija",
        institution_mk="АД Државна лотарија",
        companies=["HEJ DOEL Skopje"],
        individuals=[
            "Artan Grubi",       # Former Deputy PM (fled, international warrant)
            "Perparim Bajrami"   # Former Lottery Director (fled, international warrant)
        ],
        estimated_damage_eur=8200000,
        contract_value_eur=400000,  # Fake equipment tenders
        tender_ids=[
            # Verified partial matches from Државна видеолотарија:
            "21437/2023",  # Software license maintenance
            "21441/2023",  # Commercial audit services
        ],
        tender_type="services",
        sector="gambling/lottery",
        description="""
        Former Deputy PM Artan Grubi and State Lottery Director Perparim Bajrami
        allegedly embezzled 8.2 million EUR. Bajrami also charged with renting
        inadequate office space at double the market price (9 EUR/m2 vs 2.5-4.5 EUR).
        Additional allegations of fake equipment tenders (TVs, computers) worth
        400,000 EUR where goods were never delivered.
        Verified tender_ids are from the State Lottery (Државна видеолотарија).
        """,
        corruption_type=["embezzlement", "overpricing", "fake_delivery"],
        sources=[
            "https://makfax.com.mk/top/nova-krivichna-protiv-perparim-bajrami/",
            "https://sdk.mk/index.php/makedonija/nova-krivichna-prijava-protiv-eksdirektorot-na-drzhavna-lotarija-perparim-bajrami/",
            "https://www.slobodnaevropa.mk/a/istraga-koruocija-lotarija-sozr-pucko-petrol-/33629724.html"
        ],
        conviction_date=None,
        sentence_years=None,
        keywords_en=["lottery", "grubi", "bajrami", "embezzlement"],
        keywords_mk=["лотарија", "груби", "бајрами", "проневера"]
    ),

    CorruptionCase(
        case_id="MK-2024-003",
        case_name="SOZR Tender Fraud - Mirchevski",
        case_name_mk="СОЗР тендери",
        year=2021,
        status="investigation",
        institution="Service for General and Common Affairs (SOZR)",
        institution_mk="Служба за општи и заеднички работи (СОЗР)",
        companies=["Unnamed Skopje company"],
        individuals=[
            "Pece Mirchevski"  # Former SOZR Director
        ],
        estimated_damage_eur=None,
        contract_value_eur=None,
        tender_ids=[],
        tender_type="mixed",
        sector="government_services",
        description="""
        From June 2021 to June 2024, former SOZR Director Mirchevski allegedly
        signed five public procurement contracts with a Skopje company without
        declaring conflict of interest. He allegedly used a Volkswagen Passat
        from the company winning tenders, and his wife used transportation services.
        """,
        corruption_type=["conflict_of_interest", "bid_rigging"],
        sources=[
            "https://mkd.mk/direktori-na-sozr-i-generalni-sekretari-na-vladite-vo-kandzhite-na-tenderskata-koruptivnost/"
        ],
        conviction_date=None,
        sentence_years=None,
        keywords_en=["SOZR", "conflict of interest", "government services"],
        keywords_mk=["СОЗР", "судир на интереси", "владини служби"]
    ),

    CorruptionCase(
        case_id="MK-2016-001",
        case_name="Trajectory (Sinohydro Highway)",
        case_name_mk="Случај Траекторија",
        year=2012,
        status="prosecution",  # Statute expires 2033
        institution="Public Enterprise for State Roads",
        institution_mk="Јавно претпријатие за државни патишта",
        companies=["Sinohydro"],
        individuals=[
            "Nikola Gruevski",    # Former PM (fled to Hungary)
            "Vladimir Peshevski", # Deputy PM
            "Mile Janakieski",    # Transport Minister
            "Ljupcho Georgievski" # PESR Director
        ],
        estimated_damage_eur=155000000,
        contract_value_eur=638000000,
        tender_ids=[],
        tender_type="works",
        sector="infrastructure",
        description="""
        Chinese SOE Sinohydro was selected to build two highways (Miladinovci-Shtip
        and Kichevo-Ohrid) in a deal that became one of the biggest corruption
        scandals in Macedonian history. Wiretaps revealed alleged 5% kickbacks
        (approx 155M EUR). Sinohydro subcontracted work at 54% markup. Some items
        marked up 300%. Gruevski fled to Hungary in 2018.
        """,
        corruption_type=["kickback", "bid_rigging", "subcontractor_markup"],
        sources=[
            "https://balkaninsight.com/2024/06/11/despite-delay-and-scandal-chinese-firm-wins-more-work-in-north-macedonia/",
            "https://chinaobservers.eu/exporting-corruption-the-case-of-a-chinese-highway-project-in-north-macedonia/",
            "https://thepeoplesmap.net/project/kicevo-ohrid-highway/"
        ],
        conviction_date=None,  # Gruevski fled, statute expires 2033
        sentence_years=None,
        keywords_en=["sinohydro", "highway", "trajectory", "china", "kickback"],
        keywords_mk=["синохидро", "автопат", "траекторија", "кина", "провизија"]
    ),
]

# =============================================================================
# HIGH-RISK ENTITIES (US Sanctions / Patterns of Corruption)
# =============================================================================

SANCTIONED_ENTITIES: List[Dict] = [
    {
        "name": "Jordan 'Orce' Kamcev",
        "name_mk": "Јордан 'Орце' Камчев",
        "type": "individual",
        "sanction_source": "US Treasury OFAC",
        "sanction_date": "2023-07",
        "reason": "Corruption, abuse of office, money laundering, bribery of government officials",
        "companies": ["Orka Holding", "Various subsidiaries"],
        "reference": "https://home.treasury.gov/news/press-releases/jy1628"
    },
    {
        "name": "Nikola Gruevski",
        "name_mk": "Никола Груевски",
        "type": "individual",
        "status": "fled_to_hungary",
        "convicted_cases": ["Tank Case", "Trajectory"],
        "reference": "Multiple court verdicts"
    },
    {
        "name": "Saso Mijalkov",
        "name_mk": "Сашо Мијалков",
        "type": "individual",
        "status": "convicted",
        "total_sentence_years": 20,  # 12 + 8 years
        "cases": ["Target-Tvrdina", "Trezor"],
        "reference": "Court verdicts 2021-2022"
    }
]

# =============================================================================
# RED FLAG INDICATORS (from research and cases)
# =============================================================================

CORRUPTION_INDICATORS = {
    "bid_rigging_patterns": [
        "Single bidder with high contract value",
        "Losing bidders submit incomplete documentation",
        "Bid prices match undisclosed estimated value",
        "Same companies repeatedly compete (rotating winners)",
        "Company founded shortly before tender",
        "Winner subcontracts to losing bidders",
    ],
    "conflict_of_interest": [
        "Official uses services/goods from winning company",
        "Family members employed by winning company",
        "Official has ownership in winning company",
        "Previous employment relationship with winner",
    ],
    "price_manipulation": [
        "Contract price significantly above market rate",
        "Large unexplained price increases through amendments",
        "Subcontractor prices 50%+ below main contract prices",
        "Items marked up 100%+ from comparable tenders",
    ],
    "fake_delivery": [
        "Payment made but goods/services not delivered",
        "Equipment purchased that's never used",
        "Services invoiced but no evidence of work",
    ],
    "intermediary_fraud": [
        "Purchases through unnecessary intermediaries",
        "Intermediary company founded recently",
        "Intermediary adds no value but increases cost",
    ],
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_convicted_cases() -> List[CorruptionCase]:
    """Return all cases with confirmed convictions."""
    return CONVICTED_CASES


def get_all_investigation_cases() -> List[CorruptionCase]:
    """Return all cases under active investigation."""
    return INVESTIGATION_CASES


def get_all_cases() -> List[CorruptionCase]:
    """Return all known corruption cases."""
    return CONVICTED_CASES + INVESTIGATION_CASES


def get_cases_by_sector(sector: str) -> List[CorruptionCase]:
    """Return cases filtered by sector."""
    return [c for c in get_all_cases() if c.sector == sector]


def get_cases_by_year(year: int) -> List[CorruptionCase]:
    """Return cases from a specific year."""
    return [c for c in get_all_cases() if c.year == year]


def get_cases_by_institution(institution_keyword: str) -> List[CorruptionCase]:
    """Return cases involving a specific institution (partial match)."""
    keyword_lower = institution_keyword.lower()
    results = []
    for case in get_all_cases():
        if case.institution and keyword_lower in case.institution.lower():
            results.append(case)
        elif case.institution_mk and keyword_lower in case.institution_mk.lower():
            results.append(case)
    return results


def get_company_names() -> List[str]:
    """Return all company names mentioned in corruption cases."""
    companies = set()
    for case in get_all_cases():
        companies.update(case.companies)
    return list(companies)


def get_individual_names() -> List[str]:
    """Return all individual names mentioned in corruption cases."""
    individuals = set()
    for case in get_all_cases():
        individuals.update(case.individuals)
    return list(individuals)


def get_keywords_mk() -> List[str]:
    """Return all Macedonian keywords for matching."""
    keywords = set()
    for case in get_all_cases():
        keywords.update(case.keywords_mk)
    return list(keywords)


def get_keywords_en() -> List[str]:
    """Return all English keywords for matching."""
    keywords = set()
    for case in get_all_cases():
        keywords.update(case.keywords_en)
    return list(keywords)


def get_total_damage_estimate() -> float:
    """Calculate total estimated damage across all cases in EUR."""
    total = 0
    for case in get_all_cases():
        if case.estimated_damage_eur:
            total += case.estimated_damage_eur
    return total


# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

def print_summary():
    """Print summary of known corruption cases."""
    convicted = get_all_convicted_cases()
    investigating = get_all_investigation_cases()

    print("=" * 60)
    print("MACEDONIAN PUBLIC PROCUREMENT CORRUPTION - GROUND TRUTH DATA")
    print("=" * 60)
    print(f"\nTotal cases: {len(get_all_cases())}")
    print(f"  - Convicted: {len(convicted)}")
    print(f"  - Under investigation: {len(investigating)}")
    print(f"\nTotal estimated damage: EUR {get_total_damage_estimate():,.0f}")
    print(f"\nUnique companies mentioned: {len(get_company_names())}")
    print(f"Unique individuals: {len(get_individual_names())}")
    print(f"\nSectors covered:")

    sectors = {}
    for case in get_all_cases():
        if case.sector:
            sectors[case.sector] = sectors.get(case.sector, 0) + 1
    for sector, count in sorted(sectors.items()):
        print(f"  - {sector}: {count}")

    print(f"\nCorruption types:")
    types = {}
    for case in get_all_cases():
        for ctype in case.corruption_type:
            types[ctype] = types.get(ctype, 0) + 1
    for ctype, count in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  - {ctype}: {count}")


if __name__ == "__main__":
    print_summary()
