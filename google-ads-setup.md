# Google Ads Setup Guide for nabavkidata.com

> Complete configuration ready to copy-paste into Google Ads

---

## Step 1: Account Settings

### Business Information
- **Business Name**: nabavkidata.com
- **Business Category**: Business Services > Software > B2B Software
- **Time Zone**: Europe/Skopje (GMT+1/+2)
- **Currency**: EUR (recommended for consistency with pricing)

### Billing Country
- North Macedonia (if available) or use Germany/Austria for EUR billing

---

## Step 2: Conversion Tracking Setup

Before creating campaigns, set up these conversions in **Tools > Measurement > Conversions**:

| Conversion Name | Category | Value | Count |
|----------------|----------|-------|-------|
| Free Registration | Sign-up | €10 | One |
| Standard Plan Purchase | Purchase | €99 | One |
| Pro Plan Purchase | Purchase | €395 | One |
| Enterprise Inquiry | Lead | €50 | One |
| AI Query Used | Other | €1 | Every |

---

## Step 3: Campaign Structure

### Campaign 1: High Intent - Macedonian (60% of budget)

**Campaign Settings:**
```
Campaign Name: MK - High Intent - Tenders
Campaign Type: Search
Networks: Google Search only (disable Display Network)
Locations: North Macedonia
Languages: Macedonian, English
Budget: €30-50/day (adjust based on total budget)
Bidding: Maximize Conversions (after 30 conversions, switch to Target CPA)
```

**Ad Group 1: Core Tenders**
```
Ad Group Name: Јавни набавки - Core

Keywords (Phrase Match):
"јавни набавки"
"тендери Македонија"
"тендери"
"државни тендери"
"јавни огласи"
"оглас за набавка"

Keywords (Exact Match):
[јавни набавки]
[тендери]
[е набавки]
[државни тендери]
```

**Ad Group 2: E-Nabavki Brand**
```
Ad Group Name: Е-набавки - Brand

Keywords (Phrase Match):
"е-набавки"
"e-nabavki"
"енабавки"
"е набавки"

Keywords (Exact Match):
[е-набавки]
[e-nabavki]
[е набавки пребарување]
```

**Ad Group 3: Tender Alerts**
```
Ad Group Name: Известувања - Alerts

Keywords (Phrase Match):
"известувања за тендери"
"нови тендери"
"тендери денес"
"најнови тендери"
"тендер известување"

Keywords (Exact Match):
[нови тендери денес]
[известувања тендери]
```

**Ad Group 4: Industry Specific**
```
Ad Group Name: Индустрии - Industries

Keywords (Phrase Match):
"тендери градежништво"
"тендери ИТ"
"тендери здравство"
"тендери образование"
"тендери транспорт"
"набавки градежништво"
"ИТ тендери Македонија"

Keywords (Exact Match):
[градежни тендери]
[ит тендери]
[медицински тендери]
```

---

### Campaign 2: Problem Aware - Macedonian (25% of budget)

**Campaign Settings:**
```
Campaign Name: MK - Problem Aware - How To
Campaign Type: Search
Networks: Google Search only
Locations: North Macedonia
Languages: Macedonian, English
Budget: €15-25/day
Bidding: Maximize Clicks (initially), then Maximize Conversions
```

**Ad Group 1: How To Find**
```
Ad Group Name: Како да најдам

Keywords (Phrase Match):
"како да најдам тендер"
"каде има тендери"
"пребарување тендери"
"барање тендери"
"листа на тендери"
"сите тендери"

Keywords (Broad Match Modifier - use with caution):
+тендер +пребарување
+набавки +како
```

**Ad Group 2: Participation**
```
Ad Group Name: Учество на тендер

Keywords (Phrase Match):
"како да учествувам на тендер"
"аплицирање на тендер"
"пријава на тендер"
"услови за тендер"
"документи за тендер"
```

**Ad Group 3: CPV Codes**
```
Ad Group Name: CPV Кодови

Keywords (Phrase Match):
"CPV кодови"
"CPV код пребарување"
"CPV класификација"
"набавки по CPV"
```

---

### Campaign 3: English Keywords (10% of budget)

