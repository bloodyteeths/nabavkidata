// NabavkiData Company Presentation v2
// Modern SaaS pitch deck with real platform screenshots

#set page(paper: "a4", margin: (x: 0cm, y: 0cm))
#set text(font: "Helvetica", size: 11pt, fill: rgb("#e2e8f0"))

// Brand colors — matching the platform's dark theme
#let purple = rgb("#7c3aed")
#let purple-light = rgb("#a78bfa")
#let purple-dark = rgb("#5b21b6")
#let dark-bg = rgb("#0c0a1a")
#let card-bg = rgb("#1a1830")
#let card-border = rgb("#2d2b45")
#let cyan = rgb("#06b6d4")
#let green = rgb("#22c55e")
#let red-accent = rgb("#ef4444")
#let orange = rgb("#f97316")
#let slate = rgb("#94a3b8")
#let white = rgb("#ffffff")

// ============================================================
// PAGE 1: COVER — Bold, dark, premium
// ============================================================
#page(background: {
  place(dx: 0cm, dy: 0cm, rect(width: 100%, height: 100%, fill: dark-bg))
  // Gradient glow
  place(dx: 3cm, dy: 5cm, circle(radius: 12cm, fill: rgb(124, 58, 237, 12)))
  place(dx: 12cm, dy: 20cm, circle(radius: 8cm, fill: rgb(6, 182, 212, 8)))
})[
  #set align(center)
  #v(1.5cm)

  // Logo
  #image("logo.png", width: 3.5cm)
  #v(0.4cm)

  #text(size: 36pt, weight: "bold", fill: white, tracking: 0.5pt)[nabavkidata]

  #v(0.2cm)

  #text(size: 10pt, fill: slate, tracking: 3pt, weight: "medium")[AI-POWERED TENDER INTELLIGENCE]

  #v(0.8cm)

  #block(width: 80%)[
    #text(size: 22pt, fill: white, weight: "bold")[
      Нефер Предност во Јавните Набавки
    ]
  ]

  #v(0.4cm)

  #block(width: 70%)[
    #text(size: 11pt, fill: slate)[
      Единствената платформа во Македонија која ги комбинира сите тендери, AI анализа на документи, историски цени и анализа на конкуренцијата — на едно место.
    ]
  ]

  #v(0.7cm)

  // Stats row
  #block(
    width: 85%,
    inset: (x: 1.5cm, y: 0.5cm),
    radius: 12pt,
    fill: card-bg,
    stroke: (paint: card-border, thickness: 1pt),
  )[
    #grid(
      columns: (1fr, 1fr, 1fr, 1fr),
      gutter: 0.3cm,
      align(center)[
        #text(size: 20pt, weight: "bold", fill: purple-light)[270K+]
        #linebreak()
        #text(size: 8pt, fill: slate)[тендери]
      ],
      align(center)[
        #text(size: 20pt, weight: "bold", fill: purple-light)[40K+]
        #linebreak()
        #text(size: 8pt, fill: slate)[документи]
      ],
      align(center)[
        #text(size: 20pt, weight: "bold", fill: purple-light)[17]
        #linebreak()
        #text(size: 8pt, fill: slate)[години историја]
      ],
      align(center)[
        #text(size: 20pt, weight: "bold", fill: purple-light)[4,365+]
        #linebreak()
        #text(size: 8pt, fill: slate)[компании]
      ],
    )
  ]

  #v(0.5cm)

  // Hero screenshot — the actual platform
  #block(
    width: 85%,
    radius: 8pt,
    clip: true,
    stroke: (paint: card-border, thickness: 1pt),
  )[
    #image("ss_hero.png", width: 100%)
  ]

  #v(1fr)
  #text(size: 8pt, fill: rgb("#475569"))[nabavkidata.com #h(1cm) hello\@nabavkidata.com #h(1cm) +389 70 253 467]
  #v(0.4cm)
]

