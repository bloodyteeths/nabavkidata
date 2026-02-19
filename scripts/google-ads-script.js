/**
 * Google Ads Complete Setup & Optimization Script for NabavkiData
 *
 * This script:
 * 1. Creates ad groups with all keywords and proper bids
 * 2. Creates compelling ad copy with urgency
 * 3. Adds negative keywords
 * 4. Optimizes performance over time
 *
 * Campaign: NabavkiData
 */

// ============== CONFIGURATION ==============
var CONFIG = {
  CAMPAIGN_NAME: 'NabavkiData',
  EMAIL: 'your-email@example.com',
  FINAL_URL: 'https://nabavkidata.com',
  DISPLAY_URL: 'nabavkidata.com',

  // Bid settings (EUR)
  DEFAULT_BID: 0.80,
  HIGH_INTENT_BID: 1.20,
  MEDIUM_INTENT_BID: 0.60,
  LOW_INTENT_BID: 0.40,

  // Optimization thresholds
  MIN_IMPRESSIONS: 100,
  MIN_CLICKS: 10,
  MAX_CPC: 2.00,
  MIN_CTR: 0.02,
  MAX_COST_PER_CONVERSION: 50,
  BID_INCREASE_PERCENT: 15,
  BID_DECREASE_PERCENT: 20,
  DATE_RANGE: 'LAST_14_DAYS'
};