**Campaign Settings:**
```
Campaign Name: EN - International
Campaign Type: Search
Networks: Google Search only
Locations: North Macedonia, Serbia, Kosovo, Albania, EU Countries
Languages: English
Budget: €10-15/day
Bidding: Maximize Conversions
```

**Ad Group 1: Macedonia Tenders**
```
Ad Group Name: Macedonia Tenders

Keywords (Phrase Match):
"Macedonia tenders"
"North Macedonia public procurement"
"Macedonia government contracts"
"tender opportunities Macedonia"
"Macedonian tenders"
"e-nabavki"

Keywords (Exact Match):
[north macedonia tenders]
[macedonia public procurement]
[e-nabavki]
```

**Ad Group 2: Balkans**
```
Ad Group Name: Balkans Procurement

Keywords (Phrase Match):
"Balkans tenders"
"Western Balkans procurement"
"government contracts Balkans"
"tender database Balkans"
```

---

### Campaign 4: Competitor Keywords (5% of budget)

**Campaign Settings:**
```
Campaign Name: Competitors
Campaign Type: Search
Networks: Google Search only
Locations: North Macedonia, Balkans
Languages: Macedonian, English
Budget: €5-10/day
Bidding: Manual CPC (more control)
```

**Ad Group 1: Competitor Brands**
```
Ad Group Name: Competitors

Keywords (Exact Match only - be precise):
[tendersontime]
[globaltenders]
[tendersinfo]
[tender watch]
[balkan tender watch]
```

---

## Step 4: Negative Keywords

### Account-Level Negative Keywords
Add these at **Tools > Shared Library > Negative Keyword Lists**

```
List Name: nabavkidata - Master Negatives

-- Job seekers --
работа
вработување
jobs
job
career
кариера
оглас за работа
employment

-- Free seekers (optional - remove if targeting free tier) --
бесплатно
free
без плаќање
gratis

-- Students/Research --
туторијал
tutorial
есеј
essay
проект
семинарска
дипломска
магистерска
homework

-- Legal/Regulatory --
закон
law
legislation
регулатива
правилник

-- Irrelevant --
PDF download
документ
document download
template
шаблон
форма
формулар

-- Other countries (if not targeting) --
Србија тендери
Serbia tenders
Croatia tenders
България

-- Unrelated industries --
рецепт
recipe
игра
game
филм
movie
песна
song
```

---

## Step 5: Ad Copy Templates

### Responsive Search Ads - Macedonian (High Intent)

**Ad Group: Јавни набавки - Core**

```
Headlines (max 30 characters each - provide 15):
1. Јавни Набавки Македонија
2. Сите Тендери на Едно Место
3. AI Пребарување Тендери
4. Најди Тендер за 30 Секунди
5. Известувања за Тендери
6. nabavkidata.com
7. Бесплатна Регистрација
8. 10,000+ Активни Тендери
9. Паметно Пребарување
10. Денешни Нови Тендери
11. Анализа на Тендери
12. Не Пропуштај Тендер
13. Следи Конкуренција
14. CPV Код Пребарување
15. Државни Набавки 2025

Descriptions (max 90 characters each - provide 4):
1. Пребарувај јавни набавки со AI. Добивај известувања за нови тендери по твои критериуми.
2. Сите тендери од e-nabavki на едно место. Анализи, статистики и паметни известувања.
3. Заштеди време со AI пребарување. Најди релевантни тендери во секунди, не часови.
4. Бесплатна регистрација. Следи тендери по категорија, CPV код или клучни зборови.

Final URL: https://nabavkidata.com
Display Path: nabavkidata.com/tenderi
```

**Ad Group: Е-набавки - Brand**

```
Headlines:
1. Подобро од e-nabavki
2. e-nabavki + AI Пребарување
3. Надградба на e-nabavki
4. Паметен e-nabavki Пристап
5. e-nabavki Известувања
6. nabavkidata.com
7. AI за Јавни Набавки
8. Автоматски Аларми
9. Анализа на Понудувачи
10. Следи Победници
11. Бесплатна Проба
12. Почни Денес
13. 24/7 Мониторинг
14. Статистики и Увиди
15. Заштеди 10+ Часа Неделно

Descriptions:
1. Сите податоци од e-nabavki со AI пребарување и автоматски известувања. Пробај бесплатно.
2. Не губи време на e-nabavki. Добивај само релевантни тендери директно на твојот email.
3. AI анализа на јавни набавки. Следи конкуренција, победници и трендови во набавки.
4. Надмини ја конкуренцијата со паметни аларми. Биди прв што ќе дознае за нов тендер.

Final URL: https://nabavkidata.com
Display Path: nabavkidata.com/ai-search
```

