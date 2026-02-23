"use client";

import { motion } from "framer-motion";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { MessageCircle } from "lucide-react";

const faqs = [
  {
    question: "Што е јавна набавка?",
    answer: "Јавната набавка е процес на купување на производи, услуги или работи од јавниот сектор. Во Македонија, институциите се законски обврзани да ги објават тендерите на платформата за е-набавки како би обезбедиле транспарентност и конкуренција. Nabavkidata ви овозможува да ги пребарувате, анализирате и следите сите јавни набавки на едно место."
  },
  {
    question: "Како да најдам тендери релевантни за мојот бизнис?",
    answer: "Nabavkidata користи вештачка интелигенција за да ви помогне да најдете релевантни тендери. Можете да пребарувате по клучни зборови, CPV кодови, институција, вредност или период. Дополнително, можете да креирате автоматски алерти што ќе ве известуваат кога ќе се објави нов тендер што одговара на вашите критериуми."
  },
  {
    question: "Што е CPV код?",
    answer: "CPV (Common Procurement Vocabulary) е стандарден европски класификациски систем за јавни набавки. Секој производ, услуга или работа има свој уникатен CPV код. На пример, градежните работи се под код 45000000, а софтверските услуги под 48000000. Користењето на CPV кодови ви овозможува прецизно пребарување на тендери во вашата област."
  },
  {
    question: "Како функционира AI анализата?",
    answer: "Нашата AI технологија автоматски ги анализира сите тендерски документи и извлекува клучни информации: производи, количини, цени, рокови и барања. AI асистентот може да одговара на прашања за тендерот, да ви даде препораки за понуда и да ви овозможи споредба со минати тендери. Ова ви заштедува часови на рачна анализа."
  },
  {
    question: "Како да поднесам понуда?",
    answer: "Nabavkidata ви овозможува да ги анализирате тендерите, но самата понуда се поднесува директно на платформата на Бирото за јавни набавки (e-nabavki.gov.mk). Нашата платформа ви дава детални инсајти, AI препораки и конкурентска интелигенција за да креирате поконкурентна понуда и да ги зголемите шансите за успех."
  },
  {
    question: "Колку чини користењето на Nabavkidata?",
    answer: "Nabavkidata нуди неколку планови: бесплатен план за основно пребарување, Pro план за напредни AI функции и Premium план за корпоративни клиенти со неограничен пристап. Сите планови нудат 7-дневен бесплатен пробен период. Проверете ја нашата страница за цени за детални информации."
  }
];

export default function FAQSection() {
  return (
    <section id="faq" className="py-24 relative overflow-hidden">
      {/* JSON-LD Schema for FAQ */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faqs.map(faq => ({
              "@type": "Question",
              "name": faq.question,
              "acceptedAnswer": {
                "@type": "Answer",
                "text": faq.answer
              }
            }))
          })
        }}
      />

      {/* Background Elements */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-purple-900/20 via-background to-background" />

      <div className="container relative z-10 px-4 md:px-6">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <div className="flex items-center justify-center gap-3 mb-4">
            <MessageCircle className="h-8 w-8 text-primary" />
            <h2 className="text-3xl md:text-5xl font-bold">
              <span className="text-foreground">Најчесто</span>
              <span className="text-gradient"> Поставувани Прашања</span>
            </h2>
          </div>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Дознајте повеќе за јавните набавки и како Nabavkidata може да ви помогне
          </p>
        </motion.div>

        {/* FAQ Accordion */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="max-w-3xl mx-auto"
        >
          <div className="rounded-2xl bg-foreground/5 border border-border backdrop-blur-sm p-6 md:p-8">
            <Accordion type="single" collapsible className="space-y-4">
              {faqs.map((faq, index) => (
                <AccordionItem
                  key={index}
                  value={`item-${index}`}
                  className="border-b border-border last:border-0"
                >
                  <AccordionTrigger className="text-left text-foreground hover:text-primary transition-colors text-base md:text-lg font-semibold py-4">
                    {faq.question}
                  </AccordionTrigger>
                  <AccordionContent className="text-muted-foreground leading-relaxed text-sm md:text-base pb-4">
                    {faq.answer}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </motion.div>

        {/* Bottom CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="text-center mt-12"
        >
          <p className="text-muted-foreground mb-4">
            Имате друго прашање?
          </p>
          <a
            href="mailto:support@nabavkidata.com"
            className="inline-flex items-center justify-center px-6 py-2.5 rounded-lg bg-foreground/5 hover:bg-foreground/10 border border-border hover:border-primary/50 text-foreground font-medium transition-all duration-300"
          >
            <MessageCircle className="h-4 w-4 mr-2" />
            Контактирајте не
          </a>
        </motion.div>
      </div>
    </section>
  );
}
