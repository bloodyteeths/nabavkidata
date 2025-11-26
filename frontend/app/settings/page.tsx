"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { api, UserPreferences } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { billing, BillingPlan } from "@/lib/billing";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { X, Check, Sparkles, CreditCard, Zap, HelpCircle, Search, AlertTriangle, ChevronDown } from "lucide-react";
import { toast } from "sonner";

// Expanded sectors based on common procurement categories in Macedonia
const AVAILABLE_SECTORS = [
  { id: "it", label: "ИТ и Софтвер", description: "Информатичка технологија, софтвер, хардвер" },
  { id: "construction", label: "Градежништво", description: "Градежни работи, инфраструктура" },
  { id: "consulting", label: "Консултантски услуги", description: "Стручни консултации, анализи" },
  { id: "equipment", label: "Опрема и машини", description: "Канцелариска и индустриска опрема" },
  { id: "medical", label: "Медицина и здравство", description: "Медицинска опрема, лекови, услуги" },
  { id: "education", label: "Образование", description: "Образовни услуги и материјали" },
  { id: "transport", label: "Транспорт", description: "Возила, транспортни услуги" },
  { id: "food", label: "Храна и пијалоци", description: "Прехранбени производи" },
  { id: "cleaning", label: "Чистење и одржување", description: "Хигиенски услуги, одржување" },
  { id: "security", label: "Обезбедување", description: "Физичко и техничко обезбедување" },
  { id: "energy", label: "Енергетика", description: "Електрична енергија, гориво, греење" },
  { id: "printing", label: "Печатење", description: "Печатарски услуги, канцелариски материјал" },
];

