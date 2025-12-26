# Corruption Case to Tender Matching Report

Generated: 2025-12-26T04:15:56.537806

## Database Overview

- **Total tenders in database**: 274,353
- **Tenders with corruption flags**: 0

### Tenders by Year

| Year | Count |
|------|-------|
| 9999 | 9 |
| 9998 | 11 |
| 9997 | 9 |
| 9996 | 10 |
| 9995 | 14 |
| 9994 | 10 |
| 9993 | 7 |
| 9992 | 11 |
| 9991 | 16 |
| 9990 | 7 |
| 9989 | 11 |
| 9988 | 12 |
| 9987 | 10 |
| 9986 | 11 |
| 9985 | 18 |

## Summary of Results

- **Total cases analyzed**: 11
- **Cases with exact/partial matches**: 2
- **Total exact matches**: 0
- **Total partial matches**: 6

### Match Confidence Levels

- **Exact**: Multiple matching criteria (institution + product + company keywords)
- **Partial**: Some matching criteria (institution + product OR company)
- **Possible**: Single matching criterion

## Case-by-Case Results

### MK-2023-001: Tank Case (Mercedes)

- **Exact matches**: 0
- **Partial matches**: 0
- **Possible matches**: 0

*No matches found in database*

---

### MK-2021-001: Software Case (Biometric)

- **Exact matches**: 0
- **Partial matches**: 0
- **Possible matches**: 0

*No matches found in database*

---

### MK-2021-002: Trezor Case (Surveillance)

- **Exact matches**: 0
- **Partial matches**: 0
- **Possible matches**: 0

*No matches found in database*

---

### MK-2021-003: Target-Tvrdina (Mass Surveillance)

- **Exact matches**: 0
- **Partial matches**: 0
- **Possible matches**: 0

*No matches found in database*

---

### MK-2023-002: Zekiri Consulting

- **Exact matches**: 0
- **Partial matches**: 0
- **Possible matches**: 0

*No matches found in database*

---

### MK-2022-001: Kamcev Land Parcels

- **Exact matches**: 0
- **Partial matches**: 0
- **Possible matches**: 50

#### Top Matches

| Tender ID | Title | Entity | Value (EUR) | Confidence | Reasons |
|-----------|-------|--------|-------------|------------|---------|
| OT-d7446d999f45/2020 | No.05-1034/2014 — ‘Overground pedestrian... | Municipality of Cair | 9,152,195 | possible | Product: land |
| OT-365f008a3de5/2020 | Изведба на улици и уредување на градежно... | Општина Струмица | 1,315,971 | possible | Product: земјиште |
| OT-668cdb41b793/2020 | За изведба на улици и уредување на граде... | Општина Струмица | 1,171,283 | possible | Product: земјиште |
| OT-ed17f1c97f50/2020 | Изведба на работи- За изведба на улици и... | Општина Струмица | 1,074,824 | possible | Product: земјиште |
| OT-f52363a62007/2020 | Изведба на улици и уредување на градежно... | Општина Струмица | 937,026 | possible | Product: земјиште |

---

### MK-2025-001: ESM District Heating

- **Exact matches**: 0
- **Partial matches**: 0
- **Possible matches**: 0

*No matches found in database*

---

### MK-2024-001: TEC Negotino Fuel Oil

- **Exact matches**: 0
- **Partial matches**: 4
- **Possible matches**: 0

#### Top Matches

| Tender ID | Title | Entity | Value (EUR) | Confidence | Reasons |
|-----------|-------|--------|-------------|------------|---------|
| OT-55159e63b614/2020 | Purchase of goods - Light burning oil - ... | PHI Specialized hospital for g... | 34,829,352 | partial | Product: oil, Company: Pucko |
| 17600/2024 | Горива | ЈП Комунална хигиена Скопје | 2,878,049 | partial | Company: Pucko |
| OT-e5ea5d1ac434/2020 | Fuels | JP Komunalna higiena Skopje | 1,463,415 | partial | Product: fuel, Company: Pucko |
| OT-ca2ba6203427/2020 | Fuels | JP Komunalna higiena Skopje | 1,463,415 | partial | Product: fuel, Company: Pucko |

---

### MK-2024-002: State Lottery

- **Exact matches**: 0
- **Partial matches**: 2
- **Possible matches**: 0

#### Top Matches

| Tender ID | Title | Entity | Value (EUR) | Confidence | Reasons |
|-----------|-------|--------|-------------|------------|---------|
| 21437/2023 | Набавка и одржување на лиценца на веќе р... | Државна видеолотарија на Репуб... | 10,937 | partial | Institution: лотарија, Product: компјутер |
| 21441/2023 | Услуги за комерцијална ревизија за финас... | Државна видеолотарија на Репуб... | 3,837 | partial | Institution: лотарија, Product: TV |

---

### MK-2024-003: SOZR Tender Fraud

- **Exact matches**: 0
- **Partial matches**: 0
- **Possible matches**: 0

*No matches found in database*

---

### MK-2016-001: Trajectory (Sinohydro Highway)

- **Exact matches**: 0
- **Partial matches**: 0
- **Possible matches**: 0

*No matches found in database*

---

## Cases Without Matches

The following cases had no exact or partial matches in the database:

- **MK-2023-001**: Tank Case (Mercedes)
- **MK-2021-001**: Software Case (Biometric)
- **MK-2021-002**: Trezor Case (Surveillance)
- **MK-2021-003**: Target-Tvrdina (Mass Surveillance)
- **MK-2023-002**: Zekiri Consulting
- **MK-2022-001**: Kamcev Land Parcels
- **MK-2025-001**: ESM District Heating
- **MK-2024-003**: SOZR Tender Fraud
- **MK-2016-001**: Trajectory (Sinohydro Highway)

### Possible Reasons for Missing Matches

1. **Tender predates database coverage** (2008-2024)
2. **Non-public procurement** (direct contracts, classified)
3. **Different naming conventions** (entity names changed)
4. **Tender not in e-nabavki system** (different platform)

## Recommendations

1. **Verify matches manually** - Review matched tenders to confirm they are the actual corruption cases
2. **Add tender_ids to known_cases.py** - Update the ground truth file with confirmed tender IDs
3. **Expand search criteria** - For cases with no matches, try alternative keywords or entity names
4. **Check archived records** - Some cases may be in archived/cancelled tenders