// ============================================================
// PAGE 2: PROBLEM + COMPARISON
// ============================================================
#page(background: {
  place(dx: 0cm, dy: 0cm, rect(width: 100%, height: 100%, fill: white))
})[
  #set text(fill: rgb("#1e293b"))

  // Purple top bar
  #block(
    width: 100%, height: 0.35cm,
    fill: gradient.linear(purple-dark, purple, cyan, angle: 0deg),
  )[]

  #block(inset: (x: 2.2cm, y: 1.5cm))[

    #text(size: 9pt, fill: purple, weight: "bold", tracking: 2pt)[ПРОБЛЕМ]
    #v(0.2cm)
    #text(size: 24pt, weight: "bold", fill: rgb("#0f172a"))[
      Што губите без вистински податоци?
    ]
    #v(0.5cm)

    // Value prop screenshot from the actual platform
    #block(
      width: 100%,
      radius: 10pt,
      clip: true,
      stroke: (paint: rgb("#e2e8f0"), thickness: 1pt),
    )[
      #image("ss_value.png", width: 100%)
    ]

    #v(0.6cm)

    // Comparison table — manual vs AI (from the platform)
    #block(
      width: 100%,
      radius: 10pt,
      clip: true,
      stroke: (paint: rgb("#e2e8f0"), thickness: 1pt),
    )[
      #image("ss_compare.png", width: 100%)
    ]
  ]
]

// ============================================================
// PAGE 3: TENDER SEARCH + AI ANALYSIS (real product)
// ============================================================
#page(background: {
  place(dx: 0cm, dy: 0cm, rect(width: 100%, height: 100%, fill: dark-bg))
  place(dx: -2cm, dy: 14cm, circle(radius: 10cm, fill: rgb(124, 58, 237, 8)))
})[

  #block(inset: (x: 2.2cm, y: 1.2cm))[

    #text(size: 9pt, fill: cyan, weight: "bold", tracking: 2pt)[ТЕНДЕРИ И AI]
    #v(0.2cm)
    #text(size: 22pt, weight: "bold", fill: white)[
      Пребарувајте, анализирајте, победувајте
    ]
    #v(0.15cm)
    #text(size: 10pt, fill: slate)[
      273,000+ тендери на дофат. AI го чита секој документ наместо вас.
    ]
    #v(0.5cm)

    // Tender search screenshot
    #block(
      width: 100%,
      radius: 10pt,
      clip: true,
      stroke: (paint: card-border, thickness: 1pt),
    )[
      #image("ss_tenders.png", width: 100%)
    ]

    #v(0.4cm)

    // Two screenshots side by side: tender detail + AI chat
    #grid(
      columns: (1fr, 1fr),
      gutter: 0.4cm,

      // Tender detail with AI summary
      block(
        width: 100%,
        radius: 10pt,
        clip: true,
        stroke: (paint: card-border, thickness: 1pt),
      )[
        #image("ss_tender_detail.png", width: 100%)
      ],

      // AI assistant chat
      block(
        width: 100%,
        radius: 10pt,
        clip: true,
        stroke: (paint: card-border, thickness: 1pt),
      )[
        #image("ss_ai_chat.png", width: 100%)
      ],
    )

    #v(0.3cm)

    // Labels under screenshots
    #grid(
      columns: (1fr, 1fr),
      gutter: 0.4cm,
      align(center)[
        #text(size: 9pt, weight: "bold", fill: purple-light)[AI Резиме]
        #h(0.15cm)
        #text(size: 8pt, fill: slate)[Автоматска анализа на секој тендер]
      ],
      align(center)[
        #text(size: 9pt, weight: "bold", fill: purple-light)[AI Асистент]
        #h(0.15cm)
        #text(size: 8pt, fill: slate)[Прашајте го за документите]
      ],
    )

  ]
]