// ============== KEYWORDS BY AD GROUP ==============
var AD_GROUPS = {
  // HIGH INTENT - People actively looking for tenders (highest bids)
  'Јавни Набавки - High Intent': {
    bid: CONFIG.HIGH_INTENT_BID,
    keywords: [
      // Exact match [keyword]
      { text: '[јавни набавки]', matchType: 'EXACT' },
      { text: '[тендери]', matchType: 'EXACT' },
      { text: '[тендери македонија]', matchType: 'EXACT' },
      { text: '[државни тендери]', matchType: 'EXACT' },
      { text: '[е набавки]', matchType: 'EXACT' },
      { text: '[e-nabavki]', matchType: 'EXACT' },
      { text: '[јавни огласи]', matchType: 'EXACT' },
      { text: '[тендер оглас]', matchType: 'EXACT' },
      { text: '[активни тендери]', matchType: 'EXACT' },
      { text: '[отворени тендери]', matchType: 'EXACT' },
      // Phrase match "keyword"
      { text: '"јавни набавки"', matchType: 'PHRASE' },
      { text: '"тендери македонија"', matchType: 'PHRASE' },
      { text: '"државни тендери"', matchType: 'PHRASE' },
      { text: '"е-набавки"', matchType: 'PHRASE' },
      { text: '"тендер оглас"', matchType: 'PHRASE' },
      { text: '"јавни огласи за набавки"', matchType: 'PHRASE' },
      { text: '"нови тендери"', matchType: 'PHRASE' },
      { text: '"тендери денес"', matchType: 'PHRASE' }
    ]
  },

  // E-NABAVKI SEARCHERS - People searching for the government portal
  'Е-Набавки - Portal Searchers': {
    bid: CONFIG.HIGH_INTENT_BID,
    keywords: [
      { text: '[е набавки]', matchType: 'EXACT' },
      { text: '[e nabavki]', matchType: 'EXACT' },
      { text: '[енабавки]', matchType: 'EXACT' },
      { text: '[e-nabavki.gov.mk]', matchType: 'EXACT' },
      { text: '[е набавки пребарување]', matchType: 'EXACT' },
      { text: '[е набавки тендери]', matchType: 'EXACT' },
      { text: '"е набавки"', matchType: 'PHRASE' },
      { text: '"e-nabavki"', matchType: 'PHRASE' },
      { text: '"е набавки македонија"', matchType: 'PHRASE' },
      { text: '"пребарување е набавки"', matchType: 'PHRASE' }
    ]
  },

  // INDUSTRY SPECIFIC - Higher conversion potential
  'Индустрии - Industry Specific': {
    bid: CONFIG.HIGH_INTENT_BID,
    keywords: [
      { text: '[тендери градежништво]', matchType: 'EXACT' },
      { text: '[градежни тендери]', matchType: 'EXACT' },
      { text: '[тендери ит]', matchType: 'EXACT' },
      { text: '[ит тендери македонија]', matchType: 'EXACT' },
      { text: '[тендери здравство]', matchType: 'EXACT' },
      { text: '[медицински тендери]', matchType: 'EXACT' },
      { text: '[тендери образование]', matchType: 'EXACT' },
      { text: '[тендери транспорт]', matchType: 'EXACT' },
      { text: '[тендери енергетика]', matchType: 'EXACT' },
      { text: '[тендери храна]', matchType: 'EXACT' },
      { text: '"тендери градежништво"', matchType: 'PHRASE' },
      { text: '"набавки градежништво"', matchType: 'PHRASE' },
      { text: '"ит тендери"', matchType: 'PHRASE' },
      { text: '"софтвер тендери"', matchType: 'PHRASE' },
      { text: '"медицинска опрема тендери"', matchType: 'PHRASE' }
    ]
  },

  // ALERT SEEKERS - People wanting notifications
  'Известувања - Alert Seekers': {
    bid: CONFIG.MEDIUM_INTENT_BID,
    keywords: [
      { text: '[известувања за тендери]', matchType: 'EXACT' },
      { text: '[тендер известување]', matchType: 'EXACT' },
      { text: '[нови тендери денес]', matchType: 'EXACT' },
      { text: '[најнови тендери]', matchType: 'EXACT' },
      { text: '[дневни тендери]', matchType: 'EXACT' },
      { text: '"известувања за тендери"', matchType: 'PHRASE' },
      { text: '"нови тендери"', matchType: 'PHRASE' },
      { text: '"тендери денес"', matchType: 'PHRASE' },
      { text: '"најнови тендери македонија"', matchType: 'PHRASE' },
      { text: '"следи тендери"', matchType: 'PHRASE' }
    ]
  },

  // PROBLEM AWARE - People struggling with manual search
  'Проблем - Problem Aware': {
    bid: CONFIG.MEDIUM_INTENT_BID,
    keywords: [
      { text: '"како да најдам тендер"', matchType: 'PHRASE' },
      { text: '"каде има тендери"', matchType: 'PHRASE' },
      { text: '"пребарување тендери"', matchType: 'PHRASE' },
      { text: '"барање тендери"', matchType: 'PHRASE' },
      { text: '"листа на тендери"', matchType: 'PHRASE' },
      { text: '"сите тендери"', matchType: 'PHRASE' },
      { text: '"како да учествувам на тендер"', matchType: 'PHRASE' },
      { text: '"аплицирање на тендер"', matchType: 'PHRASE' },
      { text: '"cpv кодови"', matchType: 'PHRASE' },
      { text: '"cpv класификација"', matchType: 'PHRASE' }
    ]
  },

  // ENGLISH - International/English speakers
  'English - International': {
    bid: CONFIG.MEDIUM_INTENT_BID,
    keywords: [
      { text: '[macedonia tenders]', matchType: 'EXACT' },
      { text: '[north macedonia public procurement]', matchType: 'EXACT' },
      { text: '[north macedonia tenders]', matchType: 'EXACT' },
      { text: '[macedonian government contracts]', matchType: 'EXACT' },
      { text: '[e-nabavki]', matchType: 'EXACT' },
      { text: '"macedonia tenders"', matchType: 'PHRASE' },
      { text: '"north macedonia procurement"', matchType: 'PHRASE' },
      { text: '"tender opportunities macedonia"', matchType: 'PHRASE' },
      { text: '"government contracts balkans"', matchType: 'PHRASE' },
      { text: '"public procurement macedonia"', matchType: 'PHRASE' }
    ]
  },

  // COMPETITORS - Capture competitor traffic
  'Конкуренти - Competitors': {
    bid: CONFIG.LOW_INTENT_BID,
    keywords: [
      { text: '[tendersontime]', matchType: 'EXACT' },
      { text: '[globaltenders]', matchType: 'EXACT' },
      { text: '[tendersinfo]', matchType: 'EXACT' },
      { text: '[balkan tender watch]', matchType: 'EXACT' },
      { text: '[tender watch]', matchType: 'EXACT' }
    ]
  }
};

