import { Metadata } from "next";
import { notFound } from "next/navigation";
import SectorClient from "../SectorClient";

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

const REGIONS: Record<string, { name: string; query: string }> = {
  skopje: { name: "Скопје", query: "Скопје" },
  bitola: { name: "Битола", query: "Битола" },
  kumanovo: { name: "Куманово", query: "Куманово" },
  prilep: { name: "Прилеп", query: "Прилеп" },
  tetovo: { name: "Тетово", query: "Тетово" },
  ohrid: { name: "Охрид", query: "Охрид" },
  veles: { name: "Велес", query: "Велес" },
  stip: { name: "Штип", query: "Штип" },
  strumica: { name: "Струмица", query: "Струмица" },
  gostivar: { name: "Гостивар", query: "Гостивар" },
  kavadarci: { name: "Кавадарци", query: "Кавадарци" },
  kocani: { name: "Кочани", query: "Кочани" },
};

export function generateStaticParams() {
  const params: { sector: string; region: string }[] = [];
  for (const sector of Object.keys(SECTORS)) {
    for (const region of Object.keys(REGIONS)) {
      params.push({ sector, region });
    }
  }
  return params;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ sector: string; region: string }>;
}): Promise<Metadata> {
  const { sector, region } = await params;
  const sectorData = SECTORS[sector];
  const regionData = REGIONS[region];
  if (!sectorData || !regionData)
    return { title: "Сектор | NabavkiData" };

  const title = `${sectorData.name} тендери во ${regionData.name} | NabavkiData`;
  const description = `${sectorData.description} Филтрирано за регионот ${regionData.name}.`;

  return {
    title,
    description,
    openGraph: {
      title: `${sectorData.name} тендери во ${regionData.name}`,
      description,
      url: `https://nabavkidata.com/sectors/${sector}/${region}`,
    },
    alternates: {
      canonical: `https://nabavkidata.com/sectors/${sector}/${region}`,
    },
  };
}

export default async function SectorRegionPage({
  params,
}: {
  params: Promise<{ sector: string; region: string }>;
}) {
  const { sector, region } = await params;
  const sectorData = SECTORS[sector];
  const regionData = REGIONS[region];
  if (!sectorData || !regionData) notFound();

  const combinedQuery = `${sectorData.query} ${regionData.query}`;

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            name: `${sectorData.name} тендери во ${regionData.name}`,
            description: `${sectorData.description} Филтрирано за регионот ${regionData.name}.`,
            url: `https://nabavkidata.com/sectors/${sector}/${region}`,
            inLanguage: "mk",
            about: { "@type": "Thing", name: sectorData.name },
            spatialCoverage: {
              "@type": "Place",
              name: regionData.name,
              address: {
                "@type": "PostalAddress",
                addressLocality: regionData.name,
                addressCountry: "MK",
              },
            },
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
                name: sectorData.name,
                item: `https://nabavkidata.com/sectors/${sector}`,
              },
              {
                "@type": "ListItem",
                position: 4,
                name: regionData.name,
              },
            ],
          }),
        }}
      />

      <div className="sr-only" aria-hidden="true">
        <h1>
          {sectorData.name} тендери во {regionData.name}
        </h1>
        <p>
          {sectorData.description} Филтрирано за регионот {regionData.name}.
        </p>
      </div>

      <SectorClient
        sectorSlug={sector}
        sectorName={`${sectorData.name} — ${regionData.name}`}
        searchQuery={combinedQuery}
      />
    </>
  );
}
