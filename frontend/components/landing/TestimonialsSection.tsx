"use client";

import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Quote, Star, Building2, User } from "lucide-react";

const testimonials = [
  {
    name: "Марко Петровски",
    role: "Извршен директор",
    company: "ТехноСолуции ДООЕЛ",
    content: "Nabavkidata ни помогна да ги зголемиме нашите шанси за освојување на тендери за 40%. AI анализата на конкуренцијата ни дава невообичаена предност.",
    rating: 5,
    avatar: "MP"
  },
  {
    name: "Елена Димитриевска",
    role: "Менаџер набавки",
    company: "Градител Инженеринг",
    content: "Автоматските известувања и деталните инсајти ни заштедуваат над 15 часа неделно. Платформата е неопходна за секој сериозен понудувач.",
    rating: 5,
    avatar: "ЕД"
  },
  {
    name: "Александар Стојановски",
    role: "Сопственик",
    company: "МедОпрема Трејд",
    content: "Преку Nabavkidata успеавме да ги идентификуваме трендовите во нашиот сектор и да ги прилагодиме нашите цени. Резултатите зборуваат сами за себе.",
    rating: 5,
    avatar: "АС"
  },
  {
    name: "Даниела Николовска",
    role: "Директор продажба",
    company: "ОфисПро ДООЕЛ",
    content: "AI асистентот ми овозможува да добијам брзи одговори за секој тендер. Повеќе не морам да читам стотици страници документи.",
    rating: 5,
    avatar: "ДН"
  },
  {
    name: "Горан Трајковски",
    role: "Раководител тендери",
    company: "ЕкоГрупа",
    content: "Конкурентската анализа и историските податоци ни помогнаа да развиеме подобра стратегија. Освоивме 3 големи тендери во последните 6 месеци.",
    rating: 5,
    avatar: "ГТ"
  },
  {
    name: "Ана Ристовска",
    role: "Консултант",
    company: "БизнисКонсалтинг",
    content: "Користам Nabavkidata за мојте клиенти и секогаш добиваат вреден инсајт. Платформата е интуитивна и моќна.",
    rating: 5,
    avatar: "АР"
  }
];

export default function TestimonialsSection() {
  return (
    <section id="testimonials" className="py-24 relative overflow-hidden">
      {/* JSON-LD Schema for Reviews */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Nabavkidata",
            "url": "https://nabavkidata.com",
            "aggregateRating": {
              "@type": "AggregateRating",
              "ratingValue": "5.0",
              "reviewCount": testimonials.length,
              "bestRating": "5",
              "worstRating": "1"
            },
            "review": testimonials.map(testimonial => ({
              "@type": "Review",
              "author": {
                "@type": "Person",
                "name": testimonial.name,
                "jobTitle": testimonial.role,
                "worksFor": {
                  "@type": "Organization",
                  "name": testimonial.company
                }
              },
              "reviewRating": {
                "@type": "Rating",
                "ratingValue": testimonial.rating.toString(),
                "bestRating": "5",
                "worstRating": "1"
              },
              "reviewBody": testimonial.content
            }))
          })
        }}
      />

      {/* Background Elements */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-900/20 via-background to-background" />

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
            <Quote className="h-8 w-8 text-primary" />
            <h2 className="text-3xl md:text-5xl font-bold">
              <span className="text-foreground">Што велат</span>
              <span className="text-gradient"> нашите клиенти</span>
            </h2>
          </div>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Придружете им се на стотици македонски компании што успеваат со Nabavkidata
          </p>
        </motion.div>

        {/* Testimonials Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-7xl mx-auto">
          {testimonials.map((testimonial, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
            >
              <Card className="h-full bg-foreground/5 border-border backdrop-blur-sm hover:bg-foreground/10 transition-all duration-300 hover:border-primary/30">
                <CardContent className="p-6 flex flex-col h-full">
                  {/* Rating Stars */}
                  <div className="flex items-center gap-1 mb-4">
                    {Array.from({ length: testimonial.rating }).map((_, i) => (
                      <Star key={i} className="h-4 w-4 fill-yellow-500 text-yellow-500" />
                    ))}
                  </div>

                  {/* Quote Icon */}
                  <Quote className="h-8 w-8 text-primary/30 mb-3" />

                  {/* Testimonial Content */}
                  <p className="text-muted-foreground text-sm leading-relaxed mb-6 flex-1">
                    "{testimonial.content}"
                  </p>

                  {/* Author Info */}
                  <div className="flex items-center gap-3 pt-4 border-t border-border">
                    {/* Avatar */}
                    <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
                      {testimonial.avatar}
                    </div>

                    {/* Name and Company */}
                    <div className="flex-1 min-w-0">
                      <p className="text-foreground font-semibold text-sm truncate">
                        {testimonial.name}
                      </p>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <User className="h-3 w-3" />
                        <span className="truncate">{testimonial.role}</span>
                      </div>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
                        <Building2 className="h-3 w-3" />
                        <span className="truncate">{testimonial.company}</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Trust Badge */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.6 }}
          className="text-center mt-12"
        >
          <div className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-foreground/5 border border-border">
            <div className="flex items-center gap-1">
              {Array.from({ length: 5 }).map((_, i) => (
                <Star key={i} className="h-4 w-4 fill-yellow-500 text-yellow-500" />
              ))}
            </div>
            <span className="text-foreground font-semibold">5.0</span>
            <span className="text-muted-foreground">од {testimonials.length} рецензии</span>
          </div>
        </motion.div>

        {/* Bottom CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.7 }}
          className="text-center mt-12"
        >
          <p className="text-muted-foreground mb-4">
            Подготвени да станете дел од успешната приказна?
          </p>
          <a
            href="/auth/register"
            className="inline-flex items-center justify-center px-8 py-3 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground font-medium transition-all duration-300 shadow-[0_0_30px_rgba(124,58,237,0.5)] hover:shadow-[0_0_50px_rgba(124,58,237,0.7)]"
          >
            Започни бесплатно денес
          </a>
        </motion.div>
      </div>
    </section>
  );
}
