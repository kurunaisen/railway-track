export type TranscriptIssueSeverity = "warning" | "error";

export interface TranscriptIssue {
  id: string;
  start: number;
  end: number;
  severity: TranscriptIssueSeverity;
  title: string;
  description: string;
  safeFix?: {
    replacement: string;
    label: string;
  };
}

export interface TranscriptQualitySegment {
  text: string;
  issue?: TranscriptIssue;
}

type DraftIssue = Omit<TranscriptIssue, "id">;

const TRACK_GAUGE_MIN_MM = 1510;
const TRACK_GAUGE_MAX_MM = 1560;
const WORD_LEFT = "(?<![A-Za-zА-Яа-яЁё0-9])";
const WORD_RIGHT = "(?![A-Za-zА-Яа-яЁё0-9])";
const WORD_TAIL = "[A-Za-zА-Яа-яЁё]*";

function addIssue(issues: DraftIssue[], issue: DraftIssue): void {
  if (issue.start < 0 || issue.end <= issue.start) return;
  issues.push(issue);
}

function isPlausibleGauge(value: number): boolean {
  return value >= TRACK_GAUGE_MIN_MM && value <= TRACK_GAUGE_MAX_MM;
}

function capitalizePlaceName(value: string): string {
  return value
    .split(/(\s*-\s*|\s+)/)
    .map((part) => {
      if (!part.trim() || part.includes("-")) return part;
      return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
    })
    .join("");
}

function hasLowercasePlaceName(value: string): boolean {
  return /(^|[\s-])[а-яё]/u.test(value);
}

function collectGaugeIssues(text: string, issues: DraftIssue[]): void {
  const gaugeRe = new RegExp(
    `${WORD_LEFT}(?:уширение|ширина)\\s+колеи(?<middle>[\\sA-Za-zА-Яа-яЁё,.-]{0,30}?)(?<first>\\d{3,4})\\s+(?<second>\\d{3,4})\\s*мм${WORD_RIGHT}`,
    "giu",
  );
  const looseGaugeRe = new RegExp(
    `${WORD_LEFT}(?<first>\\d{3,4})\\s+(?<second>\\d{3,4})\\s*мм${WORD_RIGHT}`,
    "giu",
  );
  const railGaugeContextRe = new RegExp(`${WORD_LEFT}коле[яи]${WORD_RIGHT}`, "iu");
  const seen = new Set<string>();

  for (const match of text.matchAll(gaugeRe)) {
    const first = Number(match.groups?.first);
    const second = Number(match.groups?.second);
    const firstText = match.groups?.first ?? "";
    const secondText = match.groups?.second ?? "";
    const base = match.index ?? 0;
    const firstStart = base + match[0].indexOf(firstText);
    const secondStart = base + match[0].lastIndexOf(secondText);

    if (!Number.isFinite(first) || !Number.isFinite(second)) continue;
    seen.add(`${firstStart}:${secondStart + secondText.length}`);

    if (!isPlausibleGauge(first) && isPlausibleGauge(second)) {
      addIssue(issues, {
        start: firstStart,
        end: firstStart + firstText.length,
        severity: "error",
        title: "Подозрительное число перед измерением колеи",
        description: `Перед "${second} мм" найдено лишнее или ошибочное число "${first}". Проверьте transcript вручную.`,
        safeFix: {
          replacement: "",
          label: `Удалить "${first}"`,
        },
      });
      continue;
    }

    addIssue(issues, {
      start: firstStart,
      end: secondStart + secondText.length,
      severity: "warning",
      title: "Два числа перед \"мм\"",
      description: "В измерении колеи найдено два числа подряд. Возможно, ASR добавил лишнее число.",
    });
  }

  for (const match of text.matchAll(looseGaugeRe)) {
    const first = Number(match.groups?.first);
    const second = Number(match.groups?.second);
    const firstText = match.groups?.first ?? "";
    const secondText = match.groups?.second ?? "";
    const base = match.index ?? 0;
    const firstStart = base + match[0].indexOf(firstText);
    const secondEnd = base + match[0].lastIndexOf(secondText) + secondText.length;
    const key = `${firstStart}:${secondEnd}`;
    if (seen.has(key)) continue;
    if (!Number.isFinite(first) || !Number.isFinite(second)) continue;

    const context = text.slice(Math.max(0, base - 45), Math.min(text.length, secondEnd + 12));
    if (!railGaugeContextRe.test(context)) continue;
    if (!isPlausibleGauge(first) && isPlausibleGauge(second)) {
      addIssue(issues, {
        start: firstStart,
        end: firstStart + firstText.length,
        severity: "error",
        title: "Подозрительное число перед измерением колеи",
        description: `Рядом с колеёй перед "${second} мм" найдено лишнее или ошибочное число "${first}".`,
        safeFix: {
          replacement: "",
          label: `Удалить "${first}"`,
        },
      });
    }
  }
}

