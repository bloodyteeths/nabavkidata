export default function PrivacyPage() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <h1 className="text-3xl font-bold mb-6">Политика за приватност</h1>

      <div className="prose prose-invert max-w-none">
        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">1. Вовед</h2>
          <p className="text-muted-foreground">
            Добредојдовте на Nabavki Data. Ние ја цениме вашата приватност и сме посветени на заштитата на вашите лични податоци.
            Оваа политика за приватност ќе ве информира како се грижиме за вашите лични податоци кога ја посетувате нашата веб-страница.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">2. Податоци што ги собираме</h2>
          <p className="text-muted-foreground mb-4">Можеме да собираме, користиме, складираме и пренесуваме различни видови лични податоци за вас:</p>
          <ul className="list-disc list-inside text-muted-foreground space-y-2">
            <li>Податоци за идентитет: име, презиме, корисничко име</li>
            <li>Контакт податоци: адреса на е-пошта, телефонски броеви</li>
            <li>Технички податоци: IP адреса, податоци за најава, тип и верзија на прелистувач</li>
            <li>Податоци за профил: корисничко име и лозинка, вашите интереси, преференци</li>
            <li>Податоци за користење: информации за тоа како ги користите нашите услуги</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">3. Како ги користиме вашите податоци</h2>
          <p className="text-muted-foreground mb-4">Ги користиме вашите податоци за:</p>
          <ul className="list-disc list-inside text-muted-foreground space-y-2">
            <li>Да ви овозможиме пристап до нашите услуги</li>
            <li>Да ви обезбедиме персонализирани препораки за тендери</li>
            <li>Да комуницираме со вас за нашите услуги</li>
            <li>Да ја подобриме нашата веб-страница и услуги</li>
            <li>Да процесираме плаќања и претплати</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">4. Безбедност на податоците</h2>
          <p className="text-muted-foreground">
            Ние имплементиравме соодветни безбедносни мерки за да спречиме случајна загуба, користење или пристап до вашите лични податоци на неовластен начин.
            Користиме шифрирање, безбедни протоколи и редовни безбедносни ревизии.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">5. Вашите права</h2>
          <p className="text-muted-foreground mb-4">Имате право да:</p>
          <ul className="list-disc list-inside text-muted-foreground space-y-2">
            <li>Побарате пристап до вашите лични податоци</li>
            <li>Побарате корекција на вашите лични податоци</li>
            <li>Побарате бришење на вашите лични податоци</li>
            <li>Се противставите на обработката на вашите лични податоци</li>
            <li>Побарате ограничување на обработката на вашите лични податоци</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">6. Колачиња (Cookies)</h2>
          <p className="text-muted-foreground">
            Нашата веб-страница користи колачиња за да ја подобри вашата корисничка искуство. Колачињата се мали текстуални датотеки
            што се складираат на вашиот уред кога ја посетувате нашата веб-страница.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">7. Контакт</h2>
          <p className="text-muted-foreground">
            Ако имате прашања за оваа политика за приватност или за тоа како ги обработуваме вашите податоци, ве молиме контактирајте не на:
            <br />
            <a href="mailto:privacy@nabavkidata.com" className="text-primary hover:underline">
              privacy@nabavkidata.com
            </a>
          </p>
        </section>

        <section className="mb-8">
          <p className="text-sm text-muted-foreground">
            Последна ажурирање: Ноември 2025
          </p>
        </section>
      </div>
    </div>
  );
}
