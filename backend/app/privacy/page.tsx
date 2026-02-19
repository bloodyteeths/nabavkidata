'use client';

import { useState } from 'react';

export default function PrivacyPage() {
  const [language, setLanguage] = useState<'mk' | 'en'>('mk');

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">
          {language === 'mk' ? 'Политика за приватност' : 'Privacy Policy'}
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

      <div className="prose prose-invert max-w-none">
        {language === 'mk' ? <MacedonianContent /> : <EnglishContent />}
      </div>
    </div>
  );
}

function MacedonianContent() {
  return (
    <>
      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">1. Вовед</h2>
        <p className="text-muted-foreground mb-4">
          Добредојдовте на nabavkidata.com ("Платформата", "ние", "нас" или "нашите"). Ние ја цениме вашата приватност и сме посветени на заштитата на вашите лични податоци. Оваа политика за приватност ќе ве информира како собираме, користиме, чуваме и заштитуваме ваши лични податоци кога ја посетувате нашата веб-страница и ги користите нашите услуги.
        </p>
        <p className="text-muted-foreground">
          nabavkidata.com е платформа за податоци за јавни набавки која автоматски собира и обработува информации од порталот e-nabavki.gov.mk, користи вештачка интелигенција за анализа и резимеа, и нуди услуги на претплата за пристап до напредни функции.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">2. Податоци што ги собираме</h2>
        <p className="text-muted-foreground mb-4">
          Можеме да собираме, користиме, складираме и пренесуваме различни видови лични податоци за вас:
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">2.1 Информации за сметката</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Адреса на е-пошта</li>
          <li>Име и презиме</li>
          <li>Лозинка (шифрирана)</li>
          <li>Информации за корисничкиот профил</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">2.2 Податоци за користење</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Историја на пребарувања и прашања</li>
          <li>Зачувани тендери и преференци</li>
          <li>Број на барања до AI услугите (за ограничување на употреба)</li>
          <li>Историја на користење на чет функцијата</li>
          <li>Модели на пристап до платформата</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">2.3 Технички податоци</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>IP адреса</li>
          <li>Тип и верзија на прелистувач</li>
          <li>Оперативен систем</li>
          <li>Временска зона и локација</li>
          <li>Информации за уредот</li>
          <li>Лог датотеки и податоци за користење</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">2.4 Финансиски податоци</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Информации за плаќање (обработени од Stripe)</li>
          <li>Историја на претплати и трансакции</li>
          <li>Тип на претплата и план</li>
          <li>Историја на фактурирање</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">2.5 Колачиња и слични технологии</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Колачиња за сесија и автентикација</li>
          <li>Колачиња за преференци</li>
          <li>Аналитички колачиња</li>
          <li>Функционални колачиња</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">3. Како ги користиме вашите податоци</h2>
        <p className="text-muted-foreground mb-4">Ги користиме вашите лични податоци за следните цели:</p>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.1 Обезбедување на услуги</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Креирање и управување со вашата корисничка сметка</li>
          <li>Обезбедување пристап до податоци за тендери од e-nabavki.gov.mk</li>
          <li>Генерирање на AI-базирани резимеа и анализи користејќи Google Gemini</li>
          <li>Овозможување на чет функција со AI асистент</li>
          <li>Зачувување на вашите преференци и зачувани тендери</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.2 Ограничување на употреба и контрола</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Следење на вашата употреба на AI услуги за имплементација на лимити на планови</li>
          <li>Спречување на злоупотреба и прекумерна употреба</li>
          <li>Управување со пристапни права според вашиот тип на претплата</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.3 Обработка на плаќања</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Обработка на претплати преку Stripe</li>
          <li>Управување со фактурирање и обновување</li>
          <li>Справување со спорови и рефундации</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.4 Подобрување на услугите</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Анализа на модели на користење за подобрување на платформата</li>
          <li>Развој на нови функции и услуги</li>
          <li>Подобрување на точноста и релевантноста на AI резимеа</li>
          <li>Оптимизација на перформансите на платформата</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.5 Комуникација</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Испраќање на известувања за услугите</li>
          <li>Информирање за промени во услови или политики</li>
          <li>Одговарање на вашите барања и поддршка</li>
          <li>Испраќање на ажурирања за претплата и фактурирање</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.6 Правна усогласеност</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Усогласување со правни обврски</li>
          <li>Заштита од измама и злоупотреба</li>
          <li>Спроведување на нашите услови и одредби</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">4. Споделување на податоци со трети страни</h2>
        <p className="text-muted-foreground mb-4">
          Ние може да ги споделиме вашите лични податоци со следните трети страни:
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.1 Даватели на услуги</h3>
        <div className="mb-4">
          <p className="text-muted-foreground mb-2"><strong>Google (Gemini AI)</strong></p>
          <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4 ml-4">
            <li>Цел: Генерирање на AI резимеа и обезбедување на чет функција</li>
            <li>Податоци споделени: Текст од тендери, корисничко прашања, контекст на разговор</li>
            <li>Локација: Може да се обработуваат надвор од Македонија</li>
            <li>Политика: <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Google Privacy Policy</a></li>
          </ul>

          <p className="text-muted-foreground mb-2"><strong>Stripe</strong></p>
          <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4 ml-4">
            <li>Цел: Обработка на плаќања и управување со претплати</li>
            <li>Податоци споделени: Е-пошта, информации за плаќање, детали за трансакции</li>
            <li>Локација: Податоците може да се обработуваат глобално</li>
            <li>Политика: <a href="https://stripe.com/privacy" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Stripe Privacy Policy</a></li>
          </ul>
        </div>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.2 Јавни извори</h3>
        <p className="text-muted-foreground mb-4">
          Платформата автоматски собира јавно достапни информации за тендери од официјалниот портал e-nabavki.gov.mk. Овие податоци се јавни по природа и не се сметаат за лични податоци од корисниците.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.3 Правни барања</h3>
        <p className="text-muted-foreground mb-4">
          Може да ги откријеме вашите лични податоци ако тоа е потребно со закон, судска наредба, или во одговор на валидни барања од јавни власти.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">5. Складирање и безбедност на податоците</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">5.1 Безбедносни мерки</h3>
        <p className="text-muted-foreground mb-4">
          Ние имплементиравме соодветни технички и организациски безбедносни мерки за да ги заштитиме вашите лични податоци:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Шифрирање на податоци при пренос (SSL/TLS)</li>
          <li>Шифрирање на лозинки користејќи индустриски стандарди</li>
          <li>Безбедна автентикација и управување со сесии</li>
          <li>Редовни безбедносни проверки и ажурирања</li>
          <li>Контроли на пристап и авторизација</li>
          <li>Заштита од чести безбедносни ранливости</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">5.2 Период на чување</h3>
        <p className="text-muted-foreground mb-4">
          Ние ги задржуваме вашите лични податоци онолку колку што е потребно за:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Обезбедување на нашите услуги додека вашата сметка е активна</li>
          <li>Усогласување со правни, сметководствени или известувачки барања</li>
          <li>Решавање на спорови и спроведување на нашите договори</li>
          <li>Легитимни деловни цели и правни обврски</li>
        </ul>
        <p className="text-muted-foreground">
          Кога ќе побарате бришење на сметка, ние ќе ги избришеме или анонимизираме вашите лични податоци, освен ако законот бара да ги задржиме.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">5.3 Меѓународен трансфер</h3>
        <p className="text-muted-foreground mb-4">
          Вашите податоци може да се пренесуваат и обработуваат во земји надвор од Република Македонија, вклучувајќи ги Соединетите Американски Држави (за Google Gemini и Stripe услуги). Обезбедуваме соодветни гаранции за заштита на вашите податоци во согласност со применливите закони за заштита на податоци.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">6. Колачиња и технологии за следење</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">6.1 Типови на колачиња</h3>
        <p className="text-muted-foreground mb-4">Нашата платформа користи следните типови на колачиња:</p>

        <div className="mb-4">
          <p className="text-muted-foreground mb-2"><strong>Суштински колачиња</strong></p>
          <p className="text-muted-foreground mb-2 ml-4">
            Потребни за работа на платформата, вклучувајќи автентикација на сесија и безбедносни функции. Овие колачиња не можат да се оневозможат.
          </p>

          <p className="text-muted-foreground mb-2 mt-4"><strong>Функционални колачиња</strong></p>
          <p className="text-muted-foreground mb-2 ml-4">
            Складираат ваши преференци (јазик, поставки за приказ) за подобро корисничко искуство.
          </p>

          <p className="text-muted-foreground mb-2 mt-4"><strong>Аналитички колачиња</strong></p>
          <p className="text-muted-foreground mb-2 ml-4">
            Помагаат да разбереме како корисниците ја користат платформата за да ја подобриме функционалноста и перформансите.
          </p>
        </div>

        <h3 className="text-xl font-semibold mb-3 mt-6">6.2 Управување со колачиња</h3>
        <p className="text-muted-foreground mb-4">
          Можете да ги контролирате колачињата преку поставките на вашиот прелистувач. Меѓутоа, оневозможувањето на суштинските колачиња може да влијае на функционалноста на платформата.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">7. Вашите права</h2>
        <p className="text-muted-foreground mb-4">
          Во согласност со применливите закони за заштита на податоци, имате следните права:
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.1 Право на пристап</h3>
        <p className="text-muted-foreground mb-4">
          Можете да побарате копија од личните податоци што ги чуваме за вас.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.2 Право на корекција</h3>
        <p className="text-muted-foreground mb-4">
          Можете да побарате да ги коригираме неточни или нецелосни лични податоци.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.3 Право на бришење</h3>
        <p className="text-muted-foreground mb-4">
          Можете да побарате да ги избришеме вашите лични податоци под одредени услови.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.4 Право на ограничување</h3>
        <p className="text-muted-foreground mb-4">
          Можете да побарате ограничување на обработката на вашите лични податоци.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.5 Право на преносливост</h3>
        <p className="text-muted-foreground mb-4">
          Можете да побарате да ги пренесете вашите податоци до друг давател на услуги.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.6 Право на приговор</h3>
        <p className="text-muted-foreground mb-4">
          Можете да се противставите на обработката на вашите лични податоци под одредени околности.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.7 Повлекување на согласност</h3>
        <p className="text-muted-foreground mb-4">
          Каде што обработката се базира на согласност, можете да ја повлечете согласноста во секое време.
        </p>

        <p className="text-muted-foreground mt-6">
          За да ги остварите било кое од овие права, ве молиме контактирајте не на privacy@nabavkidata.com. Ние ќе одговориме на вашето барање во рок од 30 дена.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">8. Заштита на малолетници</h2>
        <p className="text-muted-foreground">
          Нашата платформа не е наменета за лица под 18 години. Ние свесно не собираме лични податоци од малолетници. Ако откриеме дека сме собрале лични податоци од малолетник без соодветна согласност, ќе преземеме чекори за бришење на таквите информации.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">9. Промени на политиката за приватност</h2>
        <p className="text-muted-foreground mb-4">
          Можеме да ја ажурираме оваа политика за приватност од време на време за да ги одразиме промените во нашите практики или од правни причини. Ќе ве известиме за секоја материјална промена преку:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Испраќање на известување на вашата е-пошта адреса</li>
          <li>Објавување на истакнато известување на платформата</li>
          <li>Ажурирање на датумот "Последна ажурирање" на врвот на оваа политика</li>
        </ul>
        <p className="text-muted-foreground">
          Продолжувањето на користењето на платформата по промените значи дека ги прифаќате ревидираните услови.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">10. Контакт и прашања</h2>
        <p className="text-muted-foreground mb-4">
          Ако имате прашања, грижи или барања во врска со оваа политика за приватност или како ги обработуваме вашите лични податоци, ве молиме контактирајте не на:
        </p>
        <div className="bg-secondary/50 p-6 rounded-lg mb-4">
          <p className="text-foreground mb-2"><strong>Компанија:</strong></p>
          <p className="mb-4">Tamsar, Inc.</p>
          <p className="text-foreground mb-2"><strong>Адреса:</strong></p>
          <p className="mb-4">131 Continental Dr Ste 305, New Castle, DE 19713</p>
          <p className="text-foreground mb-2"><strong>E-пошта:</strong></p>
          <p className="mb-4">
            <a href="mailto:privacy@nabavkidata.com" className="text-primary hover:underline">
              privacy@nabavkidata.com
            </a>
          </p>
          <p className="text-foreground mb-2"><strong>Веб-страница:</strong></p>
          <p className="mb-4">
            <a href="https://nabavkidata.com" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
              nabavkidata.com
            </a>
          </p>
        </div>
        <p className="text-muted-foreground">
          Ние сме посветени на решавање на секоја загриженост што можеби ја имате во врска со вашата приватност и заштита на податоци.
        </p>
      </section>

      <section className="mb-8">
        <div className="bg-primary/10 border-l-4 border-primary p-6 rounded">
          <p className="text-sm text-muted-foreground">
            <strong>Последна ажурирање:</strong> Ноември 2025
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            <strong>Верзија:</strong> 1.0
          </p>
        </div>
      </section>
    </>
  );
}