// ============================================================
// PAGE 4: COMPETITORS + PRODUCTS + FEATURES
// ============================================================
#page(background: {
  place(dx: 0cm, dy: 0cm, rect(width: 100%, height: 100%, fill: rgb("#fafafa")))
})[
  #set text(fill: rgb("#1e293b"))

  #block(
    width: 100%, height: 0.35cm,
    fill: gradient.linear(purple-dark, purple, cyan, angle: 0deg),
  )[]

  #block(inset: (x: 1.5cm, y: 0.8cm))[

    #grid(
      columns: (auto, 1fr),
      gutter: 0.5cm,
      align(left + horizon)[
        #text(size: 9pt, fill: purple, weight: "bold", tracking: 2pt)[КОНКУРЕНТИ И ЦЕНИ]
      ],
      align(right + horizon)[
        #text(size: 8pt, fill: rgb("#64748b"))[1,873 компании | 7,597 производи | Head-to-head споредби]
      ],
    )
    #v(0.3cm)

    // Competitors — full width
    #block(
      width: 100%,
      radius: 8pt,
      clip: true,
      stroke: (paint: rgb("#e2e8f0"), thickness: 1pt),
    )[
      #image("ss_competitors.png", width: 100%)
    ]

    #v(0.08cm)
    #text(size: 8pt, weight: "bold", fill: purple)[Анализа на конкуренти]
    #h(0.15cm)
    #text(size: 7.5pt, fill: rgb("#94a3b8"))[Win rate, вкупна вредност, market share и head-to-head споредби]

    #v(0.25cm)

    // Products — full width
    #block(
      width: 100%,
      radius: 8pt,
      clip: true,
      stroke: (paint: rgb("#e2e8f0"), thickness: 1pt),
    )[
      #image("ss_products.png", width: 100%)
    ]

    #v(0.08cm)
    #text(size: 8pt, weight: "bold", fill: purple)[Каталог на производи]
    #h(0.15cm)
    #text(size: 7.5pt, fill: rgb("#94a3b8"))[Историски мин, макс и просечни цени по категорија и институција]
  ]
]

