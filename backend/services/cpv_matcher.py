"""
CPV Code Matcher Service
Uses AI to match tender titles/descriptions to CPV codes

The EU Common Procurement Vocabulary (CPV) is a standardized classification system.
Since scraped tenders may not have CPV codes, this service infers them using AI.
"""
import os
import re
from typing import List, Dict, Optional, Tuple
from functools import lru_cache

# CPV Code Dictionary - Main categories and subcategories
# Based on EU CPV 2008 classification
CPV_CATEGORIES = {
    # Division 03 - Agricultural products
    "03": {
        "name_mk": "Земјоделски производи",
        "name_en": "Agricultural products",
        "keywords": ["земјоделски", "земјоделство", "житарици", "семиња", "растенија", "овошје", "зеленчук", "добиток", "agricultural", "farming", "crops", "seeds"]
    },
    # Division 09 - Petroleum products
    "09": {
        "name_mk": "Нафта и горива",
        "name_en": "Petroleum products, fuel",
        "keywords": ["нафта", "гориво", "дизел", "бензин", "мазут", "гас", "петрол", "fuel", "petroleum", "diesel", "gasoline", "oil"]
    },
    # Division 14 - Mining products
    "14": {
        "name_mk": "Рударски производи",
        "name_en": "Mining products",
        "keywords": ["рударство", "камен", "песок", "глина", "минерали", "mining", "stone", "sand", "clay", "minerals"]
    },
    # Division 15 - Food
    "15": {
        "name_mk": "Храна и пијалоци",
        "name_en": "Food, beverages",
        "keywords": ["храна", "пијалоци", "месо", "риба", "млеко", "леб", "кафе", "food", "beverages", "meat", "fish", "dairy", "bread", "coffee", "прехрана", "оброци", "ручек"]
    },
    # Division 18 - Clothing
    "18": {
        "name_mk": "Облека и обувки",
        "name_en": "Clothing, footwear",
        "keywords": ["облека", "обувки", "униформи", "текстил", "clothing", "footwear", "uniforms", "textile", "работна облека"]
    },
    # Division 22 - Printed matter
    "22": {
        "name_mk": "Печатени материјали",
        "name_en": "Printed matter",
        "keywords": ["печатење", "книги", "весници", "брошури", "формулари", "printing", "books", "newspapers", "brochures", "forms"]
    },
    # Division 24 - Chemical products
    "24": {
        "name_mk": "Хемиски производи",
        "name_en": "Chemical products",
        "keywords": ["хемикалии", "бои", "лакови", "ѓубрива", "chemicals", "paints", "fertilizers", "хемиски"]
    },
    # Division 30 - Office and computing machinery
    "30": {
        "name_mk": "Канцелариска и компјутерска опрема",
        "name_en": "Office and computing machinery",
        "keywords": ["компјутер", "лаптоп", "принтер", "копир", "канцелариски", "компјутерска", "хардвер", "computer", "laptop", "printer", "copier", "office", "hardware", "сервер", "монитор", "тастатура"]
    },
    # Division 31 - Electrical machinery
    "31": {
        "name_mk": "Електрични машини",
        "name_en": "Electrical machinery",
        "keywords": ["електрични", "генератор", "трансформатор", "кабли", "осветлување", "electrical", "generator", "transformer", "cables", "lighting", "електро"]
    },
    # Division 32 - Radio, TV, telecommunications
    "32": {
        "name_mk": "Телекомуникации",
        "name_en": "Radio, TV, telecommunications",
        "keywords": ["телекомуникации", "радио", "телевизија", "антена", "телефон", "мобилен", "telecommunications", "radio", "television", "antenna", "phone", "mobile", "интернет"]
    },
    # Division 33 - Medical equipment and pharmaceuticals
    "33": {
        "name_mk": "Медицинска опрема и лекови",
        "name_en": "Medical equipment, pharmaceuticals",
        "keywords": ["медицински", "лекови", "фармацевтски", "болница", "здравство", "дијагностика", "хируршки", "стоматолошки", "лабораториски", "рендген", "ултразвук", "вакцини", "инсулин", "антибиотици", "medical", "pharmaceutical", "hospital", "healthcare", "diagnostic", "surgical", "dental", "laboratory", "x-ray", "ultrasound", "vaccine", "протези", "имплант", "дијализа", "инфузија", "шприц", "игли", "завои", "газа"]
    },
    # Division 34 - Transport equipment
    "34": {
        "name_mk": "Транспортна опрема",
        "name_en": "Transport equipment",
        "keywords": ["возило", "автомобил", "автобус", "камион", "мотор", "гуми", "vehicle", "car", "bus", "truck", "motor", "tires", "транспорт", "превоз"]
    },
    # Division 35 - Security equipment
    "35": {
        "name_mk": "Безбедносна опрема",
        "name_en": "Security equipment",
        "keywords": ["безбедност", "противпожарн", "алармни", "надзор", "камери", "security", "fire-fighting", "alarm", "surveillance", "cameras", "обезбедување"]
    },
    # Division 37 - Musical instruments, sports
    "37": {
        "name_mk": "Музички инструменти и спортски производи",
        "name_en": "Musical instruments, sporting goods",
        "keywords": ["музички", "инструменти", "спорт", "опрема", "игри", "musical", "instruments", "sports", "equipment", "games"]
    },
    # Division 38 - Laboratory equipment
    "38": {
        "name_mk": "Лабораториска опрема",
        "name_en": "Laboratory equipment",
        "keywords": ["лабораторија", "микроскоп", "мерење", "тестирање", "анализа", "laboratory", "microscope", "measuring", "testing", "analysis"]
    },
    # Division 39 - Furniture
    "39": {
        "name_mk": "Мебел",
        "name_en": "Furniture",
        "keywords": ["мебел", "столови", "маси", "кревети", "ормари", "канцелариски мебел", "furniture", "chairs", "tables", "beds", "cabinets", "office furniture"]
    },
    # Division 42 - Industrial machinery
    "42": {
        "name_mk": "Индустриски машини",
        "name_en": "Industrial machinery",
        "keywords": ["машини", "пумпи", "компресори", "индустриски", "производство", "machinery", "pumps", "compressors", "industrial", "manufacturing"]
    },
    # Division 43 - Machinery for mining
    "43": {
        "name_mk": "Машини за рударство",
        "name_en": "Machinery for mining",
        "keywords": ["рударски машини", "копање", "дупчење", "mining machinery", "excavation", "drilling"]
    },
    # Division 44 - Construction structures
    "44": {
        "name_mk": "Градежни конструкции",
        "name_en": "Construction structures",
        "keywords": ["конструкции", "метални", "цевки", "резервоари", "structures", "metal", "pipes", "tanks", "градежен материјал", "бетон", "цемент", "арматура"]
    },
    # Division 45 - Construction work
    "45": {
        "name_mk": "Градежни работи",
        "name_en": "Construction work",
        "keywords": ["градење", "изградба", "реконструкција", "санација", "ремонт", "адаптација", "construction", "building", "reconstruction", "renovation", "repair", "adaptation", "градежништво", "објект", "зграда", "патишта", "инфраструктура", "водовод", "канализација"]
    },
    # Division 48 - Software packages
    "48": {
        "name_mk": "Софтверски пакети",
        "name_en": "Software packages",
        "keywords": ["софтвер", "програми", "апликации", "систем", "база на податоци", "software", "programs", "applications", "system", "database", "лиценца", "лиценци"]
    },
    # Division 50 - Repair and maintenance
    "50": {
        "name_mk": "Поправка и одржување",
        "name_en": "Repair and maintenance",
        "keywords": ["поправка", "одржување", "сервис", "сервисирање", "repair", "maintenance", "service", "servicing"]
    },
    # Division 51 - Installation services
    "51": {
        "name_mk": "Услуги за инсталација",
        "name_en": "Installation services",
        "keywords": ["инсталација", "монтажа", "поставување", "installation", "mounting", "setup"]
    },
    # Division 55 - Hotel and restaurant
    "55": {
        "name_mk": "Хотелски и ресторантски услуги",
        "name_en": "Hotel, restaurant services",
        "keywords": ["хотел", "ресторан", "сместување", "кетеринг", "hotel", "restaurant", "accommodation", "catering", "угостителство"]
    },
    # Division 60 - Transport services
    "60": {
        "name_mk": "Транспортни услуги",
        "name_en": "Transport services",
        "keywords": ["транспорт", "превоз", "достава", "железнички", "воздушен", "transport", "delivery", "rail", "air", "логистика"]
    },
    # Division 63 - Supporting transport
    "63": {
        "name_mk": "Поддршка за транспорт",
        "name_en": "Supporting transport services",
        "keywords": ["товарење", "складирање", "логистика", "туристички", "loading", "storage", "logistics", "tourism"]
    },
    # Division 64 - Postal and telecommunications
    "64": {
        "name_mk": "Поштенски и телекомуникациски услуги",
        "name_en": "Postal and telecommunications services",
        "keywords": ["пошта", "курир", "телекомуникации", "интернет", "post", "courier", "telecommunications", "internet"]
    },
    # Division 65 - Public utilities
    "65": {
        "name_mk": "Јавни комунални услуги",
        "name_en": "Public utilities",
        "keywords": ["вода", "гас", "струја", "електрична енергија", "комунални", "water", "gas", "electricity", "utilities"]
    },
    # Division 66 - Financial services
    "66": {
        "name_mk": "Финансиски услуги",
        "name_en": "Financial services",
        "keywords": ["финансиски", "банкарски", "осигурување", "financial", "banking", "insurance", "кредит", "заем"]
    },
    # Division 70 - Real estate
    "70": {
        "name_mk": "Недвижности",
        "name_en": "Real estate services",
        "keywords": ["недвижности", "изнајмување", "закуп", "real estate", "rental", "lease", "простории", "објекти"]
    },
    # Division 71 - Architectural and engineering
    "71": {
        "name_mk": "Архитектонски и инженерски услуги",
        "name_en": "Architectural, engineering services",
        "keywords": ["архитектонски", "инженерски", "проектирање", "надзор", "консултантски", "architectural", "engineering", "design", "supervision", "consulting", "урбанистички", "геодетски"]
    },
    # Division 72 - IT services
    "72": {
        "name_mk": "ИТ услуги",
        "name_en": "IT services",
        "keywords": ["ИТ", "информатички", "софтверски", "програмирање", "развој", "IT", "information", "software", "programming", "development", "консалтинг", "имплементација", "веб", "интернет", "дигитализација"]
    },
    # Division 73 - R&D services
    "73": {
        "name_mk": "Истражување и развој",
        "name_en": "R&D services",
        "keywords": ["истражување", "развој", "research", "development", "студија", "анализа"]
    },
    # Division 75 - Administration, defence
    "75": {
        "name_mk": "Јавна администрација",
        "name_en": "Administration, defence",
        "keywords": ["администрација", "одбрана", "социјално", "administration", "defence", "social"]
    },
    # Division 77 - Agricultural services
    "77": {
        "name_mk": "Земјоделски услуги",
        "name_en": "Agricultural services",
        "keywords": ["земјоделски услуги", "хортикултура", "шумарство", "agricultural services", "horticulture", "forestry", "зеленило", "паркови"]
    },
    # Division 79 - Business services
    "79": {
        "name_mk": "Деловни услуги",
        "name_en": "Business services",
        "keywords": ["правни", "сметководствени", "консултантски", "маркетинг", "преведување", "legal", "accounting", "consulting", "marketing", "translation", "ревизија", "нотар", "адвокат", "рекламирање", "оглас"]
    },
    # Division 80 - Education
    "80": {
        "name_mk": "Образовни услуги",
        "name_en": "Education services",
        "keywords": ["образование", "обука", "тренинг", "семинар", "education", "training", "seminar", "курс", "училиште"]
    },
    # Division 85 - Health and social
    "85": {
        "name_mk": "Здравствени и социјални услуги",
        "name_en": "Health and social services",
        "keywords": ["здравствени услуги", "болнички", "медицински услуги", "социјална работа", "health services", "hospital services", "medical services", "social work", "нега", "амбуланта"]
    },
    # Division 90 - Sewage, cleaning
    "90": {
        "name_mk": "Канализација, чистење",
        "name_en": "Sewage, refuse, cleaning",
        "keywords": ["канализација", "отпад", "чистење", "хигиена", "дезинфекција", "sewage", "waste", "cleaning", "hygiene", "disinfection", "ѓубре", "смет"]
    },
    # Division 92 - Recreational, cultural
    "92": {
        "name_mk": "Рекреативни и културни услуги",
        "name_en": "Recreational, cultural services",
        "keywords": ["култура", "спорт", "забава", "музеј", "библиотека", "culture", "sports", "entertainment", "museum", "library"]
    },
    # Division 98 - Other services
    "98": {
        "name_mk": "Други услуги",
        "name_en": "Other services",
        "keywords": ["други услуги", "разни", "other services", "miscellaneous"]
    }
}