function collectRailwayTermIssues(text: string, issues: DraftIssue[]): void {
  const kolaMurmanskMisheardRe = new RegExp(
    `${WORD_LEFT}(?<name>перед\\s+гонк(?:ой|а|у)?\\s+мурманск(?:ом|а)?)${WORD_RIGHT}`,
    "giu",
  );
  for (const match of text.matchAll(kolaMurmanskMisheardRe)) {
    const name = match.groups?.name ?? "";
    const start = (match.index ?? 0) + match[0].indexOf(name);
    const end = start + name.length;
    addIssue(issues, {
      start,
      end,
      severity: "error",
      title: "Похоже на перегон Кола - Мурманск",
      description: "ASR распознал «перегон Кола-Мурманск» как «перед гонкой Мурманск».",
      safeFix: {
        replacement: "перегон Кола — Мурманск",
        label: "Заменить на перегон Кола — Мурманск",
      },
    });
  }

  const lizatRe = new RegExp(`${WORD_LEFT}лизат${WORD_RIGHT}`, "giu");
  for (const match of text.matchAll(lizatRe)) {
    const start = match.index ?? 0;
    const original = match[0];
    addIssue(issues, {
      start,
      end: start + original.length,
      severity: "error",
      title: "Похоже на слово «лежат»",
      description: "ASR распознал слово как «лизат». В этом контексте, скорее всего, имелось в виду «лежат».",
      safeFix: {
        replacement: original[0] === original[0]?.toUpperCase() ? "Лежат" : "лежат",
        label: "Заменить на «лежат»",
      },
    });
  }

  const magnetityShonguyRe = new RegExp(
    `${WORD_LEFT}(?<name>(?:магн[еи]т${WORD_TAIL}\\s*[-–—]?\\s*ш[оа](?:н|нг|мг|м)${WORD_TAIL}|(?:от\\s+)?никит${WORD_TAIL}\\s+ш[оа](?:н|нг|мг|м)${WORD_TAIL}))${WORD_RIGHT}`,
    "giu",
  );
  const matchedAliases: Array<[number, number]> = [];
  for (const match of text.matchAll(magnetityShonguyRe)) {
    const name = match.groups?.name ?? "";
    const start = (match.index ?? 0) + match[0].indexOf(name);
    const end = start + name.length;
    matchedAliases.push([start, end]);
    addIssue(issues, {
      start,
      end,
      severity: "warning",
      title: "Похоже на перегон Магнетиты - Шонгуй",
      description: "ASR часто искажает этот перегон. Проверьте и при необходимости примените исправление.",
      safeFix: {
        replacement: "Магнетиты - Шонгуй",
        label: "Заменить на Магнетиты - Шонгуй",
      },
    });
  }

  const patterns: Array<[RegExp, TranscriptIssueSeverity, string, string]> = [
    [
      new RegExp(`${WORD_LEFT}пике${WORD_RIGHT}`, "giu"),
      "error",
      "Похоже на неполное слово",
      "Возможно, имелось в виду \"пикет\". Проверьте привязку.",
    ],
    [
      new RegExp(`${WORD_LEFT}шомгу${WORD_RIGHT}`, "giu"),
      "error",
      "Подозрительное название",
      "Слово похоже на ASR-искажение названия. Проверьте станцию или перегон.",
    ],
    [
      new RegExp(`${WORD_LEFT}магнититы${WORD_RIGHT}`, "giu"),
      "warning",
      "Проверьте название станции",
      "Возможно, ASR распознал \"Магнетиты\" как \"магнититы\".",
    ],
  ];

  for (const [pattern, severity, title, description] of patterns) {
    for (const match of text.matchAll(pattern)) {
      const start = match.index ?? 0;
      const end = start + match[0].length;
      if (matchedAliases.some(([aliasStart, aliasEnd]) => start >= aliasStart && end <= aliasEnd)) {
        continue;
      }
      addIssue(issues, {
        start,
        end,
        severity,
        title,
        description,
      });
    }
  }

  const missingKmNumberRe = new RegExp(
    `${WORD_LEFT}(?:км|километр)\\s*(?:пикет|пк)${WORD_RIGHT}`,
    "giu",
  );
  for (const match of text.matchAll(missingKmNumberRe)) {
    const start = match.index ?? 0;
    const before = text.slice(Math.max(0, start - 12), start);
    if (/\d+\s*$/u.test(before)) continue;
    addIssue(issues, {
      start,
      end: start + match[0].length,
      severity: "warning",
      title: "Неполная привязка",
      description: "Перед словом «км/километр» не найден номер километра. Проверьте привязку км/пк/м.",
    });
  }
}