// ============== AD COPY - URGENCY & FOMO ==============
var ADS = {
  // Main ad group - Macedonian High Intent
  'Јавни Набавки - High Intent': {
    headlines: [
      // Max 30 characters each - URGENCY & FOMO focused
      'Тендери Што Ги Пропуштате?',      // 26 - Fear of missing
      'Додека Вие Барате, Други Печалат', // 30 - Others winning
      '847 Нови Тендери Денес',           // 23 - Specific number
      'Конкуренцијата Веќе Знае',         // 25 - Competitors ahead
      'Стоп на Рачно Пребарување',        // 26 - Pain point
      'AI Ги Најде - Вие Не',             // 21 - AI advantage
      'Зошто Секогаш Доцните?',           // 22 - Why always late
      'Милиони Пропуштени Тендери',       // 27 - Millions missed
      'Другите Користат nabavkidata',     // 29 - Social proof
      '10.000+ Компании Веќе Знаат',      // 28 - Social proof
      'Престанете Да Губите Време',       // 27 - Time wasting
      'Секој Ден = Пропуштен Тендер',     // 28 - Daily loss
      'Бидете Први, Не Последни',         // 26 - Be first
      'Автоматски Тендер Аларми',         // 25 - Feature
      'Бесплатно Пробајте Денес'          // 24 - Free trial
    ],
    descriptions: [
      // Max 90 characters each - PAIN + SOLUTION + URGENCY
      'Додека рачно пребарувате e-nabavki, конкуренцијата веќе аплицира. AI ги најде сите!', // 89
      'Секој ден пропуштате тендери вредни милиони. Вашата конкуренција не пропушта. Зошто вие?', // 90
      'Професионалците користат nabavkidata. 847 нови тендери денес. Колку пропуштивте?', // 87
      'Стоп на часови губење време на e-nabavki. AI наоѓа релевантни тендери за 30 секунди.', // 90
      'Вашите конкуренти добиваат известувања за тендери пред вас. Време е да ги престигнете.', // 90
      'Бесплатна регистрација. Почнете да добивате тендери што ги пропуштате секој ден.', // 85
      '10.000+ компании веќе го користат. Не дозволувајте конкуренцијата да ве престигне.', // 88
      'AI анализа на сите јавни набавки. Добивајте само релевантни тендери, без губење време.', // 90
    ],
    finalUrl: CONFIG.FINAL_URL,
    path1: 'тендери',
    path2: 'денес'
  },

  // E-Nabavki searchers - Position as better alternative
  'Е-Набавки - Portal Searchers': {
    headlines: [
      'e-nabavki е Застарено',             // 22
      'Подобро од e-nabavki',              // 20
      'e-nabavki + AI = Победа',           // 22
      'Уморни од e-nabavki?',              // 19
      'e-nabavki Алтернатива',             // 22
      'Надградете го e-nabavki',           // 23
      'e-nabavki на Стероиди',             // 22
      'Паметно e-nabavki',                 // 18
      'e-nabavki со AI Мозок',             // 22
      'Бегајте од Рачно Барање',           // 24
      'Автоматско e-nabavki',              // 20
      'e-nabavki Известувања',             // 22
      'AI за Јавни Набавки',               // 20
      'Другите Веќе Преминаа',             // 24
      'Не Губете Време Рачно'              // 21
    ],
    descriptions: [
      'Уморни од бавно пребарување на e-nabavki? Нашиот AI го прави за вас 100x побрзо.', // 86
      'e-nabavki е само почеток. nabavkidata е каде паметните компании ги наоѓаат тендерите.', // 90
      'Додека вие рачно барате на e-nabavki, конкуренцијата добива автоматски известувања.', // 90
      'Престанете да губите часови на e-nabavki. AI ги наоѓа сите релевантни тендери за вас.', // 90
      'e-nabavki + AI пребарување + автоматски аларми = Никогаш повеќе пропуштен тендер.', // 88
      'Секој ден 847 нови тендери на e-nabavki. Колку гледате? AI ги гледа сите за вас.', // 87
      'Компаниите што печалат не седат на e-nabavki цел ден. Тие користат nabavkidata.', // 87
      'Бесплатно пробајте. Видете што пропуштате секој ден на e-nabavki. Ќе бидете шокирани.', // 90
    ],
    finalUrl: CONFIG.FINAL_URL,
    path1: 'e-nabavki',
    path2: 'upgrade'
  },

  // Industry specific
  'Индустрии - Industry Specific': {
    headlines: [
      'Градежни Тендери - AI',             // 21
      'ИТ Тендери Македонија',             // 22
      'Медицински Тендери Денес',          // 25
      'Тендери За Вашата Индустрија',      // 28
      'Специјализирани Тендери',           // 23
      'CPV Код Пребарување',               // 20
      'Тендери по Категорија',             // 22
      'Филтрирајте по Индустрија',         // 26
      'Само Релевантни Тендери',           // 24
      'Без Шум, Само Тендери',             // 22
      'Точно Што Ви Треба',                // 19
      'Персонализирани Резултати',         // 26
      'AI Знае Што Барате',                // 21
      'Тендери за Вас Лично',              // 21
      'Индустриски Аларми'                 // 18
    ],
    descriptions: [
      'AI ги филтрира 10.000+ тендери и ви покажува само оние за вашата индустрија. Прецизно.', // 90
      'Градежништво, ИТ, здравство, транспорт - добивајте тендери само за вашата дејност.', // 88
      'Конкуренцијата во вашата индустрија веќе ги добива тендерите прва. Приклучете се.', // 89
      'CPV код пребарување + AI филтрирање = Само тендери што навистина ви требаат.', // 82
      'Не губете време на ирелевантни тендери. AI знае точно што барате. Пробајте бесплатно.', // 90
      'Секој ден нови тендери во вашата индустрија. Добивајте ги први, пред конкуренцијата.', // 90
      'Поставете филтри еднаш, добивајте релевантни тендери засекогаш. AI работи 24/7.', // 87
      'Вашите конкуренти добиваат индустриски аларми. Вие сè уште рачно барате?', // 77
    ],
    finalUrl: CONFIG.FINAL_URL,
    path1: 'индустрии',
    path2: 'тендери'
  },

  // Alert seekers
  'Известувања - Alert Seekers': {
    headlines: [
      'Тендер Аларми 24/7',                // 18
      'Никогаш Пропуштен Тендер',          // 25
      'Известувања во Секунда',            // 24
      'Бидете Први Што Знаете',            // 24
      'Автоматски Email Аларми',           // 23
      'AI Ве Известува Прв',               // 21
      'Стоп на Пропуштени Шанси',          // 25
      'Аларм = Победен Тендер',            // 23
      'Мобилни Известувања',               // 20
      'Реално Време Аларми',               // 20
      'Поставете и Заборавете',            // 23
      'AI Работи Додека Спиете',           // 25
      'Секој Тендер, Секој Пат',           // 23
      'Нула Пропуштени Тендери',           // 23
      '100% Покриеност'                    // 15
    ],
    descriptions: [
      'Додека вие спиете, AI ги следи сите нови тендери. Утре ќе имате се во inbox-от.', // 87
      'Поставете критериуми еднаш. Добивајте известувања засекогаш. Никогаш пропуштен тендер.', // 90
      'Вашата конкуренција добива аларми во 6 наутро. Вие дознавате на пладне. Тоа е проблем.', // 90
      'Email + мобилни известувања = Секој релевантен тендер, секој пат, веднаш.', // 75
      'AI ги скенира 847 нови тендери дневно и ве известува само за вашите. Бесплатно.', // 87
      'Компаниите со аларми печалат повеќе тендери. Математика е едноставна. Приклучете се.', // 90
      'Престанете да проверувате e-nabavki секој час. Нека AI ве извести кога треба.', // 82
      'Секој пропуштен тендер = пропуштени пари. Нашите аларми гарантираат 0 пропуштени.', // 88
    ],
    finalUrl: CONFIG.FINAL_URL,
    path1: 'аларми',
    path2: 'тендери'
  },

  // Problem aware
  'Проблем - Problem Aware': {
    headlines: [
      'Уморни од Барање Тендери?',         // 26
      'Пронајдете Тендер за 30сек',        // 27
      'Стоп на Фрустрација',               // 20
      'Решение за Тендер Хаос',            // 24
      'Најдете го Вистинскиот',            // 24
      'Без Губење Време',                  // 17
      'Едноставно Пребарување',            // 23
      'Тендери на Дланка',                 // 19
      'AI го Прави за Вас',                // 21
      'Работете Паметно',                  // 18
      'Автоматизирајте Барањето',          // 25
      'Од Хаос до Систем',                 // 18
      'Заштедете 10ч Неделно',             // 22
      'Ефикасно Пребарување',              // 22
      'Паметен Начин'                      // 14
    ],
    descriptions: [
      'Колку часови неделно губите барајќи тендери? AI го прави истото за 30 секунди.', // 84
      'Рачното пребарување е од минатото. Паметните компании користат AI. Вие?', // 77
      'Фрустрирани од e-nabavki? Не сте сами. 10.000+ компании преминаа на nabavkidata.', // 87
      'Од 847 дневни тендери, само 5-10 се релевантни за вас. AI ги наоѓа. Вие не можете.', // 90
      'Секој час на рачно барање = 1 час помалку за подготовка на понуда. Работете паметно.', // 90
      'CPV кодови, филтри, известувања - сè на едно место. Престанете да губите време.', // 85
      'Вашата конкуренција не бара рачно. Тие имаат систем. Време е и вие да имате.', // 84
      'Бесплатна регистрација. Видете колку е лесно да најдете тендер. Ќе се прашувате зошто досега.', // 97 - trim to 90
    ],
    finalUrl: CONFIG.FINAL_URL,
    path1: 'лесно',
    path2: 'барање'
  },

  // English
  'English - International': {
    headlines: [
      'Macedonia Tenders - AI Search',     // 26
      'Miss Tenders? Never Again',         // 24
      'Your Competitors Know First',       // 26
      'AI-Powered Tender Alerts',          // 23
      'North Macedonia Contracts',         // 26
      '847 New Tenders Today',             // 22
      'Stop Manual Searching',             // 22
      'Tender Intelligence Platform',      // 29
      'Get Notified First',                // 19
      'Win More Government Bids',          // 25
      'Balkans Procurement Hub',           // 24
      'Smart Tender Discovery',            // 23
      'Automated Tender Alerts',           // 24
      'Free Trial - Start Now',            // 21
      'Beat Your Competition'              // 21
    ],
    descriptions: [
      'While you manually search e-nabavki, competitors already applied. AI found everything.', // 90
      'Every day you miss million-worth tenders. Your competition doesn\'t. Why do you?', // 84
      '10,000+ companies use nabavkidata for Macedonia tenders. Don\'t let competition win.', // 89
      'AI scans 847 new tenders daily and alerts you instantly. Never miss an opportunity.', // 89
      'Stop wasting hours on e-nabavki. Get only relevant North Macedonia tenders via AI.', // 88
      'Free registration. See what you\'ve been missing every day. You\'ll be shocked.', // 84
      'Your competitors get tender alerts before you. Time to level the playing field.', // 86
      'Set filters once, receive relevant tenders forever. AI works 24/7 for you.', // 79
    ],
    finalUrl: CONFIG.FINAL_URL,
    path1: 'tenders',
    path2: 'macedonia'
  },

  // Competitors
  'Конкуренти - Competitors': {
    headlines: [
      'Подобро од TendersOnTime',           // 24
      'Macedonian Tender Expert',          // 25
      'Локална Алтернатива',               // 20
      'Специјализирано за МК',             // 22
      'Подобро Покривање',                 // 18
      'AI vs Стари Платформи',             // 22
      'Македонски Тендер Експерт',         // 26
      'Најдобар Избор за МК',              // 21
      'Локална Поддршка',                  // 17
      'Разбираме Македонски',              // 22
      'Подобри Резултати',                 // 18
      'Попаметно Пребарување',             // 22
      'Прецизни МК Тендери',               // 20
      'Бесплатна Проба',                   // 15
      'Преминете Денес'                    // 16
    ],
    descriptions: [
      'Меѓународните платформи не го разбираат македонскиот пазар. Ние сме локални експерти.', // 90
      'Зошто плаќате за меѓународни платформи? nabavkidata е специјализиран за Македонија.', // 90
      'AI направен за македонски тендери. Подобро покривање, подобри резултати, подобра цена.', // 90
      'Локална поддршка на македонски. Разбираме вашиот пазар подобро од кој било друг.', // 88
      'Преминете од меѓународни на локална платформа. Подобри резултати, гарантирано.', // 85
      'TendersOnTime, GlobalTenders? Пробајте nabavkidata - специјализиран за Македонија.', // 88
      'Македонски пазар бара македонско решение. 10.000+ компании веќе преминаа.', // 79
      'Бесплатна проба. Споредете ги резултатите со вашата сегашна платформа. Ќе видите.', // 89
    ],
    finalUrl: CONFIG.FINAL_URL,
    path1: 'споредба',
    path2: 'платформи'
  }
};

