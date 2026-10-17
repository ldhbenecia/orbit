import { STORIES, type StoryKey } from "@/lib/rule-stories";

// 접어 두는 설명 — 처음 보는 규칙이 누구의 어떤 생각인지 궁금할 때만 펼침
export function RuleStory({ story, label = "이 규칙은 어디서 왔나요?" }: { story: StoryKey; label?: string }) {
  const s = STORIES[story];
  const rows: [string, string][] = [
    ["누가", s.who],
    ["어떤 생각", s.idea],
    ["orbit 규칙", s.rule],
    ["깨지는 때", s.breaks],
    ["요즘 근거", s.now],
  ];
  return (
    <details className="group text-xs">
      <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden text-muted hover:text-foreground focus-visible:text-foreground">
        <span className="mr-1 inline-block transition-transform group-open:rotate-90" aria-hidden>
          ›
        </span>
        {label}
      </summary>
      <div className="mt-2 space-y-2 rounded-xl bg-background px-4 py-3 leading-relaxed">
        <p className="font-medium">{s.title}</p>
        <dl className="space-y-1.5">
          {rows.map(([term, text]) => (
            <div key={term}>
              <dt className="text-muted">{term}</dt>
              <dd>{text}</dd>
            </div>
          ))}
        </dl>
      </div>
    </details>
  );
}
