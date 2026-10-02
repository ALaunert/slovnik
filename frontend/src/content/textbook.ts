import data from "./serbian-textbook.json";

export type TextbookChapter = {
  id: string;
  group_id: string;
  title: string;
  summary: string;
  objectives: string[];
  sections: Array<{ title: string; paragraphs: string[]; table?: { headers: string[]; rows: string[][] } }>;
  examples: Array<{ serbian: string; translation: string; note: string }>;
  practice: Array<{ prompt: string; answer: string; explanation: string; answer_language?: string }>;
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
  // Search accepts both Serbian scripts. This is an index normalization,
  // not a spelling converter (Latin digraphs have lexical exceptions).
  const cyrillic: Record<string, string> = {
    а: "a", б: "b", в: "v", г: "g", д: "d", ђ: "đ", е: "e", ж: "ž", з: "z",
    и: "i", ј: "j", к: "k", л: "l", љ: "lj", м: "m", н: "n", њ: "nj", о: "o",
    п: "p", р: "r", с: "s", т: "t", ћ: "ć", у: "u", ф: "f", х: "h", ц: "c",
    ч: "č", џ: "dž", ш: "š",
  };
  return text.toLocaleLowerCase("ru").replace(/[а-яђјљњћџ]/gu, (letter) => cyrillic[letter] ?? letter)
    .normalize("NFD").replace(/\p{M}/gu, "").replace(/đ|dj/gu, "d");
}

export function matchesChapter(chapter: TextbookChapter, query: string): boolean {
  const words = normalizeSearch(query).trim().split(/\s+/u).filter(Boolean);
  const searchable = normalizeSearch([
    chapter.title, chapter.summary, ...chapter.objectives, ...chapter.pitfalls,
    ...chapter.sections.flatMap((section) => [section.title, ...section.paragraphs,
      ...(section.table?.headers ?? []), ...(section.table?.rows.flat() ?? [])]),
    ...chapter.examples.flatMap((example) => [example.serbian, example.translation, example.note]),
    ...chapter.practice.flatMap((exercise) => [exercise.prompt, exercise.answer, exercise.explanation]),
  ].join(" "));
  return words.every((word) => searchable.includes(word));
}