// ============== NEGATIVE KEYWORDS ==============
var NEGATIVE_KEYWORDS = [
  // Job seekers - EXACT
  '[работа]',
  '[вработување]',
  '[job]',
  '[jobs]',
  '[career]',
  '[кариера]',
  '[оглас за работа]',
  '[employment]',
  '[hiring]',
  '[cv]',
  '[резиме]',

  // Free seekers - PHRASE
  '"бесплатно преземање"',
  '"free download"',
  '"бесплатен софтвер"',
  '"free software"',

  // Students/Academic - EXACT
  '[туторијал]',
  '[tutorial]',
  '[есеј]',
  '[essay]',
  '[семинарска]',
  '[дипломска]',
  '[магистерска]',
  '[homework]',
  '[домашна задача]',
  '[проект за училиште]',

  // Legal/Research - EXACT
  '[закон]',
  '[law]',
  '[legislation]',
  '[регулатива]',
  '[правилник]',
  '[закон за јавни набавки]',

  // Downloads/Templates - PHRASE
  '"pdf download"',
  '"шаблон"',
  '"template"',
  '"формулар"',
  '"образец"',
  '"документ download"',

  // Other countries - EXACT
  '[србија тендери]',
  '[serbia tenders]',
  '[croatia tenders]',
  '[bulgaria tenders]',
  '[hrvatska natječaji]',

  // Irrelevant - EXACT
  '[рецепт]',
  '[recipe]',
  '[игра]',
  '[game]',
  '[филм]',
  '[movie]',
  '[песна]',
  '[song]',
  '[wikipedia]',
  '[дефиниција]',
  '[definition]',
  '[што е тендер]',
  '[what is tender]'
];

