export function MarkdownView({ markdown }: { markdown: string }) {
  const blocks: React.ReactNode[] = [];
  let list: string[] = [];

  function flushList() {
    if (list.length === 0) return;
    const items = list;
    list = [];
    blocks.push(
      <ul key={`list-${blocks.length}`}>
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>,
    );
  }

  markdown.split("\n").forEach((line) => {
    if (line.startsWith("### ")) {
      flushList();
      blocks.push(<h3 key={`h-${blocks.length}`}>{line.slice(4)}</h3>);
    } else if (line.startsWith("## ")) {
      flushList();
      blocks.push(<h2 key={`h-${blocks.length}`}>{line.slice(3)}</h2>);
    } else if (line.startsWith("# ")) {
      flushList();
      blocks.push(<h2 key={`h-${blocks.length}`}>{line.slice(2)}</h2>);
    } else if (line.startsWith("- ")) {
      list.push(line.slice(2));
    } else if (line.trim() === "") {
      flushList();
    } else {
      flushList();
      blocks.push(<p key={`p-${blocks.length}`}>{line}</p>);
    }
  });
  flushList();
  return <article className="markdown">{blocks}</article>;
}
