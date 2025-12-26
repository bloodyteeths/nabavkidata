# Hybrid Anomaly Detection Report

**Generated:** 2025-12-26 03:59:51

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Tenders Analyzed | 1000 |
| Anomalies Detected (>0.5) | 109 (10.9%) |
| Mean Anomaly Score | 0.2683 |
| Median Anomaly Score | 0.2184 |
| Std Dev | 0.1868 |
| Min Score | 0.0057 |
| Max Score | 1.0000 |
| 95th Percentile | 0.6755 |

## Detection Methods Performance

The hybrid detector combines four unsupervised methods:

1. **Isolation Forest** (25% weight): Tree-based outlier detection
2. **Autoencoder** (30% weight): Neural network reconstruction error
3. **Local Outlier Factor** (20% weight): Density-based local anomalies
4. **One-Class SVM** (25% weight): Boundary-based detection

### Method Agreement

- High confidence predictions (>0.7): 822 (82.2%)

## Top 15 Most Important Features

Features most influential in detecting anomalies:

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | price_very_close_estimate | 0.0148 |
| 2 | institution_total_tenders | 0.0144 |
| 3 | single_bidder | 0.0141 |
| 4 | value_small | 0.0136 |
| 5 | num_disqualified | 0.0130 |
| 6 | pub_weekend | 0.0130 |
| 7 | bidder_clustering_score | 0.0128 |
| 8 | deadline_days | 0.0128 |
| 9 | winner_experienced_supplier | 0.0128 |
| 10 | has_eval_method | 0.0127 |
| 11 | status_closed | 0.0126 |
| 12 | winner_win_rate_at_institution | 0.0125 |
| 13 | new_bidders_ratio | 0.0124 |
| 14 | bid_low_variance | 0.0124 |
| 15 | disqualification_rate | 0.0122 |

## Common Patterns in Flagged Tenders

Among the 109 flagged anomalies:

- **Single bidder tenders:** 82 (75.2%)
- **High winner win rate:** 50 (45.9%)
- **Large price deviation:** 68 (62.4%)

## Top 20 Most Suspicious Tenders

### 1. 12695/2025

**Anomaly Score:** 1.0000 | **Confidence:** 1.0000

| Field | Value |
|-------|-------|
| Title | Услуги за осигурување и издавање полномошно... |
| Institution | Министерство за внатрешни работи на РСМ |
| Winner | Акционерско друштво за осигурување и реосигурување МАКЕДОНИЈА Скопје - Виена Иншуренс Груп |
| Estimated Value (MKD) | 102,000,000 |
| Actual Value (MKD) | 1,000,000 |
| Price Deviation | -99.0% |
| Number of Bidders | 1 |
| Publication Date | 2025-12-10 |
| Existing Flags | ["single_bidder"] |

**Method Scores:**
- Isolation Forest: 1.0000
- Autoencoder: 1.0000
- LOF: 1.0000
- One-Class SVM: 1.0000

**Top Contributing Features:**
- bid_std: 0.0857
- bid_range: 0.0851
- bid_mean: 0.0845
- bid_median: 0.0845
- bid_max: 0.0843

---

### 2. 17717/2025

**Anomaly Score:** 1.0000 | **Confidence:** 1.0000

| Field | Value |
|-------|-------|
| Title | 2.5.9.Осигурување на имот... |
| Institution | АД за поштенски сообраќај Пошта на Северна Македонија во државна сопственост |
| Winner | Акционерско друштво ЕВРОИНС ОСИГУРУВАЊЕ Скопје |
| Estimated Value (MKD) | 12,000,000 |
| Actual Value (MKD) | 10,800,000 |
| Price Deviation | -10.0% |
| Number of Bidders | 2 |
| Publication Date | 2025-12-05 |
| Existing Flags | {} |

**Method Scores:**
- Isolation Forest: 1.0000
- Autoencoder: 1.0000
- LOF: 1.0000
- One-Class SVM: 1.0000

**Top Contributing Features:**
- bid_min: 0.0736
- two_bidders: 0.0461
- bid_median: 0.0414
- bid_mean: 0.0413
- winner_vs_mean_ratio: 0.0398