# More specific subcategory mappings (8-digit codes)
CPV_SUBCATEGORIES = {
    # Medical subcategories
    "33100000": {"name": "Медицински апарати", "keywords": ["медицински апарат", "апарат за", "опрема за болница"]},
    "33110000": {"name": "Опрема за сликање", "keywords": ["рендген", "мри", "скенер", "томограф", "ехо", "ултразвук"]},
    "33140000": {"name": "Медицински потрошен материјал", "keywords": ["шприц", "игли", "катетер", "завои", "газа", "маски", "ракавици"]},
    "33150000": {"name": "Радиотерапија", "keywords": ["радиотерапија", "зрачење", "онкологија"]},
    "33170000": {"name": "Анестезија", "keywords": ["анестезија", "реанимација", "интензивна нега"]},
    "33180000": {"name": "Дијализа", "keywords": ["дијализа", "хемодијализа", "бубрежно"]},
    "33182000": {"name": "Кардиолошка опрема", "keywords": ["дефибрилатор", "пејсмејкер", "срце", "кардио", "ЕКГ"]},
    "33190000": {"name": "Медицински мебел", "keywords": ["болнички кревет", "операциона маса", "инвалидска количка"]},
    "33600000": {"name": "Фармацевтски производи", "keywords": ["лек", "лекови", "таблети", "ампули", "капсули", "сируп"]},
    "33690000": {"name": "Вакцини", "keywords": ["вакцина", "имунизација", "серум"]},

    # IT subcategories
    "72200000": {"name": "Програмирање", "keywords": ["програмирање", "развој на софтвер", "апликација", "веб развој"]},
    "72300000": {"name": "Обработка на податоци", "keywords": ["податоци", "база", "дигитализација", "скенирање"]},
    "72400000": {"name": "Интернет услуги", "keywords": ["интернет", "хостинг", "домен", "веб"]},
    "72500000": {"name": "Компјутерски услуги", "keywords": ["компјутерски услуги", "ИТ поддршка", "хелп деск"]},

    # Construction subcategories
    "45200000": {"name": "Работи на згради", "keywords": ["зграда", "објект", "изградба", "фасада"]},
    "45230000": {"name": "Патишта", "keywords": ["пат", "улица", "асфалт", "коловоз"]},
    "45300000": {"name": "Инсталации", "keywords": ["инсталација", "водовод", "електрика", "греење"]},
    "45400000": {"name": "Завршни работи", "keywords": ["боење", "малтерисување", "подови", "плочки"]},
}


