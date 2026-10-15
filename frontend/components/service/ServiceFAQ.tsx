"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { MessageCircle } from "lucide-react";

export const serviceFaqs = [
    {
        question: "Што ви треба од нас за да ја подготвите понудата?",
        answer:
            "Тендерот што ве интересира (или само вашата дејност, па ние ќе предложиме тендери) и документите на фирмата што ги бара тендерската документација: тековна состојба, потврди, сертификати, референци, биографии на кадарот. Сè друго — изјавите, техничката и финансиската понуда — го подготвуваме ние.",
    },
    {
        question: "Колку однапред треба да ве контактираме пред рокот?",
        answer:
            "Колку порано, толку подобро. Најдобро е да нè контактирате една до две недели пред крајниот рок за поднесување. За пократки рокови прво проверуваме дали понудата може квалитетно да се подготви навреме и ви кажуваме искрено пред да договориме работа.",
    },
    {
        question: "Кој ја поднесува понудата?",
        answer:
            "Вие. Ние ја подготвуваме комплетната понуда и ви ја предаваме на преглед. Вие ја потпишувате со вашиот дигитален сертификат и ја поднесувате на е-набавки. Понудата и односот со договорниот орган секогаш остануваат ваши.",
    },
    {
        question: "Што ако не победиме?",
        answer:
            "Тогаш не плаќате надомест за успех. Надоместот за подготовка се договара однапред и се плаќа за извршената работа, без оглед на исходот. Никој не може искрено да гарантира победа — одлуката ја носи договорниот орган — но подготвуваме понуда што ги исполнува сите услови од документацијата.",
    },
    {
        question: "Колку чини услугата?",
        answer:
            "Подготовката на понуда чини од 30.000 МКД по понуда (без ДДВ), а точниот износ се договара однапред, пред да почне работата. Ако победите, надоместот за успех е 5% од вредноста на договорот за првата година, а надоместот за подготовка што сте го платиле за таа понуда се одбива од него. Следењето на тендери, известувањата и анализите се вклучени за клиентите. Нема месечна претплата.",
    },
    {
        question: "Како се плаќа?",
        answer:
            "Надоместот за подготовка го плаќате со картичка преку Stripe пред да почнеме со работа, или на барање со фактура од Фактурино ДООЕЛ, по банкарска трансакција. Картичката се зачувува за надоместот за успех: ако победите, ве известуваме писмено и наплатата е најрано седум дена потоа, а забелешка во тој рок ја запира наплатата. Ако плаќате со фактура, надоместот за успех се договара со писмено овластување и се фактурира. Нема претплата.",
    },
    {
        question: "Дали може да ги користите вашите сертификати или референци за нашата понуда?",
        answer:
            "Не. ISO сертификатите, референците, финансиските показатели и кадарот се ваши — условите за способност ги исполнува фирмата што ја поднесува понудата (или нејзин партнер, ако тендерската документација тоа го дозволува). Пред да договориме работа ви кажуваме однапред ако некој услов од тендерот не го исполнувате, за да не трошите време и пари на понуда без шанса.",
    },
    {
        question: "Дали нашите податоци и цени остануваат доверливи?",
        answer:
            "Да. Документите, цените и сите информации што ни ги давате ги користиме само за подготовка на вашата понуда и не ги споделуваме со трети лица.",
    },
    {
        question: "За кои сектори подготвувате понуди?",
        answer:
            "За услуги, стоки и работи — ИТ и софтвер, консултантски услуги, медицинска опрема и потрошен материјал, канцелариски материјали, одржување, градежни работи и други. Пред да договориме работа проверуваме дали конкретниот тендер одговара на вашата фирма.",
    },
    {
        question: "Дали и понатаму можам да пребарувам тендери на платформата?",
        answer:
            "Да. Пребарувањето на тендери останува достапно, а следењето и известувањата се вклучени за клиентите. Разликата е што сега, ако сакате, ние ја пишуваме понудата наместо вас.",
    },
];

export default function ServiceFAQ() {
    return (
        <section id="faq" className="py-16 relative overflow-hidden scroll-mt-20">
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{
                    __html: JSON.stringify({
                        "@context": "https://schema.org",
                        "@type": "FAQPage",
                        mainEntity: serviceFaqs.map((faq) => ({
                            "@type": "Question",
                            name: faq.question,
                            acceptedAnswer: { "@type": "Answer", text: faq.answer },
                        })),
                    }),
                }}
            />

            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/10 via-background to-background" />

            <div className="container relative z-10 px-4 md:px-6">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5 }}
                    className="text-center mb-10"
                >
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        <span className="text-foreground">Чести </span>
                        <span className="text-gradient">прашања</span>
                    </h2>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="max-w-3xl mx-auto"
                >
                    <div className="rounded-2xl bg-foreground/5 border border-border backdrop-blur-sm p-6 md:p-8">
                        <Accordion type="single" collapsible className="space-y-2">
                            {serviceFaqs.map((faq, index) => (
                                <AccordionItem key={faq.question} value={`item-${index}`} className="border-b border-border last:border-0">
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

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.3 }}
                    className="text-center mt-8"
                >
                    <p className="text-muted-foreground inline-flex items-center gap-2 flex-wrap justify-center">
                        <MessageCircle className="w-4 h-4" />
                        Имате друго прашање?{" "}
                        <Link href="/contact" className="text-primary hover:underline underline-offset-4">
                            Контактирајте нè
                        </Link>
                    </p>
                </motion.div>
            </div>
        </section>
    );
}