function EnglishContent() {
  return (
    <>
      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">1. Introduction</h2>
        <p className="text-muted-foreground mb-4">
          Welcome to nabavkidata.com (the "Platform", "we", "us", or "our"). We value your privacy and are committed to protecting your personal data. This privacy policy will inform you about how we collect, use, store, and protect your personal information when you visit our website and use our services.
        </p>
        <p className="text-muted-foreground">
          nabavkidata.com is a public procurement data platform that automatically collects and processes information from the e-nabavki.gov.mk portal, uses artificial intelligence for analysis and summaries, and offers subscription-based services for access to advanced features.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">2. Data We Collect</h2>
        <p className="text-muted-foreground mb-4">
          We may collect, use, store, and transfer various types of personal data about you:
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">2.1 Account Information</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Email address</li>
          <li>First and last name</li>
          <li>Password (encrypted)</li>
          <li>User profile information</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">2.2 Usage Data</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Search history and queries</li>
          <li>Saved tenders and preferences</li>
          <li>Number of requests to AI services (for rate limiting)</li>
          <li>Chat function usage history</li>
          <li>Platform access patterns</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">2.3 Technical Data</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>IP address</li>
          <li>Browser type and version</li>
          <li>Operating system</li>
          <li>Time zone and location</li>
          <li>Device information</li>
          <li>Log files and usage data</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">2.4 Financial Data</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Payment information (processed by Stripe)</li>
          <li>Subscription and transaction history</li>
          <li>Subscription type and plan</li>
          <li>Billing history</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">2.5 Cookies and Similar Technologies</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Session and authentication cookies</li>
          <li>Preference cookies</li>
          <li>Analytics cookies</li>
          <li>Functional cookies</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">3. How We Use Your Data</h2>
        <p className="text-muted-foreground mb-4">We use your personal data for the following purposes:</p>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.1 Service Provision</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Creating and managing your user account</li>
          <li>Providing access to tender data from e-nabavki.gov.mk</li>
          <li>Generating AI-powered summaries and analyses using Google Gemini</li>
          <li>Enabling chat functionality with AI assistant</li>
          <li>Saving your preferences and saved tenders</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.2 Rate Limiting and Control</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Tracking your usage of AI services to implement plan limits</li>
          <li>Preventing abuse and excessive usage</li>
          <li>Managing access rights based on your subscription tier</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.3 Payment Processing</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Processing subscriptions through Stripe</li>
          <li>Managing billing and renewals</li>
          <li>Handling disputes and refunds</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.4 Service Improvement</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Analyzing usage patterns to improve the platform</li>
          <li>Developing new features and services</li>
          <li>Improving accuracy and relevance of AI summaries</li>
          <li>Optimizing platform performance</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.5 Communication</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Sending service notifications</li>
          <li>Informing about changes to terms or policies</li>
          <li>Responding to your requests and support inquiries</li>
          <li>Sending subscription and billing updates</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.6 Legal Compliance</h3>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Complying with legal obligations</li>
          <li>Protecting against fraud and abuse</li>
          <li>Enforcing our terms and conditions</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">4. Third-Party Data Sharing</h2>
        <p className="text-muted-foreground mb-4">
          We may share your personal data with the following third parties:
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.1 Service Providers</h3>
        <div className="mb-4">
          <p className="text-muted-foreground mb-2"><strong>Google (Gemini AI)</strong></p>
          <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4 ml-4">
            <li>Purpose: Generating AI summaries and providing chat functionality</li>
            <li>Data shared: Tender text, user queries, conversation context</li>
            <li>Location: May be processed outside of North Macedonia</li>
            <li>Policy: <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Google Privacy Policy</a></li>
          </ul>

          <p className="text-muted-foreground mb-2"><strong>Stripe</strong></p>
          <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4 ml-4">
            <li>Purpose: Payment processing and subscription management</li>
            <li>Data shared: Email, payment information, transaction details</li>
            <li>Location: Data may be processed globally</li>
            <li>Policy: <a href="https://stripe.com/privacy" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Stripe Privacy Policy</a></li>
          </ul>
        </div>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.2 Public Sources</h3>
        <p className="text-muted-foreground mb-4">
          The platform automatically collects publicly available tender information from the official e-nabavki.gov.mk portal. This data is public by nature and is not considered personal data of our users.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.3 Legal Requirements</h3>
        <p className="text-muted-foreground mb-4">
          We may disclose your personal data if required by law, court order, or in response to valid requests from public authorities.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">5. Data Storage and Security</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">5.1 Security Measures</h3>
        <p className="text-muted-foreground mb-4">
          We have implemented appropriate technical and organizational security measures to protect your personal data:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Encryption of data in transit (SSL/TLS)</li>
          <li>Password encryption using industry standards</li>
          <li>Secure authentication and session management</li>
          <li>Regular security audits and updates</li>
          <li>Access controls and authorization</li>
          <li>Protection against common security vulnerabilities</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">5.2 Retention Period</h3>
        <p className="text-muted-foreground mb-4">
          We retain your personal data for as long as necessary to:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Provide our services while your account is active</li>
          <li>Comply with legal, accounting, or reporting requirements</li>
          <li>Resolve disputes and enforce our agreements</li>
          <li>Legitimate business purposes and legal obligations</li>
        </ul>
        <p className="text-muted-foreground">
          When you request account deletion, we will delete or anonymize your personal data unless we are required by law to retain it.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">5.3 International Transfer</h3>
        <p className="text-muted-foreground mb-4">
          Your data may be transferred to and processed in countries outside the Republic of North Macedonia, including the United States (for Google Gemini and Stripe services). We ensure appropriate safeguards are in place to protect your data in accordance with applicable data protection laws.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">6. Cookies and Tracking Technologies</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">6.1 Types of Cookies</h3>
        <p className="text-muted-foreground mb-4">Our platform uses the following types of cookies:</p>

        <div className="mb-4">
          <p className="text-muted-foreground mb-2"><strong>Essential Cookies</strong></p>
          <p className="text-muted-foreground mb-2 ml-4">
            Required for the platform to function, including session authentication and security features. These cookies cannot be disabled.
          </p>

          <p className="text-muted-foreground mb-2 mt-4"><strong>Functional Cookies</strong></p>
          <p className="text-muted-foreground mb-2 ml-4">
            Store your preferences (language, display settings) for an improved user experience.
          </p>

          <p className="text-muted-foreground mb-2 mt-4"><strong>Analytics Cookies</strong></p>
          <p className="text-muted-foreground mb-2 ml-4">
            Help us understand how users interact with the platform to improve functionality and performance.
          </p>
        </div>

        <h3 className="text-xl font-semibold mb-3 mt-6">6.2 Managing Cookies</h3>
        <p className="text-muted-foreground mb-4">
          You can control cookies through your browser settings. However, disabling essential cookies may affect the functionality of the platform.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">7. Your Rights</h2>
        <p className="text-muted-foreground mb-4">
          Under applicable data protection laws, you have the following rights:
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.1 Right to Access</h3>
        <p className="text-muted-foreground mb-4">
          You can request a copy of the personal data we hold about you.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.2 Right to Rectification</h3>
        <p className="text-muted-foreground mb-4">
          You can request that we correct inaccurate or incomplete personal data.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.3 Right to Erasure</h3>
        <p className="text-muted-foreground mb-4">
          You can request that we delete your personal data under certain conditions.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.4 Right to Restriction</h3>
        <p className="text-muted-foreground mb-4">
          You can request restriction of processing of your personal data.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.5 Right to Data Portability</h3>
        <p className="text-muted-foreground mb-4">
          You can request to transfer your data to another service provider.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.6 Right to Object</h3>
        <p className="text-muted-foreground mb-4">
          You can object to the processing of your personal data under certain circumstances.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.7 Withdrawal of Consent</h3>
        <p className="text-muted-foreground mb-4">
          Where processing is based on consent, you can withdraw consent at any time.
        </p>

        <p className="text-muted-foreground mt-6">
          To exercise any of these rights, please contact us at privacy@nabavkidata.com. We will respond to your request within 30 days.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">8. Children's Privacy</h2>
        <p className="text-muted-foreground">
          Our platform is not intended for individuals under 18 years of age. We do not knowingly collect personal data from minors. If we discover that we have collected personal data from a minor without appropriate consent, we will take steps to delete such information.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">9. Changes to Privacy Policy</h2>
        <p className="text-muted-foreground mb-4">
          We may update this privacy policy from time to time to reflect changes in our practices or for legal reasons. We will notify you of any material changes by:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 mb-4">
          <li>Sending a notice to your email address</li>
          <li>Posting a prominent notice on the platform</li>
          <li>Updating the "Last Updated" date at the top of this policy</li>
        </ul>
        <p className="text-muted-foreground">
          Continued use of the platform after changes constitutes acceptance of the revised terms.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">10. Contact and Questions</h2>
        <p className="text-muted-foreground mb-4">
          If you have questions, concerns, or requests regarding this privacy policy or how we handle your personal data, please contact us at:
        </p>
        <div className="bg-secondary/50 p-6 rounded-lg mb-4">
          <p className="text-foreground mb-2"><strong>Company:</strong></p>
          <p className="mb-4">Tamsar, Inc.</p>
          <p className="text-foreground mb-2"><strong>Address:</strong></p>
          <p className="mb-4">131 Continental Dr Ste 305, New Castle, DE 19713</p>
          <p className="text-foreground mb-2"><strong>Email:</strong></p>
          <p className="mb-4">
            <a href="mailto:privacy@nabavkidata.com" className="text-primary hover:underline">
              privacy@nabavkidata.com
            </a>
          </p>
          <p className="text-foreground mb-2"><strong>Website:</strong></p>
          <p className="mb-4">
            <a href="https://nabavkidata.com" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
              nabavkidata.com
            </a>
          </p>
        </div>
        <p className="text-muted-foreground">
          We are committed to resolving any concerns you may have about your privacy and data protection.
        </p>
      </section>

      <section className="mb-8">
        <div className="bg-primary/10 border-l-4 border-primary p-6 rounded">
          <p className="text-sm text-muted-foreground">
            <strong>Last Updated:</strong> November 2025
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            <strong>Version:</strong> 1.0
          </p>
        </div>
      </section>
    </>
  );
}
