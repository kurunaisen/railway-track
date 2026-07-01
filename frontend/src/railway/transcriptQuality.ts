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

function addIssue(issues: DraftIssue[], issue: DraftIssue): void {
  if (issue.start < 0 || issue.end <= issue.start) return;
  issues.push(issue);
}

function isPlausibleGauge(value: number): boolean {
  return value >= TRACK_GAUGE_MIN_MM && value <= TRACK_GAUGE_MAX_MM;
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
  const patterns: Array<[RegExp, TranscriptIssueSeverity, string, string]> = [
    [
      new RegExp(`${WORD_LEFT}пике${WORD_RIGHT}`, "giu"),
      "warning",
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
    [
      new RegExp(`${WORD_LEFT}(?:км|километр)\\s*(?:пикет|пк)${WORD_RIGHT}`, "giu"),
      "warning",
      "Неполная привязка",
      "После километра не найден номер км. Проверьте привязку км/пк/м.",
    ],
  ];

  for (const [pattern, severity, title, description] of patterns) {
    for (const match of text.matchAll(pattern)) {
      addIssue(issues, {
        start: match.index ?? 0,
        end: (match.index ?? 0) + match[0].length,
        severity,
        title,
        description,
      });
    }
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
