import { Metadata } from "next";
import { notFound } from "next/navigation";
import SectorClient from "./SectorClient";

const SECTORS: Record<
  string,
  { name: string; query: string; description: string }
> = {
  "it-digitalni-uslugi": {
    name: "ИТ и дигитални услуги",
    query: "ИТ услуги информатичка технологија софтвер",
    description:
      "Тендери за софтвер, хардвер, IT услуги, информациски системи, дигитализација и телекомуникации во Македонија.",
  },
  gradeznistvo: {
    name: "Градежништво",
    query: "градежни работи градба реконструкција",
    description:
      "Тендери за градежни работи, реконструкции, инфраструктура, патишта и објекти во Македонија.",
  },
  "medicinska-oprema": {
    name: "Медицинска опрема",
    query: "медицинска опрема здравство лекови",
    description:
      "Тендери за медицинска опрема, лекови, болнички материјали и здравствени услуги.",
  },
  "kancelariski-materijali": {
    name: "Канцелариски материјали",
    query: "канцелариски материјали тонери",
    description:
      "Тендери за канцелариски материјали, тонери, хартија и канцелариска опрема.",
  },
  "hrana-pijaloci": {
    name: "Храна и пијалоци",
    query: "храна пијалоци прехранбени",
    description:
      "Тендери за прехранбени производи, кетеринг, пијалоци и исхрана во јавни институции.",
  },
  "transport-vozila": {
    name: "Транспорт и возила",
    query: "транспорт возила превоз",
    description:
      "Тендери за транспортни услуги, набавка на возила, одржување и превоз.",
  },
  "cistenje-odrzuvanje": {
    name: "Чистење и одржување",
    query: "чистење хигиена одржување",
    description:
      "Тендери за услуги за чистење, хигиена, одржување на објекти и зелени површини.",
  },
  obezbeduvawe: {
    name: "Обезбедување",
    query: "обезбедување безбедност заштита",
    description:
      "Тендери за физичко обезбедување, безбедносни системи, видео надзор и заштита.",
  },
  "konsultantski-uslugi": {
    name: "Консултантски услуги",
    query: "консултантски услуги ревизија",
    description:
      "Тендери за консултантски услуги, ревизија, правни услуги и стручна помош.",
  },
  "oprema-masini": {
    name: "Опрема и машини",
    query: "опрема машини апарати",
    description:
      "Тендери за индустриска опрема, машини, апарати и техничка опрема.",
  },
  energetika: {
    name: "Енергетика",
    query: "електрична енергија гориво греење",
    description:
      "Тендери за електрична енергија, горива, греење и енергетски услуги.",
  },
  "pecatenje-marketing": {
    name: "Печатење и маркетинг",
    query: "печатење рекламен материјал",
    description:
      "Тендери за печатарски услуги, рекламни материјали и маркетинг услуги.",
  },
};

export function generateStaticParams() {
  return Object.keys(SECTORS).map((sector) => ({ sector }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ sector: string }>;
}): Promise<Metadata> {
  const { sector } = await params;
  const data = SECTORS[sector];
  if (!data) return { title: "Сектор | NabavkiData" };

  return {
    title: `${data.name} — тендери и набавки | NabavkiData`,
    description: data.description,
    openGraph: {
      title: `${data.name} — тендери во Македонија`,
      description: data.description,
      url: `https://nabavkidata.com/sectors/${sector}`,
    },
    alternates: {
      canonical: `https://nabavkidata.com/sectors/${sector}`,
    },
  };
}

export default async function SectorPage({
  params,
}: {
  params: Promise<{ sector: string }>;
}) {
  const { sector } = await params;
  const data = SECTORS[sector];
  if (!data) notFound();

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            name: `${data.name} — јавни набавки`,
            description: data.description,
            url: `https://nabavkidata.com/sectors/${sector}`,
            inLanguage: "mk",
            about: { "@type": "Thing", name: data.name },
          }),
        }}
      />

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            itemListElement: [
              {
                "@type": "ListItem",
                position: 1,
                name: "Почетна",
                item: "https://nabavkidata.com",
              },
              {
                "@type": "ListItem",
                position: 2,
                name: "Сектори",
                item: "https://nabavkidata.com/sectors",
              },
              {
                "@type": "ListItem",
                position: 3,
                name: data.name,
              },
            ],
          }),
        }}
      />

      <div className="sr-only" aria-hidden="true">
        <h1>Тендери за {data.name}</h1>
        <p>{data.description}</p>
        <nav>
          <h2>Региони</h2>
          <ul>
            <li><a href={`/sectors/${sector}/skopje`}>Скопје</a></li>
            <li><a href={`/sectors/${sector}/bitola`}>Битола</a></li>
            <li><a href={`/sectors/${sector}/kumanovo`}>Куманово</a></li>
            <li><a href={`/sectors/${sector}/prilep`}>Прилеп</a></li>
            <li><a href={`/sectors/${sector}/tetovo`}>Тетово</a></li>
            <li><a href={`/sectors/${sector}/ohrid`}>Охрид</a></li>
            <li><a href={`/sectors/${sector}/veles`}>Велес</a></li>
            <li><a href={`/sectors/${sector}/stip`}>Штип</a></li>
            <li><a href={`/sectors/${sector}/strumica`}>Струмица</a></li>
            <li><a href={`/sectors/${sector}/gostivar`}>Гостивар</a></li>
            <li><a href={`/sectors/${sector}/kavadarci`}>Кавадарци</a></li>
            <li><a href={`/sectors/${sector}/kocani`}>Кочани</a></li>
          </ul>
        </nav>
      </div>

      <SectorClient sectorSlug={sector} sectorName={data.name} searchQuery={data.query} />
    </>
  );
}
