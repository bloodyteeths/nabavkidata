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

  // Division 33 - Medical equipment, pharmaceuticals, personal care (EXPANDED)
  { code: "33000000", label: "Медицинска опрема и фармацевтски производи", labelEn: "Medical equipment, pharmaceuticals" },
  { code: "33100000", label: "Медицински апарати", labelEn: "Medical equipment" },
  { code: "33110000", label: "Опрема за сликање (рендген, МРИ, ЦТ)", labelEn: "Imaging equipment for medical use" },
  { code: "33111000", label: "Рендген апарати", labelEn: "X-ray devices" },
  { code: "33111600", label: "Радиографски апарати", labelEn: "Radiography devices" },
  { code: "33112000", label: "Ехо и ултразвучна опрема", labelEn: "Echo, ultrasound and doppler imaging equipment" },
  { code: "33112200", label: "Ултразвучни апарати", labelEn: "Ultrasound unit" },
  { code: "33113000", label: "МРИ опрема (магнетна резонанца)", labelEn: "Magnetic resonance imaging equipment" },
  { code: "33114000", label: "Спектроскопија и спектрометрија", labelEn: "Spectroscopy equipment" },
  { code: "33115000", label: "Томографски апарати (ЦТ скенери)", labelEn: "Tomography devices" },
  { code: "33120000", label: "Системи за снимање и истражување", labelEn: "Recording systems and exploration devices" },
  { code: "33121000", label: "Амбулантни системи за снимање", labelEn: "Ambulatory monitoring system" },
  { code: "33122000", label: "Офталмолошка опрема", labelEn: "Ophthalmology equipment" },
  { code: "33123000", label: "Кардиоваскуларни апарати", labelEn: "Cardiovascular devices" },
  { code: "33123100", label: "Тензиометри", labelEn: "Tensiometer" },
  { code: "33123200", label: "ЕКГ апарати (електрокардиографи)", labelEn: "Electrocardiography devices" },
  { code: "33123210", label: "Монитори за срце", labelEn: "Cardiac-monitoring devices" },
  { code: "33124000", label: "Дијагностичка и радиодијагностичка опрема", labelEn: "Diagnostic and radiodiagnostic equipment" },
  { code: "33124100", label: "Дијагностички апарати", labelEn: "Diagnostic devices" },
  { code: "33124110", label: "Дијагностички системи", labelEn: "Diagnostic systems" },
  { code: "33124130", label: "Дијагностички прибор", labelEn: "Diagnostic supplies" },
  { code: "33125000", label: "Уролошка опрема", labelEn: "Urological-examination devices" },
  { code: "33126000", label: "Стоматолошка опрема", labelEn: "Stomatological devices" },
  { code: "33127000", label: "Имунолошки анализатори", labelEn: "Immunoanalysis devices" },
  { code: "33128000", label: "Ласерски медицински апарати", labelEn: "Medical laser equipment" },
  { code: "33130000", label: "Забна и стоматолошка опрема", labelEn: "Dental and subspeciality instruments" },
  { code: "33131000", label: "Забни инструменти", labelEn: "Dental hand instruments" },
  { code: "33131100", label: "Хируршки забни инструменти", labelEn: "Dental surgical instruments" },
  { code: "33131500", label: "Инструменти за вадење заби", labelEn: "Dental extraction instruments" },
  { code: "33132000", label: "Забни имплантати", labelEn: "Dental implants" },
  { code: "33133000", label: "Материјали за забни отпечатоци", labelEn: "Dental impression supplies" },
  { code: "33134000", label: "Ендодонтски прибор", labelEn: "Endodontics supplies" },
  { code: "33135000", label: "Ортодонтски апарати", labelEn: "Orthodontic appliances" },
  { code: "33136000", label: "Ротирачки и абразивни инструменти", labelEn: "Rotary and abrasive instruments" },
  { code: "33137000", label: "Забна профилакса и помошни средства", labelEn: "Dental prophylaxis aids" },
  { code: "33138000", label: "Протетички и ортопедски производи", labelEn: "Prosthetic and orthopaedic supplies" },
  { code: "33138100", label: "Протези", labelEn: "Prostheses" },
  { code: "33140000", label: "Медицински потрошен материјал", labelEn: "Medical consumables" },
  { code: "33141000", label: "Нехемиски медицински потрошни материјали", labelEn: "Disposable non-chemical medical consumables" },
  { code: "33141100", label: "Завои и лигатури", labelEn: "Dressings, clips, sutures, ligatures" },
  { code: "33141110", label: "Завои", labelEn: "Dressings" },
  { code: "33141111", label: "Адхезивни завои", labelEn: "Adhesive dressings" },
  { code: "33141112", label: "Фластери", labelEn: "Plasters" },
  { code: "33141113", label: "Бинт", labelEn: "Bandages" },
  { code: "33141114", label: "Медицинска газа", labelEn: "Medical gauze" },
  { code: "33141115", label: "Медицинска волна", labelEn: "Medical wadding" },
  { code: "33141116", label: "Комплети за завивање", labelEn: "Dressing packs" },
  { code: "33141117", label: "Волна и памук", labelEn: "Cotton wool" },
  { code: "33141118", label: "Влажни марамици", labelEn: "Wipes" },
  { code: "33141120", label: "Клипси, шевови, лигатури", labelEn: "Clips, sutures, ligatures" },
  { code: "33141121", label: "Хируршки шевови", labelEn: "Surgical sutures" },
  { code: "33141122", label: "Хируршки клипси", labelEn: "Surgical clips" },
  { code: "33141123", label: "Контејнери за остри предмети", labelEn: "Sharps containers" },
  { code: "33141200", label: "Катетри", labelEn: "Catheters" },
  { code: "33141210", label: "Катетри со балон", labelEn: "Balloon catheters" },
  { code: "33141220", label: "Канили", labelEn: "Cannulae" },
  { code: "33141230", label: "Дилататори", labelEn: "Dilators" },
  { code: "33141300", label: "Апарати за венепункција и земање крв", labelEn: "Venepuncture, blood-sampling devices" },
  { code: "33141310", label: "Шприцови", labelEn: "Syringes" },
  { code: "33141320", label: "Игли за медицинска употреба", labelEn: "Medical needles" },
  { code: "33141321", label: "Игли за анестезија", labelEn: "Anaesthesia needles" },
  { code: "33141322", label: "Артериски игли", labelEn: "Arterial needles" },
  { code: "33141323", label: "Игли за биопсија", labelEn: "Biopsy needles" },
  { code: "33141324", label: "Игли за дијализа", labelEn: "Dialysis needles" },
  { code: "33141325", label: "Игли за вадење крв", labelEn: "Phlebotomy needles" },
  { code: "33141326", label: "Игли за шиење", labelEn: "Suture needles" },
  { code: "33141400", label: "Жица за сечење и хируршки ножеви", labelEn: "Wire cutters and scalpels" },
  { code: "33141410", label: "Скалпели", labelEn: "Scalpels" },
  { code: "33141411", label: "Сечива за скалпели", labelEn: "Scalpel blades" },
  { code: "33141500", label: "Хематолошки потрошни материјали", labelEn: "Haematological consumables" },
  { code: "33141510", label: "Крвни производи", labelEn: "Blood products" },
  { code: "33141520", label: "Деривати на плазма", labelEn: "Plasma derivatives" },
  { code: "33141530", label: "Коагуланти за крв", labelEn: "Blood coagulants" },
  { code: "33141540", label: "Албумин", labelEn: "Albumin" },
  { code: "33141550", label: "Хепарин", labelEn: "Heparin" },
  { code: "33141560", label: "Крвни органи", labelEn: "Blood organs" },
  { code: "33141570", label: "Човечка крв", labelEn: "Human blood" },
  { code: "33141580", label: "Животинска крв", labelEn: "Animal blood" },
  { code: "33141600", label: "Контејнери за телесни течности", labelEn: "Collectors, bags, drainage equipment" },
  { code: "33141610", label: "Кеси за собирање", labelEn: "Collection bags" },
  { code: "33141613", label: "Кеси за крв", labelEn: "Blood bags" },
  { code: "33141614", label: "Кеси за плазма", labelEn: "Plasma bags" },
  { code: "33141615", label: "Кеси за урина", labelEn: "Urine bags" },
  { code: "33141620", label: "Медицински комплети", labelEn: "Medical kits" },
  { code: "33141621", label: "Комплети за прва помош", labelEn: "First-aid kits" },
  { code: "33141622", label: "Комплети за превенција од СИДА", labelEn: "AIDS prevention kits" },
  { code: "33141623", label: "Комплети за прва помош во автомобил", labelEn: "Motor vehicle first aid kits" },
  { code: "33141624", label: "Комплети за земање крв", labelEn: "Blood sampling kits" },
  { code: "33141625", label: "Дијагностички комплети", labelEn: "Diagnostic kits" },
  { code: "33141626", label: "Комплети за дозирање", labelEn: "Dosimetry kits" },
  { code: "33141700", label: "Ортопедски помагала", labelEn: "Orthopaedic supplies" },
  { code: "33141710", label: "Патерици", labelEn: "Crutches" },
  { code: "33141720", label: "Помагала за одење", labelEn: "Walking aids" },
  { code: "33141730", label: "Јаки за вратот", labelEn: "Cervical collars" },
  { code: "33141740", label: "Ортопедски обувки", labelEn: "Orthopaedic footwear" },
  { code: "33141750", label: "Вештачки зглобови", labelEn: "Artificial joints" },
  { code: "33141760", label: "Шини", labelEn: "Splints" },
  { code: "33141770", label: "Фрактурни помагала", labelEn: "Fracture appliances" },
  { code: "33141800", label: "Дентални потрошни материјали", labelEn: "Dental consumables" },
  { code: "33141810", label: "Материјали за полнење на заби", labelEn: "Dental filling materials" },
  { code: "33141820", label: "Заби (протези)", labelEn: "Teeth" },
  { code: "33141821", label: "Порцелански заби", labelEn: "Porcelain teeth" },
  { code: "33141822", label: "Акрилни заби", labelEn: "Acrylic teeth" },
  { code: "33141830", label: "Цемент за заби", labelEn: "Cement bases" },
  { code: "33141840", label: "Стоматолошки хемостатици", labelEn: "Dental haemostatics" },
  { code: "33141850", label: "Производи за хигиена на уста", labelEn: "Dental hygiene products" },
  { code: "33141900", label: "Ножеви за микро хирургија", labelEn: "Cutting knives for microsurgery" },
  { code: "33150000", label: "Радиотераписка и радиолошка опрема", labelEn: "Radiotherapy, mechanotherapy equipment" },
  { code: "33151000", label: "Радиотераписки апарати", labelEn: "Radiotherapy devices" },
  { code: "33151100", label: "Гама терапија апарати", labelEn: "Gamma-therapy devices" },
  { code: "33151200", label: "Линеарни акцелератори", labelEn: "Linear accelerators" },
  { code: "33151300", label: "Спектрографи", labelEn: "Spectrographs" },
  { code: "33151400", label: "Брахитерапија опрема", labelEn: "Brachytherapy equipment" },
  { code: "33152000", label: "Инкубатори", labelEn: "Incubators" },
  { code: "33153000", label: "Литотриптори (дробење камења)", labelEn: "Lithotripter" },
  { code: "33154000", label: "Механотерапија апарати", labelEn: "Mechanotherapy devices" },
  { code: "33155000", label: "Апарати за физиотерапија", labelEn: "Physiotherapy apparatus" },
  { code: "33156000", label: "Психолошки тестирачки апарати", labelEn: "Psychological testing apparatus" },
  { code: "33157000", label: "Апарати за кислородна терапија", labelEn: "Oxygen therapy and respiration devices" },
  { code: "33157100", label: "Маски за медицински гасови", labelEn: "Medical gas masks" },
  { code: "33157110", label: "Кислородни маски", labelEn: "Oxygen masks" },
  { code: "33157200", label: "Кислородни комплети", labelEn: "Oxygen kits" },
  { code: "33157300", label: "Кислородни шатори", labelEn: "Oxygen tents" },
  { code: "33157400", label: "Медицински респиратори", labelEn: "Medical respirators" },
  { code: "33157500", label: "Хипербарични комори", labelEn: "Hyperbaric chambers" },
  { code: "33157700", label: "Инхалатори", labelEn: "Inhalators" },
  { code: "33157800", label: "Апарати за давање кислород", labelEn: "Oxygen administration unit" },
  { code: "33157810", label: "Кислородна терапија единица", labelEn: "Oxygen therapy unit" },
  { code: "33158000", label: "Електрична и механотерапија", labelEn: "Electrical, electromagnetic and mechanical treatment" },
  { code: "33158100", label: "Електромагнетни апарати", labelEn: "Electromagnetic unit" },
  { code: "33158200", label: "Апарати за електротерапија", labelEn: "Electrotherapy apparatus" },
  { code: "33158210", label: "Стимулатори", labelEn: "Stimulators" },
  { code: "33158300", label: "УВ медицински апарати", labelEn: "UV medical devices" },
  { code: "33158400", label: "Механотерапија единица", labelEn: "Mechanotherapy unit" },
  { code: "33158500", label: "ИР (инфрацрвени) медицински апарати", labelEn: "Infrared medical devices" },
  { code: "33160000", label: "Оперативни техники", labelEn: "Operating techniques" },
  { code: "33161000", label: "Електрохируршки апарати", labelEn: "Electrosurgical unit" },
  { code: "33162000", label: "Апарати за операциони сали", labelEn: "Operating theatre devices" },
  { code: "33162100", label: "Опрема за операциони сали", labelEn: "Operating theatre equipment" },
  { code: "33162200", label: "Хируршки инструменти", labelEn: "Operating theatre instruments" },
  { code: "33163000", label: "Шатори за медицинска употреба", labelEn: "Tents for medical use" },
  { code: "33164000", label: "Лапароскопски апарати", labelEn: "Laparoscopy devices" },
  { code: "33164100", label: "Колпоскоп", labelEn: "Colposcope" },
  { code: "33165000", label: "Криохируршки и криотераписки апарати", labelEn: "Cryosurgery and cryotherapy devices" },
  { code: "33166000", label: "Дерматолошки апарати", labelEn: "Dermatological devices" },
  { code: "33167000", label: "Хируршки светла", labelEn: "Surgical lights" },
  { code: "33168000", label: "Ендоскопски и ендохируршки апарати", labelEn: "Endoscopy, endosurgery devices" },
  { code: "33168100", label: "Ендоскопи", labelEn: "Endoscopes" },
  { code: "33169000", label: "Хируршки инструменти", labelEn: "Surgical instruments" },
  { code: "33169100", label: "Хируршки ласери", labelEn: "Surgical laser" },
  { code: "33169200", label: "Хируршки кошници", labelEn: "Surgical baskets" },
  { code: "33169300", label: "Хируршки тацни", labelEn: "Surgical trays" },
  { code: "33169400", label: "Хируршки контејнери", labelEn: "Surgical containers" },
  { code: "33169500", label: "Хируршки системи за следење", labelEn: "Surgical tracking systems" },
  { code: "33170000", label: "Анестезија и реанимација", labelEn: "Anaesthesia and resuscitation" },
  { code: "33171000", label: "Анестезиолошки инструменти", labelEn: "Instruments for anaesthesia and resuscitation" },
  { code: "33171100", label: "Анестезиолошки апарати", labelEn: "Anaesthesia instruments" },
  { code: "33171110", label: "Анестезиолошки маски", labelEn: "Anaesthesia masks" },
  { code: "33171200", label: "Реанимациски апарати", labelEn: "Resuscitation instruments" },
  { code: "33171210", label: "Реанимациски маски", labelEn: "Resuscitation masks" },
  { code: "33171300", label: "Епидурални комплети", labelEn: "Epidural kits" },
  { code: "33172000", label: "Апарати за анестезија и реанимација", labelEn: "Anaesthesia and resuscitation devices" },
  { code: "33172100", label: "Апарати за анестезија", labelEn: "Anaesthesia devices" },
  { code: "33172200", label: "Апарати за реанимација", labelEn: "Resuscitation devices" },
  { code: "33180000", label: "Функционална поддршка", labelEn: "Functional support" },
  { code: "33181000", label: "Апарати за поддршка на бубрези", labelEn: "Renal support devices" },
  { code: "33181100", label: "Апарати за хемодијализа", labelEn: "Haemodialysis devices" },
  { code: "33181200", label: "Дијализни филтри", labelEn: "Dialysis filters" },
  { code: "33181300", label: "Индивидуални монитори за хемодијализа", labelEn: "Individual monitors for haemodialysis" },
  { code: "33181400", label: "Мулти-станични апарати за хемодијализа", labelEn: "Multi-station for haemodialysis" },
  { code: "33181500", label: "Потрошен материјал за бубрежно лекување", labelEn: "Renal treatment consumables" },
  { code: "33181510", label: "Бубрежни течности", labelEn: "Renal fluid" },
  { code: "33181520", label: "Потрошен материјал за дијализа", labelEn: "Renal dialysis consumables" },
  { code: "33182000", label: "Апарати за срцева поддршка", labelEn: "Cardiac support devices" },
  { code: "33182100", label: "Дефибрилатори", labelEn: "Defibrillator" },
  { code: "33182200", label: "Апарати за срцева стимулација", labelEn: "Cardiac stimulation devices" },
  { code: "33182210", label: "Пејсмејкери", labelEn: "Pacemaker" },
  { code: "33182220", label: "Срцеви залистоци", labelEn: "Cardiac valves" },
  { code: "33182230", label: "Комори (срцеви)", labelEn: "Ventricles" },
  { code: "33182240", label: "Делови и додатоци за пејсмејкери", labelEn: "Pacemaker parts and accessories" },
  { code: "33182241", label: "Батерии за пејсмејкери", labelEn: "Pacemaker batteries" },
  { code: "33182300", label: "Апарати за срцева хирургија", labelEn: "Cardiac surgery devices" },
  { code: "33182400", label: "Кардиолошки рендген системи", labelEn: "Cardiac X-ray system" },
  { code: "33183000", label: "Ортопедски поддршка апарати", labelEn: "Orthopaedic support devices" },
  { code: "33183100", label: "Ортопедски имплантати", labelEn: "Orthopaedic implants" },
  { code: "33183200", label: "Ортопедски протези", labelEn: "Orthopaedic prostheses" },
  { code: "33183300", label: "Остеосинтетски апарати", labelEn: "Osteosynthesis devices" },
  { code: "33184000", label: "Вештачки делови на телото", labelEn: "Artificial parts of the body" },
  { code: "33184100", label: "Хируршки имплантати", labelEn: "Surgical implants" },
  { code: "33184200", label: "Васкуларни протези", labelEn: "Vascular prostheses" },
  { code: "33184300", label: "Срцеви протези", labelEn: "Cardiac prostheses" },
  { code: "33184400", label: "Градни протези", labelEn: "Breast prostheses" },
  { code: "33184410", label: "Внатрешни градни протези", labelEn: "Internal breast prostheses" },
  { code: "33184420", label: "Надворешни градни протези", labelEn: "External breast prostheses" },
  { code: "33184500", label: "Коронарни стентови", labelEn: "Coronary stents" },
  { code: "33184600", label: "Вештачки очни јаболка", labelEn: "Artificial eyes" },
  { code: "33185000", label: "Слушни апарати", labelEn: "Hearing aids" },
  { code: "33185100", label: "Делови и додатоци за слушни апарати", labelEn: "Parts and accessories of hearing aids" },
  { code: "33185200", label: "Кохлеарни имплантати", labelEn: "Cochlear implants" },
  { code: "33185300", label: "ОРЛ имплантати", labelEn: "Implants for otorhinolaryngology" },
  { code: "33185400", label: "Вештачки грклан", labelEn: "Artificial larynx" },
  { code: "33186000", label: "Апарати за срцево-белодробен бајпас", labelEn: "Heart-lung machines" },
  { code: "33186100", label: "Оксигенатори", labelEn: "Oxygenator" },
  { code: "33186200", label: "Апарати за загревање на крв и течности", labelEn: "Blood and fluid warming devices" },
  { code: "33190000", label: "Разни медицински апарати и производи", labelEn: "Miscellaneous medical devices and products" },
  { code: "33191000", label: "Апарати за стерилизација и дезинфекција", labelEn: "Sterilisation, disinfection devices" },
  { code: "33191100", label: "Стерилизатори", labelEn: "Sterilisers" },
  { code: "33191110", label: "Автоклави", labelEn: "Autoclaves" },
  { code: "33192000", label: "Медицински мебел", labelEn: "Medical furniture" },
  { code: "33192100", label: "Болнички кревети", labelEn: "Medical beds" },
  { code: "33192110", label: "Ортопедски кревети", labelEn: "Orthopaedic beds" },
  { code: "33192120", label: "Болнички кревети", labelEn: "Hospital beds" },
  { code: "33192130", label: "Кревети со мотор", labelEn: "Motorised beds" },
  { code: "33192140", label: "Психијатриски лежишта", labelEn: "Psychiatric couches" },
  { code: "33192150", label: "Терапевтски кревети", labelEn: "Therapy beds" },
  { code: "33192160", label: "Носилки", labelEn: "Stretchers" },
  { code: "33192200", label: "Медицински маси", labelEn: "Medical tables" },
  { code: "33192210", label: "Маси за прегледи", labelEn: "Examination tables" },
  { code: "33192230", label: "Операциони маси", labelEn: "Operating tables" },
  { code: "33192300", label: "Медицински мебел освен кревети и маси", labelEn: "Medical furniture except beds and tables" },
  { code: "33192310", label: "Апарати за тракција на кревети", labelEn: "Traction devices for medical beds" },
  { code: "33192320", label: "Држачи за крвни кеси", labelEn: "Blood bag holders" },
  { code: "33192330", label: "Рамки за трансфузија", labelEn: "Transfusion frames" },
  { code: "33192340", label: "Мебел за операциони сали", labelEn: "Operating theatre furniture" },
  { code: "33192350", label: "Кабинети за медицински култури", labelEn: "Medical culture cabinets" },
  { code: "33192400", label: "Стоматолошки работни станици", labelEn: "Dental work stations" },
  { code: "33192410", label: "Стоматолошки столици", labelEn: "Dental chairs" },
  { code: "33192500", label: "Епрувети", labelEn: "Test-tubes" },
  { code: "33192600", label: "Опрема за подигање во здравствениот сектор", labelEn: "Lifting equipment for health sector" },
  { code: "33193000", label: "Инвалидски колички", labelEn: "Wheelchairs and invalid carriages" },
  { code: "33193100", label: "Инвалидски колички", labelEn: "Invalid carriages and wheelchairs" },
  { code: "33193110", label: "Инвалидски колички со мотор", labelEn: "Motorised invalid carriages and wheelchairs" },
  { code: "33193120", label: "Инвалидски колички", labelEn: "Wheelchairs" },
  { code: "33193121", label: "Инвалидски колички со мотор", labelEn: "Motorised wheelchairs" },
  { code: "33193200", label: "Делови и додатоци за инвалидски колички", labelEn: "Parts and accessories for invalid carriages" },
  { code: "33193210", label: "Делови за инвалидски колички со мотор", labelEn: "Parts for motorised invalid carriages" },
  { code: "33193211", label: "Мотори за инвалидски колички", labelEn: "Motors for motorised invalid carriages" },
  { code: "33193212", label: "Управувачи за инвалидски колички", labelEn: "Steering for motorised invalid carriages" },
  { code: "33193213", label: "Контролни уреди за инвалидски колички", labelEn: "Control devices for motorised wheelchairs" },
  { code: "33193214", label: "Шасии за инвалидски колички", labelEn: "Chassis for motorised invalid carriages" },
  { code: "33193220", label: "Делови за инвалидски колички", labelEn: "Parts for wheelchairs" },
  { code: "33193221", label: "Перници за инвалидски колички", labelEn: "Seat cushions for wheelchairs" },
  { code: "33193222", label: "Рамки за инвалидски колички", labelEn: "Frames for wheelchairs" },
  { code: "33193223", label: "Седишта за инвалидски колички", labelEn: "Seats for wheelchairs" },
  { code: "33193224", label: "Тркала за инвалидски колички", labelEn: "Wheels for wheelchairs" },
  { code: "33193225", label: "Гуми за инвалидски колички", labelEn: "Tyres for wheelchairs" },
  { code: "33194000", label: "Апарати и инструменти за трансфузија", labelEn: "Devices and instruments for transfusion" },
  { code: "33194100", label: "Апарати за инфузија", labelEn: "Devices for infusion" },
  { code: "33194110", label: "Пумпи за инфузија", labelEn: "Infusion pumps" },
  { code: "33194120", label: "Прибор за инфузија", labelEn: "Infusion supplies" },
  { code: "33194200", label: "Апарати за трансфузија", labelEn: "Devices for transfusion" },
  { code: "33194210", label: "Апарати за трансфузија на крв", labelEn: "Blood-transfusion devices" },
  { code: "33194220", label: "Прибор за трансфузија на крв", labelEn: "Blood-transfusion supplies" },
  { code: "33195000", label: "Систем за следење на пациенти", labelEn: "Patient-monitoring system" },
  { code: "33195100", label: "Монитори", labelEn: "Monitors" },
  { code: "33195110", label: "Монитори за следење на респирација", labelEn: "Respiration monitors" },
  { code: "33195200", label: "Централна станица за следење", labelEn: "Central monitoring station" },
  { code: "33196000", label: "Медицински помагала", labelEn: "Medical aids" },
  { code: "33196100", label: "Опрема за стари лица", labelEn: "Devices for elderly" },
  { code: "33196200", label: "Опрема за хендикепирани", labelEn: "Devices for disabled" },
  { code: "33197000", label: "Медицинска компјутерска опрема", labelEn: "Medical computer equipment" },
  { code: "33198000", label: "Болнички артикли од хартија", labelEn: "Hospital paper articles" },
  { code: "33198100", label: "Хартиени облоги", labelEn: "Paper envelopes" },
  { code: "33198200", label: "Хартиени стерилизациски пакети", labelEn: "Paper sterilisation bags or wraps" },
  { code: "33199000", label: "Медицинска облека", labelEn: "Medical clothing" },

  // Division 33 - Pharmaceutical products (33600000-33699999)
  { code: "33600000", label: "Фармацевтски производи", labelEn: "Pharmaceutical products" },
  { code: "33610000", label: "Лекови за дигестивен тракт и метаболизам", labelEn: "Medicinal products for alimentary tract and metabolism" },
  { code: "33611000", label: "Лекови за нарушувања поврзани со киселина", labelEn: "Medicinal products for acid related disorders" },
  { code: "33612000", label: "Лекови за функционални гастроинтестинални нарушувања", labelEn: "Medicinal products for functional gastrointestinal disorders" },
  { code: "33613000", label: "Лаксативи", labelEn: "Laxatives" },
  { code: "33614000", label: "Антидијароици и интестинални антиинфламаторни агенси", labelEn: "Antidiarrheals, intestinal antiinflammatory agents" },
  { code: "33615000", label: "Лекови за дијабетес", labelEn: "Medicinal products for diabetes" },
  { code: "33615100", label: "Инсулини", labelEn: "Insulins" },
  { code: "33616000", label: "Витамини", labelEn: "Vitamins" },
  { code: "33617000", label: "Минерални додатоци", labelEn: "Mineral supplements" },
  { code: "33620000", label: "Лекови за крв и хематопоетски органи", labelEn: "Medicinal products for blood and blood-forming organs" },
  { code: "33621000", label: "Лекови за крв и хематопоетски органи", labelEn: "Medicinal products for blood and blood-forming organs" },
  { code: "33621100", label: "Антитромботични агенси", labelEn: "Antithrombotic agents" },
  { code: "33621200", label: "Антихеморагични агенси", labelEn: "Antihemorrhagics" },
  { code: "33621300", label: "Антианемични препарати", labelEn: "Antianemic preparations" },
  { code: "33621400", label: "Крвни супститути и перфузиони раствори", labelEn: "Blood substitutes and perfusion solutions" },
  { code: "33622000", label: "Лекови за кардиоваскуларен систем", labelEn: "Medicinal products for the cardiovascular system" },
  { code: "33622100", label: "Лекови за срцева терапија", labelEn: "Medicinal products for cardiac therapy" },
  { code: "33622200", label: "Антихипертензивни лекови", labelEn: "Antihypertensives" },
  { code: "33622300", label: "Диуретици", labelEn: "Diuretics" },
  { code: "33622400", label: "Вазопротективни лекови", labelEn: "Vasoprotectives" },
  { code: "33622500", label: "Антихемороиди", labelEn: "Antihemorrhoidals" },
  { code: "33622600", label: "Бета-блокатори", labelEn: "Beta blocking agents" },
  { code: "33622700", label: "Калциум канал блокатори", labelEn: "Calcium channel blockers" },
  { code: "33622800", label: "Лекови за ренин-ангиотензин систем", labelEn: "Medicinal products for renin-angiotensin system" },
  { code: "33630000", label: "Лекови за дерматолошки состојби", labelEn: "Medicinal products for dermatological conditions" },
  { code: "33631000", label: "Антимикотици за дерматолошка употреба", labelEn: "Antifungals for dermatological use" },
  { code: "33632000", label: "Антибиотици и хемотерапевтици за дерматолошка употреба", labelEn: "Antibiotics and chemotherapeutics for dermatological use" },
  { code: "33640000", label: "Лекови за генито-уринарен систем и хормони", labelEn: "Medicinal products for the genito urinary system and sex hormones" },
  { code: "33641000", label: "Лекови за урологија", labelEn: "Medicinal products for urology" },
  { code: "33641100", label: "Антисептици и антиинфективи за урологија", labelEn: "Antiseptics and antiinfectives for urological use" },
  { code: "33641200", label: "Други лекови за урологија", labelEn: "Other urological medicinal products" },
  { code: "33641300", label: "Полови хормони и модулатори", labelEn: "Sex hormones and modulators" },
  { code: "33641400", label: "Контрацептивни средства", labelEn: "Contraceptives" },
  { code: "33641410", label: "Хормонски контрацептиви", labelEn: "Hormonal contraceptives" },
  { code: "33641420", label: "Хемиски контрацептиви", labelEn: "Chemical contraceptives" },
  { code: "33641430", label: "Интраутерини контрацептиви", labelEn: "Intrauterine contraceptives" },
  { code: "33641440", label: "Механички контрацептиви", labelEn: "Mechanical contraceptives" },
  { code: "33650000", label: "Општи антиинфективи за системска употреба, вакцини", labelEn: "General antiinfectives for systemic use, vaccines" },
  { code: "33651000", label: "Општи антиинфективи за системска употреба", labelEn: "General antiinfectives for systemic use" },
  { code: "33651100", label: "Антибактериски лекови за системска употреба", labelEn: "Antibacterials for systemic use" },
  { code: "33651200", label: "Антимикотици за системска употреба", labelEn: "Antimycotics for systemic use" },
  { code: "33651300", label: "Антимикобактериски лекови", labelEn: "Antimycobacterials" },
  { code: "33651400", label: "Антивирални лекови за системска употреба", labelEn: "Antivirals for systemic use" },
  { code: "33651500", label: "Имуносеруми и имуноглобулини", labelEn: "Immune sera and immunoglobulins" },
  { code: "33651510", label: "Имуносеруми", labelEn: "Immune sera" },
  { code: "33651520", label: "Имуноглобулини", labelEn: "Immunoglobulins" },
  { code: "33651600", label: "Вакцини", labelEn: "Vaccines" },
  { code: "33651610", label: "Дифтерија-пертусис-тетанус вакцини", labelEn: "Diphtheria-pertussis-tetanus vaccines" },
  { code: "33651620", label: "Дифтерија-тетанус вакцини", labelEn: "Diphtheria-tetanus vaccines" },
  { code: "33651630", label: "BCG вакцини (против туберкулоза)", labelEn: "BCG vaccines (dried)" },
  { code: "33651640", label: "Морбили-заушки-рубеола вакцини (МЗР)", labelEn: "Measles, mumps, rubella (MMR) vaccines" },
  { code: "33651650", label: "Вакцини за тифус", labelEn: "Typhoid vaccines" },
  { code: "33651660", label: "Вакцини за грип", labelEn: "Influenza vaccines" },
  { code: "33651670", label: "Вакцини за полио", labelEn: "Poliomyelitis vaccines" },
  { code: "33651680", label: "Вакцини за хепатитис Б", labelEn: "Hepatitis B vaccines" },
  { code: "33651690", label: "Вакцини за ветеринарна употреба", labelEn: "Vaccines for veterinary medicine" },
  { code: "33660000", label: "Лекови за нервен систем", labelEn: "Medicinal products for the nervous system" },
  { code: "33661000", label: "Аналгетици (лекови против болка)", labelEn: "Medicinal products for the nervous system" },
  { code: "33661100", label: "Анестетици", labelEn: "Anaesthetics" },
  { code: "33661200", label: "Аналгетици", labelEn: "Analgesics" },
  { code: "33661300", label: "Антиепилептици", labelEn: "Antiepileptics" },
  { code: "33661400", label: "Антипаркинсонски лекови", labelEn: "Antiparkinson medicinal products" },
  { code: "33661500", label: "Психолептици (седативи, антипсихотици)", labelEn: "Psycholeptics" },
  { code: "33661600", label: "Психоаналептици (антидепресиви)", labelEn: "Psychoanaleptics" },
  { code: "33661700", label: "Други лекови за нервен систем", labelEn: "Other nervous system medicinal products" },
  { code: "33670000", label: "Лекови за респираторен систем", labelEn: "Medicinal products for the respiratory system" },
  { code: "33673000", label: "Лекови за опструктивни болести на дишните патишта", labelEn: "Medicinal products for obstructive airway diseases" },
  { code: "33674000", label: "Антихистаминици за системска употреба", labelEn: "Antihistamines for systemic use" },
  { code: "33675000", label: "Лекови за кашлица и настинка", labelEn: "Medicinal products for cough and cold" },
  { code: "33680000", label: "Фармацевтски артикли", labelEn: "Pharmaceutical articles" },
  { code: "33681000", label: "Цуцли (дуди)", labelEn: "Teats, nipple shields and similar articles" },
  { code: "33682000", label: "Гумени плочки", labelEn: "Rubber tiles" },
  { code: "33683000", label: "Гумени тампони", labelEn: "Rubber buffers" },
  { code: "33690000", label: "Разни медикаменти", labelEn: "Various medicinal products" },
  { code: "33691000", label: "Антипаразитски производи, инсектициди и репеленти", labelEn: "Antiparasitic products, insecticides and repellents" },
  { code: "33692000", label: "Лекови за мускулно-скелетен систем", labelEn: "Medicinal products for musculo-skeletal system" },
  { code: "33692100", label: "Антиинфламаторни и антиревматски лекови", labelEn: "Antiinflammatory and antirheumatic products" },
  { code: "33692200", label: "Локални лекови за мускулно-скелетна болка", labelEn: "Topical products for muscular pain" },
  { code: "33692300", label: "Мускулни релаксанси", labelEn: "Muscle relaxants" },
  { code: "33692400", label: "Лекови за третман на коски", labelEn: "Medicinal products for treatment of bones" },
  { code: "33692500", label: "Интравенски раствори", labelEn: "Intravenous solutions" },
  { code: "33692510", label: "Интравенски течности", labelEn: "Intravenous fluids" },
  { code: "33692600", label: "Галенски препарати", labelEn: "Galenical preparations" },
  { code: "33692700", label: "Раствори за глукоза", labelEn: "Glucose solutions" },
  { code: "33692800", label: "Раствори за дијализа", labelEn: "Dialysis solutions" },
  { code: "33693000", label: "Сите други терапевтски производи", labelEn: "All other therapeutic products" },
  { code: "33694000", label: "Дијагностички агенси", labelEn: "Diagnostic agents" },
  { code: "33695000", label: "Сите други не-терапевтски производи", labelEn: "All other non-therapeutic products" },
  { code: "33696000", label: "Реагенси и контрастни средства", labelEn: "Reagents and contrast media" },
  { code: "33696100", label: "Реагенси за крвни групи", labelEn: "Reagents for blood-grouping" },
  { code: "33696200", label: "Реагенси за крвни тестови", labelEn: "Reagents for blood tests" },
  { code: "33696300", label: "Хемиски реагенси", labelEn: "Chemical reagents" },
  { code: "33696400", label: "Изотопски реагенси", labelEn: "Isotopic reagents" },
  { code: "33696500", label: "Лабораториски реагенси", labelEn: "Laboratory reagents" },
  { code: "33696600", label: "Реагенси за електрофореза", labelEn: "Reagents for electrophoresis" },
  { code: "33696700", label: "Уролошки реагенси", labelEn: "Urological reagents" },
  { code: "33696800", label: "Контрастни средства за рендген", labelEn: "Contrast media for X-ray" },
  { code: "33697000", label: "Медицински препарати освен дентални потрошни материјали", labelEn: "Medical preparations except dental consumables" },
  { code: "33697100", label: "Дезинфектанси", labelEn: "Disinfectant preparations" },
  { code: "33697110", label: "Материјали за реконструкција на коски", labelEn: "Bone reconstruction cements" },
  { code: "33698000", label: "Клинички производи", labelEn: "Clinical products" },
  { code: "33698100", label: "Микробиолошки култури", labelEn: "Microbiological cultures" },
  { code: "33698200", label: "Жлезди и нивни екстракти", labelEn: "Glands and their extracts" },
  { code: "33698300", label: "Пептични супстанции", labelEn: "Peptic substances" },

  // Division 33 - Personal care products (33700000-33799999)
  { code: "33700000", label: "Производи за лична хигиена", labelEn: "Personal care products" },
  { code: "33710000", label: "Парфеми, тоалетни производи и кондоми", labelEn: "Perfumes, toiletries and condoms" },
  { code: "33711000", label: "Парфеми и тоалетни производи", labelEn: "Perfumes and toiletries" },
  { code: "33711100", label: "Води за тоалета", labelEn: "Toilet water" },
  { code: "33711110", label: "Дезодоранси", labelEn: "Deodorants" },
  { code: "33711120", label: "Антиперспиранти", labelEn: "Antiperspirants" },
  { code: "33711130", label: "Колонии", labelEn: "Cologne" },
  { code: "33711140", label: "Мириси", labelEn: "Fragrances" },
  { code: "33711150", label: "Розина вода", labelEn: "Rose water" },
  { code: "33711200", label: "Козметички производи", labelEn: "Make-up products" },
  { code: "33711300", label: "Манипулативни производи", labelEn: "Manicure or pedicure products" },
  { code: "33711400", label: "Средства за нега на коса", labelEn: "Hair care items" },
  { code: "33711410", label: "Четки за коса", labelEn: "Hairbrushes" },
  { code: "33711420", label: "Опрема за убавина", labelEn: "Beauty equipment" },
  { code: "33711430", label: "Еднократни бричеви", labelEn: "Disposable razors" },
  { code: "33711440", label: "Гел за бричење", labelEn: "Shaving gel" },
  { code: "33711450", label: "Украси за коса", labelEn: "Tattoo" },
  { code: "33711500", label: "Производи за нега на кожа", labelEn: "Skincare products" },
  { code: "33711510", label: "Производи за заштита од сонце", labelEn: "Sun protection products" },
  { code: "33711520", label: "Соли за бања", labelEn: "Bath gels" },
  { code: "33711530", label: "Капи за бања", labelEn: "Shower caps" },
  { code: "33711540", label: "Пара-фармацевтски кремови и лосиони", labelEn: "Parapharmaceutical creams or lotions" },
  { code: "33711600", label: "Препарати и артикли за коса", labelEn: "Hair preparations and articles" },
  { code: "33711610", label: "Шампони", labelEn: "Shampoos" },
  { code: "33711620", label: "Чешли", labelEn: "Combs" },
  { code: "33711630", label: "Перики", labelEn: "Wigs" },
  { code: "33711640", label: "Комплети за тоалета", labelEn: "Vanity cases" },
  { code: "33711700", label: "Артикли за орална и дентална хигиена", labelEn: "Articles for oral or dental hygiene" },
  { code: "33711710", label: "Четки за заби", labelEn: "Toothbrushes" },
  { code: "33711720", label: "Паста за заби", labelEn: "Toothpaste" },
  { code: "33711730", label: "Држачи за заби", labelEn: "Toothpicks" },
  { code: "33711740", label: "Течност за уста", labelEn: "Mouthwash" },
  { code: "33711750", label: "Освежувачи за здив", labelEn: "Breath fresheners" },
  { code: "33711760", label: "Конец за заби", labelEn: "Dental floss" },
  { code: "33711770", label: "Дуди за бебиња", labelEn: "Dummies for babies" },
  { code: "33711780", label: "Таблети за чистење на протези", labelEn: "Denture-cleaning tablets" },
  { code: "33711790", label: "Комплети за заби", labelEn: "Tooth kits" },
  { code: "33711800", label: "Производи за бричење", labelEn: "Shaving preparations" },
  { code: "33711810", label: "Кремови за бричење", labelEn: "Shaving creams" },
  { code: "33711900", label: "Сапуни", labelEn: "Soap" },
  { code: "33712000", label: "Кондоми", labelEn: "Condoms" },
  { code: "33720000", label: "Бричеви и комплети за манипулација", labelEn: "Razors and manicure or pedicure sets" },
  { code: "33721000", label: "Бричеви", labelEn: "Razors" },
  { code: "33721100", label: "Сечива за бричење", labelEn: "Razor blades" },
  { code: "33721200", label: "Електрични бричеви", labelEn: "Electric shavers" },
  { code: "33722000", label: "Комплети за манипулација", labelEn: "Manicure or pedicure sets" },
  { code: "33722100", label: "Комплети за маникир", labelEn: "Manicure sets" },
  { code: "33722110", label: "Нокторезци", labelEn: "Nail clippers" },
  { code: "33722200", label: "Комплети за педикир", labelEn: "Pedicure sets" },
  { code: "33730000", label: "Производи за нега на очи и корективни леќи", labelEn: "Eye-care and corrective lenses" },
  { code: "33731000", label: "Контактни леќи", labelEn: "Contact lenses" },
  { code: "33731100", label: "Корективни леќи", labelEn: "Corrective lenses" },
  { code: "33731110", label: "Интраокуларни леќи", labelEn: "Intraocular lenses" },
  { code: "33731120", label: "Леќи за очила", labelEn: "Spectacle lenses" },
  { code: "33732000", label: "Течности за контактни леќи", labelEn: "Contact-lens solutions" },
  { code: "33733000", label: "Очила за сонце", labelEn: "Sunglasses" },
  { code: "33734000", label: "Очила", labelEn: "Spectacles" },
  { code: "33734100", label: "Рамки и држачи за очила", labelEn: "Spectacle frames and mountings" },
  { code: "33734200", label: "Стакла за очила", labelEn: "Spectacle glasses" },
  { code: "33735000", label: "Заштитни очила", labelEn: "Goggles" },
  { code: "33735100", label: "Заштитни очила за пливање", labelEn: "Swimming goggles" },
  { code: "33735200", label: "Заштитни очила за скијање", labelEn: "Goggles for skiing" },
  { code: "33740000", label: "Производи за нега на раце и нокти", labelEn: "Hand and nail care products" },
  { code: "33741000", label: "Производи за нега на раце", labelEn: "Hand care products" },
  { code: "33741100", label: "Средства за чистење на раце", labelEn: "Hand cleaner" },
  { code: "33741200", label: "Лосион или крем за раце", labelEn: "Hand lotion or cream" },
  { code: "33741300", label: "Дезинфектанс за раце", labelEn: "Hand sanitizer" },
  { code: "33742000", label: "Производи за нега на нокти", labelEn: "Nail care products" },
  { code: "33742100", label: "Клешти за нокти", labelEn: "Nail clippers" },
  { code: "33742200", label: "Лак за нокти", labelEn: "Nail varnish" },
  { code: "33750000", label: "Производи за нега на бебиња", labelEn: "Baby care products" },
  { code: "33751000", label: "Еднократни пелени", labelEn: "Disposable nappies" },
  { code: "33752000", label: "Помпи за дојки", labelEn: "Breast pump" },
  { code: "33760000", label: "Тоалетна хартија, марамици и салфетки", labelEn: "Toilet paper, handkerchiefs, hand towels and serviettes" },
  { code: "33761000", label: "Тоалетна хартија", labelEn: "Toilet paper" },
  { code: "33762000", label: "Хартиени марамици", labelEn: "Paper handkerchiefs" },
  { code: "33763000", label: "Хартиени крпи за раце", labelEn: "Paper hand towels" },
  { code: "33764000", label: "Хартиени салфетки", labelEn: "Paper serviettes" },
  { code: "33770000", label: "Хартија за санитарна употреба", labelEn: "Paper for sanitary use" },
  { code: "33771000", label: "Хартиени санитарни производи", labelEn: "Sanitary towels of paper" },
  { code: "33771100", label: "Хигиенски влошки или тампони", labelEn: "Sanitary towels or tampons" },
  { code: "33771200", label: "Хартиени пелени", labelEn: "Nappies of paper" },
  { code: "33772000", label: "Еднократни производи од хартија", labelEn: "Disposable paper products" },

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

  // Hydration guard to prevent client-side errors
  const [isHydrated, setIsHydrated] = useState(false);

  // Autocomplete suggestions
  const [entitySuggestions, setEntitySuggestions] = useState<string[]>([]);
  const [showEntitySuggestions, setShowEntitySuggestions] = useState(false);
  const [competitorSuggestions, setCompetitorSuggestions] = useState<string[]>([]);
  const [showCompetitorSuggestions, setShowCompetitorSuggestions] = useState(false);

  // Validation state
  const [budgetError, setBudgetError] = useState<string | null>(null);

  const { user } = useAuth();
  const userId = user?.user_id;

  // Track hydration
  useEffect(() => {
    setIsHydrated(true);
  }, []);

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
          tier: 'trial',
          name: 'Пробен период',
          price_monthly_mkd: 0,
          price_yearly_mkd: 0,
          price_monthly_id: '',
          price_yearly_id: '',
          daily_queries: 50,
          trial_days: 7,
          allow_vpn: true,
          features: ['50 AI пораки', '15 екстракции', '5 извози', '20 конкурентски известувања']
        },
        {
          tier: 'start',
          name: 'Стартуј',
          price_monthly_mkd: 1990,
          price_yearly_mkd: 19900,
          price_monthly_id: 'price_1ShgNPHkVI5icjTly68LrF4r',
          price_yearly_id: 'price_1ShgNcHkVI5icjTl1cZHOEf6',
          daily_queries: 15,
          trial_days: 0,
          allow_vpn: true,
          features: ['15 AI прашања дневно', '10 известувања', 'CSV извоз', 'Основна аналитика']
        },
        {
          tier: 'pro',
          name: 'Про',
          price_monthly_mkd: 5990,
          price_yearly_mkd: 59900,
          price_monthly_id: 'price_1ShgO8HkVI5icjTl68Mk5BXJ',
          price_yearly_id: 'price_1ShgOEHkVI5icjTlMN2CAj7h',
          daily_queries: 50,
          trial_days: 0,
          allow_vpn: true,
          features: ['50 AI прашања дневно', 'Анализа на ризик', 'PDF извоз', 'Приоритетна поддршка']
        },
        {
          tier: 'team',
          name: 'Тим',
          price_monthly_mkd: 12990,
          price_yearly_mkd: 129900,
          price_monthly_id: 'price_1ShgPVHkVI5icjTl20YY8LUw',
          price_yearly_id: 'price_1ShgPZHkVI5icjTl3HeYecMd',
          daily_queries: -1,
          trial_days: 0,
          allow_vpn: true,
          features: ['Неограничени AI прашања', 'До 5 членови', 'API пристап', 'Приоритетна поддршка']
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

  // Fetch entity suggestions from real database (460+ procuring organizations)
  const fetchEntitySuggestions = useCallback(async (query: string) => {
    if (query.length < 2) {
      setEntitySuggestions([]);
      return;
    }
    try {
      // Use the entities API which has 460+ real procuring organizations
      const result = await api.searchEntities(query, 10);
      const entities = result.items.map(e => e.entity_name);
      setEntitySuggestions(entities);
    } catch {
      // Fallback to searching tenders if entities API fails
      try {
        const result = await api.searchTenders({
          query: query,
          page: 1,
          page_size: 20
        });
        const entities = [...new Set(
          result.items
            .map(t => t.procuring_entity)
            .filter((e): e is string => !!e && e.toLowerCase().includes(query.toLowerCase()))
        )].slice(0, 8);
        setEntitySuggestions(entities);
      } catch {
        setEntitySuggestions([]);
      }
    }
  }, []);

  // Fetch competitor suggestions from real database (suppliers who won tenders)
  const fetchCompetitorSuggestions = useCallback(async (query: string) => {
    if (query.length < 2) {
      setCompetitorSuggestions([]);
      return;
    }
    try {
      // Use the suppliers API which has real companies that won tenders
      const result = await api.getSuppliers({ search: query, page_size: 10 });
      const companies = result.items.map(s => s.company_name);
      setCompetitorSuggestions(companies);
    } catch {
      // Fallback to e-Pazar suppliers
      try {
        const result = await api.getEPazarSuppliers({ search: query, page_size: 8 });
        const companies = result.items.map(s => s.company_name);
        setCompetitorSuggestions(companies);
      } catch {
        setCompetitorSuggestions([]);
      }
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

  // Show loading state until hydrated and data loaded
  if (!isHydrated || loading) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-center">Се вчитува...</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-4 md:py-8 px-3 md:px-4 max-w-6xl">
      <div className="mb-4 md:mb-6">
        <h1 className="text-2xl md:text-3xl font-bold">Поставки</h1>
        <p className="text-sm md:text-base text-muted-foreground mt-1 md:mt-2">
          Конфигурирајте ги вашите преференци за да добивате персонализирани препораки за тендери
        </p>
      </div>

      <div className="space-y-6">
        {/* Subscription Plans */}
        <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
          <CardHeader className="p-4 md:p-6">
            <CardTitle className="flex items-center gap-2 text-lg md:text-xl">
              <Sparkles className="h-4 w-4 md:h-5 md:w-5 text-primary" />
              Претплата и цени
            </CardTitle>
            <CardDescription className="text-xs md:text-sm">Одберете го планот што најдобро одговара на вашите потреби</CardDescription>
          </CardHeader>
          <CardContent className="p-4 md:p-6 pt-0">
            {/* Monthly/Yearly Toggle */}
            <div className="flex justify-center mb-4 md:mb-6">
              <div className="inline-flex rounded-lg border border-primary/20 p-1 bg-background/50">
                <button
                  onClick={() => setInterval('monthly')}
                  className={`px-3 py-1.5 md:px-4 md:py-2 rounded-md text-xs md:text-sm font-medium transition-all ${interval === 'monthly'
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                    }`}
                >
                  Месечно
                </button>
                <button
                  onClick={() => setInterval('yearly')}
                  className={`px-3 py-1.5 md:px-4 md:py-2 rounded-md text-xs md:text-sm font-medium transition-all ${interval === 'yearly'
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                    }`}
                >
                  Годишно
                  <Badge variant="secondary" className="ml-1 md:ml-2 bg-green-500/10 text-green-400 border-green-500/20 text-[10px] md:text-xs px-1 py-0">
                    -17%
                  </Badge>
                </button>
              </div>
            </div>

            {/* Plans Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
              {plans.map((plan) => {
                const isCurrentPlan = plan.tier === currentTier;
                const price = interval === 'monthly' ? plan.price_monthly_mkd : plan.price_yearly_mkd;
                const isFree = plan.tier === 'free' || plan.tier === 'trial';
                const isPopular = plan.tier === 'pro';

                return (
                  <div key={plan.tier} className="relative">
                    {isPopular && (
                      <div className="absolute -top-3 md:-top-4 left-0 right-0 flex justify-center z-10">
                        <Badge className="bg-primary text-primary-foreground text-[10px] md:text-xs">
                          Најпопуларно
                        </Badge>
                      </div>
                    )}
                    <Card className={`h-full ${isCurrentPlan ? 'border-primary shadow-lg shadow-primary/20' : ''} ${isPopular ? 'border-primary/50' : ''}`}>
                      <CardHeader className="p-4 md:p-6">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-lg md:text-xl">{plan.name}</CardTitle>
                          {isCurrentPlan && (
                            <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20 text-[10px] md:text-xs">
                              Тековен
                            </Badge>
                          )}
                        </div>
                        <div className="mt-2 md:mt-4">
                          <div className="flex items-baseline gap-1">
                            <span className="text-2xl md:text-4xl font-bold">{price.toLocaleString('mk-MK')}</span>
                            <span className="text-xs md:text-sm text-muted-foreground">
                              ден{isFree ? '/засекогаш' : `/${interval === 'monthly' ? 'мес' : 'год'}`}
                            </span>
                          </div>
                          {!isFree && interval === 'yearly' && (
                            <p className="text-xs md:text-sm text-muted-foreground mt-1">
                              {Math.round(price / 12).toLocaleString('mk-MK')} ден месечно
                            </p>
                          )}
                        </div>
                      </CardHeader>
                      <CardContent className="p-4 md:p-6 pt-0 space-y-3 md:space-y-4">
                        <div className="flex items-center gap-2 text-xs md:text-sm">
                          <Zap className="h-3 w-3 md:h-4 md:w-4 text-primary" />
                          <span className="font-medium">
                            {plan.daily_queries === -1 ? 'Неограничени' : plan.daily_queries} AI пребарувања дневно
                          </span>
                        </div>
                        {plan.trial_days > 0 && (
                          <div className="flex items-center gap-2 text-xs md:text-sm text-muted-foreground">
                            <Check className="h-3 w-3 md:h-4 md:w-4" />
                            <span>{plan.trial_days}-дневен пробен период</span>
                          </div>
                        )}
                        <div className="space-y-2 pt-2 border-t">
                          {plan.features.map((feature, idx) => (
                            <div key={idx} className="flex items-start gap-2 text-xs md:text-sm">
                              <Check className="h-3 w-3 md:h-4 md:w-4 text-primary mt-0.5 flex-shrink-0" />
                              <span className="text-muted-foreground">{feature}</span>
                            </div>
                          ))}
                        </div>
                        <div className="pt-4">
                          {isCurrentPlan ? (
                            <Button variant="outline" className="w-full text-xs md:text-sm h-8 md:h-10" onClick={handleManageBilling}>
                              <CreditCard className="mr-2 h-3 w-3 md:h-4 md:w-4" />
                              Управувај претплата
                            </Button>
                          ) : isFree ? (
                            <Button variant="outline" className="w-full text-xs md:text-sm h-8 md:h-10" disabled>
                              Тековен план
                            </Button>
                          ) : (
                            <Button
                              className={`w-full text-xs md:text-sm h-8 md:h-10 ${isPopular ? 'bg-primary hover:bg-primary/90' : ''}`}
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

            {currentTier === 'trial' && (
              <div className="mt-4 md:mt-6 p-3 md:p-4 rounded-lg bg-green-500/10 border border-green-500/20">
                <p className="text-xs md:text-sm text-green-400">
                  <strong>🎁 Активен пробен период:</strong> Имате пристап до Про функциите со 50 AI пораки, 15 екстракции на документи, 5 извози и 20 конкурентски известувања. Надградете пред истекот!
                </p>
              </div>
            )}
            {currentTier === 'free' && (
              <div className="mt-4 md:mt-6 p-3 md:p-4 rounded-lg bg-orange-500/10 border border-orange-500/20">
                <p className="text-xs md:text-sm text-orange-400">
                  <strong>⚠️ Пробниот период истече:</strong> Надградете на платен план за да продолжите да ги користите сите функции.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Sectors - Improved with descriptions */}
        <Card>
          <CardHeader className="p-4 md:p-6">
            <CardTitle className="flex items-center gap-2 text-lg md:text-xl">
              Сектори на интерес
              <span className="text-[10px] md:text-xs font-normal text-muted-foreground bg-primary/10 px-2 py-1 rounded">
                {preferences.sectors.length} избрани
              </span>
            </CardTitle>
            <CardDescription className="text-xs md:text-sm">
              Одберете ги секторите за кои сакате да добивате препораки. Можете да изберете повеќе сектори.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 md:p-6 pt-0">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 md:gap-3">
              {AVAILABLE_SECTORS.map((sector) => (
                <div
                  key={sector.id}
                  onClick={() => toggleSector(sector.id)}
                  className={`cursor-pointer p-3 rounded-lg border transition-all ${preferences.sectors.includes(sector.id)
                      ? 'border-primary bg-primary/10 shadow-sm'
                      : 'border-border hover:border-primary/50 hover:bg-accent/50'
                    }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm md:text-base">{sector.label}</span>
                    {preferences.sectors.includes(sector.id) && (
                      <Check className="h-3 w-3 md:h-4 md:w-4 text-primary" />
                    )}
                  </div>
                  <p className="text-[10px] md:text-xs text-muted-foreground mt-1">{sector.description}</p>
                </div>
              ))}
            </div>
            {preferences.sectors.length === 0 && (
              <p className="text-xs md:text-sm text-muted-foreground mt-3 flex items-center gap-2">
                <HelpCircle className="h-3 w-3 md:h-4 md:w-4" />
                Изберете барем еден сектор за подобри препораки
              </p>
            )}
          </CardContent>
        </Card>

        {/* CPV Codes - Searchable dropdown with multi-select */}
        <Card className={`relative ${showCpvDropdown ? 'z-[200]' : ''}`}>
          <CardHeader className="p-4 md:p-6">
            <CardTitle className="flex items-center gap-2 text-lg md:text-xl">
              CPV Кодови
              <span className="text-[10px] md:text-xs font-normal text-muted-foreground bg-primary/10 px-2 py-1 rounded">
                {preferences.cpv_codes.length} додадени
              </span>
            </CardTitle>
            <CardDescription className="text-xs md:text-sm">
              CPV (Common Procurement Vocabulary) кодовите се стандардизирани EU кодови за категоризација на набавки.
              Пребарајте и изберете кодови за попрецизни препораки.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 md:p-6 pt-0">
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
                <div className="absolute top-full left-0 right-0 mt-1 bg-background border rounded-lg shadow-xl z-[250] max-h-80 overflow-auto">
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

            {/* Click outside to close - positioned behind the dropdown but above other content */}
            {showCpvDropdown && (
              <div
                className="fixed inset-0 z-[199]"
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

        {/* Entities - With autocomplete */}
        <Card className="relative z-[50]">
          <CardHeader className="p-4 md:p-6">
            <CardTitle className="flex items-center gap-2 text-lg md:text-xl">
              Набавувачки организации
              <span className="text-[10px] md:text-xs font-normal text-muted-foreground bg-primary/10 px-2 py-1 rounded">
                {preferences.entities.length} следени
              </span>
            </CardTitle>
            <CardDescription className="text-xs md:text-sm">
              Додадете имиња на институции/организации чии тендери сакате да ги следите (министерства, општини, јавни претпријатија и сл.)
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 md:p-6 pt-0">
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
          <CardHeader className="p-4 md:p-6">
            <CardTitle className="text-lg md:text-xl">Буџетски опсег</CardTitle>
            <CardDescription className="text-xs md:text-sm">Дефинирајте минимален и максимален буџет за тендерите што ве интересираат (во МКД)</CardDescription>
          </CardHeader>
          <CardContent className="p-4 md:p-6 pt-0">
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
          <CardHeader className="p-4 md:p-6">
            <CardTitle className="flex items-center gap-2 text-lg md:text-xl">
              Исклучени клучни зборови
              <span className="text-[10px] md:text-xs font-normal text-destructive/70 bg-destructive/10 px-2 py-1 rounded">
                {preferences.exclude_keywords.length} исклучени
              </span>
            </CardTitle>
            <CardDescription className="text-xs md:text-sm">
              Тендери што содржат овие зборови во насловот нема да се прикажуваат во вашите препораки
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 md:p-6 pt-0">
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
          <CardHeader className="p-4 md:p-6">
            <CardTitle className="flex items-center gap-2 text-lg md:text-xl">
              Конкурентски компании
              <span className="text-[10px] md:text-xs font-normal text-orange-400 bg-orange-500/10 px-2 py-1 rounded">
                {preferences.competitor_companies.length} следени
              </span>
            </CardTitle>
            <CardDescription className="text-xs md:text-sm">
              Следете ги активностите на конкурентските компании - ќе добиете известувања кога тие добиваат тендери
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 md:p-6 pt-0">
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
          <CardHeader className="p-4 md:p-6">
            <CardTitle className="text-lg md:text-xl">Нотификации</CardTitle>
            <CardDescription className="text-xs md:text-sm">Конфигурирајте како сакате да примате известувања за нови тендери и активности</CardDescription>
          </CardHeader>
          <CardContent className="p-4 md:p-6 pt-0">
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
        <div className="flex gap-2 md:gap-3 justify-end sticky bottom-3 md:bottom-4 bg-background/80 backdrop-blur-sm p-3 md:p-4 rounded-lg border z-[60]">
          <Button variant="outline" onClick={handleReset} className="text-xs md:text-sm h-9 md:h-10">Ресетирај се</Button>
          <Button
            onClick={handleSave}
            disabled={saving || !!budgetError}
            className="min-w-24 md:min-w-32 text-xs md:text-sm h-9 md:h-10"
          >
            {saving ? "Се зачувува..." : "Зачувај преференци"}
          </Button>
        </div>
      </div>
    </div>
  );
}