class CPVMatcher:
    """AI-powered CPV code matcher for tenders without CPV codes"""

    def __init__(self):
        self.categories = CPV_CATEGORIES
        self.subcategories = CPV_SUBCATEGORIES

    def infer_cpv_from_text(self, title: str, description: str = "", category: str = "") -> List[Dict]:
        """
        Infer CPV codes from tender title/description using keyword matching.
        Returns list of matched CPV codes with confidence scores.
        """
        text = f"{title} {description} {category}".lower()
        matches = []

        # First, try specific subcategories (more precise)
        for code, info in self.subcategories.items():
            score = self._calculate_match_score(text, info["keywords"])
            if score > 0:
                matches.append({
                    "cpv_code": code,
                    "name": info["name"],
                    "confidence": min(score, 1.0),
                    "level": "subcategory"
                })

        # Then try main categories
        for division, info in self.categories.items():
            score = self._calculate_match_score(text, info["keywords"])
            if score > 0:
                matches.append({
                    "cpv_code": f"{division}000000",
                    "name_mk": info["name_mk"],
                    "name_en": info["name_en"],
                    "confidence": min(score * 0.8, 1.0),  # Slightly lower confidence for broad categories
                    "level": "category"
                })

        # Sort by confidence and return top matches
        matches.sort(key=lambda x: x["confidence"], reverse=True)
        return matches[:5]

    def _calculate_match_score(self, text: str, keywords: List[str]) -> float:
        """Calculate match score based on keyword presence"""
        if not text or not keywords:
            return 0.0

        matches = 0
        total_keywords = len(keywords)

        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in text:
                # Exact match
                matches += 1.0
            elif any(word in text for word in keyword_lower.split()):
                # Partial match
                matches += 0.5

        return matches / total_keywords if total_keywords > 0 else 0.0

    def matches_user_preferences(
        self,
        tender_title: str,
        tender_description: str,
        tender_category: str,
        user_cpv_codes: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Check if a tender matches user's CPV preferences.
        Returns (is_match, list of matched reasons)
        """
        if not user_cpv_codes:
            return False, []

        # Infer CPV codes from tender
        inferred = self.infer_cpv_from_text(tender_title, tender_description, tender_category)

        if not inferred:
            return False, []

        matched_reasons = []

        for user_cpv in user_cpv_codes:
            user_prefix = user_cpv[:2]  # First 2 digits (division)

            for inf in inferred:
                inf_code = inf["cpv_code"]

                # Check if user's CPV matches inferred CPV
                if inf_code.startswith(user_prefix):
                    confidence = inf["confidence"]
                    if confidence >= 0.3:  # Minimum confidence threshold
                        name = inf.get("name_mk") or inf.get("name")
                        matched_reasons.append(f"CPV: {name}")

        # Remove duplicates
        matched_reasons = list(set(matched_reasons))

        return len(matched_reasons) > 0, matched_reasons[:2]

    def get_category_for_display(self, cpv_code: str) -> str:
        """Get display name for a CPV code"""
        if not cpv_code:
            return ""

        # Try exact subcategory match
        if cpv_code in self.subcategories:
            return self.subcategories[cpv_code]["name"]

        # Try division match
        division = cpv_code[:2]
        if division in self.categories:
            return self.categories[division]["name_mk"]

        return ""


# Singleton instance for use across the application
_cpv_matcher_instance = None

def get_cpv_matcher() -> CPVMatcher:
    """Get or create CPV matcher singleton"""
    global _cpv_matcher_instance
    if _cpv_matcher_instance is None:
        _cpv_matcher_instance = CPVMatcher()
    return _cpv_matcher_instance