// ============== SITELINKS ==============
var SITELINKS = [
  {
    text: 'Пребарај Тендери',
    description1: 'AI пребарување на сите тендери',
    description2: 'Резултати за 30 секунди',
    finalUrl: 'https://nabavkidata.com/tenders'
  },
  {
    text: 'Бесплатна Проба',
    description1: 'Регистрирајте се бесплатно',
    description2: 'Без кредитна картичка',
    finalUrl: 'https://nabavkidata.com/auth/register'
  },
  {
    text: 'Цени и Планови',
    description1: 'Од бесплатно до Enterprise',
    description2: 'Најдете го вашиот план',
    finalUrl: 'https://nabavkidata.com/billing/plans'
  },
  {
    text: 'Тендер Аларми',
    description1: 'Автоматски известувања',
    description2: '24/7 мониторинг',
    finalUrl: 'https://nabavkidata.com/alerts'
  },
  {
    text: 'AI Анализа',
    description1: 'Паметни увиди',
    description2: 'Анализа на конкуренција',
    finalUrl: 'https://nabavkidata.com/analytics'
  },
  {
    text: 'За Компании',
    description1: 'Enterprise решенија',
    description2: 'API пристап',
    finalUrl: 'https://nabavkidata.com/enterprise'
  }
];

// ============== CALLOUTS ==============
var CALLOUTS = [
  '847 Нови Тендери Дневно',
  'AI Пребарување',
  '24/7 Мониторинг',
  'Бесплатна Регистрација',
  'Email Известувања',
  '10.000+ Компании',
  'Македонски Експерти',
  'Без Пропуштени Тендери',
  'CPV Филтрирање',
  'Извоз во Excel',
  'Мобилен Пристап',
  'Локална Поддршка'
];