---

### 3. 19253/2025

**Anomaly Score:** 1.0000 | **Confidence:** 1.0000

| Field | Value |
|-------|-------|
| Title | Хемиски средства за хигиена... |
| Institution | ЈЗУ Општа болница -Куманово |
| Winner | Друштво за трговија и услуги ММ ХОСПИТАЛ ХИГИЕНА ДООЕЛ Скопје |
| Estimated Value (MKD) | 767,000 |
| Actual Value (MKD) | 373,543 |
| Price Deviation | -51.3% |
| Number of Bidders | 1 |
| Publication Date | 2025-12-02 |
| Existing Flags | ["single_bidder"] |

**Method Scores:**
- Isolation Forest: 1.0000
- Autoencoder: 1.0000
- LOF: 1.0000
- One-Class SVM: 1.0000

**Top Contributing Features:**
- winner_vs_median_ratio: 0.1067
- winner_vs_mean_ratio: 0.0877
- winner_bid_z_score: 0.0598
- num_bidders: 0.0473
- bidders_vs_category_avg: 0.0467

---

### 4. 31db19fa-de8f-4af2-b498-22460190aa13

**Anomaly Score:** 0.9899 | **Confidence:** 0.9918

| Field | Value |
|-------|-------|
| Title | Изградба на водовод, атмосферска канализација и реконструкција на улици во с.Лас... |
| Institution | Општина Сарај |
| Winner | Друштво за градежништво, транспорт, трговија и услуги ЈУ-БАЈ 2 ДООЕЛ Скопје |
| Estimated Value (MKD) | 243,569,860 |
| Actual Value (MKD) | 243,553,841 |
| Price Deviation | -0.0% |
| Number of Bidders | 15 |
| Publication Date | 2025-11-28 |
| Existing Flags | {} |

**Method Scores:**
- Isolation Forest: 0.9597
- Autoencoder: 1.0000
- LOF: 1.0000
- One-Class SVM: 1.0000

**Top Contributing Features:**
- actual_value_mkd: 0.1597
- estimated_value_mkd: 0.0798
- winner_dominant_supplier: 0.0793
- value_very_large: 0.0524
- winner_market_share_at_institution: 0.0389

---

### 5. 21280/2025

**Anomaly Score:** 0.9490 | **Confidence:** 0.9545

| Field | Value |
|-------|-------|
| Title | Реконструкција и санација на прва фаза на IV грана од ХМС Липково-повторена пост... |
| Institution | Акционерско друштво Водостопанство на Република Северна Македонија, во државна сопственост, Скопје |
| Winner | Друштво за градежништво ИЗГРЕВ ИНЖЕЊЕРИНГ ДООЕЛ Велес |
| Estimated Value (MKD) | 10,791,056 |
| Actual Value (MKD) | 6,493,180 |
| Price Deviation | -39.8% |
| Number of Bidders | 1 |
| Publication Date | 2025-11-25 |
| Existing Flags | ["single_bidder"] |

**Method Scores:**
- Isolation Forest: 0.7961
- Autoencoder: 1.0000
- LOF: 1.0000
- One-Class SVM: 1.0000

**Top Contributing Features:**
- deadline_normal: 0.0931
- deadline_days: 0.0917
- many_documents: 0.0466
- num_docs_extracted: 0.0465
- total_doc_content_length: 0.0455

---

### 6. 21889/2025

**Anomaly Score:** 0.9410 | **Confidence:** 0.9465

| Field | Value |
|-------|-------|
| Title | Реагенси за хематолошки апарат Beckman Coulter DxH560 или еквивалент... |
| Institution | ЈЗУ Клиничка Болница Тетово |
| Winner | Друштво за промет и услуги БИОТЕК ДОО експорт-импорт Скопје |
| Estimated Value (MKD) | 1,550,000 |
| Actual Value (MKD) | 1,473,515 |
| Price Deviation | -4.9% |
| Number of Bidders | 1 |
| Publication Date | 2025-12-24 |
| Existing Flags | ["single_bidder"] |

