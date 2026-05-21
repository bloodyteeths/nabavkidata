import { Metadata } from "next";
import CategoryClient from "./CategoryClient";

const CPV_CATEGORIES: Record<string, string> = {
  "45000000": "Градежни работи",
  "30000000": "Канцелариска и компјутерска опрема",
  "31000000": "Електрична опрема и апарати",
  "32000000": "Радио, телевизиска, комуникациска и телекомуникациска опрема",
  "33000000": "Медицинска опрема",
  "34000000": "Транспортна опрема",
  "35000000": "Безбедносна опрема",
  "39000000": "Мебел, подни и други покривки",
  "44000000": "Конструкциски материјали",
  "48000000": "Софтверски пакети и информациски системи",
  "50000000": "Услуги за поправка и одржување",
  "60000000": "Транспортни услуги",
  "70000000": "Услуги поврзани со недвижен имот",
  "71000000": "Архитектонски, инженерски и градежни услуги",
  "72000000": "ИТ услуги",
  "73000000": "Истражување и развој",
  "75000000": "Јавна администрација",
  "76000000": "Услуги поврзани со нафтена и гасна индустрија",
  "77000000": "Услуги поврзани со земјоделство, шумарство и рибарство",
  "79000000": "Деловни услуги",
  "80000000": "Образовни и обучни услуги",
  "85000000": "Здравствени и социјални услуги",
  "90000000": "Услуги за отстранување на отпад и канализација",
  "92000000": "Рекреативни, културни и спортски услуги",
  "98000000": "Други услуги",
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ cpv: string }>;
}): Promise<Metadata> {
  const { cpv } = await params;
  const cpvCode = decodeURIComponent(cpv);
  const categoryName = CPV_CATEGORIES[cpvCode] || `CPV ${cpvCode}`;

  return {
    title: `${categoryName} — тендери CPV ${cpvCode} | NabavkiData`,
    description: `Тендери и јавни набавки во категоријата ${categoryName} (CPV ${cpvCode}). Пребарувајте активни и минати набавки во Македонија.`,
    openGraph: {
      title: `${categoryName} — јавни набавки`,
      description: `Сите тендери класифицирани под CPV ${cpvCode} (${categoryName}) во Република Македонија.`,
      url: `https://nabavkidata.com/categories/${cpvCode}`,
    },
    alternates: {
      canonical: `https://nabavkidata.com/categories/${cpvCode}`,
    },
  };
}

export default async function CategoryPage() {
  return <CategoryClient />;
}