### Responsive Search Ads - English

**Ad Group: Macedonia Tenders**

```
Headlines:
1. Macedonia Tender Database
2. AI-Powered Tender Search
3. North Macedonia Tenders
4. Government Contracts MK
5. nabavkidata.com
6. Free Registration
7. Smart Tender Alerts
8. 10,000+ Active Tenders
9. Find Tenders in Seconds
10. Competitor Analysis
11. CPV Code Search
12. Daily Tender Updates
13. Never Miss a Tender
14. Procurement Intelligence
15. Start Free Today

Descriptions:
1. Search all North Macedonia public tenders with AI. Get instant alerts for new opportunities.
2. Complete e-nabavki database with smart search, analytics, and automated notifications.
3. Save hours finding relevant tenders. AI matches opportunities to your business profile.
4. Free tier available. Monitor tenders by category, CPV code, or keywords automatically.

Final URL: https://nabavkidata.com
Display Path: nabavkidata.com/tenders
```

---

## Step 6: Ad Extensions (Assets)

### Sitelink Extensions

```
Sitelink 1:
Text: Пребарај Тендери
Description 1: AI пребарување на сите јавни набавки
Description 2: Резултати во секунди
Final URL: https://nabavkidata.com/tenders

Sitelink 2:
Text: Цени и Планови
Description 1: Бесплатен план достапен
Description 2: Pro план од €99/месец
Final URL: https://nabavkidata.com/pricing

Sitelink 3:
Text: Регистрација
Description 1: Бесплатно креирај профил
Description 2: Почни за 2 минути
Final URL: https://nabavkidata.com/register

Sitelink 4:
Text: AI Анализа
Description 1: Паметни увиди и статистики
Description 2: Анализа на конкуренција
Final URL: https://nabavkidata.com/analytics

Sitelink 5 (English):
Text: Search Tenders
Description 1: AI-powered tender search
Description 2: All Macedonia procurement
Final URL: https://nabavkidata.com/tenders

Sitelink 6 (English):
Text: Pricing Plans
Description 1: Free tier available
Description 2: Pro plans from €99/mo
Final URL: https://nabavkidata.com/pricing
```

### Callout Extensions

```
Macedonian:
- Бесплатна Регистрација
- AI Пребарување
- 24/7 Мониторинг
- Email Известувања
- 10,000+ Тендери
- CPV Класификација
- Анализа на Победници
- Извоз во Excel

English:
- Free Registration
- AI-Powered Search
- Real-time Alerts
- Competitor Tracking
- Export to Excel
- CPV Code Filter
```

### Structured Snippet Extensions

```
Header: Types (Типови)
Values: Градежништво, ИТ Услуги, Здравство, Образование, Транспорт, Енергетика

Header: Features (Карактеристики)
Values: AI Search, Smart Alerts, Analytics, Export, API Access
```

### Call Extension (if you have a phone)

```
Phone: +389 XX XXX XXX
Call reporting: On
```

### Price Extensions

```
Type: Services

Item 1:
Header: Бесплатен План
Price: €0
Description: 5 AI пребарувања дневно
Final URL: https://nabavkidata.com/pricing

Item 2:
Header: Standard План
Price: €99/месец
Description: 100 пребарувања, известувања
Final URL: https://nabavkidata.com/pricing

Item 3:
Header: Pro План
Price: €395/месец
Description: 500 пребарувања, API пристап
Final URL: https://nabavkidata.com/pricing
```

---

## Step 7: Audience Targeting

### Create Custom Audiences

**Tools > Shared Library > Audience Manager > Custom Audiences**

```
Audience 1: Tender Seekers
Type: People who searched for these terms
Terms:
- јавни набавки
- тендери
- government contracts
- public procurement
- e-nabavki

Audience 2: Business Owners MK
Type: People with interests in
Interests:
- Business services
- B2B
- Government relations
- Construction industry
- IT services
- Healthcare industry

Audience 3: Competitor Visitors
Type: People who browse websites similar to
URLs:
- tendersontime.com
- globaltenders.com
- tendersinfo.com
```