// Complete CPV codes dictionary based on EU Common Procurement Vocabulary 2008
// Source: https://ted.europa.eu/en/simap/cpv
const CPV_CODES_DICTIONARY = [
  // Division 03 - Agricultural products
  { code: "03000000", label: "Земјоделски производи", labelEn: "Agricultural products" },
  { code: "03100000", label: "Земјоделски и градинарски производи", labelEn: "Agricultural and horticultural products" },
  { code: "03200000", label: "Житарици и градинарски култури", labelEn: "Cereals and crops" },
  { code: "03300000", label: "Сточарски производи", labelEn: "Farming products" },
  { code: "03400000", label: "Шумарски производи", labelEn: "Forestry products" },

  // Division 09 - Petroleum and fuels
  { code: "09000000", label: "Нафта и горива", labelEn: "Petroleum products, fuel" },
  { code: "09100000", label: "Горива", labelEn: "Fuels" },
  { code: "09130000", label: "Нафта и нафтени деривати", labelEn: "Petroleum and distillates" },
  { code: "09134000", label: "Гасни масла", labelEn: "Gas oils" },
  { code: "09135000", label: "Масла за горење", labelEn: "Heating oils" },

  // Division 14 - Mining products
  { code: "14000000", label: "Рударски производи", labelEn: "Mining products" },
  { code: "14200000", label: "Песок и глина", labelEn: "Sand and clay" },
  { code: "14500000", label: "Рударски и каменоломни производи", labelEn: "Mining and quarrying products" },

  // Division 15 - Food and beverages
  { code: "15000000", label: "Храна и пијалоци", labelEn: "Food, beverages, tobacco" },
  { code: "15100000", label: "Сточарски производи, месо", labelEn: "Animal products, meat" },
  { code: "15200000", label: "Риба и рибни производи", labelEn: "Fish and fish products" },
  { code: "15300000", label: "Овошје и зеленчук", labelEn: "Fruit, vegetables" },
  { code: "15400000", label: "Масла и масти", labelEn: "Oils and fats" },
  { code: "15500000", label: "Млечни производи", labelEn: "Dairy products" },
  { code: "15600000", label: "Мелнички производи", labelEn: "Grain mill products" },
  { code: "15800000", label: "Разни прехранбени производи", labelEn: "Miscellaneous food products" },
  { code: "15900000", label: "Пијалоци", labelEn: "Beverages" },

  // Division 18 - Clothing
  { code: "18000000", label: "Облека и додатоци", labelEn: "Clothing, footwear, luggage" },
  { code: "18100000", label: "Работна облека", labelEn: "Occupational clothing" },
  { code: "18200000", label: "Надворешна облека", labelEn: "Outerwear" },
  { code: "18800000", label: "Обувки", labelEn: "Footwear" },

  // Division 22 - Printed matter
  { code: "22000000", label: "Печатени материјали", labelEn: "Printed matter" },
  { code: "22100000", label: "Книги и брошури", labelEn: "Books, brochures" },
  { code: "22200000", label: "Весници и списанија", labelEn: "Newspapers, journals" },
  { code: "22400000", label: "Марки и формулари", labelEn: "Stamps, forms" },

  // Division 24 - Chemical products
  { code: "24000000", label: "Хемиски производи", labelEn: "Chemical products" },
  { code: "24100000", label: "Гасови", labelEn: "Gases" },
  { code: "24300000", label: "Бои и лакови", labelEn: "Paints and varnishes" },
  { code: "24400000", label: "Ѓубрива и азотни соединенија", labelEn: "Fertilisers and nitrogen compounds" },
  { code: "24500000", label: "Пластика", labelEn: "Plastics" },
  { code: "24900000", label: "Фини и разни хемикалии", labelEn: "Fine and various chemicals" },

  // Division 30 - Office and computing machinery
  { code: "30000000", label: "Канцелариска и компјутерска опрема", labelEn: "Office and computing machinery" },
  { code: "30100000", label: "Канцелариски машини и опрема", labelEn: "Office machines and equipment" },
  { code: "30120000", label: "Фотокопири и принтери", labelEn: "Photocopying and printing machines" },
  { code: "30190000", label: "Канцелариски материјали", labelEn: "Office equipment" },
  { code: "30200000", label: "Компјутерска опрема", labelEn: "Computer equipment" },
  { code: "30210000", label: "Машини за процесирање податоци (хардвер)", labelEn: "Data-processing machines (hardware)" },
  { code: "30230000", label: "Компјутерска опрема", labelEn: "Computer-related equipment" },
  { code: "30231000", label: "Компјутерски екрани и конзоли", labelEn: "Computer screens and consoles" },
  { code: "30232000", label: "Периферна опрема", labelEn: "Peripheral equipment" },
  { code: "30233000", label: "Медиуми за складирање", labelEn: "Media storage devices" },
  { code: "30236000", label: "Разна компјутерска опрема", labelEn: "Miscellaneous computer equipment" },
  { code: "30237000", label: "Делови и додатоци за компјутери", labelEn: "Computer parts and accessories" },

  // Division 31 - Electrical machinery
  { code: "31000000", label: "Електрични машини и апарати", labelEn: "Electrical machinery and apparatus" },
  { code: "31100000", label: "Електромотори и генератори", labelEn: "Electric motors and generators" },
  { code: "31200000", label: "Апарати за дистрибуција на струја", labelEn: "Electricity distribution apparatus" },
  { code: "31500000", label: "Осветлување", labelEn: "Lighting equipment" },
  { code: "31600000", label: "Електрична опрема", labelEn: "Electrical equipment" },

  // Division 32 - Radio and TV equipment
  { code: "32000000", label: "Радио, ТВ и телекомуникациска опрема", labelEn: "Radio, television, communication equipment" },
  { code: "32200000", label: "Радиотелефонска опрема", labelEn: "Radio telephony apparatus" },
  { code: "32300000", label: "ТВ и радио приемници", labelEn: "Television and radio receivers" },
  { code: "32400000", label: "Мрежи", labelEn: "Networks" },
  { code: "32500000", label: "Телекомуникациска опрема", labelEn: "Telecommunications equipment" },
  { code: "32550000", label: "Телефонска опрема", labelEn: "Telephone equipment" },

  // Division 33 - Medical equipment
  { code: "33000000", label: "Медицинска опрема и фармацевтски производи", labelEn: "Medical equipment, pharmaceuticals" },
  { code: "33100000", label: "Медицински апарати", labelEn: "Medical equipment" },
  { code: "33110000", label: "Опрема за сликање", labelEn: "Imaging equipment" },
  { code: "33120000", label: "Системи за снимање", labelEn: "Recording systems" },
  { code: "33130000", label: "Забна и стоматолошка опрема", labelEn: "Dental and subspeciality instruments" },
  { code: "33140000", label: "Медицински потрошен материјал", labelEn: "Medical consumables" },
  { code: "33150000", label: "Радиотераписка опрема", labelEn: "Radiotherapy devices" },
  { code: "33160000", label: "Оперативни техники", labelEn: "Operating techniques" },
  { code: "33170000", label: "Анестезија и реанимација", labelEn: "Anaesthesia and resuscitation" },
  { code: "33180000", label: "Функционална поддршка", labelEn: "Functional support" },
  { code: "33190000", label: "Разни медицински апарати", labelEn: "Miscellaneous medical devices" },
  { code: "33600000", label: "Фармацевтски производи", labelEn: "Pharmaceutical products" },
  { code: "33690000", label: "Разни медикаменти", labelEn: "Various medicinal products" },
  { code: "33700000", label: "Производи за лична хигиена", labelEn: "Personal care products" },

  // Division 34 - Transport equipment
  { code: "34000000", label: "Транспортна опрема и помошни производи", labelEn: "Transport equipment and auxiliary products" },
  { code: "34100000", label: "Моторни возила", labelEn: "Motor vehicles" },
  { code: "34110000", label: "Патнички автомобили", labelEn: "Passenger cars" },
  { code: "34120000", label: "Моторни возила за превоз", labelEn: "Motor vehicles for transport" },
  { code: "34130000", label: "Моторни возила за превоз на стоки", labelEn: "Motor vehicles for goods transport" },
  { code: "34140000", label: "Тешки моторни возила", labelEn: "Heavy-duty motor vehicles" },
  { code: "34144000", label: "Моторни возила за специјални намени", labelEn: "Special-purpose motor vehicles" },
  { code: "34300000", label: "Делови за возила", labelEn: "Parts for vehicles" },
  { code: "34400000", label: "Мотоцикли и велосипеди", labelEn: "Motorcycles and bicycles" },

  // Division 35 - Security equipment
  { code: "35000000", label: "Безбедносна опрема", labelEn: "Security, fire-fighting equipment" },
  { code: "35100000", label: "Опрема за итни случаи", labelEn: "Emergency and security equipment" },
  { code: "35110000", label: "Противпожарна опрема", labelEn: "Firefighting equipment" },
  { code: "35120000", label: "Системи за надзор", labelEn: "Surveillance systems" },

  // Division 37 - Musical instruments
  { code: "37000000", label: "Музички инструменти и спортски производи", labelEn: "Musical instruments, sporting goods" },
  { code: "37300000", label: "Музички инструменти", labelEn: "Musical instruments" },
  { code: "37400000", label: "Спортски производи", labelEn: "Sports goods" },
  { code: "37500000", label: "Игри и играчки", labelEn: "Games and toys" },

  // Division 38 - Laboratory equipment
  { code: "38000000", label: "Лабораториска и оптичка опрема", labelEn: "Laboratory, optical and precision equipment" },
  { code: "38200000", label: "Геолошки и геофизички инструменти", labelEn: "Geological and geophysical instruments" },
  { code: "38300000", label: "Инструменти за мерење", labelEn: "Measuring instruments" },
  { code: "38400000", label: "Инструменти за проверка", labelEn: "Instruments for checking" },
  { code: "38500000", label: "Апарати за проверка", labelEn: "Checking and testing apparatus" },

  // Division 39 - Furniture
  { code: "39000000", label: "Мебел и опрема за домаќинство", labelEn: "Furniture, furnishings, appliances" },
  { code: "39100000", label: "Мебел", labelEn: "Furniture" },
  { code: "39110000", label: "Седишта и столици", labelEn: "Seats, chairs and related products" },
  { code: "39120000", label: "Маси и бироа", labelEn: "Tables, cupboards, desks" },
  { code: "39130000", label: "Канцелариски мебел", labelEn: "Office furniture" },
  { code: "39140000", label: "Мебел за домаќинство", labelEn: "Domestic furniture" },
  { code: "39150000", label: "Разен мебел", labelEn: "Miscellaneous furniture" },
  { code: "39200000", label: "Опрема за домаќинство", labelEn: "Furnishing equipment" },
  { code: "39500000", label: "Текстилни производи", labelEn: "Textile articles" },
  { code: "39700000", label: "Апарати за домаќинство", labelEn: "Domestic appliances" },
  { code: "39800000", label: "Производи за чистење", labelEn: "Cleaning products" },

  // Division 42 - Industrial machinery
  { code: "42000000", label: "Индустриски машини", labelEn: "Industrial machinery" },
  { code: "42100000", label: "Машини за производство на енергија", labelEn: "Machinery for production of energy" },
  { code: "42200000", label: "Машини за обработка на храна", labelEn: "Food processing machinery" },
  { code: "42400000", label: "Опрема за подигање и ракување", labelEn: "Lifting and handling equipment" },
  { code: "42500000", label: "Опрема за ладење и вентилација", labelEn: "Cooling and ventilation equipment" },
  { code: "42900000", label: "Разни машини", labelEn: "Various general-purpose machinery" },

  // Division 43 - Mining machinery
  { code: "43000000", label: "Машини за рударство и градежништво", labelEn: "Machinery for mining and construction" },
  { code: "43200000", label: "Машини за земјени работи", labelEn: "Earth-moving and excavating machinery" },
  { code: "43300000", label: "Градежни машини", labelEn: "Construction machinery" },

  // Division 44 - Construction structures
  { code: "44000000", label: "Градежни конструкции и материјали", labelEn: "Construction structures and materials" },
  { code: "44100000", label: "Градежни материјали", labelEn: "Construction materials" },
  { code: "44200000", label: "Структурни производи", labelEn: "Structural products" },
  { code: "44300000", label: "Кабел и жици", labelEn: "Cable, wire and related products" },
  { code: "44400000", label: "Разни фабрикувани производи", labelEn: "Various fabricated products" },
  { code: "44500000", label: "Алати и опрема", labelEn: "Tools, locks, keys" },
  { code: "44600000", label: "Резервоари и контејнери", labelEn: "Tanks, reservoirs and containers" },

  // Division 45 - Construction work
  { code: "45000000", label: "Градежни работи", labelEn: "Construction work" },
  { code: "45100000", label: "Подготвителни градежни работи", labelEn: "Site preparation work" },
  { code: "45110000", label: "Рушење и земјени работи", labelEn: "Building demolition and wrecking work" },
  { code: "45200000", label: "Работи за комплетни или делумни згради", labelEn: "Works for complete or part construction" },
  { code: "45210000", label: "Градежни работи за згради", labelEn: "Building construction work" },
  { code: "45220000", label: "Инженерски работи", labelEn: "Engineering works" },
  { code: "45230000", label: "Градба на цевководи и патишта", labelEn: "Construction work for pipelines and roads" },
  { code: "45240000", label: "Хидроградежни работи", labelEn: "Construction work for water projects" },
  { code: "45250000", label: "Градежни работи за постројки", labelEn: "Construction work for plants" },
  { code: "45260000", label: "Покривање и фасадни работи", labelEn: "Roof works and other special trade works" },
  { code: "45300000", label: "Инсталациски работи во згради", labelEn: "Building installation work" },
  { code: "45310000", label: "Електро-инсталациски работи", labelEn: "Electrical installation work" },
  { code: "45320000", label: "Изолациски работи", labelEn: "Insulation work" },
  { code: "45330000", label: "Водоводни и санитарни работи", labelEn: "Plumbing and sanitary works" },
  { code: "45340000", label: "Инсталација на огради", labelEn: "Fencing installation work" },
  { code: "45400000", label: "Завршни градежни работи", labelEn: "Building completion work" },
  { code: "45410000", label: "Малтерисување", labelEn: "Plastering work" },
  { code: "45420000", label: "Столарски работи", labelEn: "Joinery installation work" },
  { code: "45430000", label: "Подови и ѕидни облоги", labelEn: "Floor and wall covering work" },
  { code: "45440000", label: "Молерофарбарски работи", labelEn: "Painting and glazing work" },
  { code: "45450000", label: "Други завршни работи", labelEn: "Other building completion work" },
  { code: "45500000", label: "Изнајмување на градежна опрема", labelEn: "Hire of construction and civil engineering equipment" },

  // Division 48 - Software packages
  { code: "48000000", label: "Софтверски пакети и системи", labelEn: "Software package and information systems" },
  { code: "48100000", label: "Софтверски пакети за индустрија", labelEn: "Industry specific software package" },
  { code: "48200000", label: "Софтвер за мрежи и интернет", labelEn: "Networking, Internet and intranet software" },
  { code: "48300000", label: "Софтвер за креирање документи", labelEn: "Document creation software package" },
  { code: "48400000", label: "Софтвер за деловни трансакции", labelEn: "Business transaction software package" },
  { code: "48500000", label: "Софтвер за комуникација", labelEn: "Communication and multimedia software" },
  { code: "48600000", label: "Софтвер за бази на податоци", labelEn: "Database and operating software package" },
  { code: "48700000", label: "Софтверски алатки", labelEn: "Software package utilities" },
  { code: "48800000", label: "Информациски системи", labelEn: "Information systems and servers" },
  { code: "48900000", label: "Разни софтверски пакети", labelEn: "Miscellaneous software package" },

  // Division 50 - Repair and maintenance services
  { code: "50000000", label: "Услуги за поправка и одржување", labelEn: "Repair and maintenance services" },
  { code: "50100000", label: "Поправка и одржување на возила", labelEn: "Repair and maintenance of vehicles" },
  { code: "50200000", label: "Поправка на авиони", labelEn: "Repair of aircraft" },
  { code: "50300000", label: "Поправка на компјутери", labelEn: "Repair of personal computers" },
  { code: "50400000", label: "Поправка на медицинска опрема", labelEn: "Repair of medical equipment" },
  { code: "50500000", label: "Поправка на пумпи и вентили", labelEn: "Repair of pumps and valves" },
  { code: "50700000", label: "Поправка на згради", labelEn: "Repair services of building installations" },
  { code: "50800000", label: "Разни услуги за поправка", labelEn: "Miscellaneous repair services" },

  // Division 51 - Installation services
  { code: "51000000", label: "Услуги за инсталација", labelEn: "Installation services" },
  { code: "51100000", label: "Инсталација на електрична опрема", labelEn: "Installation of electrical equipment" },
  { code: "51200000", label: "Инсталација на мерна опрема", labelEn: "Installation of measuring equipment" },
  { code: "51500000", label: "Инсталација на машини", labelEn: "Installation of machinery" },

  // Division 55 - Hotel and restaurant services
  { code: "55000000", label: "Хотелски и ресторантски услуги", labelEn: "Hotel, restaurant and retail trade services" },
  { code: "55100000", label: "Хотелски услуги", labelEn: "Hotel services" },
  { code: "55200000", label: "Кампови и друго сместување", labelEn: "Camping sites and other non-hotel accommodation" },
  { code: "55300000", label: "Ресторантски услуги и кетеринг", labelEn: "Restaurant and catering services" },
  { code: "55400000", label: "Услуги за послужување пијалоци", labelEn: "Beverages-serving services" },
  { code: "55500000", label: "Услуги на менза и кетеринг", labelEn: "Canteen and catering services" },
  { code: "55520000", label: "Услуги за кетеринг", labelEn: "Catering services" },

  // Division 60 - Transport services
  { code: "60000000", label: "Транспортни услуги", labelEn: "Transport services" },
  { code: "60100000", label: "Патен транспорт", labelEn: "Road transport services" },
  { code: "60112000", label: "Услуги за јавен патен превоз", labelEn: "Public road transport services" },
  { code: "60130000", label: "Услуги за специјализиран патен превоз", labelEn: "Special-purpose road passenger-transport services" },
  { code: "60140000", label: "Редовен патнички превоз", labelEn: "Non-scheduled passenger transport" },
  { code: "60160000", label: "Поштенски транспорт", labelEn: "Mail transport by road" },
  { code: "60170000", label: "Изнајмување возила со возач", labelEn: "Hire of vehicles with driver" },
  { code: "60180000", label: "Изнајмување транспортни возила", labelEn: "Hire of goods-transport vehicles with driver" },
  { code: "60200000", label: "Железнички транспорт", labelEn: "Rail transport services" },
  { code: "60400000", label: "Воздушен транспорт", labelEn: "Air transport services" },
  { code: "60600000", label: "Воден транспорт", labelEn: "Water transport services" },

  // Division 63 - Supporting transport services
  { code: "63000000", label: "Поддршка за транспортни услуги", labelEn: "Supporting and auxiliary transport services" },
  { code: "63100000", label: "Ракување со товар", labelEn: "Cargo handling" },
  { code: "63500000", label: "Услуги на туристички агенции", labelEn: "Travel agency, tour operator services" },
  { code: "63700000", label: "Услуги за поддршка на копнен транспорт", labelEn: "Support services for land transport" },

  // Division 64 - Postal and telecommunications services
  { code: "64000000", label: "Поштенски и телекомуникациски услуги", labelEn: "Postal and telecommunications services" },
  { code: "64100000", label: "Поштенски услуги", labelEn: "Post and courier services" },
  { code: "64110000", label: "Поштенски услуги", labelEn: "Postal services" },
  { code: "64120000", label: "Курирски услуги", labelEn: "Courier services" },
  { code: "64200000", label: "Телекомуникациски услуги", labelEn: "Telecommunications services" },
  { code: "64210000", label: "Телефонски услуги и пренос на податоци", labelEn: "Telephone and data transmission services" },
  { code: "64220000", label: "Услуги за телекомуникациска опрема", labelEn: "Telecommunication services except telephone" },

  // Division 65 - Public utilities
  { code: "65000000", label: "Јавни комунални услуги", labelEn: "Public utilities" },
  { code: "65100000", label: "Дистрибуција на вода", labelEn: "Water distribution" },
  { code: "65200000", label: "Дистрибуција на гас", labelEn: "Gas distribution" },
  { code: "65300000", label: "Дистрибуција на електрична енергија", labelEn: "Electricity distribution" },
  { code: "65400000", label: "Други извори на енергија", labelEn: "Other sources of energy" },
  { code: "65500000", label: "Читање на метри", labelEn: "Meter reading services" },

  // Division 66 - Financial services
  { code: "66000000", label: "Финансиски и осигурителни услуги", labelEn: "Financial and insurance services" },
  { code: "66100000", label: "Банкарски и инвестициски услуги", labelEn: "Banking and investment services" },
  { code: "66500000", label: "Осигурителни услуги", labelEn: "Insurance services" },
  { code: "66600000", label: "Услуги на благајна", labelEn: "Treasury services" },

  // Division 70 - Real estate services
  { code: "70000000", label: "Услуги за недвижности", labelEn: "Real estate services" },
  { code: "70100000", label: "Услуги за недвижности (сопствени)", labelEn: "Real estate services with own property" },
  { code: "70200000", label: "Услуги за изнајмување", labelEn: "Letting or operating services" },
  { code: "70300000", label: "Посредништво со недвижности", labelEn: "Real estate agency services" },

  // Division 71 - Architectural and engineering services
  { code: "71000000", label: "Архитектонски и инженерски услуги", labelEn: "Architectural, construction, engineering services" },
  { code: "71200000", label: "Архитектонски услуги", labelEn: "Architectural and related services" },
  { code: "71300000", label: "Инженерски услуги", labelEn: "Engineering services" },
  { code: "71310000", label: "Консултантски инженерски услуги", labelEn: "Consultative engineering services" },
  { code: "71320000", label: "Услуги за инженерски дизајн", labelEn: "Engineering design services" },
  { code: "71350000", label: "Научно-технички услуги", labelEn: "Engineering-related scientific services" },
  { code: "71400000", label: "Услуги за урбано планирање", labelEn: "Urban planning and landscape services" },
  { code: "71500000", label: "Услуги поврзани со градежништво", labelEn: "Construction-related services" },
  { code: "71600000", label: "Услуги за технички тестирања", labelEn: "Technical testing, analysis services" },

  // Division 72 - IT services
  { code: "72000000", label: "ИТ услуги", labelEn: "IT services: consulting, software development" },
  { code: "72100000", label: "Консултации за хардвер", labelEn: "Hardware consultancy services" },
  { code: "72200000", label: "Програмирање и консалтинг", labelEn: "Software programming and consultancy" },
  { code: "72210000", label: "Програмирање на софтвер", labelEn: "Programming services" },
  { code: "72220000", label: "Консултантски услуги за системи", labelEn: "Systems and technical consultancy services" },
  { code: "72230000", label: "Услуги за развој на софтвер", labelEn: "Custom software development services" },
  { code: "72240000", label: "Услуги за анализа на системи", labelEn: "Systems analysis and programming services" },
  { code: "72250000", label: "Системска поддршка", labelEn: "System and support services" },
  { code: "72260000", label: "Услуги поврзани со софтвер", labelEn: "Software-related services" },
  { code: "72300000", label: "Услуги за обработка на податоци", labelEn: "Data services" },
  { code: "72400000", label: "Интернет услуги", labelEn: "Internet services" },
  { code: "72500000", label: "Компјутерски услуги", labelEn: "Computer-related services" },
  { code: "72600000", label: "Услуги за компјутерска поддршка", labelEn: "Computer support and consultancy services" },
  { code: "72700000", label: "Услуги за компјутерски мрежи", labelEn: "Computer network services" },
  { code: "72800000", label: "Ревизија на компјутери", labelEn: "Computer audit and testing services" },
  { code: "72900000", label: "Компјутерски backup и конверзија", labelEn: "Computer backup and conversion services" },

  // Division 73 - R&D services
  { code: "73000000", label: "Услуги за истражување и развој", labelEn: "Research and development services" },
  { code: "73100000", label: "Истражувачки услуги", labelEn: "Research and experimental development services" },
  { code: "73200000", label: "Консултантски услуги за R&D", labelEn: "Research and development consultancy services" },
  { code: "73300000", label: "Дизајн и извршување на R&D", labelEn: "Design and execution of R&D" },

  // Division 75 - Administration, defence, social security
  { code: "75000000", label: "Јавна администрација и одбрана", labelEn: "Administration, defence and social security" },
  { code: "75100000", label: "Административни услуги", labelEn: "Administration services" },
  { code: "75200000", label: "Услуги на заедницата", labelEn: "Provision of services to the community" },
  { code: "75300000", label: "Услуги за задолжително социјално осигурување", labelEn: "Compulsory social security services" },

  // Division 76 - Services related to energy
  { code: "76000000", label: "Услуги за нафта и гас", labelEn: "Services related to oil and gas industry" },
  { code: "76100000", label: "Услуги за природен гас", labelEn: "Professional services for gas industry" },
  { code: "76200000", label: "Услуги за нафтена индустрија", labelEn: "Professional services for oil industry" },
  { code: "76300000", label: "Услуги за дупчење", labelEn: "Drilling services" },
  { code: "76400000", label: "Услуги за поставување опрема", labelEn: "Rig-positioning services" },
  { code: "76500000", label: "Услуги на копно и морe", labelEn: "Onshore and offshore services" },
  { code: "76600000", label: "Инспекција на цевководи", labelEn: "Pipeline inspection services" },

  // Division 77 - Agricultural services
  { code: "77000000", label: "Земјоделски услуги", labelEn: "Agricultural, forestry, horticultural services" },
  { code: "77100000", label: "Земјоделски услуги", labelEn: "Agricultural services" },
  { code: "77200000", label: "Шумарски услуги", labelEn: "Forestry services" },
  { code: "77300000", label: "Хортикултурни услуги", labelEn: "Horticultural services" },
  { code: "77310000", label: "Садење и одржување на зеленило", labelEn: "Planting and maintenance services" },
  { code: "77400000", label: "Зоолошки услуги", labelEn: "Zoological services" },

  // Division 79 - Business services
  { code: "79000000", label: "Деловни услуги", labelEn: "Business services: law, marketing, consulting" },
  { code: "79100000", label: "Правни услуги", labelEn: "Legal services" },
  { code: "79200000", label: "Сметководствени услуги", labelEn: "Accounting, auditing and fiscal services" },
  { code: "79210000", label: "Сметководствени услуги", labelEn: "Accounting and auditing services" },
  { code: "79220000", label: "Даночни услуги", labelEn: "Fiscal services" },
  { code: "79300000", label: "Истражување на пазар и анкети", labelEn: "Market and economic research" },
  { code: "79400000", label: "Консултантски услуги за бизнис", labelEn: "Business and management consultancy" },
  { code: "79410000", label: "Консултантски услуги за бизнис и менаџмент", labelEn: "Business and management consultancy" },
  { code: "79500000", label: "Услуги за поддршка на канцеларии", labelEn: "Office support services" },
  { code: "79600000", label: "Услуги за вработување", labelEn: "Recruitment services" },
  { code: "79700000", label: "Детективски и безбедносни услуги", labelEn: "Investigation and security services" },
  { code: "79800000", label: "Печатарски услуги", labelEn: "Printing and related services" },
  { code: "79900000", label: "Разни деловни услуги", labelEn: "Miscellaneous business and related services" },
  { code: "79950000", label: "Организација на изложби и саеми", labelEn: "Exhibition, fair and congress organisation" },

  // Division 80 - Education services
  { code: "80000000", label: "Образовни услуги", labelEn: "Education and training services" },
  { code: "80100000", label: "Основно образование", labelEn: "Primary education services" },
  { code: "80200000", label: "Средно образование", labelEn: "Secondary education services" },
  { code: "80300000", label: "Високо образование", labelEn: "Higher education services" },
  { code: "80400000", label: "Образование за возрасни", labelEn: "Adult and other education services" },
  { code: "80500000", label: "Услуги за обука", labelEn: "Training services" },
  { code: "80530000", label: "Услуги за стручна обука", labelEn: "Vocational training services" },
  { code: "80600000", label: "Услуги за обука за безбедност", labelEn: "Training services in security matters" },

  // Division 85 - Health and social work services
  { code: "85000000", label: "Здравствени и социјални услуги", labelEn: "Health and social work services" },
  { code: "85100000", label: "Здравствени услуги", labelEn: "Health services" },
  { code: "85110000", label: "Болнички услуги", labelEn: "Hospital and related services" },
  { code: "85120000", label: "Медицински услуги", labelEn: "Medical practice and related services" },
  { code: "85130000", label: "Стоматолошки услуги", labelEn: "Dental practice and related services" },
  { code: "85140000", label: "Разни здравствени услуги", labelEn: "Miscellaneous health services" },
  { code: "85200000", label: "Ветеринарни услуги", labelEn: "Veterinary services" },
  { code: "85300000", label: "Социјална работа", labelEn: "Social work and related services" },

  // Division 90 - Sewage, refuse, cleaning services
  { code: "90000000", label: "Канализација, отпад, чистење", labelEn: "Sewage, refuse, cleaning and environmental services" },
  { code: "90400000", label: "Услуги за канализација", labelEn: "Sewage services" },
  { code: "90500000", label: "Услуги за отпад", labelEn: "Refuse and waste related services" },
  { code: "90510000", label: "Отстранување на отпад", labelEn: "Refuse disposal and treatment" },
  { code: "90600000", label: "Услуги за чистење", labelEn: "Cleaning services for urban and rural areas" },
  { code: "90700000", label: "Услуги за животна средина", labelEn: "Environmental services" },
  { code: "90900000", label: "Услуги за чистење и санитација", labelEn: "Cleaning and sanitation services" },
  { code: "90910000", label: "Услуги за чистење", labelEn: "Cleaning services" },
  { code: "90911000", label: "Услуги за чистење на канцеларии", labelEn: "Housing and building cleaning services" },
  { code: "90919000", label: "Чистење на училишта", labelEn: "Office, school and office equipment cleaning" },

  // Division 92 - Recreational, cultural, sporting services
  { code: "92000000", label: "Рекреативни, културни и спортски услуги", labelEn: "Recreational, cultural and sporting services" },
  { code: "92100000", label: "Филмски и видео услуги", labelEn: "Motion picture and video services" },
  { code: "92200000", label: "Радио и ТВ услуги", labelEn: "Radio and television services" },
  { code: "92300000", label: "Услуги за забава", labelEn: "Entertainment services" },
  { code: "92400000", label: "Услуги на новински агенции", labelEn: "News-agency services" },
  { code: "92500000", label: "Услуги на библиотеки и архиви", labelEn: "Library, archives, museums services" },
  { code: "92600000", label: "Спортски услуги", labelEn: "Sporting services" },
  { code: "92700000", label: "Услуги на интернет кафе", labelEn: "Cybercafe services" },

  // Division 98 - Other community, social, personal services
  { code: "98000000", label: "Други комунални и лични услуги", labelEn: "Other community, social and personal services" },
  { code: "98100000", label: "Услуги на организации", labelEn: "Membership organisation services" },
  { code: "98200000", label: "Услуги за консултации за еднаквост", labelEn: "Equal opportunities consultancy services" },
  { code: "98300000", label: "Разни услуги", labelEn: "Miscellaneous services" },
  { code: "98390000", label: "Други услуги", labelEn: "Other services" },
];