**Method Scores:**
- Isolation Forest: 0.7640
- Autoencoder: 1.0000
- LOF: 1.0000
- One-Class SVM: 1.0000

**Top Contributing Features:**
- bidder_clustering_score: 0.1723
- two_bidders: 0.0838
- single_bidder: 0.0698
- price_very_close_estimate: 0.0476
- winner_total_bids: 0.0305

---

### 7. 17580/2025

**Anomaly Score:** 0.9318 | **Confidence:** 0.9324

| Field | Value |
|-------|-------|
| Title | Реагенси и потрошен материјал за биохемиска лабораторија... |
| Institution | Јавна здравствена организација Здравствен дом Академик Проф.д-р. Димитар Арсов - Крива Паланка |
| Winner | Трговско друштво за вработување на инвалидни лица ИНТЕР-ХЕМ ДООЕЛ Друштво за производство,промет и услуги во хемиската индустрија-Скопје |
| Estimated Value (MKD) | 7,080,000 |
| Actual Value (MKD) | 71,200 |
| Price Deviation | -99.0% |
| Number of Bidders | 3 |
| Publication Date | 2025-12-11 |
| Existing Flags | {} |

**Method Scores:**
- Isolation Forest: 1.0000
- Autoencoder: 1.0000
- LOF: 0.6590
- One-Class SVM: 1.0000

**Top Contributing Features:**
- bid_coefficient_of_variation: 0.0788
- num_bidders: 0.0773
- bidders_vs_category_avg: 0.0765
- winner_win_rate_at_institution: 0.0494
- num_documents: 0.0398

---

### 8. 18597/2025

**Anomaly Score:** 0.9306 | **Confidence:** 0.9410

| Field | Value |
|-------|-------|
| Title | Тековно одржување и одржување на хигиена... |
| Institution | Агенција за финансиска поддршка во земјоделството и руралниот развој |
| Winner | Трговско друштво за еколошки, комунални и други услуги РЕМОНДИС МЕДИСОН ДООЕЛ Скопје |
| Estimated Value (MKD) | 1,770,000 |
| Actual Value (MKD) | 918,000 |
| Price Deviation | -48.1% |
| Number of Bidders | 4 |
| Publication Date | 2025-12-19 |
| Existing Flags | {} |

**Method Scores:**
- Isolation Forest: 1.0000
- Autoencoder: 0.8865
- LOF: 0.8234
- One-Class SVM: 1.0000

**Top Contributing Features:**
- two_bidders: 0.0726
- single_bidder: 0.0569
- bid_min: 0.0548
- market_concentration_hhi: 0.0541
- pub_friday: 0.0490

---

### 9. 21017/2025

**Anomaly Score:** 0.9244 | **Confidence:** 0.9284

| Field | Value |
|-------|-------|
| Title | Набавка на услуги за одржување на информатичка опрема за електронски надзор при ... |
| Institution | Министерство за правда, Управа за извршување на санкциите |
| Winner | Друштво за промет на стока и услуги САГА МК ДООЕЛ увоз-извоз Скопје |
| Estimated Value (MKD) | 8,906,404 |
| Actual Value (MKD) | 7,542,000 |
| Price Deviation | -15.3% |
| Number of Bidders | 1 |
| Publication Date | 2025-12-23 |
| Existing Flags | ["single_bidder", "short_deadline"] |

**Method Scores:**
- Isolation Forest: 0.9580
- Autoencoder: 1.0000
- LOF: 0.6746
- One-Class SVM: 1.0000

**Top Contributing Features:**
- deadline_short: 0.0753
- deadline_very_short: 0.0750
- winner_dominant_supplier: 0.0634
- winner_market_share_at_institution: 0.0551
- num_documents: 0.0546

---

### 10. 16323/2025

**Anomaly Score:** 0.9137 | **Confidence:** 0.9191

