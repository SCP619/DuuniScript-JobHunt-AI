import { parseDraft } from "@/lib/applications";

/** Preview of draft text. Renders React text nodes only; nothing is interpreted as HTML. */
export function DraftPreview({ content }: { content: string }) {
  const blocks = parseDraft(content);
  return (
    <div data-testid="draft-preview" className="space-y-2 text-sm leading-relaxed">
      {blocks.map((b, i) => {
        switch (b.type) {
          case "name": return <p key={i} className="font-display text-2xl font-medium">{b.text}</p>;
          case "section": return <p key={i} className="mt-4 border-b pb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground [font-variant:small-caps]">{b.text}</p>;
          case "entry": return <p key={i} className="mt-2 font-semibold">{b.text}</p>;
          case "meta": return <p key={i} className="italic text-muted-foreground">{b.text}</p>;
          case "list": return <ul key={i} className="list-disc space-y-0.5 pl-5">{b.items.map((t, j) => <li key={j}>{t}</li>)}</ul>;
          default: return <p key={i}>{b.text}</p>;
        }
      })}
      {blocks.length === 0 && <p className="text-muted-foreground">Nothing to preview yet.</p>}
    </div>
  );
}