function collectPlaceNameIssues(text: string, issues: DraftIssue[]): void {
  const peregonRe = new RegExp(
    `${WORD_LEFT}перегон\\s+(?<name>[А-Яа-яЁё]+(?:\\s*-\\s*[А-Яа-яЁё]+)+)`,
    "giu",
  );
  const stationRe = new RegExp(
    `${WORD_LEFT}станци[ия]\\s+(?<name>[А-Яа-яЁё]+)`,
    "giu",
  );

  for (const match of text.matchAll(peregonRe)) {
    const name = match.groups?.name ?? "";
    if (!hasLowercasePlaceName(name)) continue;
    const start = (match.index ?? 0) + match[0].indexOf(name);
    addIssue(issues, {
      start,
      end: start + name.length,
      severity: "warning",
      title: "Название перегона с маленькой буквы",
      description: "Названия станций в перегоне лучше писать с большой буквы: например, \"Магнетиты - Шонгуй\".",
      safeFix: {
        replacement: capitalizePlaceName(name),
        label: "Написать станции с большой буквы",
      },
    });
  }

  for (const match of text.matchAll(stationRe)) {
    const name = match.groups?.name ?? "";
    if (!hasLowercasePlaceName(name)) continue;
    const start = (match.index ?? 0) + match[0].indexOf(name);
    addIssue(issues, {
      start,
      end: start + name.length,
      severity: "warning",
      title: "Название станции с маленькой буквы",
      description: "Название станции лучше писать с большой буквы.",
      safeFix: {
        replacement: capitalizePlaceName(name),
        label: "Написать станцию с большой буквы",
      },
    });
  }
}

function finalizeIssues(issues: DraftIssue[]): TranscriptIssue[] {
  const sorted = [...issues].sort((a, b) => {
    if (a.start !== b.start) return a.start - b.start;
    return b.end - a.end;
  });
  const result: TranscriptIssue[] = [];
  let cursor = -1;
  for (const issue of sorted) {
    if (issue.start < cursor) continue;
    result.push({ ...issue, id: `${issue.severity}-${issue.start}-${issue.end}` });
    cursor = issue.end;
  }
  return result;
}

export function analyzeTranscriptQuality(text: string): TranscriptIssue[] {
  const issues: DraftIssue[] = [];
  collectGaugeIssues(text, issues);
  collectRailwayTermIssues(text, issues);
  collectPlaceNameIssues(text, issues);
  return finalizeIssues(issues);
}

export function buildTranscriptQualitySegments(
  text: string,
  issues: TranscriptIssue[],
): TranscriptQualitySegment[] {
  if (!issues.length) return [{ text }];

  const segments: TranscriptQualitySegment[] = [];
  let cursor = 0;
  for (const issue of issues) {
    if (issue.start > cursor) {
      segments.push({ text: text.slice(cursor, issue.start) });
    }
    segments.push({ text: text.slice(issue.start, issue.end), issue });
    cursor = issue.end;
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor) });
  }
  return segments;
}

export function applyTranscriptSafeFixes(text: string, issues: TranscriptIssue[]): string {
  const fixes = issues
    .filter((issue) => issue.safeFix)
    .sort((a, b) => b.start - a.start);
  let next = text;
  for (const issue of fixes) {
    const before = next.slice(0, issue.start).replace(/[ \t]+$/, "");
    const after = next.slice(issue.end).replace(/^[ \t]+/, "");
    const replacement = issue.safeFix?.replacement ?? "";
    const joiner = before && after && replacement === "" ? " " : "";
    next = `${before}${replacement}${joiner}${after}`;
  }
  return next.replace(/[ \t]{2,}/g, " ");
}