| Field | Value |
|-------|-------|
| Title | Одржување на фотокопири и наем на фотокопир... |
| Institution | Универзитет Св. Кирил и Методиј Економски факултет - Скопје |
| Winner | Друштво за производство,трговија и услуги СТЕРНА ДОО увоз-извоз,Скопје |
| Estimated Value (MKD) | 472,000 |
| Actual Value (MKD) | 250,000 |
| Price Deviation | -47.0% |
| Number of Bidders | 4 |
| Publication Date | 2025-12-12 |
| Existing Flags | {} |

**Method Scores:**
- Isolation Forest: 0.9688
- Autoencoder: 1.0000
- LOF: 0.6547
- One-Class SVM: 0.9621

**Top Contributing Features:**
- two_bidders: 0.0716
- single_bidder: 0.0552
- market_concentration_hhi: 0.0534
- winner_bid_z_score: 0.0483
- winner_vs_mean_ratio: 0.0465

---

### 11. 9c33a108-939b-4fd3-839d-c784c8c27313

**Anomaly Score:** 0.9015 | **Confidence:** 0.9153

| Field | Value |
|-------|-------|
| Title | Реконструкција на улица „Маршал Тито“ Гевгелија од ул.„Гевгелиски Партизански Од... |
| Institution | Општина Гевгелија |
| Winner | Друштво за градежништво и трговија ЖИКОЛ ДООЕЛ експорт импорт Струмица |
| Estimated Value (MKD) | 82,596,823 |
| Actual Value (MKD) | 82,596,823 |
| Price Deviation | +0.0% |
| Number of Bidders | 12 |
| Publication Date | 2025-11-25 |
| Existing Flags | {} |

**Method Scores:**
- Isolation Forest: 0.7347
- Autoencoder: 0.9397
- LOF: 0.9874
- One-Class SVM: 0.9536

**Top Contributing Features:**
- avg_doc_content_length: 0.1035
- total_doc_content_length: 0.0846
- value_very_large: 0.0606
- actual_value_mkd: 0.0592
- tender_very_recent: 0.0590

---

### 12. 21497/2025

**Anomaly Score:** 0.8913 | **Confidence:** 0.9097

| Field | Value |
|-------|-------|
| Title | Санитарни прегледи на вработени  и дезинфекција ,дезинсекција и дератизација на ... |
| Institution | ОЈУДГ Младост Тетово |
| Winner | Република  Македонија ,Јавна здравствена установа ЦЕНТАР ЗА ЈАВНО ЗДРАВЈЕ Тетово |
| Estimated Value (MKD) | 354,000 |
| Actual Value (MKD) | 300,000 |
| Price Deviation | -15.3% |
| Number of Bidders | 2 |
| Publication Date | 2025-12-11 |
| Existing Flags | {} |

**Method Scores:**
- Isolation Forest: 0.8111
- Autoencoder: 1.0000
- LOF: 0.8241
- One-Class SVM: 0.8948

**Top Contributing Features:**
- time_to_award_days: 0.0980
- deadline_short: 0.0844
- deadline_very_short: 0.0838
- deadline_days: 0.0510
- has_lots: 0.0479

---

### 13. 21554/2025

**Anomaly Score:** 0.8864 | **Confidence:** 0.8921

| Field | Value |
|-------|-------|
| Title | Набавка на течни горива- нафта... |
| Institution | ССОУ Димитрија Чуповски - Велес |
| Winner | Друштво за производство,трговија и услуги ДАДИ ОИЛ ДООЕЛ Јакимово, Виница |
| Estimated Value (MKD) | 725,700 |
| Actual Value (MKD) | 615,000 |
| Price Deviation | -15.3% |
| Number of Bidders | 2 |
| Publication Date | 2025-12-10 |
| Existing Flags | {} |

**Method Scores:**
- Isolation Forest: 0.8755
- Autoencoder: 1.0000
- LOF: 0.5877
- One-Class SVM: 1.0000

**Top Contributing Features:**
- time_to_award_days: 0.0935
- deadline_very_short: 0.0800
- deadline_short: 0.0800
- winner_dominant_supplier: 0.0691
- winner_market_share_at_institution: 0.0599

---

### 14. 21493/2025

**Anomaly Score:** 0.8852 | **Confidence:** 0.9032