// ============================================================
// PAGE 5: PRICING
// ============================================================
#page(background: {
  place(dx: 0cm, dy: 0cm, rect(width: 100%, height: 100%, fill: white))
})[
  #set text(fill: rgb("#1e293b"))

  #block(
    width: 100%, height: 0.35cm,
    fill: gradient.linear(purple-dark, purple, cyan, angle: 0deg),
  )[]

  #block(inset: (x: 2.2cm, y: 1.2cm))[

    #text(size: 9pt, fill: purple, weight: "bold", tracking: 2pt)[ЦЕНИ]
    #v(0.2cm)
    #text(size: 24pt, weight: "bold", fill: rgb("#0f172a"))[
      Планови за секоја потреба
    ]
    #v(0.15cm)
    #text(size: 10.5pt, fill: rgb("#64748b"))[
      Започнете бесплатно. Надградете кога ќе видите вредност.
    ]
    #v(0.5cm)

    // Pricing cards
    #let price-card(name, mkd, eur, ai-q, features, highlighted: false) = {
      let bg = if highlighted { gradient.linear(purple-dark, purple, angle: 135deg) } else { white }
      let tc = if highlighted { white } else { rgb("#0f172a") }
      let accent = if highlighted { cyan } else { purple }
      let border-c = if highlighted { purple } else { rgb("#e2e8f0") }
      let feat-c = if highlighted { rgb("#c4b5fd") } else { rgb("#64748b") }

      block(
        width: 100%,
        inset: (x: 0.6cm, y: 0.5cm),
        radius: 10pt,
        fill: bg,
        stroke: (paint: border-c, thickness: if highlighted { 2pt } else { 1pt }),
      )[
        #if highlighted {
          align(center)[
            #block(
              inset: (x: 0.5cm, y: 0.1cm),
              radius: 20pt, fill: cyan,
            )[#text(size: 6.5pt, weight: "bold", fill: dark-bg, tracking: 1pt)[НАЈПОПУЛАРЕН]]
            #v(0.15cm)
          ]
        }
        #align(center)[
          #text(size: 13pt, weight: "bold", fill: tc)[#name]
          #linebreak()
          #v(0.15cm)
          #text(size: 20pt, weight: "bold", fill: accent)[#mkd]
          #linebreak()
          #text(size: 8pt, fill: feat-c)[#eur / месечно]
          #linebreak()
          #v(0.1cm)
          #text(size: 8pt, fill: feat-c)[#ai-q AI прашања/ден]
        ]
        #v(0.2cm)
        #line(length: 100%, stroke: (paint: if highlighted { rgb(255,255,255,20) } else { rgb("#e2e8f0") }, thickness: 0.5pt))
        #v(0.15cm)
        #for feat in features {
          text(size: 8pt, fill: feat-c)[#text(fill: accent)[+] #h(0.15cm) #feat]
          linebreak()
          v(0.08cm)
        }
      ]
    }

    #grid(
      columns: (1fr, 1fr, 1fr),
      gutter: 0.4cm,
      price-card("Стартуј", "1,990 ден", "39\u{20AC}", "5", (
        "Напредно пребарување",
        "5 AI прашања дневно",
        "Email аларми",
        "Основна анализа",
        "PDF документи",
      )),
      price-card("Про", "5,990 ден", "99\u{20AC}", "25", (
        "Се од Стартуј +",
        "25 AI прашања дневно",
        "Анализа конкуренти",
        "Историски цени",
        "Анализа на ризик",
        "Приоритетна поддршка",
      ), highlighted: true),
      price-card("Тим", "12,990 ден", "199\u{20AC}", "100", (
        "Се од Про +",
        "100 AI прашања дневно",
        "5 корисници",
        "Детална бизнис аналитика",
        "API пристап",
        "Дедициран менаџер",
      )),
    )

    #v(0.3cm)

    // Free + Enterprise — compact
    #grid(
      columns: (1fr, 1fr),
      gutter: 0.4cm,
      block(
        width: 100%, inset: (x: 0.8cm, y: 0.4cm), radius: 8pt,
        fill: rgb("#f8fafc"), stroke: (paint: rgb("#e2e8f0"), thickness: 1pt),
      )[
        #text(size: 11pt, weight: "bold", fill: rgb("#0f172a"))[Бесплатен]
        #h(0.3cm)
        #text(size: 8.5pt, fill: rgb("#64748b"))[0 ден | 2 AI прашања/ден]
        #linebreak()
        #text(size: 8.5pt, fill: rgb("#64748b"))[Основно пребарување и преглед — засекогаш бесплатно]
      ],
      block(
        width: 100%, inset: (x: 0.8cm, y: 0.4cm), radius: 8pt,
        fill: rgb("#f8fafc"), stroke: (paint: rgb("#e2e8f0"), thickness: 1pt),
      )[
        #text(size: 11pt, weight: "bold", fill: rgb("#0f172a"))[Претпријатие]
        #h(0.3cm)
        #text(size: 8.5pt, fill: rgb("#64748b"))[По договор | 500+ AI/ден]
        #linebreak()
        #text(size: 8.5pt, fill: rgb("#64748b"))[За големи организации — прилагодено решение и SLA]
      ],
    )

    #v(0.3cm)

    // Trial badge
    #align(center)[
      #block(
        inset: (x: 1.2cm, y: 0.3cm), radius: 30pt,
        fill: rgb("#f0fdf4"), stroke: (paint: rgb("#86efac"), thickness: 1pt),
      )[
        #text(size: 10pt, weight: "bold", fill: rgb("#166534"))[
          7 дена бесплатен пробен период за сите платени планови
        ]
      ]
    ]

    #v(0.4cm)

    // Comparison highlight
    #block(
      width: 100%, inset: (x: 1cm, y: 0.5cm), radius: 8pt,
      fill: dark-bg,
    )[
      #align(center)[
        #text(size: 9pt, fill: slate)[Сите податоци се јавно достапни од #text(weight: "bold", fill: purple-light)[е-набавки.гов.мк] и #text(weight: "bold", fill: purple-light)[е-пазар.гов.мк]]
      ]
    ]
  ]
]