// ============== MAIN FUNCTION ==============
function main() {
  Logger.log('===========================================');
  Logger.log('NabavkiData Google Ads Setup & Optimization');
  Logger.log('===========================================');
  Logger.log('');

  // Get campaign
  var campaignIterator = AdsApp.campaigns()
    .withCondition('Name CONTAINS "' + CONFIG.CAMPAIGN_NAME + '"')
    .get();

  if (!campaignIterator.hasNext()) {
    Logger.log('ERROR: Campaign "' + CONFIG.CAMPAIGN_NAME + '" not found!');
    Logger.log('Please create the campaign first, then run this script.');
    return;
  }

  var campaign = campaignIterator.next();
  Logger.log('Found campaign: ' + campaign.getName());
  Logger.log('');

  // Run setup or optimization based on campaign age
  var stats = campaign.getStatsFor('ALL_TIME');

  if (stats.getImpressions() < 100) {
    Logger.log('Campaign is new - running SETUP mode...');
    Logger.log('');
    runSetup(campaign);
  } else {
    Logger.log('Campaign has data - running OPTIMIZATION mode...');
    Logger.log('');
    runOptimization(campaign);
  }
}

// ============== SETUP MODE ==============
function runSetup(campaign) {
  var results = {
    adGroupsCreated: 0,
    keywordsAdded: 0,
    adsCreated: 0,
    negativeKeywordsAdded: 0
  };

  // 1. Create Ad Groups with Keywords and Ads
  Logger.log('--- Creating Ad Groups ---');
  for (var adGroupName in AD_GROUPS) {
    var adGroupConfig = AD_GROUPS[adGroupName];

    // Check if ad group exists
    var existingAdGroup = campaign.adGroups()
      .withCondition('Name = "' + adGroupName + '"')
      .get();

    var adGroup;
    if (existingAdGroup.hasNext()) {
      adGroup = existingAdGroup.next();
      Logger.log('Ad group exists: ' + adGroupName);
    } else {
      // Create new ad group
      var adGroupBuilder = campaign.newAdGroupBuilder()
        .withName(adGroupName)
        .withCpc(adGroupConfig.bid)
        .withStatus('ENABLED')
        .build();

      if (adGroupBuilder.isSuccessful()) {
        adGroup = adGroupBuilder.getResult();
        Logger.log('CREATED ad group: ' + adGroupName + ' (bid: €' + adGroupConfig.bid + ')');
        results.adGroupsCreated++;
      } else {
        Logger.log('ERROR creating ad group: ' + adGroupName);
        continue;
      }
    }

    // Add keywords to ad group
    Logger.log('  Adding keywords...');
    for (var i = 0; i < adGroupConfig.keywords.length; i++) {
      var kw = adGroupConfig.keywords[i];
      try {
        var keywordOperation = adGroup.newKeywordBuilder()
          .withText(kw.text)
          .withCpc(adGroupConfig.bid)
          .build();

        if (keywordOperation.isSuccessful()) {
          results.keywordsAdded++;
        }
      } catch (e) {
        // Keyword might already exist
      }
    }
    Logger.log('  Keywords processed: ' + adGroupConfig.keywords.length);

    // Create ads for this ad group
    if (ADS[adGroupName]) {
      Logger.log('  Creating responsive search ad...');
      var adConfig = ADS[adGroupName];

      try {
        var adOperation = adGroup.newAd().responsiveSearchAdBuilder()
          .withHeadlines(adConfig.headlines.slice(0, 15))
          .withDescriptions(adConfig.descriptions.slice(0, 4))
          .withFinalUrl(adConfig.finalUrl)
          .withPath1(adConfig.path1)
          .withPath2(adConfig.path2)
          .build();

        if (adOperation.isSuccessful()) {
          Logger.log('  CREATED responsive search ad');
          results.adsCreated++;
        }
      } catch (e) {
        Logger.log('  Note: Could not create ad (may already exist)');
      }
    }

    Logger.log('');
  }

  // 2. Add Negative Keywords
  Logger.log('--- Adding Negative Keywords ---');
  for (var i = 0; i < NEGATIVE_KEYWORDS.length; i++) {
    try {
      campaign.createNegativeKeyword(NEGATIVE_KEYWORDS[i]);
      results.negativeKeywordsAdded++;
    } catch (e) {
      // May already exist
    }
  }
  Logger.log('Negative keywords processed: ' + NEGATIVE_KEYWORDS.length);
  Logger.log('');

  // 3. Log results
  Logger.log('========== SETUP COMPLETE ==========');
  Logger.log('Ad Groups Created: ' + results.adGroupsCreated);
  Logger.log('Keywords Added: ' + results.keywordsAdded);
  Logger.log('Ads Created: ' + results.adsCreated);
  Logger.log('Negative Keywords: ' + results.negativeKeywordsAdded);
  Logger.log('====================================');
  Logger.log('');
  Logger.log('NEXT STEPS:');
  Logger.log('1. Review the ad groups and keywords in Google Ads');
  Logger.log('2. Add sitelinks and callouts manually (script cannot add extensions to Performance Max)');
  Logger.log('3. Set the script to run daily for optimization');
}