| Field | Value |
|-------|-------|
| Title | Опрема,мебел и материјали за осовременување на  лаборотарија за сито печат - мет... |
| Institution | Факултет за ликовни уметности |
| Winner | Друштво за производство,услуги и трговија МЕТАЛПРОМЕТ Цветан ДОО Радовиш |
| Estimated Value (MKD) | 129,800 |
| Actual Value (MKD) | 110,000 |
| Price Deviation | -15.3% |
| Number of Bidders | 3 |
| Publication Date | 2025-12-12 |
| Existing Flags | {} |

**Method Scores:**
- Isolation Forest: 0.8038
- Autoencoder: 1.0000
- LOF: 0.7719
- One-Class SVM: 0.9196

**Top Contributing Features:**
- time_to_award_days: 0.0957
- deadline_short: 0.0837
- deadline_very_short: 0.0831
- deadline_days: 0.0549
- many_documents: 0.0481

---

### 15. 20607/2025

**Anomaly Score:** 0.8765 | **Confidence:** 0.8583

| Field | Value |
|-------|-------|
| Title | Осигурување на недвижности, колективно осигурување на вработените и патничко оси... |
| Institution | Дирекција за безбедност на класифицирани информации |
| Winner | Национална групација за осигурување АД ОСИГУРИТЕЛНА ПОЛИСА Скопје |
| Estimated Value (MKD) | 200,000 |
| Actual Value (MKD) | 16,250 |
| Price Deviation | -91.9% |
| Number of Bidders | 1 |
| Publication Date | 2025-12-04 |
| Existing Flags | {} |

**Method Scores:**
- Isolation Forest: 1.0000
- Autoencoder: 1.0000
- LOF: 0.3825
- One-Class SVM: 1.0000

**Top Contributing Features:**
- bidders_vs_institution_avg: 0.0605
- two_bidders: 0.0599
- winner_dominant_supplier: 0.0581
- winner_market_share_at_institution: 0.0500
- single_bidder: 0.0438

---

### 16. 79f4faea-fc5c-4dcb-b7c2-4456ea85e534

**Anomaly Score:** 0.8762 | **Confidence:** 0.8755

| Field | Value |
|-------|-------|
| Title | Изградба на водоснабдителен систем за с. Калково, III фаза, Општина Валандово... |
| Institution | Министерство за животна средина и просторно планирање |
| Winner | Друштво за градежни работи, производство, трговија и услуги МИНТ-ИНЖЕНЕРИНГ ДООЕЛ с Батинци Скопје |
| Estimated Value (MKD) | 37,820,003 |
| Actual Value (MKD) | 35,706,242 |
| Price Deviation | -5.6% |
| Number of Bidders | 12 |
| Publication Date | 2025-11-25 |
| Existing Flags | {} |

**Method Scores:**
- Isolation Forest: 0.5193
- Autoencoder: 1.0000
- LOF: 1.0000
- One-Class SVM: 0.9855

**Top Contributing Features:**
- avg_doc_content_length: 0.1404
- total_doc_content_length: 0.1145
- value_very_large: 0.0697
- tender_very_recent: 0.0605
- price_deviation_large: 0.0317

---

### 17. 20153/2025

**Anomaly Score:** 0.8640 | **Confidence:** 0.8833

| Field | Value |
|-------|-------|
| Title | Набавка на реагенси за биохемиски анализи... |
| Institution | Јавна Здравствена установа ЗДРАВСТВЕН ДОМ НА СКОПЈЕ ЦО Скопје |
| Winner | Друштво за промет и услуги БИОТЕК ДОО експорт-импорт Скопје |
| Estimated Value (MKD) | 9,440,000 |
| Actual Value (MKD) | 8,000,000 |
| Price Deviation | -15.3% |
| Number of Bidders | 1 |
| Publication Date | 2025-12-11 |
| Existing Flags | ["single_bidder", "short_deadline"] |

**Method Scores:**
- Isolation Forest: 0.6843
- Autoencoder: 0.9127
- LOF: 0.9997
- One-Class SVM: 0.8769