// Budget presets in MKD
const BUDGET_PRESETS = [
  { label: "Мало (до 500K)", min: 0, max: 500000 },
  { label: "Средно (500K - 3M)", min: 500000, max: 3000000 },
  { label: "Големо (3M - 10M)", min: 3000000, max: 10000000 },
  { label: "Многу големо (над 10M)", min: 10000000, max: undefined },
];

const DEFAULT_PREFERENCES: UserPreferences = {
  sectors: [],
  cpv_codes: [],
  entities: [],
  min_budget: undefined,
  max_budget: undefined,
  exclude_keywords: [],
  competitor_companies: [],
  notification_frequency: "daily",
  email_enabled: true,
};

export default function SettingsPage() {
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [cpvSearch, setCpvSearch] = useState("");
  const [showCpvDropdown, setShowCpvDropdown] = useState(false);
  const [entityInput, setEntityInput] = useState("");
  const [keywordInput, setKeywordInput] = useState("");
  const [competitorInput, setCompetitorInput] = useState("");
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [currentTier, setCurrentTier] = useState<string>("free");
  const [interval, setInterval] = useState<'monthly' | 'yearly'>('monthly');
  const [upgrading, setUpgrading] = useState<string | null>(null);

  // Autocomplete suggestions
  const [entitySuggestions, setEntitySuggestions] = useState<string[]>([]);
  const [showEntitySuggestions, setShowEntitySuggestions] = useState(false);
  const [competitorSuggestions, setCompetitorSuggestions] = useState<string[]>([]);
  const [showCompetitorSuggestions, setShowCompetitorSuggestions] = useState(false);

  // Validation state
  const [budgetError, setBudgetError] = useState<string | null>(null);

  const { user } = useAuth();
  const userId = user?.user_id;

  // Filtered CPV codes based on search
  const filteredCpvCodes = useMemo(() => {
    if (!cpvSearch.trim()) return CPV_CODES_DICTIONARY.slice(0, 20);
    const search = cpvSearch.toLowerCase();
    return CPV_CODES_DICTIONARY.filter(cpv =>
      cpv.code.includes(search) ||
      cpv.label.toLowerCase().includes(search) ||
      cpv.labelEn.toLowerCase().includes(search)
    ).slice(0, 30);
  }, [cpvSearch]);

  useEffect(() => {
    const init = async () => {
      if (userId) {
        await loadPreferences();
      } else {
        setLoading(false);
      }
      await loadPlans();
    };
    init();
  }, [userId]);

  // Validate budget whenever it changes
  useEffect(() => {
    if (preferences.min_budget && preferences.max_budget) {
      if (preferences.min_budget > preferences.max_budget) {
        setBudgetError("Минималниот буџет не може да биде поголем од максималниот");
      } else {
        setBudgetError(null);
      }
    } else {
      setBudgetError(null);
    }
  }, [preferences.min_budget, preferences.max_budget]);

  const loadPreferences = async () => {
    try {
      if (!userId) {
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const prefs = await api.getPreferences(userId);
        setPreferences(prefs);
      } catch {
        console.log("No existing preferences, using defaults");
        setPreferences(DEFAULT_PREFERENCES);
      }
    } catch (error) {
      console.error("Грешка при вчитување на преференци:", error);
      setPreferences(DEFAULT_PREFERENCES);
    } finally {
      setLoading(false);
    }
  };

  const loadPlans = async () => {
    try {
      const hardcodedPlans: BillingPlan[] = [
        {
          tier: 'free',
          name: 'Free',
          price_monthly_eur: 0,
          price_yearly_eur: 0,
          price_monthly_id: '',
          price_yearly_id: '',
          daily_queries: 3,
          trial_days: 14,
          allow_vpn: false,
          features: ['3 AI queries per day', '14-day trial', 'Basic search', 'Email support']
        },
        {
          tier: 'starter',
          name: 'Starter',
          price_monthly_eur: 14.99,
          price_yearly_eur: 149.99,
          price_monthly_id: 'price_1SWeAsHkVI5icjTl9GZ8Ciui',
          price_yearly_id: 'price_1SWeAsHkVI5icjTlGRvOP17d',
          daily_queries: 5,
          trial_days: 14,
          allow_vpn: true,
          features: ['5 AI queries per day', '14-day trial', 'Advanced filters', 'CSV/PDF export', 'Priority support']
        },
        {
          tier: 'professional',
          name: 'Professional',
          price_monthly_eur: 39.99,
          price_yearly_eur: 399.99,
          price_monthly_id: 'price_1SWeAtHkVI5icjTl8UxSYNYX',
          price_yearly_id: 'price_1SWeAuHkVI5icjTlrbC5owFk',
          daily_queries: 20,
          trial_days: 14,
          allow_vpn: true,
          features: ['20 AI queries per day', '14-day trial', 'Analytics', 'Integrations', 'Dedicated support']
        },
        {
          tier: 'enterprise',
          name: 'Enterprise',
          price_monthly_eur: 99.99,
          price_yearly_eur: 999.99,
          price_monthly_id: 'price_1SWeAvHkVI5icjTlF8eFK8kh',
          price_yearly_id: 'price_1SWeAvHkVI5icjTlcKi7RFu7',
          daily_queries: -1,
          trial_days: 14,
          allow_vpn: true,
          features: ['Unlimited queries', '14-day trial', 'White-label', 'API access', '24/7 support']
        }
      ];
      setPlans(hardcodedPlans);

      try {
        const status = await billing.getSubscriptionStatus();
        setCurrentTier(status.tier);
      } catch {
        console.log('No subscription found, defaulting to free tier');
        setCurrentTier('free');
      }
    } catch (error) {
      console.error("Failed to load plans:", error);
      setCurrentTier('free');
    }
  };

  // Fetch entity suggestions (debounced)
  const fetchEntitySuggestions = useCallback(async (query: string) => {
    if (query.length < 2) {
      setEntitySuggestions([]);
      return;
    }
    try {
      // Search for entities in existing tenders
      const result = await api.searchTenders({
        query: query,
        page: 1,
        page_size: 20
      });
      // Extract unique procuring entities
      const entities = [...new Set(
        result.items
          .map(t => t.procuring_entity)
          .filter((e): e is string => !!e && e.toLowerCase().includes(query.toLowerCase()))
      )].slice(0, 8);
      setEntitySuggestions(entities);
    } catch {
      setEntitySuggestions([]);
    }
  }, []);

  // Fetch competitor suggestions (from e-Pazar suppliers)
  const fetchCompetitorSuggestions = useCallback(async (query: string) => {
    if (query.length < 2) {
      setCompetitorSuggestions([]);
      return;
    }
    try {
      const result = await api.getEPazarSuppliers({ search: query, page_size: 8 });
      const companies = result.items.map(s => s.company_name);
      setCompetitorSuggestions(companies);
    } catch {
      setCompetitorSuggestions([]);
    }
  }, []);

  const handleUpgrade = async (tier: string) => {
    if (tier === 'free') return;
    try {
      setUpgrading(tier);
      const session = await api.createCheckoutSession(tier, interval);
      window.location.href = session.checkout_url;
    } catch (error) {
      console.error("Failed to create checkout session:", error);
      toast.error("Грешка при креирање на сесија за плаќање. Ве молиме обидете се повторно.");
    } finally {
      setUpgrading(null);
    }
  };

  const handleManageBilling = async () => {
    try {
      const portal = await api.createPortalSession();
      window.location.href = portal.url;
    } catch (error) {
      console.error("Failed to open billing portal:", error);
      toast.error("Грешка при отворање на порталот за наплата.");
    }
  };

  const handleSave = async () => {
    // Validate before saving
    if (budgetError) {
      toast.error(budgetError);
      return;
    }

    try {
      if (!userId) {
        toast.error("Мора да сте најавени за да ги зачувате преференциите");
        return;
      }
      setSaving(true);
      await api.savePreferences(userId, preferences);
      toast.success("Преференциите се успешно зачувани! Вашата персонализирана табла ќе се ажурира.");
    } catch (error) {
      console.error("Грешка при зачувување:", error);
      toast.error("Грешка при зачувување на преференците. Проверете ја интернет конекцијата.");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (window.confirm("Дали сте сигурни дека сакате да ги ресетирате сите преференци?")) {
      setPreferences(DEFAULT_PREFERENCES);
      toast.success("Преференциите се ресетирани на стандардни");
    }
  };

  const toggleSector = (sectorId: string) => {
    setPreferences((prev) => ({
      ...prev,
      sectors: prev.sectors.includes(sectorId)
        ? prev.sectors.filter((s) => s !== sectorId)
        : [...prev.sectors, sectorId]
    }));
  };

  const toggleCpvCode = (code: string) => {
    setPreferences((prev) => ({
      ...prev,
      cpv_codes: prev.cpv_codes.includes(code)
        ? prev.cpv_codes.filter((c) => c !== code)
        : [...prev.cpv_codes, code]
    }));
  };

  const addItem = (field: keyof UserPreferences, value: string, setter: (v: string) => void) => {
    if (value.trim() && !(preferences[field] as string[]).includes(value.trim())) {
      setPreferences((prev) => ({ ...prev, [field]: [...(prev[field] as string[]), value.trim()] }));
      setter("");
    }
  };

  const removeItem = (field: keyof UserPreferences, value: string) => {
    setPreferences((prev) => ({ ...prev, [field]: (prev[field] as string[]).filter((i) => i !== value) }));
  };

  const applyBudgetPreset = (preset: typeof BUDGET_PRESETS[0]) => {
    setPreferences((prev) => ({
      ...prev,
      min_budget: preset.min || undefined,
      max_budget: preset.max || undefined
    }));
  };

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('mk-MK').format(num);
  };

  if (loading) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-center">Се вчитува...</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 max-w-6xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Поставки</h1>
        <p className="text-muted-foreground mt-2">
          Конфигурирајте ги вашите преференци за да добивате персонализирани препораки за тендери
        </p>
      </div>

      <div className="space-y-6">
        {/* Subscription Plans */}
        <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              Претплата и цени
            </CardTitle>
            <CardDescription>Одберете го планот што најдобро одговара на вашите потреби</CardDescription>
          </CardHeader>
          <CardContent>
            {/* Monthly/Yearly Toggle */}
            <div className="flex justify-center mb-6">
              <div className="inline-flex rounded-lg border border-primary/20 p-1 bg-background/50">
                <button
                  onClick={() => setInterval('monthly')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${interval === 'monthly'
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                    }`}
                >
                  Месечно
                </button>
                <button
                  onClick={() => setInterval('yearly')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${interval === 'yearly'
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                    }`}
                >
                  Годишно
                  <Badge variant="secondary" className="ml-2 bg-green-500/10 text-green-400 border-green-500/20">
                    Заштеди 17%
                  </Badge>
                </button>
              </div>
            </div>

            {/* Plans Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {plans.map((plan) => {
                const isCurrentPlan = plan.tier === currentTier;
                const price = interval === 'monthly' ? plan.price_monthly_eur : plan.price_yearly_eur;
                const isFree = plan.tier === 'free';
                const isPopular = plan.tier === 'professional';

                return (
                  <div key={plan.tier} className="relative">
                    {isPopular && (
                      <div className="absolute -top-4 left-0 right-0 flex justify-center">
                        <Badge className="bg-primary text-primary-foreground">
                          Најпопуларно
                        </Badge>
                      </div>
                    )}
                    <Card className={`h-full ${isCurrentPlan ? 'border-primary shadow-lg shadow-primary/20' : ''} ${isPopular ? 'border-primary/50' : ''}`}>
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-xl">{plan.name}</CardTitle>
                          {isCurrentPlan && (
                            <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20">
                              Тековен
                            </Badge>
                          )}
                        </div>
                        <div className="mt-4">
                          <div className="flex items-baseline gap-1">
                            <span className="text-4xl font-bold">€{price.toFixed(2)}</span>
                            <span className="text-muted-foreground">
                              {isFree ? '/засекогаш' : `/${interval === 'monthly' ? 'мес' : 'год'}`}
                            </span>
                          </div>
                          {!isFree && interval === 'yearly' && (
                            <p className="text-sm text-muted-foreground mt-1">
                              €{(price / 12).toFixed(2)} месечно
                            </p>
                          )}
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="flex items-center gap-2 text-sm">
                          <Zap className="h-4 w-4 text-primary" />
                          <span className="font-medium">
                            {plan.daily_queries === -1 ? 'Неограничени' : plan.daily_queries} AI пребарувања дневно
                          </span>
                        </div>
                        {plan.trial_days > 0 && (
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Check className="h-4 w-4" />
                            <span>{plan.trial_days}-дневен пробен период</span>
                          </div>
                        )}
                        <div className="space-y-2 pt-2 border-t">
                          {plan.features.map((feature, idx) => (
                            <div key={idx} className="flex items-start gap-2 text-sm">
                              <Check className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                              <span className="text-muted-foreground">{feature}</span>
                            </div>
                          ))}
                        </div>
                        <div className="pt-4">
                          {isCurrentPlan ? (
                            <Button variant="outline" className="w-full" onClick={handleManageBilling}>
                              <CreditCard className="mr-2 h-4 w-4" />
                              Управувај претплата
                            </Button>
                          ) : isFree ? (
                            <Button variant="outline" className="w-full" disabled>
                              Тековен план
                            </Button>
                          ) : (
                            <Button
                              className={`w-full ${isPopular ? 'bg-primary hover:bg-primary/90' : ''}`}
                              onClick={() => handleUpgrade(plan.tier)}
                              disabled={upgrading === plan.tier}
                            >
                              {upgrading === plan.tier ? 'Се обработува...' : 'Надогради'}
                            </Button>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                );
              })}
            </div>

            {currentTier === 'free' && (
              <div className="mt-6 p-4 rounded-lg bg-orange-500/10 border border-orange-500/20">
                <p className="text-sm text-orange-400">
                  <strong>Важно:</strong> Бесплатниот план е ограничен на 14 дена. По истекот на пробниот период, ќе треба да надоградите за да продолжите да ја користите платформата.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Sectors - Improved with descriptions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Сектори на интерес
              <span className="text-xs font-normal text-muted-foreground bg-primary/10 px-2 py-1 rounded">
                {preferences.sectors.length} избрани
              </span>
            </CardTitle>
            <CardDescription>
              Одберете ги секторите за кои сакате да добивате препораки. Можете да изберете повеќе сектори.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {AVAILABLE_SECTORS.map((sector) => (
                <div
                  key={sector.id}
                  onClick={() => toggleSector(sector.id)}
                  className={`cursor-pointer p-3 rounded-lg border transition-all ${
                    preferences.sectors.includes(sector.id)
                      ? 'border-primary bg-primary/10 shadow-sm'
                      : 'border-border hover:border-primary/50 hover:bg-accent/50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{sector.label}</span>
                    {preferences.sectors.includes(sector.id) && (
                      <Check className="h-4 w-4 text-primary" />
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{sector.description}</p>
                </div>
              ))}
            </div>
            {preferences.sectors.length === 0 && (
              <p className="text-sm text-muted-foreground mt-3 flex items-center gap-2">
                <HelpCircle className="h-4 w-4" />
                Изберете барем еден сектор за подобри препораки
              </p>
            )}
          </CardContent>
        </Card>

        {/* CPV Codes - Searchable dropdown with multi-select */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              CPV Кодови
              <span className="text-xs font-normal text-muted-foreground bg-primary/10 px-2 py-1 rounded">
                {preferences.cpv_codes.length} додадени
              </span>
            </CardTitle>
            <CardDescription>
              CPV (Common Procurement Vocabulary) кодовите се стандардизирани EU кодови за категоризација на набавки.
              Пребарајте и изберете кодови за попрецизни препораки.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Searchable CPV dropdown */}
            <div className="relative mb-4">
              <div
                className="flex items-center gap-2 p-3 border rounded-lg cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => setShowCpvDropdown(!showCpvDropdown)}
              >
                <Search className="h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Пребарај CPV кодови по број или опис..."
                  className="flex-1 bg-transparent border-none outline-none text-sm"
                  value={cpvSearch}
                  onChange={(e) => {
                    setCpvSearch(e.target.value);
                    setShowCpvDropdown(true);
                  }}
                  onFocus={() => setShowCpvDropdown(true)}
                />
                <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${showCpvDropdown ? 'rotate-180' : ''}`} />
              </div>

              {/* Dropdown with CPV codes */}
              {showCpvDropdown && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-background border rounded-lg shadow-xl z-[100] max-h-80 overflow-auto">
                  <div className="sticky top-0 bg-muted/50 backdrop-blur-sm px-3 py-2 border-b">
                    <p className="text-xs text-muted-foreground">
                      {filteredCpvCodes.length} кодови пронајдени - кликнете за да изберете
                    </p>
                  </div>
                  {filteredCpvCodes.map((cpv) => {
                    const isSelected = preferences.cpv_codes.includes(cpv.code);
                    return (
                      <div
                        key={cpv.code}
                        className={`px-3 py-2 cursor-pointer flex items-center gap-3 hover:bg-accent transition-colors ${isSelected ? 'bg-primary/10' : ''}`}
                        onClick={() => toggleCpvCode(cpv.code)}
                      >
                        <div className={`w-5 h-5 rounded border flex items-center justify-center ${isSelected ? 'bg-primary border-primary' : 'border-border'}`}>
                          {isSelected && <Check className="h-3 w-3 text-primary-foreground" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-sm text-primary">{cpv.code}</span>
                            <span className="text-sm truncate">{cpv.label}</span>
                          </div>
                          <p className="text-xs text-muted-foreground truncate">{cpv.labelEn}</p>
                        </div>
                      </div>
                    );
                  })}
                  {filteredCpvCodes.length === 0 && (
                    <div className="px-3 py-4 text-center text-muted-foreground text-sm">
                      Нема резултати за &quot;{cpvSearch}&quot;
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Click outside to close */}
            {showCpvDropdown && (
              <div
                className="fixed inset-0 z-[99]"
                onClick={() => setShowCpvDropdown(false)}
              />
            )}

            {/* Selected CPV codes */}
            <div className="flex flex-wrap gap-2">
              {preferences.cpv_codes.length === 0 ? (
                <p className="text-sm text-muted-foreground flex items-center gap-2">
                  <HelpCircle className="h-4 w-4" />
                  Нема избрани CPV кодови. Користете го пребарувањето погоре за да додадете.
                </p>
              ) : (
                preferences.cpv_codes.map((code) => {
                  const cpvInfo = CPV_CODES_DICTIONARY.find(c => c.code === code);
                  return (
                    <Badge key={code} variant="secondary" className="gap-1 py-1.5 pr-1">
                      <span className="font-mono">{code}</span>
                      {cpvInfo && <span className="text-xs opacity-70">- {cpvInfo.label}</span>}
                      <button
                        className="ml-1 p-0.5 rounded hover:bg-destructive/20 transition-colors"
                        onClick={() => removeItem("cpv_codes", code)}
                      >
                        <X className="h-3 w-3 hover:text-destructive" />
                      </button>
                    </Badge>
                  );
                })
              )}
            </div>
          </CardContent>
        </Card>

        {/* Entities - With autocomplete - FIXED z-index */}
        <Card className="relative z-[80]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Набавувачки организации
              <span className="text-xs font-normal text-muted-foreground bg-primary/10 px-2 py-1 rounded">
                {preferences.entities.length} следени
              </span>
            </CardTitle>
            <CardDescription>
              Додадете имиња на институции/организации чии тендери сакате да ги следите (министерства, општини, јавни претпријатија и сл.)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground z-10" />
                <Input
                  placeholder="Пребарај организации (пр. Министерство за здравство)"
                  value={entityInput}
                  onChange={(e) => {
                    setEntityInput(e.target.value);
                    fetchEntitySuggestions(e.target.value);
                    setShowEntitySuggestions(true);
                  }}
                  onFocus={() => setShowEntitySuggestions(true)}
                  onBlur={() => setTimeout(() => setShowEntitySuggestions(false), 200)}
                  onKeyPress={(e) => e.key === "Enter" && addItem("entities", entityInput, setEntityInput)}
                  className="pl-10"
                />
                {/* Autocomplete dropdown - Fixed positioning */}
                {showEntitySuggestions && entitySuggestions.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-background border rounded-md shadow-xl z-[100] max-h-48 overflow-auto">
                    {entitySuggestions.map((entity, idx) => (
                      <div
                        key={idx}
                        className="px-3 py-2 hover:bg-accent cursor-pointer text-sm"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          addItem("entities", entity, setEntityInput);
                          setShowEntitySuggestions(false);
                        }}
                      >
                        {entity}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <Button onClick={() => addItem("entities", entityInput, setEntityInput)}>Додади</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.entities.length === 0 ? (
                <p className="text-sm text-muted-foreground flex items-center gap-2">
                  <HelpCircle className="h-4 w-4" />
                  Почнете да пишувате за да добиете предлози од базата на тендери
                </p>
              ) : (
                preferences.entities.map((entity) => (
                  <Badge key={entity} variant="secondary" className="gap-1">
                    {entity}
                    <X className="h-3 w-3 cursor-pointer hover:text-destructive" onClick={() => removeItem("entities", entity)} />
                  </Badge>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Budget - With presets and validation */}
        <Card>
          <CardHeader>
            <CardTitle>Буџетски опсег</CardTitle>
            <CardDescription>Дефинирајте минимален и максимален буџет за тендерите што ве интересираат (во МКД)</CardDescription>
          </CardHeader>
          <CardContent>
            {/* Budget presets */}
            <div className="mb-4">
              <p className="text-sm font-medium mb-2">Брзи опции:</p>
              <div className="flex flex-wrap gap-2">
                {BUDGET_PRESETS.map((preset, idx) => (
                  <Button
                    key={idx}
                    variant="outline"
                    size="sm"
                    onClick={() => applyBudgetPreset(preset)}
                    className="text-xs"
                  >
                    {preset.label}
                  </Button>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPreferences(prev => ({ ...prev, min_budget: undefined, max_budget: undefined }))}
                  className="text-xs"
                >
                  Без ограничување
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Минимален буџет (МКД)</label>
                <Input
                  type="text"
                  placeholder="0"
                  value={preferences.min_budget ? formatNumber(preferences.min_budget) : ""}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, '');
                    setPreferences((prev) => ({ ...prev, min_budget: value ? Number(value) : undefined }));
                  }}
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Максимален буџет (МКД)</label>
                <Input
                  type="text"
                  placeholder="Без лимит"
                  value={preferences.max_budget ? formatNumber(preferences.max_budget) : ""}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, '');
                    setPreferences((prev) => ({ ...prev, max_budget: value ? Number(value) : undefined }));
                  }}
                />
              </div>
            </div>

            {budgetError && (
              <div className="mt-3 flex items-center gap-2 text-destructive text-sm">
                <AlertTriangle className="h-4 w-4" />
                {budgetError}
              </div>
            )}

            {(preferences.min_budget || preferences.max_budget) && !budgetError && (
              <p className="text-sm text-muted-foreground mt-3">
                Ќе прикажуваме тендери со вредност: {preferences.min_budget ? formatNumber(preferences.min_budget) + ' МКД' : '0 МКД'}
                {' - '}
                {preferences.max_budget ? formatNumber(preferences.max_budget) + ' МКД' : 'без лимит'}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Exclude Keywords */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Исклучени клучни зборови
              <span className="text-xs font-normal text-destructive/70 bg-destructive/10 px-2 py-1 rounded">
                {preferences.exclude_keywords.length} исклучени
              </span>
            </CardTitle>
            <CardDescription>
              Тендери што содржат овие зборови во насловот нема да се прикажуваат во вашите препораки
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3">
              <Input
                placeholder="Внесете збор за исклучување (пр. санација, ремонт)"
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && addItem("exclude_keywords", keywordInput, setKeywordInput)}
              />
              <Button variant="destructive" onClick={() => addItem("exclude_keywords", keywordInput, setKeywordInput)}>
                Исклучи
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.exclude_keywords.length === 0 ? (
                <p className="text-sm text-muted-foreground flex items-center gap-2">
                  <HelpCircle className="h-4 w-4" />
                  Нема исклучени зборови. Додадете зборови за да ги филтрирате нерелевантните тендери.
                </p>
              ) : (
                preferences.exclude_keywords.map((keyword) => (
                  <Badge key={keyword} variant="destructive" className="gap-1">
                    {keyword}
                    <X className="h-3 w-3 cursor-pointer" onClick={() => removeItem("exclude_keywords", keyword)} />
                  </Badge>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Competitor Companies - With autocomplete */}
        <Card className="relative z-[70]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Конкурентски компании
              <span className="text-xs font-normal text-orange-400 bg-orange-500/10 px-2 py-1 rounded">
                {preferences.competitor_companies.length} следени
              </span>
            </CardTitle>
            <CardDescription>
              Следете ги активностите на конкурентските компании - ќе добиете известувања кога тие добиваат тендери
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground z-10" />
                <Input
                  placeholder="Пребарај компании (пр. Неоком, Сеавус)"
                  value={competitorInput}
                  onChange={(e) => {
                    setCompetitorInput(e.target.value);
                    fetchCompetitorSuggestions(e.target.value);
                    setShowCompetitorSuggestions(true);
                  }}
                  onFocus={() => setShowCompetitorSuggestions(true)}
                  onBlur={() => setTimeout(() => setShowCompetitorSuggestions(false), 200)}
                  onKeyPress={(e) => e.key === "Enter" && addItem("competitor_companies", competitorInput, setCompetitorInput)}
                  className="pl-10"
                />
                {/* Autocomplete dropdown */}
                {showCompetitorSuggestions && competitorSuggestions.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-background border rounded-md shadow-xl z-[100] max-h-48 overflow-auto">
                    {competitorSuggestions.map((company, idx) => (
                      <div
                        key={idx}
                        className="px-3 py-2 hover:bg-accent cursor-pointer text-sm"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          addItem("competitor_companies", company, setCompetitorInput);
                          setShowCompetitorSuggestions(false);
                        }}
                      >
                        {company}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <Button onClick={() => addItem("competitor_companies", competitorInput, setCompetitorInput)}>Додади</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.competitor_companies.length === 0 ? (
                <p className="text-sm text-muted-foreground flex items-center gap-2">
                  <HelpCircle className="h-4 w-4" />
                  Почнете да пишувате за да пребарате добавувачи од е-Пазар базата
                </p>
              ) : (
                preferences.competitor_companies.map((competitor) => (
                  <Badge key={competitor} className="gap-1 bg-orange-500/10 text-orange-400 border-orange-500/20">
                    {competitor}
                    <X className="h-3 w-3 cursor-pointer hover:text-destructive" onClick={() => removeItem("competitor_companies", competitor)} />
                  </Badge>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card>
          <CardHeader>
            <CardTitle>Нотификации</CardTitle>
            <CardDescription>Конфигурирајте како сакате да примате известувања за нови тендери и активности</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Фреквенција на email известувања</label>
                <Select value={preferences.notification_frequency} onValueChange={(value) => setPreferences((prev) => ({ ...prev, notification_frequency: value }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="instant">Моментално (веднаш по објава)</SelectItem>
                    <SelectItem value="daily">Дневен извештај (секое утро)</SelectItem>
                    <SelectItem value="weekly">Неделен извештај (секој понеделник)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-accent/50">
                <input
                  type="checkbox"
                  id="email-enabled"
                  checked={preferences.email_enabled}
                  onChange={(e) => setPreferences((prev) => ({ ...prev, email_enabled: e.target.checked }))}
                  className="w-5 h-5 cursor-pointer rounded border-primary"
                />
                <div>
                  <label htmlFor="email-enabled" className="text-sm font-medium cursor-pointer block">
                    Овозможи email нотификации
                  </label>
                  <p className="text-xs text-muted-foreground">
                    Примајте известувања за нови тендери и конкурентски активности на вашиот email
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Save/Reset Buttons */}
        <div className="flex gap-3 justify-end sticky bottom-4 bg-background/80 backdrop-blur-sm p-4 rounded-lg border z-[60]">
          <Button variant="outline" onClick={handleReset}>Ресетирај се</Button>
          <Button
            onClick={handleSave}
            disabled={saving || !!budgetError}
            className="min-w-32"
          >
            {saving ? "Се зачувува..." : "Зачувај преференци"}
          </Button>
        </div>
      </div>
    </div>
  );
}
