'use client';

import { useState } from 'react';

export default function TermsPage() {
  const [language, setLanguage] = useState<'mk' | 'en'>('mk');

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="flex justify-between items-center mb-8">
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

function MacedonianTerms() {
  return (
    <div className="prose prose-invert max-w-none space-y-8">
      <section>
        <p className="text-sm text-muted-foreground mb-6">
          Последно ажурирање: Ноември 2025
        </p>
        <p className="text-muted-foreground mb-6">
          Ве молиме внимателно прочитајте ги овие Услови за користење ("Услови", "Услови за користење") пред да ја користите
          веб-страницата nabavkidata.com (заедно или индивидуално "Услугата") управувана од Tamsar, Inc. ("нас", "ние", или "наш").
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">1. Прифаќање на условите</h2>
        <p className="text-muted-foreground mb-4">
          Со пристапувањето и користењето на платформата, вие се согласувате да ги прифатите и да се придржувате
          кон овие Услови за користење и сите применливи закони и прописи. Ако не се согласувате со кој било од овие услови,
          ве молиме не користете ја нашата платформа.
        </p>
        <p className="text-muted-foreground">
          Вашиот пристап до и користење на Услугата е исто така условен со вашето прифаќање и усогласеност со нашата Политика
          за приватност. Нашата Политика за приватност ги опишува нашите политики и процедури за собирање, користење и
          откривање на вашите лични информации кога ја користите Услугата.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">2. Опис на услугата</h2>
        <p className="text-muted-foreground mb-4">
          nabavkidata.com е платформа за анализа и следење на јавни набавки и тендери во Република Северна
          Македонија, управувана од Tamsar, Inc. Нашата Услуга обезбедува:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Пристап до обемна база на податоци за тендери и јавни набавки</li>
          <li>AI-базирана анализа на тендерска документација и конкурентност</li>
          <li>Интелигентни препораки за релевантни тендери</li>
          <li>Персонализирана контролна табла со детални инсајти и статистики</li>
          <li>Следење и анализа на конкуренти</li>
          <li>Известувања во реално време за нови тендери</li>
          <li>Напредни алатки за пребарување и филтрирање</li>
          <li>Извештаи и аналитика за пазарни трендови</li>
        </ul>
        <p className="text-muted-foreground mt-4">
          Податоците што ги обезбедуваме се собираат од јавно достапни извори, вклучувајќи официјални портали за јавни набавки
          и владини веб-страници. Ние не гарантираме апсолутна точност, комплетност или ажурност на податоците, иако се
          трудиме да ги одржуваме информациите точни и навремени.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">3. Кориснички профил и право на пристап</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.1 Креирање на профил</h3>
        <p className="text-muted-foreground mb-4">За користење на нашите услуги, мора да:</p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Креирате кориснички профил со точни, комплетни и ажурни информации</li>
          <li>Бидете најмалку 18 години стари</li>
          <li>Имате правна способност да склучувате обврзувачки договори</li>
          <li>Обезбедите валидна е-маил адреса</li>
          <li>Одржувате ја безбедноста и доверливоста на вашата лозинка</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.2 Одговорност за профилот</h3>
        <p className="text-muted-foreground mb-4">Вие сте одговорни за:</p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Сите активности што се случуваат под вашиот кориснички профил</li>
          <li>Одржување на доверливоста на вашите креденцијали за најава</li>
          <li>Известување на Tamsar, Inc. веднаш за било какво неовластено користење на вашиот профил</li>
          <li>Обезбедување дека вашите информации за контакт се ажурирани</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.3 Ограничувања на профилот</h3>
        <p className="text-muted-foreground">
          Вие не смеете да креирате повеќе од еден бесплатен профил за да ги заобиколите ограничувањата за користење.
          Пронајдени повеќекратни профили со намера на злоупотреба може да резултираат со прекин на сите поврзани сметки.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">4. Нивоа на претплата и плаќања</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.1 Достапни пакети</h3>
        <p className="text-muted-foreground mb-4">
          Нудиме различни нивоа на претплата прилагодени на различни потреби. Сите цени се прикажани во евра (EUR) и не
          вклучуваат применливи даноци:
        </p>

        <div className="space-y-4 ml-4 not-prose">
          <div className="border border-muted rounded-lg p-4">
            <h4 className="text-lg font-semibold mb-2 text-foreground">FREE (Бесплатно)</h4>
            <p className="text-muted-foreground mb-2"><strong>Цена:</strong> €0.00/месец</p>
            <p className="text-muted-foreground mb-2"><strong>Карактеристики:</strong></p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4">
              <li>3 AI пребарувања/анализи дневно</li>
              <li>14-дневен пробен период за пристап до платени функции</li>
              <li>Ограничен пристап до база на податоци за тендери</li>
              <li>Основни филтри за пребарување</li>
            </ul>
          </div>

          <div className="border border-muted rounded-lg p-4">
            <h4 className="text-lg font-semibold mb-2 text-foreground">STARTER (Почетен)</h4>
            <p className="text-muted-foreground mb-2"><strong>Цена:</strong> €14.99/месец</p>
            <p className="text-muted-foreground mb-2"><strong>Карактеристики:</strong></p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4">
              <li>5 AI пребарувања/анализи дневно</li>
              <li>Целосен пристап до база на податоци за тендери</li>
              <li>Основна AI анализа и препораки</li>
              <li>Е-маил известувања</li>
              <li>Основна контролна табла</li>
            </ul>
          </div>

          <div className="border border-muted rounded-lg p-4">
            <h4 className="text-lg font-semibold mb-2 text-foreground">PROFESSIONAL (Професионален)</h4>
            <p className="text-muted-foreground mb-2"><strong>Цена:</strong> €39.99/месец</p>
            <p className="text-muted-foreground mb-2"><strong>Карактеристики:</strong></p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4">
              <li>20 AI пребарувања/анализи дневно</li>
              <li>Напредна AI анализа и детални инсајти</li>
              <li>Следење на конкуренти</li>
              <li>Приоритетни известувања</li>
              <li>Персонализирана контролна табла</li>
              <li>Напредна аналитика и извештаи</li>
              <li>Приоритетна поддршка</li>
            </ul>
          </div>

          <div className="border border-muted rounded-lg p-4">
            <h4 className="text-lg font-semibold mb-2 text-foreground">ENTERPRISE (Деловен)</h4>
            <p className="text-muted-foreground mb-2"><strong>Цена:</strong> €99.99/месец</p>
            <p className="text-muted-foreground mb-2"><strong>Карактеристики:</strong></p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4">
              <li>Неограничени AI пребарувања/анализи</li>
              <li>Сите професионални функции</li>
              <li>API пристап (доколку е достапен)</li>
              <li>Прилагодени извештаи</li>
              <li>Посветен менаџер на сметка</li>
              <li>Обука и онбоардинг</li>
              <li>24/7 премиум поддршка</li>
            </ul>
          </div>
        </div>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.2 Услови за плаќање</h3>
        <p className="text-muted-foreground mb-4">
          Плаќањата се обработуваат безбедно преку Stripe, наш провајдер за обработка на плаќања од трета страна.
          Со обезбедување на информациите за плаќање, вие гарантирате дека:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Имате законско право да го користите методот на плаќање</li>
          <li>Обезбедените информации се точни и комплетни</li>
          <li>Овластувате нас да ја наплатиме вашата сметка за претплатата</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.3 Автоматско обновување</h3>
        <p className="text-muted-foreground mb-4">
          Сите платени претплати се обновуваат автоматски на крајот на секој период на наплата (месечно) освен ако не
          откажете пред датумот на обновување. Ќе бидете наплатени на истата цена, освен ако не добиете претходно
          известување за промена на цената.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.4 Промена на ценовни пакети</h3>
        <p className="text-muted-foreground">
          Можете да го надоградите или намалите вашиот пакет во било кое време преку вашата контролна табла.
          При надоградба, пропорционалниот износ ќе биде пресметан автоматски. При намалување, промените ќе се
          применат на почетокот на следниот период на наплата.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.5 Даноци</h3>
        <p className="text-muted-foreground">
          Сите цени се прикажани без данок. Вие сте одговорни за плаќање на било кои применливи даноци, вклучувајќи
          ДДВ, даноци на промет или други даноци поврзани со вашата претплата.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">5. Откажување и враќање на средства</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">5.1 Откажување</h3>
        <p className="text-muted-foreground mb-4">
          Можете да ја откажете вашата претплата во било кое време преку вашата контролна табла за поставки или со
          контактирање на нашиот тим за поддршка. Откажувањето ќе стапи на сила на крајот на тековниот период на наплата,
          и ќе продолжите да имате пристап до платените функции до тогаш.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">5.2 Политика за враќање</h3>
        <p className="text-muted-foreground mb-4">
          Општо, не нудиме враќање на средства за делумно искористени периоди на претплата. Сепак, во исклучителни
          околности, можеме да разгледаме барања за враќање на средства на индивидуална основа:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Технички проблеми што спречуваат пристап до услугата</li>
          <li>Двојна наплата или грешки во наплата</li>
          <li>Откажување во првите 48 часа од првото плаќање</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">5.3 Прекин од наша страна</h3>
        <p className="text-muted-foreground">
          Ако ја прекинеме вашата претплата поради кршење на овие Услови, нема да биде обезбедено враќање на средства.
          Ако ја прекинеме услугата поради технички причини или деловни одлуки, ќе обезбедиме пропорционално враќање за
          неискористениот дел од вашата претплата.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">6. Прифатливо користење и задолженија на корисниците</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">6.1 Дозволено користење</h3>
        <p className="text-muted-foreground mb-4">
          Вие се согласувате да ја користите Услугата само за законски цели и на начин што не ги повредува правата на,
          или го ограничува или спречува користењето и уживањето на Услугата од страна на било која трета страна.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">6.2 Забранети активности</h3>
        <p className="text-muted-foreground mb-4">Се согласувате да НЕ:</p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Користите ја платформата за незаконски цели или за да ги прекршите било кои локални, државни, национални или меѓународни закони</li>
          <li>Се обидувате да пристапите до системите, серверите или мрежите без овластување</li>
          <li>Вршите автоматизирано скрепување, извлекување податоци или собирање податоци без изрична писмена дозвола</li>
          <li>Пренесувате вируси, малициозен софтвер или друг штетен компјутерски код</li>
          <li>Ја злоупотребувате AI функционалноста преку праќање на несоодветно содржина или обиди за надминување на ограничувањата</li>
          <li>Споделувате ги вашите креденцијали за најава со други или дозволувате пристап до вашиот профил од повеќе корисници</li>
          <li>Се обидувате да ги заобиколите ограничувањата за користење, вклучувајќи креирање на повеќе профили</li>
          <li>Се обидувате да реверзно инженерирате, декомпилирате или дизасемблирате било кој дел од Услугата</li>
          <li>Користите ја Услугата за создавање на конкурентен производ или услуга</li>
          <li>Отстранувате, прикривате или менувате било какви известувања за авторски права, трговски марки или други права на сопственост</li>
          <li>Намерно пратите погрешни, измамни или заведувачки информации</li>
          <li>Се обидувате да ја нарушите безбедноста или интегритетот на платформата</li>
          <li>Вршите активности што прекумерно оптоваруваат или ја оневозможуваат инфраструктурата</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">6.3 Ограничувања на стапка и превенција од измами</h3>
        <p className="text-muted-foreground">
          Ние применуваме ограничувања на стапка за да ја заштитиме платформата и да обезбедиме фер користење за сите
          корисници. Прекумерно користење или активности што ги надминуваат нормалните обрасци може да резултираат со
          привремено или трајно суспендирање. Исто така, користиме систем за детекција на измами за да ги идентификуваме
          и спречиме злоупотребите, неовластени пристапи и други злонамерни активности.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">7. Интелектуална сопственост</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.1 Наша сопственост</h3>
        <p className="text-muted-foreground mb-4">
          Услугата и нејзините оригинални содржини, карактеристики и функционалност се и ќе останат исклучива сопственост
          на Tamsar, Inc. и нејзините лиценцери. Услугата е заштитена со авторски права, трговски марки и други закони.
          Нашите трговски марки и облик не смеат да се користат без претходна писмена дозвола.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.2 Вашата лиценца за користење</h3>
        <p className="text-muted-foreground mb-4">
          Под услов да ги почитувате овие Услови, ние ви даваме ограничена, необнадена, непренослива, неексклузивна,
          отповиклива лиценца за пристап и користење на Услугата за вашите лични или деловни цели.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.3 Податоци од јавни извори</h3>
        <p className="text-muted-foreground mb-4">
          Податоците за тендери и набавки што ги агрегираме се од јавно достапни извори и владини портали. Додека
          податоците самите можеби се јавна информација, нашето собирање, организација, презентација и AI-анализа на
          тие податоци претставуваат наша интелектуална сопственост.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.4 Генериран содржина од AI</h3>
        <p className="text-muted-foreground">
          Анализите, инсајтите и препораките генерирани од нашите AI алгоритми се обезбедени за ваше користење во
          рамките на платформата. Вие можете да ги користите овие инсајти за вашите деловни цели, но не смеете да ги
          репродуцирате, дистрибуирате или препродавате како самостоен производ или услуга.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">8. Приватност и заштита на податоци</h2>
        <p className="text-muted-foreground mb-4">
          Вашата приватност е важна за нас. Нашата Политика за приватност објаснува како ги собираме, користиме,
          чуваме и заштитуваме вашите лични податоци. Со користење на Услугата, се согласувате со собирањето и
          користењето на информации во согласност со нашата Политика за приватност.
        </p>
        <p className="text-muted-foreground">
          Ние се придржуваме кон применливите закони за заштита на податоци, вклучувајќи GDPR и локалните македонски
          прописи за заштита на лични податоци.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">9. Гаранции и одговорности</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">9.1 Одрекување од гаранции</h3>
        <p className="text-muted-foreground mb-4">
          Услугата е обезбедена "КАКО ШТО Е" и "КАКО ШТО Е ДОСТАПНА" основа, без гаранции од каков било вид, експлицитни
          или имплицитни. Без да се ограничи погоре наведеното, ние изрично се откажуваме од сите гаранции, дали
          експлицитни, имплицитни, законски или други, вклучувајќи но не ограничени на:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Гаранции за продажливост, прикладност за одредена цел и непреченост</li>
          <li>Гаранции дека Услугата ќе биде непрекината, навремена, безбедна или без грешки</li>
          <li>Гаранции за точност, комплетност или веродостојност на информациите обезбедени преку Услугата</li>
          <li>Гаранции дека недостатоците ќе бидат коригирани</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">9.2 Точност на податоците</h3>
        <p className="text-muted-foreground">
          Додека полагаме разумни напори да обезбедиме точни и ажурни информации, ние не гарантираме точност, комплетност
          или ажурност на податоците за тендери и набавки. Податоците се обезбедени само за информативни цели. Вие сте
          одговорни да ги верификувате сите информации преку официјални владини канали пред да презмете било какви
          дејствија врз основа на податоците од нашата платформа.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">9.3 AI-генериран содржина</h3>
        <p className="text-muted-foreground">
          AI анализите, препораките и инсајтите се генерирани од автоматизирани системи и треба да се сметаат за
          помошни алатки, не како професионален совет. Не гарантираме точност, комплетност или соодветност на
          AI-генерираниот содржина за вашите специфични потреби.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">10. Ограничување на одговорност</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">10.1 Ограничување на одговорност</h3>
        <p className="text-muted-foreground mb-4">
          До максималниот обем дозволен од применливото право, во никој случај Tamsar, Inc., неговите директори,
          вработени, партнери, агенти, добавувачи или филијали нема да бидат одговорни за било какви индиректни,
          случајни, специјални, последични или казнени штети, вклучувајќи без ограничување, загуба на профит, податоци,
          користење, добра волја, или други нематеријални загуби, што произлегуваат од:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Вашиот пристап до или користење или неможност за пристап или користење на Услугата</li>
          <li>Било какво однесување или содржина на трети страни на Услугата</li>
          <li>Неовластен пристап, користење или измена на вашите пренесувања или содржина</li>
          <li>Грешки, неточности или пропусти во податоците</li>
          <li>Деловни одлуки донесени врз основа на информации од Услугата</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">10.2 Максимална одговорност</h3>
        <p className="text-muted-foreground">
          До максималниот обем дозволен од применливото право, нашата вкупна одговорност кон вас за сите барања
          поврзани со Услугата е ограничена на износот што сте го платиле до нас во последните 12 месеци или €100,
          која било што е поголема.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">11. Обесштетување</h2>
        <p className="text-muted-foreground">
          Вие се согласувате да ги браните, обесштетите и да ги ослободите Tamsar, Inc. и неговите филијали,
          партнери, службеници, директори, вработени, агенти и лиценцери од и против било какви и сите барања,
          штети, обврски, загуби, одговорности, трошоци или долг, и расходи (вклучувајќи, но не ограничени на,
          адвокатски хонорари), кои произлегуваат од:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4 mt-4">
          <li>Вашето користење и пристап до Услугата</li>
          <li>Вашето кршење на овие Услови</li>
          <li>Вашето кршење на било кое право на трета страна</li>
          <li>Вашето кршење на применливиот закон или пропис</li>
        </ul>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">12. Измени на услугата и условите</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">12.1 Измени на услугата</h3>
        <p className="text-muted-foreground">
          Го задржуваме правото да ја изменуваме, суспендираме или прекинеме Услугата (или било кој дел или содржина
          на истата) во било кое време без претходно известување. Нема да бидеме одговорни кон вас или кон било која
          трета страна за било каква измена, суспензија или прекин на Услугата.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">12.2 Измени на условите</h3>
        <p className="text-muted-foreground">
          Можеме да ги ревидираме овие Услови од време на време по наше апсолутно дискреција. Сите промени стапуваат
          на сила веднаш кога ќе бидат објавени. Ќе ве известиме за значајни промени преку е-пошта или преку истакнато
          известување на платформата. Вашето продолжено користење на Услугата по објавувањето на ревидираните Услови
          значи дека ги прифаќате и се согласувате со промените.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">13. Прекин и суспензија</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">13.1 Прекин од наша страна</h3>
        <p className="text-muted-foreground mb-4">
          Можеме да го прекинеме или суспендираме вашиот пристап до Услугата веднаш, без претходно известување или
          одговорност, по наше апсолутно дискреција, за било која причина, вклучувајќи, но не ограничени на:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Кршење на овие Услови за користење</li>
          <li>Активности што нè излагаат или ги излагаат другите корисници на ризик</li>
          <li>Измамнички или незаконски активности</li>
          <li>Непрекинато злоупотреба на Услугата</li>
          <li>Барање од владина агенција или агенција за спроведување на законот</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">13.2 Прекин од ваша страна</h3>
        <p className="text-muted-foreground">
          Можете да го прекинете вашиот профил во било кое време со избришување на вашиот профил или со контактирање
          на нашиот тим за поддршка. По прекин, вашето право да ја користите Услугата ќе престане веднаш.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">13.3 Ефект на прекин</h3>
        <p className="text-muted-foreground">
          По прекин на вашиот профил, сите одредби на овие Услови кои по својата природа треба да преживеат прекинот
          ќе преживеат, вклучувајќи, без ограничување, одредби за сопственост, одрекување од гаранции, обесштетување
          и ограничувања на одговорност.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">14. Применливо право и решавање на спорови</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">14.1 Применливо право</h3>
        <p className="text-muted-foreground">
          Овие Услови се регулирани и толкуваат во согласност со законите на Република Северна Македонија, без оглед
          на нејзините одредби за конфликт на закони.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">14.2 Решавање на спорови</h3>
        <p className="text-muted-foreground">
          Сите спорови што произлегуваат од или се поврзани со овие Услови или Услугата прво ќе се обидеме да ги
          решиме преку пријателски преговори. Ако споровите не можат да се решат преку преговори во рок од 30 дена,
          ќе бидат решени од надлежните судови во Скопје, Република Северна Македонија.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">14.3 Јуриздикција</h3>
        <p className="text-muted-foreground">
          Вие се согласувате да се потчините на личната и исклучивата јуриздикција на судовите лоцирани во Скопје,
          Северна Македонија, и се откажувате од било какви приговори за местото или forum non conveniens.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">15. Разни одредби</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">15.1 Целосен договор</h3>
        <p className="text-muted-foreground">
          Овие Услови, заедно со нашата Политика за приватност, сочинуваат целосен договор помеѓу вас и Tamsar, Inc.
          во однос на Услугата и ги заменуваат сите претходни и истовремени разбирања и договори.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">15.2 Одвојување</h3>
        <p className="text-muted-foreground">
          Ако било која одредба на овие Услови се смета за неважечка или неприменлива од страна на суд, преостанатите
          одредби ќе продолжат да бидат на сила. Неважечките одредби ќе бидат заменети со важечки одредби кои најмногу
          се приближуваат на намерата на оригиналната одредба.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">15.3 Одрекување</h3>
        <p className="text-muted-foreground">
          Нашето неуспеавање да спроведеме било кое право или одредба на овие Услови нема да се смета за одрекување
          од тоа право или одредба. Било какво одрекување од која било одредба на овие Услови ќе биде ефективно само
          ако е во писмена форма и потпишано од нас.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">15.4 Задача</h3>
        <p className="text-muted-foreground">
          Вие не можете да ги задавате или пренесете овие Услови или вашите права и обврски под истите без наша
          претходна писмена согласност. Ние можеме да ги задаваме овие Услови без ограничување.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">15.5 Виша сила</h3>
        <p className="text-muted-foreground">
          Нема да бидеме одговорни за било какво неуспеавање или доцнење во извршувањето на нашите обврски под
          овие Услови поради околности надвор од нашата разумна контрола, вклучувајќи природни катастрофи, војна,
          тероризам, вознемирувања, граѓански немири, недостиг на работна сила, опрема, материјали или транспорт,
          владини дејства или откази на комунални услуги.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">16. Контакт информации</h2>
        <p className="text-muted-foreground mb-4">
          Ако имате било какви прашања, забелешки или барања во врска со овие Услови за користење, ве молиме
          контактирајте не на:
        </p>
        <div className="bg-muted/30 rounded-lg p-4 space-y-2 not-prose">
          <p className="text-muted-foreground">
            <strong>Tamsar, Inc.</strong>
          </p>
          <p className="text-muted-foreground">
            Адреса: 131 Continental Dr Ste 305, New Castle, DE 19713
          </p>
          <p className="text-muted-foreground">
            Е-пошта: <a href="mailto:support@nabavkidata.com" className="text-primary hover:underline">support@nabavkidata.com</a>
          </p>
          <p className="text-muted-foreground">
            Веб-страница: <a href="https://nabavkidata.com" className="text-primary hover:underline">https://nabavkidata.com</a>
          </p>
        </div>
      </section>

      <section className="pt-8 border-t border-muted">
        <p className="text-sm text-muted-foreground text-center">
          Последно ажурирање: Ноември 2025
        </p>
        <p className="text-sm text-muted-foreground text-center mt-2">
          Со користење на nabavkidata.com, вие се согласувате да ги прифатите овие Услови за користење.
        </p>
      </section>
    </div>
  );
}

function EnglishTerms() {
  return (
    <div className="prose prose-invert max-w-none space-y-8">
      <section>
        <p className="text-sm text-muted-foreground mb-6">
          Last Updated: November 2025
        </p>
        <p className="text-muted-foreground mb-6">
          Please read these Terms of Service ("Terms", "Terms of Service") carefully before using the nabavkidata.com
          website (the "Service") operated by Tamsar, Inc. ("us", "we", or "our").
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">1. Acceptance of Terms</h2>
        <p className="text-muted-foreground mb-4">
          By accessing and using the platform, you agree to accept and comply with these Terms of Service
          and all applicable laws and regulations. If you do not agree with any of these terms, please do not use our platform.
        </p>
        <p className="text-muted-foreground">
          Your access to and use of the Service is also conditioned on your acceptance of and compliance with our Privacy
          Policy. Our Privacy Policy describes our policies and procedures on the collection, use and disclosure of your
          personal information when you use the Service.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">2. Service Description</h2>
        <p className="text-muted-foreground mb-4">
          nabavkidata.com is a platform for analyzing and tracking public procurement and tenders in the
          Republic of North Macedonia, operated by Tamsar, Inc. Our Service provides:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Access to a comprehensive database of tenders and public procurements</li>
          <li>AI-powered analysis of tender documentation and competitiveness</li>
          <li>Intelligent recommendations for relevant tenders</li>
          <li>Personalized dashboard with detailed insights and statistics</li>
          <li>Competitor tracking and analysis</li>
          <li>Real-time notifications for new tenders</li>
          <li>Advanced search and filtering tools</li>
          <li>Reports and analytics on market trends</li>
        </ul>
        <p className="text-muted-foreground mt-4">
          The data we provide is collected from publicly available sources, including official public procurement portals
          and government websites. We do not guarantee absolute accuracy, completeness, or timeliness of the data, though
          we strive to keep information accurate and up-to-date.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">3. User Account and Access Rights</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.1 Account Creation</h3>
        <p className="text-muted-foreground mb-4">To use our services, you must:</p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Create a user account with accurate, complete, and current information</li>
          <li>Be at least 18 years old</li>
          <li>Have legal capacity to enter into binding contracts</li>
          <li>Provide a valid email address</li>
          <li>Maintain the security and confidentiality of your password</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.2 Account Responsibility</h3>
        <p className="text-muted-foreground mb-4">You are responsible for:</p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>All activities that occur under your user account</li>
          <li>Maintaining the confidentiality of your login credentials</li>
          <li>Notifying Tamsar, Inc. immediately of any unauthorized use of your account</li>
          <li>Ensuring that your contact information is up-to-date</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">3.3 Account Limitations</h3>
        <p className="text-muted-foreground">
          You may not create more than one free account to circumvent usage limitations. Multiple accounts found to be
          created with intent to abuse may result in termination of all associated accounts.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">4. Subscription Tiers and Payments</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.1 Available Plans</h3>
        <p className="text-muted-foreground mb-4">
          We offer different subscription tiers tailored to different needs. All prices are displayed in Euros (EUR) and
          do not include applicable taxes:
        </p>

        <div className="space-y-4 ml-4 not-prose">
          <div className="border border-muted rounded-lg p-4">
            <h4 className="text-lg font-semibold mb-2 text-foreground">FREE</h4>
            <p className="text-muted-foreground mb-2"><strong>Price:</strong> €0.00/month</p>
            <p className="text-muted-foreground mb-2"><strong>Features:</strong></p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4">
              <li>3 AI queries/analyses per day</li>
              <li>14-day trial period for premium features</li>
              <li>Limited access to tender database</li>
              <li>Basic search filters</li>
            </ul>
          </div>

          <div className="border border-muted rounded-lg p-4">
            <h4 className="text-lg font-semibold mb-2 text-foreground">STARTER</h4>
            <p className="text-muted-foreground mb-2"><strong>Price:</strong> €14.99/month</p>
            <p className="text-muted-foreground mb-2"><strong>Features:</strong></p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4">
              <li>5 AI queries/analyses per day</li>
              <li>Full access to tender database</li>
              <li>Basic AI analysis and recommendations</li>
              <li>Email notifications</li>
              <li>Basic dashboard</li>
            </ul>
          </div>

          <div className="border border-muted rounded-lg p-4">
            <h4 className="text-lg font-semibold mb-2 text-foreground">PROFESSIONAL</h4>
            <p className="text-muted-foreground mb-2"><strong>Price:</strong> €39.99/month</p>
            <p className="text-muted-foreground mb-2"><strong>Features:</strong></p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4">
              <li>20 AI queries/analyses per day</li>
              <li>Advanced AI analysis and detailed insights</li>
              <li>Competitor tracking</li>
              <li>Priority notifications</li>
              <li>Personalized dashboard</li>
              <li>Advanced analytics and reports</li>
              <li>Priority support</li>
            </ul>
          </div>

          <div className="border border-muted rounded-lg p-4">
            <h4 className="text-lg font-semibold mb-2 text-foreground">ENTERPRISE</h4>
            <p className="text-muted-foreground mb-2"><strong>Price:</strong> €99.99/month</p>
            <p className="text-muted-foreground mb-2"><strong>Features:</strong></p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4">
              <li>Unlimited AI queries/analyses</li>
              <li>All Professional features</li>
              <li>API access (if available)</li>
              <li>Custom reports</li>
              <li>Dedicated account manager</li>
              <li>Training and onboarding</li>
              <li>24/7 premium support</li>
            </ul>
          </div>
        </div>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.2 Payment Terms</h3>
        <p className="text-muted-foreground mb-4">
          Payments are processed securely through Stripe, our third-party payment processor. By providing payment
          information, you warrant that:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>You have the legal right to use the payment method</li>
          <li>The information provided is accurate and complete</li>
          <li>You authorize us to charge your account for the subscription</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.3 Automatic Renewal</h3>
        <p className="text-muted-foreground mb-4">
          All paid subscriptions automatically renew at the end of each billing period (monthly) unless canceled before
          the renewal date. You will be charged at the same rate unless you receive prior notice of a price change.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.4 Plan Changes</h3>
        <p className="text-muted-foreground">
          You may upgrade or downgrade your plan at any time through your account dashboard. Upon upgrading, the
          prorated amount will be calculated automatically. Upon downgrading, changes will apply at the start of the
          next billing period.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">4.5 Taxes</h3>
        <p className="text-muted-foreground">
          All prices are exclusive of taxes. You are responsible for paying any applicable taxes, including VAT, sales
          tax, or other taxes associated with your subscription.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">5. Cancellation and Refunds</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">5.1 Cancellation</h3>
        <p className="text-muted-foreground mb-4">
          You may cancel your subscription at any time through your account settings dashboard or by contacting our
          support team. Cancellation will take effect at the end of the current billing period, and you will continue
          to have access to paid features until then.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">5.2 Refund Policy</h3>
        <p className="text-muted-foreground mb-4">
          Generally, we do not offer refunds for partially used subscription periods. However, in exceptional
          circumstances, we may consider refund requests on a case-by-case basis:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Technical issues preventing access to the service</li>
          <li>Duplicate billing or billing errors</li>
          <li>Cancellation within 48 hours of first payment</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">5.3 Termination by Us</h3>
        <p className="text-muted-foreground">
          If we terminate your subscription due to breach of these Terms, no refund will be provided. If we terminate
          the service for technical reasons or business decisions, we will provide a prorated refund for the unused
          portion of your subscription.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">6. Acceptable Use and User Obligations</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">6.1 Permitted Use</h3>
        <p className="text-muted-foreground mb-4">
          You agree to use the Service only for lawful purposes and in a manner that does not infringe the rights of,
          restrict or inhibit anyone else's use and enjoyment of the Service.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">6.2 Prohibited Activities</h3>
        <p className="text-muted-foreground mb-4">You agree NOT to:</p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Use the platform for illegal purposes or to violate any local, state, national, or international law</li>
          <li>Attempt to gain unauthorized access to systems, servers, or networks</li>
          <li>Perform automated scraping, data extraction, or data collection without express written permission</li>
          <li>Transmit viruses, malware, or other harmful computer code</li>
          <li>Abuse AI functionality by sending inappropriate content or attempting to bypass limitations</li>
          <li>Share your login credentials with others or allow multiple users to access your account</li>
          <li>Attempt to circumvent usage limitations, including creating multiple accounts</li>
          <li>Attempt to reverse engineer, decompile, or disassemble any part of the Service</li>
          <li>Use the Service to create a competitive product or service</li>
          <li>Remove, obscure, or alter any copyright, trademark, or other proprietary rights notices</li>
          <li>Intentionally submit false, fraudulent, or misleading information</li>
          <li>Attempt to disrupt the security or integrity of the platform</li>
          <li>Engage in activities that excessively burden or disable the infrastructure</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">6.3 Rate Limiting and Fraud Prevention</h3>
        <p className="text-muted-foreground">
          We implement rate limiting to protect the platform and ensure fair usage for all users. Excessive usage or
          activities that exceed normal patterns may result in temporary or permanent suspension. We also employ fraud
          detection systems to identify and prevent abuse, unauthorized access, and other malicious activities.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">7. Intellectual Property</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.1 Our Property</h3>
        <p className="text-muted-foreground mb-4">
          The Service and its original content, features, and functionality are and will remain the exclusive property
          of Tamsar, Inc. and its licensors. The Service is protected by copyright, trademark, and other laws. Our
          trademarks and trade dress may not be used without prior written permission.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.2 Your License to Use</h3>
        <p className="text-muted-foreground mb-4">
          Subject to your compliance with these Terms, we grant you a limited, non-sublicensable, non-transferable,
          non-exclusive, revocable license to access and use the Service for your personal or business purposes.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.3 Public Source Data</h3>
        <p className="text-muted-foreground mb-4">
          The tender and procurement data we aggregate is from publicly available sources and government portals. While
          the data itself may be public information, our collection, organization, presentation, and AI analysis of that
          data constitutes our intellectual property.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">7.4 AI-Generated Content</h3>
        <p className="text-muted-foreground">
          The analyses, insights, and recommendations generated by our AI algorithms are provided for your use within
          the platform. You may use these insights for your business purposes but may not reproduce, distribute, or
          resell them as a standalone product or service.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">8. Privacy and Data Protection</h2>
        <p className="text-muted-foreground mb-4">
          Your privacy is important to us. Our Privacy Policy explains how we collect, use, store, and protect your
          personal data. By using the Service, you agree to the collection and use of information in accordance with
          our Privacy Policy.
        </p>
        <p className="text-muted-foreground">
          We comply with applicable data protection laws, including GDPR and local Macedonian personal data protection
          regulations.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">9. Warranties and Disclaimers</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">9.1 Disclaimer of Warranties</h3>
        <p className="text-muted-foreground mb-4">
          The Service is provided on an "AS IS" and "AS AVAILABLE" basis, without warranties of any kind, either express
          or implied. Without limiting the foregoing, we expressly disclaim all warranties, whether express, implied,
          statutory, or otherwise, including but not limited to:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Warranties of merchantability, fitness for a particular purpose, and non-infringement</li>
          <li>Warranties that the Service will be uninterrupted, timely, secure, or error-free</li>
          <li>Warranties regarding the accuracy, completeness, or reliability of information provided through the Service</li>
          <li>Warranties that defects will be corrected</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">9.2 Data Accuracy</h3>
        <p className="text-muted-foreground">
          While we make reasonable efforts to provide accurate and up-to-date information, we do not warrant the
          accuracy, completeness, or timeliness of tender and procurement data. Data is provided for informational
          purposes only. You are responsible for verifying all information through official government channels before
          taking any action based on data from our platform.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">9.3 AI-Generated Content</h3>
        <p className="text-muted-foreground">
          AI analyses, recommendations, and insights are generated by automated systems and should be considered as
          assistive tools, not professional advice. We do not guarantee the accuracy, completeness, or suitability of
          AI-generated content for your specific needs.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">10. Limitation of Liability</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">10.1 Limitation of Liability</h3>
        <p className="text-muted-foreground mb-4">
          To the maximum extent permitted by applicable law, in no event shall Tamsar, Inc., its directors, employees,
          partners, agents, suppliers, or affiliates be liable for any indirect, incidental, special, consequential, or
          punitive damages, including without limitation, loss of profits, data, use, goodwill, or other intangible
          losses, resulting from:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Your access to or use of or inability to access or use the Service</li>
          <li>Any conduct or content of any third party on the Service</li>
          <li>Unauthorized access, use, or alteration of your transmissions or content</li>
          <li>Errors, inaccuracies, or omissions in data</li>
          <li>Business decisions made based on information from the Service</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">10.2 Maximum Liability</h3>
        <p className="text-muted-foreground">
          To the maximum extent permitted by applicable law, our total liability to you for all claims related to the
          Service is limited to the amount you have paid us in the last 12 months or €100, whichever is greater.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">11. Indemnification</h2>
        <p className="text-muted-foreground">
          You agree to defend, indemnify, and hold harmless Tamsar, Inc. and its affiliates, partners, officers,
          directors, employees, agents, and licensors from and against any and all claims, damages, obligations, losses,
          liabilities, costs or debt, and expenses (including but not limited to attorney's fees) arising from:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4 mt-4">
          <li>Your use and access of the Service</li>
          <li>Your violation of these Terms</li>
          <li>Your violation of any third-party right</li>
          <li>Your violation of any applicable law or regulation</li>
        </ul>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">12. Changes to Service and Terms</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">12.1 Service Modifications</h3>
        <p className="text-muted-foreground">
          We reserve the right to modify, suspend, or discontinue the Service (or any part or content thereof) at any
          time without prior notice. We shall not be liable to you or to any third party for any modification,
          suspension, or discontinuance of the Service.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">12.2 Terms Modifications</h3>
        <p className="text-muted-foreground">
          We may revise these Terms from time to time in our sole discretion. All changes are effective immediately when
          posted. We will notify you of material changes via email or through a prominent notice on the platform. Your
          continued use of the Service following the posting of revised Terms means that you accept and agree to the changes.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">13. Termination and Suspension</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">13.1 Termination by Us</h3>
        <p className="text-muted-foreground mb-4">
          We may terminate or suspend your access to the Service immediately, without prior notice or liability, in our
          sole discretion, for any reason whatsoever, including but not limited to:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-4">
          <li>Breach of these Terms of Service</li>
          <li>Activities that expose us or other users to risk</li>
          <li>Fraudulent or illegal activities</li>
          <li>Persistent abuse of the Service</li>
          <li>Request by a government agency or law enforcement</li>
        </ul>

        <h3 className="text-xl font-semibold mb-3 mt-6">13.2 Termination by You</h3>
        <p className="text-muted-foreground">
          You may terminate your account at any time by deleting your account or contacting our support team. Upon
          termination, your right to use the Service will immediately cease.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">13.3 Effect of Termination</h3>
        <p className="text-muted-foreground">
          Upon termination of your account, all provisions of these Terms which by their nature should survive
          termination shall survive, including, without limitation, ownership provisions, warranty disclaimers,
          indemnity, and limitations of liability.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">14. Governing Law and Dispute Resolution</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">14.1 Governing Law</h3>
        <p className="text-muted-foreground">
          These Terms shall be governed and construed in accordance with the laws of the Republic of North Macedonia,
          without regard to its conflict of law provisions.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">14.2 Dispute Resolution</h3>
        <p className="text-muted-foreground">
          Any disputes arising from or relating to these Terms or the Service shall first be attempted to be resolved
          through good faith negotiations. If disputes cannot be resolved through negotiation within 30 days, they shall
          be resolved by the competent courts in Skopje, Republic of North Macedonia.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">14.3 Jurisdiction</h3>
        <p className="text-muted-foreground">
          You agree to submit to the personal and exclusive jurisdiction of the courts located within Skopje, North
          Macedonia, and waive any objection to venue or forum non conveniens.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">15. Miscellaneous Provisions</h2>

        <h3 className="text-xl font-semibold mb-3 mt-6">15.1 Entire Agreement</h3>
        <p className="text-muted-foreground">
          These Terms, together with our Privacy Policy, constitute the entire agreement between you and Tamsar, Inc.
          regarding the Service and supersede all prior and contemporaneous understandings and agreements.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">15.2 Severability</h3>
        <p className="text-muted-foreground">
          If any provision of these Terms is held to be invalid or unenforceable by a court, the remaining provisions
          will continue in full force and effect. Invalid provisions will be replaced with valid provisions that most
          closely approximate the intent of the original provision.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">15.3 Waiver</h3>
        <p className="text-muted-foreground">
          Our failure to enforce any right or provision of these Terms will not be considered a waiver of those rights
          or provisions. Any waiver of any provision of these Terms will be effective only if in writing and signed by us.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">15.4 Assignment</h3>
        <p className="text-muted-foreground">
          You may not assign or transfer these Terms or your rights and obligations hereunder without our prior written
          consent. We may assign these Terms without restriction.
        </p>

        <h3 className="text-xl font-semibold mb-3 mt-6">15.5 Force Majeure</h3>
        <p className="text-muted-foreground">
          We shall not be liable for any failure or delay in performance of our obligations under these Terms due to
          circumstances beyond our reasonable control, including natural disasters, war, terrorism, riots, civil unrest,
          labor shortage, equipment, materials or transportation shortages, governmental actions, or utility failures.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4">16. Contact Information</h2>
        <p className="text-muted-foreground mb-4">
          If you have any questions, comments, or requests regarding these Terms of Service, please contact us at:
        </p>
        <div className="bg-muted/30 rounded-lg p-4 space-y-2 not-prose">
          <p className="text-muted-foreground">
            <strong>Tamsar, Inc.</strong>
          </p>
          <p className="text-muted-foreground">
            Address: 131 Continental Dr Ste 305, New Castle, DE 19713
          </p>
          <p className="text-muted-foreground">
            Email: <a href="mailto:support@nabavkidata.com" className="text-primary hover:underline">support@nabavkidata.com</a>
          </p>
          <p className="text-muted-foreground">
            Website: <a href="https://nabavkidata.com" className="text-primary hover:underline">https://nabavkidata.com</a>
          </p>
        </div>
      </section>

      <section className="pt-8 border-t border-muted">
        <p className="text-sm text-muted-foreground text-center">
          Last Updated: November 2025
        </p>
        <p className="text-sm text-muted-foreground text-center mt-2">
          By using nabavkidata.com, you agree to accept these Terms of Service.
        </p>
      </section>
    </div>
  );
}
