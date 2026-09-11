import React from 'react';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

// Helper to format inline markdown tokens (bold, italics, inline code)
function renderInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let keyIdx = 0;
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let match: RegExpExecArray | null;
  let lastIndex = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(
        <strong key={keyIdx++} style={{ fontWeight: 700 }}>
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code
          key={keyIdx++}
          style={{
            background: 'rgba(0, 0, 0, 0.08)',
            padding: '2px 6px',
            borderRadius: '4px',
            fontSize: '0.88em',
            fontFamily: 'monospace',
          }}
        >
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(
        <em key={keyIdx++} style={{ fontStyle: 'italic' }}>
          {token.slice(1, -1)}
        </em>
      );
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  return parts;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className }) => {
  if (!content) return null;

  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];

  let currentList: { type: 'ul' | 'ol'; items: React.ReactNode[] } | null = null;
  let inCodeBlock = false;
  let codeBlockLines: string[] = [];

  const flushList = () => {
    if (currentList) {
      if (currentList.type === 'ul') {
        elements.push(
          <ul key={`ul-${elements.length}`} style={{ margin: '4px 0 8px 20px', padding: 0, listStyleType: 'disc' }}>
            {currentList.items.map((item, i) => (
              <li key={i} style={{ marginBottom: '4px', lineHeight: '1.45' }}>
                {item}
              </li>
            ))}
          </ul>
        );
      } else {
        elements.push(
          <ol key={`ol-${elements.length}`} style={{ margin: '4px 0 8px 20px', padding: 0, listStyleType: 'decimal' }}>
            {currentList.items.map((item, i) => (
              <li key={i} style={{ marginBottom: '4px', lineHeight: '1.45' }}>
                {item}
              </li>
            ))}
          </ol>
        );
      }
      currentList = null;
    }
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();

    if (trimmed.startsWith('```')) {
      if (inCodeBlock) {
        elements.push(
          <pre
            key={`code-${idx}`}
            style={{
              background: '#1e293b',
              color: '#f8fafc',
              padding: '10px 14px',
              borderRadius: '6px',
              overflowX: 'auto',
              fontSize: '0.85em',
              fontFamily: 'monospace',
              margin: '8px 0',
            }}
          >
            <code>{codeBlockLines.join('\n')}</code>
          </pre>
        );
        codeBlockLines = [];
        inCodeBlock = false;
      } else {
        flushList();
        inCodeBlock = true;
      }
      return;
    }

    if (inCodeBlock) {
      codeBlockLines.push(line);
      return;
    }

    if (trimmed.startsWith('#')) {
      flushList();
      const level = trimmed.match(/^#+/)?.[0].length || 1;
      const titleText = trimmed.replace(/^#+\s*/, '');
      const formattedTitle = renderInline(titleText);

      if (level === 1) {
        elements.push(<h3 key={idx} style={{ margin: '10px 0 6px 0', fontSize: '1.1rem', fontWeight: 700 }}>{formattedTitle}</h3>);
      } else if (level === 2) {
        elements.push(<h4 key={idx} style={{ margin: '8px 0 4px 0', fontSize: '1.05rem', fontWeight: 700 }}>{formattedTitle}</h4>);
      } else {
        elements.push(<h4 key={idx} style={{ margin: '6px 0 4px 0', fontSize: '1rem', fontWeight: 700 }}>{formattedTitle}</h4>);
      }
      return;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const itemText = trimmed.replace(/^[-*]\s+/, '');
      if (!currentList || currentList.type !== 'ul') {
        flushList();
        currentList = { type: 'ul', items: [] };
      }
      currentList.items.push(renderInline(itemText));
      return;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const itemText = trimmed.replace(/^\d+\.\s+/, '');
      if (!currentList || currentList.type !== 'ol') {
        flushList();
        currentList = { type: 'ol', items: [] };
      }
      currentList.items.push(renderInline(itemText));
      return;
    }

    if (trimmed.startsWith('>')) {
      flushList();
      const quoteText = trimmed.replace(/^>\s*/, '');
      elements.push(
        <blockquote key={idx} style={{ borderLeft: '3px solid var(--teal)', margin: '6px 0', paddingLeft: '10px', opacity: 0.88 }}>
          {renderInline(quoteText)}
        </blockquote>
      );
      return;
    }

    flushList();
    if (trimmed === '') {
      elements.push(<div key={idx} style={{ height: '6px' }} />);
    } else {
      elements.push(
        <p key={idx} style={{ margin: '0 0 6px 0', lineHeight: '1.5' }}>
          {renderInline(line)}
        </p>
      );
    }
  });

  flushList();

  return <div className={`markdown-content ${className || ''}`} style={{ width: '100%' }}>{elements}</div>;
};