// ============================================================
// PAGE 6: CTA + CONTACT
// ============================================================
#page(background: {
  place(dx: 0cm, dy: 0cm, rect(width: 100%, height: 100%, fill: dark-bg))
  place(dx: -4cm, dy: 10cm, circle(radius: 14cm, fill: rgb(124, 58, 237, 8)))
  place(dx: 15cm, dy: 2cm, circle(radius: 8cm, fill: rgb(6, 182, 212, 6)))
})[
  #set align(center)

  #v(4cm)

  #text(size: 9pt, fill: cyan, weight: "bold", tracking: 3pt)[ЗАПОЧНЕТЕ ДЕНЕС]

  #v(0.5cm)

  #block(width: 75%)[
    #text(size: 30pt, weight: "bold", fill: white)[
      Подготвени сте да победувате повеќе тендери?
    ]
  ]

  #v(0.6cm)

  #block(width: 65%)[
    #text(size: 12pt, fill: slate)[
      Приклучете се на 4,365+ компании кои веќе ја користат НабавкиДата за поинтелигентно учество на јавни набавки.
    ]
  ]

  #v(1.5cm)

  // CTA Button
  #block(
    inset: (x: 2.5cm, y: 0.7cm),
    radius: 8pt,
    fill: gradient.linear(purple, purple-dark, angle: 135deg),
    stroke: (paint: purple-light, thickness: 1pt),
  )[
    #text(size: 15pt, weight: "bold", fill: white)[
      Почни Бесплатно \u{2192}
    ]
  ]

  #v(0.3cm)
  #text(size: 9pt, fill: rgb("#475569"))[Не е потребна кредитна картичка]

  #v(2cm)

  // Contact card
  #block(
    width: 65%,
    inset: (x: 1.5cm, y: 1cm),
    radius: 12pt,
    fill: card-bg,
    stroke: (paint: card-border, thickness: 1pt),
  )[
    #grid(
      columns: (1fr, 1fr, 1fr),
      gutter: 0.5cm,
      align(center)[
        #block(width: 2.5cm, height: 2pt, radius: 1pt, fill: purple)[]
        #v(0.3cm)
        #text(size: 8pt, fill: slate)[Вебсајт]
        #linebreak()
        #text(size: 11pt, weight: "bold", fill: white)[nabavkidata.com]
      ],
      align(center)[
        #block(width: 2.5cm, height: 2pt, radius: 1pt, fill: cyan)[]
        #v(0.3cm)
        #text(size: 8pt, fill: slate)[Email]
        #linebreak()
        #text(size: 11pt, weight: "bold", fill: white)[hello\@nabavkidata.com]
      ],
      align(center)[
        #block(width: 2.5cm, height: 2pt, radius: 1pt, fill: green)[]
        #v(0.3cm)
        #text(size: 8pt, fill: slate)[Телефон]
        #linebreak()
        #text(size: 11pt, weight: "bold", fill: white)[+389 70 253 467]
      ],
    )

    #v(0.6cm)
    #line(length: 90%, stroke: (paint: card-border, thickness: 0.5pt))
    #v(0.5cm)

    #align(center)[
      #text(size: 10pt, fill: purple-light, weight: "medium")[
        Закажете бесплатна онлајн демонстрација
      ]
      #linebreak()
      #v(0.15cm)
      #text(size: 9pt, fill: slate)[
        Испратете email или јавете се — ќе ви покажеме како платформата работи за вашиот бизнис
      ]
    ]
  ]

  #v(1fr)

  // Footer
  #block(width: 100%, inset: (x: 2cm, y: 0.6cm), fill: rgb(0, 0, 0, 40))[
    #grid(
      columns: (auto, 1fr, auto),
      gutter: 0.5cm,
      align(left + horizon)[
        #image("logo.png", width: 1.5cm)
      ],
      align(center + horizon)[
        #text(size: 7.5pt, fill: rgb("#475569"))[
          \u{00A9} 2026 НабавкиДата | AI-базирана платформа за јавни набавки
        ]
      ],
      align(right + horizon)[
        #text(size: 7.5pt, fill: rgb("#475569"))[nabavkidata.com]
      ],
    )
  ]
]
