import { Highlight, themes } from "prism-react-renderer";

interface JsonViewerProps {
  data: object;
}

/**
 * Displays JSON data with syntax highlighting and line numbers.
 * Uses VS Code dark theme for consistent developer experience.
 */
export function JsonViewer({ data }: JsonViewerProps) {
  const jsonString = JSON.stringify(data, null, 2);

  return (
    <div className="h-full overflow-auto bg-[#1e1e1e] p-4">
      <Highlight theme={themes.vsDark} code={jsonString} language="json">
        {({ style, tokens, getLineProps, getTokenProps }) => (
          <pre style={style} className="text-sm font-mono">
            {tokens.map((line, i) => (
              <div key={i} {...getLineProps({ line })}>
                <span className="select-none text-gray-500 w-10 inline-block text-right pr-3">
                  {i + 1}
                </span>
                {line.map((token, key) => (
                  <span key={key} {...getTokenProps({ token })} />
                ))}
              </div>
            ))}
          </pre>
        )}
      </Highlight>
    </div>
  );
}