### Remarketing Audiences (set up after launch)

```
Audience: All Visitors
Membership duration: 90 days
URL: contains nabavkidata.com

Audience: Pricing Page Visitors
Membership duration: 30 days
URL: contains /pricing

Audience: Registered Users (exclude from acquisition)
Membership duration: 540 days
URL: contains /dashboard
```

---

## Step 8: Bid Adjustments

### Device Adjustments

```
Desktop: +0% (baseline)
Mobile: -20% (test and adjust - B2B typically desktop heavy)
Tablet: -10%
```

### Location Adjustments (within North Macedonia)

```
Скопје: +20% (capital, most businesses)
Битола: +10%
Куманово: +5%
Other cities: +0%
```

### Time Schedule (Ad Schedule)

```
Monday-Friday:
  - 08:00-18:00: +20% (business hours)
  - 18:00-22:00: +0%
  - 22:00-08:00: -50%

Saturday:
  - 09:00-14:00: +0%
  - Other times: -30%

Sunday:
  - All day: -50%
```

---

## Step 9: Landing Page Recommendations

Create dedicated landing pages for each campaign:

### /lp/tenderi (High Intent - Macedonian)
- Headline: "Сите Јавни Набавки на Едно Место"
- Show: Search bar, recent tenders, category filters
- CTA: "Пребарај Бесплатно" / "Регистрирај се"

### /lp/e-nabavki (E-nabavki searchers)
- Headline: "e-nabavki + AI = Заштеда на Време"
- Show: Comparison with manual e-nabavki search
- CTA: "Почни Бесплатно"

### /lp/tenders (English)
- Headline: "North Macedonia Tender Intelligence"
- Show: English interface, key features
- CTA: "Start Free Trial"

---

## Step 10: Budget Allocation Summary

### Recommended Starting Budget: €100-150/day

```
Campaign                          | Daily Budget | % of Total
----------------------------------|--------------|------------
MK - High Intent - Tenders        | €60-75       | 50%
MK - Problem Aware - How To       | €25-35       | 25%
EN - International                | €10-25       | 15%
Competitors                       | €5-15        | 10%
```

### First Month Strategy

**Week 1-2:**
- Start with Maximize Clicks bidding
- Gather data on which keywords convert
- Monitor search terms report daily

**Week 3-4:**
- Switch to Maximize Conversions
- Add negative keywords from search terms
- Pause low-performing keywords

**Month 2+:**
- Move to Target CPA bidding
- Create RLSA campaigns for remarketing
- Test new ad copy variations

---

## Step 11: Tracking & Analytics Setup

### Google Analytics 4 Connection

1. Link Google Ads to GA4
2. Import GA4 conversions
3. Enable auto-tagging

### UTM Parameters

```
Template for manual tracking:
?utm_source=google&utm_medium=cpc&utm_campaign={campaignid}&utm_content={adgroupid}&utm_term={keyword}
```

### Key Metrics to Monitor

| Metric | Target | Action if Below |
|--------|--------|-----------------|
| CTR | >3% | Improve ad copy |
| Conversion Rate | >2% | Improve landing page |
| Cost per Conversion | <€30 | Refine keywords |
| Quality Score | >6 | Improve relevance |
| Impression Share | >50% | Increase budget |

---

## Quick Start Checklist

- [ ] Create Google Ads account
- [ ] Set up billing (EUR preferred)
- [ ] Install conversion tracking on nabavkidata.com
- [ ] Create Campaign 1 (High Intent MK)
- [ ] Create Campaign 2 (Problem Aware MK)
- [ ] Add negative keyword list
- [ ] Set up sitelink extensions
- [ ] Set up callout extensions
- [ ] Link to Google Analytics 4
- [ ] Set daily budget
- [ ] Launch and monitor daily for first week

---

## Support Resources

- [Google Ads Help Center](https://support.google.com/google-ads)
- [Google Keyword Planner](https://ads.google.com/aw/keywordplanner)
- [Google Ads Editor](https://ads.google.com/intl/en/home/tools/ads-editor/) (bulk upload)

---

*Generated for nabavkidata.com - Macedonian Tender Intelligence Platform*
*Last updated: 2025-11-26*
