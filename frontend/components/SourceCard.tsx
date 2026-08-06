import { SourceCitation } from "@/lib/types";

export default function SourceCard({ source }: { source: SourceCitation }) {
  const location = [source.page_number ? `p. ${source.page_number}` : null, source.section]
    .filter(Boolean)
    .join(" — ");

  return (
    <div className="source-card">
      <div className="source-head">
        <span className="source-title">{source.title}</span>
        <span className="source-similarity">{Math.round(source.similarity * 100)}% relevant</span>
      </div>
      <p className="source-name">
        {source.organization ? `${source.organization} · ` : ""}
        {source.source}
      </p>
      {location && <p className="source-location">{location}</p>}
      <p className="source-excerpt">{source.excerpt}</p>
      {source.source_url?.startsWith("http") && (
        <a className="source-link" href={source.source_url} target="_blank" rel="noopener noreferrer">
          View original document ↗
        </a>
      )}
    </div>
  );
}
