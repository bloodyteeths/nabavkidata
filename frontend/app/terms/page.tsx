'use client';

import { useState, type ReactNode } from 'react';

const LAST_UPDATED_MK = '14.10.2026';
const LAST_UPDATED_EN = '14 October 2026';
// Must match AGREEMENT_VERSION in backend/services/bid_payments.py.
const TERMS_VERSION = '2026-10-14';

export default function TermsPage() {
  const [language, setLanguage] = useState<'mk' | 'en'>('mk');

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="flex flex-wrap justify-between items-center gap-4 mb-8">
        <h1 className="text-3xl font-bold">
          {language === 'mk' ? 'Услови за користење' : 'Terms of Service'}
        </h1>
        <div className="flex gap-2">
          <button
            onClick={() => setLanguage('mk')}
            className={`px-4 py-2 rounded-md transition-colors ${
              language === 'mk'
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
            }`}
          >
            Македонски
          </button>
          <button
            onClick={() => setLanguage('en')}
            className={`px-4 py-2 rounded-md transition-colors ${
              language === 'en'
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
            }`}
          >
            English
          </button>
        </div>
      </div>

      {language === 'mk' ? <MacedonianTerms /> : <EnglishTerms />}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Small presentational helpers                                        */
/* ------------------------------------------------------------------ */

function Section({ id, title, children }: { id?: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24">
      <h2 className="text-2xl font-semibold mb-4">{title}</h2>
      {children}
    </section>
  );
}

function H3({ children }: { children: ReactNode }) {
  return <h3 className="text-xl font-semibold mb-3 mt-6">{children}</h3>;
}

function P({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <p className={`text-muted-foreground mb-4 ${className}`}>{children}</p>;
}

function UL({ items }: { items: ReactNode[] }) {
  return (
    <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4 mb-4">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

const mailLink = (
  <a href="mailto:hello@nabavkidata.com" className="text-primary hover:underline">
    hello@nabavkidata.com
  </a>
);

function CompanyCard({ lang }: { lang: 'mk' | 'en' }) {
  const mk = lang === 'mk';
  return (
    <div className="bg-muted/30 rounded-lg p-4 space-y-2 not-prose mb-4">
      <p className="text-foreground">
        <strong>{mk ? 'Фактурино ДООЕЛ Велес' : 'Fakturino DOOEL Veles (Фактурино ДООЕЛ)'}</strong>
      </p>
      <p className="text-muted-foreground">
        {mk ? 'Адреса: ул. Сараевска 37, 1400 Велес, Република Северна Македонија' : 'Address: ul. Saraevska 37, 1400 Veles, Republic of North Macedonia'}
      </p>
      <p className="text-muted-foreground">
        {mk ? 'ЕДБ: 4004026525934 · ЕМБС: 7922400' : 'Tax no. (EDB): 4004026525934 · Company reg. no. (EMBS): 7922400'}
      </p>
      <p className="text-muted-foreground">
        {mk ? 'Е-пошта: ' : 'Email: '}
        {mailLink}
      </p>
      <p className="text-muted-foreground">
        {mk ? 'Телефон: ' : 'Phone: '}
        <a href="tel:+38970253467" className="text-primary hover:underline">
          +389 70 253 467
        </a>
      </p>
      <p className="text-muted-foreground">
        {mk ? 'Веб-страница: ' : 'Website: '}
        <a href="https://nabavkidata.com" className="text-primary hover:underline">
          nabavkidata.com
        </a>
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Macedonian (authoritative)                                          */
/* ------------------------------------------------------------------ */

function MacedonianTerms() {
  return (
    <div className="prose prose-invert max-w-none space-y-8">
      <section>
        <p className="text-sm text-muted-foreground mb-6">
          Последно ажурирање: {LAST_UPDATED_MK} · Верзија {TERMS_VERSION}
        </p>
        <p className="text-muted-foreground mb-6">
          Ве молиме внимателно прочитајте ги овие Услови за користење („Услови“) пред да ја користите веб-страницата
          nabavkidata.com („Платформата“) или пред да ни доверите подготовка на тендерска понуда („Услугата за
          подготовка на понуди“). Платформата и Услугата за подготовка на понуди ги обезбедува Фактурино ДООЕЛ Велес
          („Фактурино“, „ние“, „нас“ или „наш“).
        </p>
      </section>

      <Section title="1. Прифаќање на условите">
        <P>
          Со пристапувањето и користењето на Платформата, или со нарачување на Услугата за подготовка на понуди, се
          согласувате со овие Услови и со применливите закони и прописи. Ако не се согласувате со некој од условите,
          ве молиме не користете ја Платформата.
        </P>
        <P>
          Користењето е условено и со нашата Политика за приватност, која опишува како ги собираме, користиме и
          заштитуваме вашите лични податоци.
        </P>
      </Section>

      <Section title="2. Опис на услугата">
        <P>
          nabavkidata.com е платформа за следење на јавни набавки во Република Северна Македонија. Преку неа ние ги
          следиме тендерите наместо вас и, на ваше барање, ја подготвуваме вашата тендерска понуда. Услугата опфаќа:
        </P>
        <UL
          items={[
            'Пристап до база на податоци за тендери и јавни набавки',
            'Следење и известувања за тендери релевантни за вашата дејност, вклучени за клиентите за кои подготвуваме понуди',
            'Анализи на тендерска документација, договорни органи и конкуренција, вклучени за клиентите',
            'Разгледување на вашето барање за понуда и проценка дали и под кои услови вреди да се поднесе понуда на конкретен тендер',
            'Подготовка на тендерска понуда за вас, според условите во член 4',
          ]}
        />
        <P>
          Податоците за тендери се собираат од јавно достапни извори, вклучувајќи го порталот e-nabavki.gov.mk и
          други официјални веб-страници. Се трудиме податоците да бидат точни и навремени, но не гарантираме нивна
          апсолутна точност, комплетност или ажурност.
        </P>
      </Section>

      <Section title="3. Кориснички профил">
        <H3>3.1 Креирање на профил</H3>
        <P>За користење на Платформата потребно е да:</P>
        <UL
          items={[
            'Креирате профил со точни, комплетни и ажурни информации',
            'Имате најмалку 18 години и правна способност да склучувате договори',
            'Обезбедите валидна адреса за е-пошта',
            'Ја чувате безбедноста и доверливоста на вашата лозинка',
          ]}
        />
        <H3>3.2 Одговорност за профилот</H3>
        <P>Вие сте одговорни за:</P>
        <UL
          items={[
            'Сите активности што се случуваат преку вашиот профил',
            'Доверливоста на вашите податоци за најава',
            'Навремено да нè известите за секое неовластено користење на вашиот профил',
            'Ажурноста на вашите податоци за контакт',
          ]}
        />
      </Section>

      <Section id="usluga-za-podgotovka-na-ponudi" title="4. Услуга за подготовка на тендерски понуди">
        <H3>4.1 Давател на услугата</H3>
        <P>Услугата за подготовка на понуди ја обезбедува:</P>
        <CompanyCard lang="mk" />

        <H3>4.2 Барање за понуда; следење вклучено за клиенти</H3>
        <P>
          Испраќањето барање за понуда („Барање за понуда“) не ве обврзува на ништо: ја разгледуваме тендерската
          документација и ве известуваме дали и под кои услови вреди да се поднесе понуда. Пребарувањето и прегледот
          на тендери се достапни на Платформата. Следењето на тендери, известувањата
          по е-пошта, AI алатките, ценовните анализи и анализите на конкуренција се вклучени за клиентите за кои
          подготвуваме понуди. Обврска за плаќање настанува дури откако ќе се договориме за подготовка на конкретна
          понуда.
        </P>

        <H3>4.3 Надомест за подготовка на понуда</H3>
        <UL
          items={[
            'Надоместот за подготовка изнесува од 30.000 МКД по понуда, во зависност од обемот и сложеноста на тендерот.',
            'Точниот износ се договара пред да започнеме со работа и е прикажан во вашиот портал. Без ваша потврда (прифаќање на овие услови во порталот, по е-пошта или со договор) не започнуваме со работа и не наплатуваме ништо.',
            'Надоместот се плаќа пред да започнеме со подготовка на понудата: со платежна картичка преку Stripe, или на ваше барање со фактура од Фактурино ДООЕЛ.',
          ]}
        />

        <H3>4.4 Надомест за успех</H3>
        <UL
          items={[
            'Надоместот за успех изнесува 5% од вредноста на договорот за првата година, за договор доделен врз основа на понуда што ја подготвивме ние. Ако договорот трае пократко од една година, основа е вкупната вредност на договорот.',
            'Се плаќа само ако победите. Ако не бидете избрани, надомест за успех не се плаќа.',
            'Основа е вредноста на договорот без ДДВ. Кај рамковна спогодба, основа е фактички реализираниот износ во првата година, а надоместот се фактурира по истекот на таа година.',
            'Надоместот за подготовка платен за таа понуда се одбива од надоместот за успех.',
            'Се наплатува откако ќе ве известиме писмено за доделувањето, според член 4.5. Ако одлуката за избор биде поништена и договор не се склучи, надомест за успех не се плаќа.',
            'Надоместот за успех нема горна граница.',
          ]}
        />

        <H3>4.5 Начин на плаќање и данок</H3>
        <UL
          items={[
            'Плаќање со картичка: надоместот за подготовка се плаќа со платежна картичка преку Stripe. Картичката се зачувува кај Stripe (ние ги чуваме само марката и последните четири цифри, никогаш целиот број) и, со прифаќање на овие услови, нè овластувате да ја користиме за надоместот за успех.',
            'Надоместот за успех се наплатува од зачуваната картичка најрано седум дена откако ќе ве известиме писмено по е-пошта за доделувањето; износот е прикажан во порталот.',
            'Ако во тие седум дена ни доставите писмена забелешка, наплатата се запира додека не ја разгледаме забелешката заедно со вас.',
            'Плаќање со фактура: на ваше барање ги издаваме фактурите за надоместот за подготовка и за надоместот за успех, со банкарски трансфер на трансакциската сметка на Фактурино ДООЕЛ Велес. Во тој случај надоместот за успех го овластувате писмено (договор или потврда по е-пошта).',
            'Не нудиме претплати, пакети или автоматско обновување.',
            'Фактурино ДООЕЛ не е обврзник за ДДВ. Сите наведени износи се без ДДВ и на нив не се пресметува ДДВ.',
          ]}
        />

        <H3>4.6 Обврски на клиентот</H3>
        <UL
          items={[
            'Клиентот навремено ги доставува сопствените документи, сертификати, референци, финансиски податоци и други докази потребни за понудата.',
            'Клиентот е единствено одговорен за вистинитоста, точноста и важноста на податоците и документите што ни ги доставува.',
            'Клиентот одговара на нашите прашања во разумен рок, за понудата да може да се подготви пред крајниот рок за поднесување.',
          ]}
        />

        <H3>4.7 Преглед, потпишување и поднесување на понудата</H3>
        <P>
          Ние ја подготвуваме понудата, а клиентот ја прегледува, ја потпишува со сопствен дигитален сертификат и ја
          поднесува преку e-nabavki.gov.mk. Клиентот е и останува понудувач во постапката и е одговорен за конечната
          содржина на понудата и за нејзино поднесување во рок. Фактурино не поднесува понуди во име на клиентот и не
          користи негови сертификати или пристапни податоци.
        </P>

        <H3>4.8 Без гаранција за успех</H3>
        <P>
          Изборот на најповолна понуда го врши договорниот орган. Не гарантираме дека понудата ќе биде избрана, ниту
          исход на жалби или други постапки. Надоместот за подготовка се плаќа за извршената работа и не зависи од
          исходот на тендерот.
        </P>

        <H3>4.9 Доверливост</H3>
        <P>
          Документите и податоците што ни ги доставувате ги користиме исклучиво за подготовка на вашата понуда. Не
          ги споделуваме со трети страни, не ги користиме за други клиенти и ги чуваме доверливо, со пристап само за
          лицата кои работат на вашата понуда. На ваше барање, по завршување на соработката ги бришеме или враќаме,
          освен податоците што сме должни да ги чуваме според закон (на пример, фактури).
        </P>

        <H3>4.10 Прекин на соработката</H3>
        <UL
          items={[
            'Секоја страна може да ја прекине соработката во секое време со писмено известување (вклучително по е-пошта).',
            'Ако ние ја прекинеме соработката пред да ја предадеме понудата, од причини на наша страна, ви го враќаме платениот надомест за подготовка на таа понуда.',
            'Ако клиентот ја прекине соработката откако сме започнале со работа, платениот надомест за подготовка не се враќа.',
            'Надоместот за успех останува должен ако клиентот добие договор со понуда што ја подготвивме ние, и кога соработката е прекината пред одлуката за избор.',
          ]}
        />

        <H3>4.11 Поединечни договори</H3>
        <P>
          За секоја понуда можеме да склучиме посебен писмен договор или да ги потврдиме условите по е-пошта. Во
          случај на разлика, писмено договореното за конкретната понуда има предност пред овој член.
        </P>
      </Section>

      <Section title="5. Прифатливо користење">
        <H3>5.1 Дозволено користење</H3>
        <P>
          Се согласувате да ја користите Платформата само за законски цели и на начин што не ги повредува правата на
          трети страни и не го попречува нивното користење на Платформата.
        </P>
        <H3>5.2 Забранети активности</H3>
        <P>Се согласувате да НЕ:</P>
        <UL
          items={[
            'Ја користите Платформата за незаконски цели',
            'Се обидувате да пристапите до системите, серверите или мрежите без овластување',
            'Вршите автоматизирано собирање податоци (скрепување) без изрична писмена дозвола',
            'Пренесувате вируси, малициозен софтвер или друг штетен код',
            'Ја злоупотребувате AI функционалноста или се обидувате да ги заобиколите техничките ограничувања',
            'Ги споделувате вашите податоци за најава со други лица',
            'Реверзно инженерирате, декомпилирате или расклопувате делови од Платформата',
            'Доставувате лажни, измамнички или заведувачки информации',
            'Ја нарушувате безбедноста или интегритетот на Платформата или прекумерно ја оптоварувате инфраструктурата',
          ]}
        />
        <H3>5.3 Заштита од злоупотреба</H3>
        <P>
          Применуваме технички ограничувања и системи за откривање злоупотреба за да ја заштитиме Платформата.
          Злоупотребата може да доведе до привремено или трајно суспендирање на профилот.
        </P>
      </Section>

      <Section title="6. Интелектуална сопственост">
        <H3>6.1 Платформата</H3>
        <P>
          Платформата, нејзиниот софтвер, дизајн, организација на податоците и анализите се сопственост на Фактурино
          и се заштитени со закон. Ви даваме ограничено, непреносливо и неексклузивно право да ја користите Платформата
          за вашите деловни цели.
        </P>
        <H3>6.2 Податоци од јавни извори</H3>
        <P>
          Податоците за тендери потекнуваат од јавни извори. Нашето собирање, организација, презентација и анализа на
          тие податоци се наша интелектуална сопственост.
        </P>
        <H3>6.3 Подготвени понуди</H3>
        <P>
          Документите од понудата што ја подготвуваме за вас, по целосно плаќање на надоместот за подготовка, ги
          користите слободно за таа и за идни ваши понуди. Вашите документи, сертификати и податоци остануваат ваша
          сопственост.
        </P>
      </Section>

      <Section title="7. Приватност и заштита на податоци">
        <P>
          Нашата Политика за приватност објаснува како ги собираме, користиме, чуваме и заштитуваме вашите лични
          податоци. Се придржуваме кон Законот за заштита на личните податоци на Република Северна Македонија и, каде
          што е применливо, GDPR.
        </P>
      </Section>

      <Section title="8. Гаранции">
        <H3>8.1 Податоци и анализи</H3>
        <P>
          Платформата се обезбедува „како што е“. Податоците за тендери се информативни и треба да ги проверите на
          официјалниот портал e-nabavki.gov.mk пред да донесете одлука. AI анализите се помошна алатка, а не правен
          совет.
        </P>
        <H3>8.2 Услуга за подготовка на понуди</H3>
        <P>
          Понудите ги подготвуваме со професионално внимание и врз основа на тендерската документација и податоците што
          ни ги доставувате. Не гарантираме избор на понудата (член 4.8).
        </P>
      </Section>

      <Section title="9. Ограничување на одговорност">
        <P>
          До обемот дозволен со закон, Фактурино не одговара за индиректна или последична штета, изгубена добивка или
          изгубени деловни можности, вклучително неизбор на понуда, отфрлање поради документи или податоци доставени
          од клиентот, или неподнесување на понудата во рок од страна на клиентот.
        </P>
        <P>
          Вкупната одговорност на Фактурино кон клиентот за конкретна понуда е ограничена на износот на надоместот
          што клиентот го платил за таа понуда. Ова ограничување не важи за штета причинета намерно или со крајна
          небрежност.
        </P>
      </Section>

      <Section title="10. Обесштетување">
        <P>
          Се согласувате да го обесштетите Фактурино за барања на трети страни што произлегуваат од вашето кршење на
          овие Услови, на закон или на права на трети лица, или од невистинити документи и податоци што сте ни ги
          доставиле.
        </P>
      </Section>

      <Section title="11. Измени на условите">
        <P>
          Можеме да ги дополнуваме функциите на Платформата и да ги ажурираме овие Услови. За значајни измени ќе ве
          известиме по е-пошта или на Платформата. Измените не важат за понуди за кои веќе писмено сме договориле
          надомест.
        </P>
      </Section>

      <Section title="12. Прекин на профилот">
        <P>
          Можеме да го суспендираме или прекинеме пристапот до профил при кршење на овие Услови, измамничка или
          незаконска активност или по барање на надлежен орган. Вие можете да го избришете вашиот профил во секое
          време или да побарате бришење на {mailLink}. Прекинот на профилот не влијае на веќе настанатите обврски
          од член 4.
        </P>
      </Section>

      <Section title="13. Применливо право и спорови">
        <P>
          На овие Услови и на Услугата за подготовка на понуди се применува правото на Република Северна Македонија.
          Страните ќе се обидат секој спор да го решат спогодбено. Ако тоа не е можно во рок од 30 дена, надлежен е
          стварно надлежниот суд во Скопје.
        </P>
      </Section>

      <Section title="14. Разни одредби">
        <UL
          items={[
            'Целосен договор: овие Услови, Политиката за приватност и писмено договореното за конкретна понуда го сочинуваат целиот договор меѓу вас и Фактурино.',
            'Делумна неважност: ако некоја одредба се смета за неважечка, другите одредби остануваат на сила.',
            'Пренос: не можете да ги пренесете правата и обврските од овие Услови без наша претходна писмена согласност.',
            'Виша сила: не одговараме за доцнење или неизвршување поради околности надвор од нашата разумна контрола, вклучително прекини во работата на порталот e-nabavki.gov.mk.',
          ]}
        />
      </Section>

      <Section title="15. Комуникации и одјава">
        <P>
          Може да ви испраќаме известувања за тендери и информации за нашите услуги, само со ваша согласност или кога
          имаме легитимен интерес. Можете да се одјавите во секое време преку линкот на дното на секоја порака или со
          порака на {mailLink}. По одјавата и понатаму може да добивате пораки неопходни за вашиот профил или за
          договорена понуда.
        </P>
      </Section>

      <Section title="16. Контакт">
        <P>За прашања во врска со овие Услови контактирајте нè на:</P>
        <CompanyCard lang="mk" />
      </Section>

      <section className="pt-8 border-t border-muted">
        <p className="text-sm text-muted-foreground text-center">Последно ажурирање: {LAST_UPDATED_MK}</p>
        <p className="text-sm text-muted-foreground text-center mt-2">
          Со користење на nabavkidata.com се согласувате со овие Услови за користење.
        </p>
      </section>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* English (convenience translation)                                   */
/* ------------------------------------------------------------------ */

function EnglishTerms() {
  return (
    <div className="prose prose-invert max-w-none space-y-8">
      <section>
        <p className="text-sm text-muted-foreground mb-6">
          Last updated: {LAST_UPDATED_EN} · Version {TERMS_VERSION}
        </p>
        <p className="text-muted-foreground mb-6">
          Please read these Terms of Service (&quot;Terms&quot;) carefully before using nabavkidata.com (the
          &quot;Platform&quot;) or asking us to prepare a tender bid for you (the &quot;Bid Preparation Service&quot;). The
          Platform and the Bid Preparation Service are provided by Fakturino DOOEL Veles (&quot;Fakturino&quot;,
          &quot;we&quot;, &quot;us&quot;). This English text is a convenience translation; the Macedonian version prevails.
        </p>
      </section>

      <Section title="1. Acceptance of Terms">
        <P>
          By accessing or using the Platform, or by ordering the Bid Preparation Service, you agree to these Terms and
          to all applicable laws. Use is also subject to our Privacy Policy.
        </P>
      </Section>

      <Section title="2. Service Description">
        <P>
          nabavkidata.com monitors public procurement in the Republic of North Macedonia. We monitor tenders for you
          and, on request, prepare your tender bid. The service includes:
        </P>
        <UL
          items={[
            'Access to a database of tenders and public procurement data',
            'Tender monitoring and alerts relevant to your business, included for clients we prepare bids for',
            'Analysis of tender documentation, contracting authorities and competition, included for clients',
            'Review of your bid request and an assessment of whether, and on what terms, a tender is worth bidding for',
            'Preparation of your tender bid, under the terms in Section 4',
          ]}
        />
        <P>
          Tender data is collected from public sources, including e-nabavki.gov.mk. We aim for accuracy but do not
          guarantee that the data is complete or up to date.
        </P>
      </Section>

      <Section title="3. User Account">
        <P>
          You must provide accurate information, be at least 18 and legally able to contract, keep your password
          confidential, and tell us promptly about any unauthorised use of your account. You are responsible for
          activity under your account.
        </P>
      </Section>

      <Section id="bid-preparation-service" title="4. Tender Bid Preparation Service">
        <H3>4.1 Provider</H3>
        <CompanyCard lang="en" />

        <H3>4.2 Bid request; monitoring included for clients</H3>
        <P>
          Sending a bid request creates no obligation: we review the tender documentation and tell you whether, and
          on what terms, it is worth bidding. Searching and viewing tenders is available on the Platform. Tender monitoring, email alerts, AI tools, price analytics and
          competitor analytics are included for clients we prepare bids for. A payment obligation arises only once we
          agree to prepare a specific bid.
        </P>

        <H3>4.3 Preparation fee</H3>
        <UL
          items={[
            'The preparation fee starts from MKD 30,000 per bid, depending on the scope and complexity of the tender.',
            'The exact amount is agreed before any work starts and is shown in your portal. Without your confirmation (accepting these Terms in the portal, by email or by contract) we do not start work and do not charge anything.',
            'The fee is payable before we start preparing the bid: by payment card through Stripe or, on request, by invoice from Fakturino DOOEL.',
          ]}
        />

        <H3>4.4 Success fee</H3>
        <UL
          items={[
            'The success fee is 5% of the first-year value of a contract awarded on a bid we prepared. If the contract runs for less than one year, the basis is the total contract value.',
            'It is payable only if you win. If you are not selected, no success fee is due.',
            'The basis is the contract value excluding VAT. For a framework agreement, the basis is the amount actually realised in the first year, invoiced once that year has ended.',
            'The preparation fee paid for that bid is deducted from the success fee.',
            'It is charged after we notify you in writing of the award, as set out in Section 4.5. If the selection decision is annulled and no contract is signed, no success fee is due.',
            'The success fee has no cap.',
          ]}
        />

        <H3>4.5 Payment and tax</H3>
        <UL
          items={[
            'Card payment: the preparation fee is paid by payment card through Stripe. The card is saved with Stripe (we keep only the card brand and last four digits, never the full number) and, by accepting these Terms, you authorise us to use it for the success fee.',
            'The success fee is charged to the saved card no earlier than seven days after we notify you in writing by email of the award; the amount is shown in the portal.',
            'If you send us a written objection within those seven days, the charge is stopped until we have resolved the objection with you.',
            'Invoice payment: on request we issue invoices for the preparation fee and the success fee, paid by bank transfer to the account of Fakturino DOOEL Veles. In that case you authorise the success fee in writing (contract or email confirmation).',
            'We offer no subscriptions, plans or automatic renewals.',
            'Fakturino DOOEL is not registered for VAT. All amounts are stated without VAT and no VAT is charged.',
          ]}
        />

        <H3>4.6 Client obligations</H3>
        <P>
          The client supplies its own documents, certificates, references, financial data and other evidence in good
          time, and is solely responsible for their truthfulness, accuracy and validity.
        </P>

        <H3>4.7 Review, signing and submission</H3>
        <P>
          We prepare the bid; the client reviews it, signs it with its own digital certificate and submits it on
          e-nabavki.gov.mk. The client is and remains the bidder and is responsible for the final content and for
          submitting on time. Fakturino does not submit bids on the client&apos;s behalf and does not use the
          client&apos;s certificates or credentials.
        </P>

        <H3>4.8 No guarantee of winning</H3>
        <P>
          The contracting authority selects the winning bid. We do not guarantee that a bid will be selected. The
          preparation fee pays for the work done and does not depend on the outcome.
        </P>

        <H3>4.9 Confidentiality</H3>
        <P>
          We use your documents and data only to prepare your bid, do not share them with third parties or use them
          for other clients, and restrict access to the people working on your bid. On request we delete or return
          them after the engagement, except records we must keep by law (such as invoices).
        </P>

        <H3>4.10 Ending the engagement</H3>
        <UL
          items={[
            'Either party may end the engagement at any time by written notice (including email).',
            'If we end it before delivering the bid for reasons on our side, we refund the preparation fee paid for that bid.',
            'If the client ends it after work has started, the preparation fee paid is not refunded.',
            'The success fee remains due if the client wins a contract with a bid we prepared, even if the engagement ended before the selection decision.',
          ]}
        />

        <H3>4.11 Individual agreements</H3>
        <P>
          Each bid may be covered by a separate written agreement or terms confirmed by email. Where they differ, the
          written terms for that bid prevail over this Section.
        </P>
      </Section>

      <Section title="5. Acceptable Use">
        <P>
          Use the Platform only for lawful purposes. Do not access systems without authorisation, scrape data without
          written permission, transmit malicious code, misuse the AI features, share your login, reverse engineer
          the Platform, submit false information, or overload the infrastructure. Misuse may lead to suspension.
        </P>
      </Section>

      <Section title="6. Intellectual Property">
        <P>
          The Platform, its software, design, data organisation and analysis belong to Fakturino. Tender data comes
          from public sources. Once the preparation fee is paid in full, you may freely use the bid documents we
          prepared for you, for that and future bids. Your own documents and data remain yours.
        </P>
      </Section>

      <Section title="7. Privacy and Data Protection">
        <P>
          Our Privacy Policy explains how we handle personal data. We comply with the Law on Personal Data Protection
          of the Republic of North Macedonia and, where applicable, the GDPR.
        </P>
      </Section>

      <Section title="8. Warranties">
        <P>
          The Platform is provided &quot;as is&quot;. Tender data is informational and should be checked on
          e-nabavki.gov.mk; AI analysis is an aid, not legal advice. Bids are prepared with professional care based on
          the tender documentation and the information you supply; selection is not guaranteed (Section 4.8).
        </P>
      </Section>

      <Section title="9. Limitation of Liability">
        <P>
          To the extent permitted by law, Fakturino is not liable for indirect or consequential loss, lost profit or
          lost opportunity, including non-selection of a bid, rejection caused by documents or data supplied by the
          client, or late submission by the client. Our total liability for a given bid is limited to the fee the
          client paid for that bid. This limit does not apply to damage caused intentionally or by gross negligence.
        </P>
      </Section>

      <Section title="10. Indemnification">
        <P>
          You agree to indemnify Fakturino against third-party claims arising from your breach of these Terms, of law
          or of third-party rights, or from untrue documents or data you supplied.
        </P>
      </Section>

      <Section title="11. Changes to These Terms">
        <P>
          We may extend the Platform and update these Terms. We will notify you of significant changes by email or on
          the Platform. Changes do not apply to bids whose fee has already been agreed in writing.
        </P>
      </Section>

      <Section title="12. Account Termination">
        <P>
          We may suspend or terminate an account for breach of these Terms, fraud, unlawful activity or at the
          request of a competent authority. You may delete your account at any time or request deletion at{' '}
          {mailLink}. Termination does not affect obligations already arising under Section 4.
        </P>
      </Section>

      <Section title="13. Governing Law and Disputes">
        <P>
          These Terms and the Bid Preparation Service are governed by the law of the Republic of North Macedonia. The
          parties will try to settle disputes amicably; failing that within 30 days, the competent court in Skopje has
          jurisdiction.
        </P>
      </Section>

      <Section title="14. Miscellaneous">
        <P>
          These Terms, the Privacy Policy and any written terms agreed for a specific bid form the entire agreement.
          If a provision is invalid, the rest remain in force. You may not assign your rights without our written
          consent. We are not liable for delays caused by events beyond our reasonable control, including outages of
          e-nabavki.gov.mk.
        </P>
      </Section>

      <Section title="15. Communications and Unsubscribe">
        <P>
          We may send tender alerts and information about our services with your consent or where we have a
          legitimate interest. You can unsubscribe at any time via the link in each email or by writing to {mailLink}.
        </P>
      </Section>

      <Section title="16. Contact">
        <CompanyCard lang="en" />
      </Section>

      <section className="pt-8 border-t border-muted">
        <p className="text-sm text-muted-foreground text-center">Last updated: {LAST_UPDATED_EN}</p>
        <p className="text-sm text-muted-foreground text-center mt-2">
          By using nabavkidata.com, you agree to these Terms of Service.
        </p>
      </section>
    </div>
  );
}
