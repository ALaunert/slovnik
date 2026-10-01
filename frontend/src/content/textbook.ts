import data from "./serbian-textbook.json";

export type TextbookChapter = {
  id: string;
  group_id: string;
  title: string;
  summary: string;
  objectives: string[];
  sections: Array<{ title: string; paragraphs: string[]; table?: { headers: string[]; rows: string[][] } }>;
  examples: Array<{ serbian: string; translation: string; note: string }>;
  practice: Array<{ prompt: string; answer: string; explanation: string }>;
  pitfalls: string[];
  source_refs: Array<{ source_id: string; locator: string }>;
  related: string[];
};

type Textbook = {
  version: number;
  title: string;
  description: string;
  groups: Array<{ id: string; title: string; description: string }>;
  sources: Array<{ id: string; title: string; url: string }>;
  chapters: TextbookChapter[];
};

export const textbook: Textbook = data;

function normalizeSearch(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase("ru");
}

export function matchesChapter(chapter: TextbookChapter, query: string): boolean {
  const words = normalizeSearch(query).trim().split(/\s+/u).filter(Boolean);
  const searchable = normalizeSearch([
    chapter.title, chapter.summary, ...chapter.objectives, ...chapter.pitfalls,
    ...chapter.sections.flatMap((section) => [section.title, ...section.paragraphs,
      ...(section.table?.rows.flat() ?? [])]),
    ...chapter.examples.flatMap((example) => [example.serbian, example.translation]),
  ].join(" "));
  return words.every((word) => searchable.includes(word));
}