// ============== OPTIMIZATION MODE ==============
function runOptimization(campaign) {
  var results = {
    keywordsPaused: 0,
    keywordsBidIncreased: 0,
    keywordsBidDecreased: 0,
    negativeKeywordsAdded: 0,
    totalSpend: 0,
    totalConversions: 0,
    totalClicks: 0,
    totalImpressions: 0
  };

  // 1. Get campaign stats
  var stats = campaign.getStatsFor(CONFIG.DATE_RANGE);
  results.totalSpend = stats.getCost();
  results.totalConversions = stats.getConversions();
  results.totalClicks = stats.getClicks();
  results.totalImpressions = stats.getImpressions();

  // 2. Optimize keywords
  Logger.log('--- Optimizing Keywords ---');
  var keywordIterator = campaign.keywords()
    .withCondition('Status = ENABLED')
    .forDateRange(CONFIG.DATE_RANGE)
    .get();

  while (keywordIterator.hasNext()) {
    var keyword = keywordIterator.next();
    var kwStats = keyword.getStatsFor(CONFIG.DATE_RANGE);

    var impressions = kwStats.getImpressions();
    var clicks = kwStats.getClicks();
    var cost = kwStats.getCost();
    var conversions = kwStats.getConversions();
    var ctr = impressions > 0 ? clicks / impressions : 0;
    var cpc = clicks > 0 ? cost / clicks : 0;

    if (impressions < CONFIG.MIN_IMPRESSIONS) continue;

    var keywordText = keyword.getText();

    // PAUSE: No conversions, high cost
    if (clicks >= CONFIG.MIN_CLICKS && conversions === 0 && cost > CONFIG.MAX_COST_PER_CONVERSION) {
      Logger.log('PAUSING: ' + keywordText + ' (€' + cost.toFixed(2) + ' spent, 0 conversions)');
      keyword.pause();
      results.keywordsPaused++;
      continue;
    }

    // DECREASE BID: Poor CTR or high CPC
    if (ctr < CONFIG.MIN_CTR || cpc > CONFIG.MAX_CPC) {
      var currentBid = keyword.bidding().getCpc();
      if (currentBid) {
        var newBid = Math.max(currentBid * 0.8, 0.10);
        keyword.bidding().setCpc(newBid);
        Logger.log('DECREASED BID: ' + keywordText + ' (€' + currentBid.toFixed(2) + ' -> €' + newBid.toFixed(2) + ')');
        results.keywordsBidDecreased++;
      }
      continue;
    }

    // INCREASE BID: Good performance
    if (conversions > 0 && ctr > CONFIG.MIN_CTR * 2) {
      var currentBid = keyword.bidding().getCpc();
      if (currentBid) {
        var newBid = Math.min(currentBid * 1.15, CONFIG.MAX_CPC * 1.5);
        keyword.bidding().setCpc(newBid);
        Logger.log('INCREASED BID: ' + keywordText + ' (€' + currentBid.toFixed(2) + ' -> €' + newBid.toFixed(2) + ')');
        results.keywordsBidIncreased++;
      }
    }
  }

  // 3. Add negative keywords from search terms
  Logger.log('');
  Logger.log('--- Analyzing Search Terms ---');
  try {
    var searchTermIterator = campaign.searchTerms()
      .forDateRange(CONFIG.DATE_RANGE)
      .withCondition('Clicks > 0')
      .withCondition('Conversions = 0')
      .orderBy('Cost DESC')
      .withLimit(50)
      .get();

    while (searchTermIterator.hasNext()) {
      var searchTerm = searchTermIterator.next();
      var query = searchTerm.getQuery().toLowerCase();
      var termStats = searchTerm.getStatsFor(CONFIG.DATE_RANGE);

      var shouldBlock = false;

      // Check against negative keyword patterns
      var blockPatterns = ['работа', 'job', 'вработување', 'бесплатно', 'free', 'tutorial', 'туторијал', 'pdf', 'download', 'шаблон'];
      for (var i = 0; i < blockPatterns.length; i++) {
        if (query.indexOf(blockPatterns[i]) !== -1) {
          shouldBlock = true;
          break;
        }
      }

      // Block high-cost, no-conversion terms
      if (termStats.getCost() > CONFIG.MAX_COST_PER_CONVERSION / 2 && termStats.getConversions() === 0) {
        shouldBlock = true;
      }

      if (shouldBlock) {
        try {
          campaign.createNegativeKeyword('[' + query + ']');
          Logger.log('BLOCKED: "' + query + '" (€' + termStats.getCost().toFixed(2) + ', 0 conv)');
          results.negativeKeywordsAdded++;
        } catch (e) {}
      }
    }
  } catch (e) {
    Logger.log('Note: Could not access search terms (may require more data)');
  }

  // 4. Report
  Logger.log('');
  Logger.log('========== OPTIMIZATION RESULTS ==========');
  Logger.log('Period: ' + CONFIG.DATE_RANGE);
  Logger.log('');
  Logger.log('PERFORMANCE:');
  Logger.log('  Impressions: ' + results.totalImpressions.toLocaleString());
  Logger.log('  Clicks: ' + results.totalClicks.toLocaleString());
  Logger.log('  Spend: €' + results.totalSpend.toFixed(2));
  Logger.log('  Conversions: ' + results.totalConversions);
  Logger.log('  CTR: ' + (results.totalImpressions > 0 ? (results.totalClicks / results.totalImpressions * 100).toFixed(2) : 0) + '%');
  Logger.log('  CPC: €' + (results.totalClicks > 0 ? (results.totalSpend / results.totalClicks).toFixed(2) : 0));
  Logger.log('');
  Logger.log('ACTIONS:');
  Logger.log('  Keywords Paused: ' + results.keywordsPaused);
  Logger.log('  Bids Increased: ' + results.keywordsBidIncreased);
  Logger.log('  Bids Decreased: ' + results.keywordsBidDecreased);
  Logger.log('  Negatives Added: ' + results.negativeKeywordsAdded);
  Logger.log('==========================================');

  // 5. Send email report
  if (CONFIG.EMAIL && CONFIG.EMAIL !== 'your-email@example.com') {
    var subject = 'NabavkiData Ads Report - ' + new Date().toLocaleDateString();
    var body = 'NabavkiData Google Ads Optimization Report\n\n' +
      'Period: ' + CONFIG.DATE_RANGE + '\n\n' +
      'PERFORMANCE:\n' +
      '- Impressions: ' + results.totalImpressions.toLocaleString() + '\n' +
      '- Clicks: ' + results.totalClicks.toLocaleString() + '\n' +
      '- Spend: €' + results.totalSpend.toFixed(2) + '\n' +
      '- Conversions: ' + results.totalConversions + '\n\n' +
      'ACTIONS TAKEN:\n' +
      '- Keywords Paused: ' + results.keywordsPaused + '\n' +
      '- Bids Increased: ' + results.keywordsBidIncreased + '\n' +
      '- Bids Decreased: ' + results.keywordsBidDecreased + '\n' +
      '- Negatives Added: ' + results.negativeKeywordsAdded;

    MailApp.sendEmail(CONFIG.EMAIL, subject, body);
    Logger.log('');
    Logger.log('Email report sent to: ' + CONFIG.EMAIL);
  }
}