**Top Contributing Features:**
- deadline_very_short: 0.1141
- deadline_short: 0.1139
- value_large: 0.0665
- value_medium: 0.0340
- winner_total_bids: 0.0282

---

### 18. 21712/2025

**Anomaly Score:** 0.8556 | **Confidence:** 0.8761

| Field | Value |
|-------|-------|
| Title | Информатичка училишна опрема... |
| Institution | ООУ,,Даме Груев,, Градско |
| Winner | Друштво за производство и трговија ДАВКА ДООЕЛ Штип |
| Estimated Value (MKD) | 500,000 |
| Actual Value (MKD) | 358,196 |
| Price Deviation | -28.4% |
| Number of Bidders | 1 |
| Publication Date | 2025-12-09 |
| Existing Flags | ["single_bidder", "single_bidder"] |

**Method Scores:**
- Isolation Forest: 0.6604
- Autoencoder: 0.9874
- LOF: 0.8645
- One-Class SVM: 0.8857

**Top Contributing Features:**
- time_to_award_days: 0.0969
- deadline_very_short: 0.0943
- deadline_short: 0.0942
- many_documents: 0.0495
- institution_activity_spike: 0.0332

---

### 19. 13e568e5-8fa7-4e6a-8591-9156d4d837f7

**Anomaly Score:** 0.8546 | **Confidence:** 0.8712

| Field | Value |
|-------|-------|
| Title | Услуги за поправка и одржување на медицински апарати (со сертификат за оддржувањ... |
| Institution | ЈЗУ Градска општа болница „8-ми Септември“ Скопје |
| Winner | Друштво за трговија и услуги КУБИС МЕДИКАЛ ДООЕЛ Скопје |
| Estimated Value (MKD) | 47,200,000 |
| Actual Value (MKD) | 4,130,000 |
| Price Deviation | -91.2% |
| Number of Bidders | 15 |
| Publication Date | 2025-11-28 |
| Existing Flags | {} |

**Method Scores:**
- Isolation Forest: 0.8383
- Autoencoder: 0.6501
- LOF: 1.0000
- One-Class SVM: 1.0000

**Top Contributing Features:**
- winner_prev_wins_at_institution: 0.1366
- winner_win_rate_at_institution: 0.0630
- value_very_large: 0.0563
- institution_tenders_same_month: 0.0506
- pub_friday: 0.0436

---

### 20. 21672/2025

**Anomaly Score:** 0.8499 | **Confidence:** 0.8658

| Field | Value |
|-------|-------|
| Title | Новогодишно украсување на територија на Општина Гази Баба... |
| Institution | Општина Гази Баба |
| Winner | Друштво за производство, трговија и услуги ЛИНК МЕДИА ПЛУС ДООЕЛ увоз-извоз Скопје |
| Estimated Value (MKD) | 1,800,000 |
| Actual Value (MKD) | 1,517,000 |
| Price Deviation | -15.7% |
| Number of Bidders | 1 |
| Publication Date | 2025-11-27 |
| Existing Flags | ["single_bidder"] |

**Method Scores:**
- Isolation Forest: 0.5977
- Autoencoder: 0.8922
- LOF: 1.0000
- One-Class SVM: 0.9314

**Top Contributing Features:**
- deadline_normal: 0.1157
- deadline_days: 0.1110
- many_documents: 0.0522
- winner_experienced_supplier: 0.0355
- total_doc_content_length: 0.0338

---

## Recommendations

Based on the analysis, the following tenders warrant further investigation:

1. **High Priority** (Score > 0.8): Immediate review recommended
   - Count: 25 tenders

2. **Medium Priority** (Score 0.6-0.8): Review when possible
   - Count: 35 tenders

3. **Low Priority** (Score 0.5-0.6): Monitor for patterns
   - Count: 49 tenders

## Methodology Notes

- The detector was trained in **unsupervised mode** assuming 5% contamination
- No ground truth labels were used; all patterns are learned from data distribution
- Higher anomaly scores indicate statistical deviation from typical tender patterns
- A high score does not prove corruption - only that the tender is unusual
- Human review is essential for final determination
