# SourceCitation Component

## Overview

The `SourceCitation` component displays document sources cited by AI in its responses. It provides a clean, organized way to show users where AI-generated information comes from, with the ability to view full documents.

## Features

- **File Type Icons**: Different colors for PDF (red), Word (blue), Excel (green)
- **Truncated Excerpts**: Shows relevant text snippets with "..." for long content
- **Relevance Scores**: Displays similarity/relevance percentages
- **Expandable List**: Shows first N sources, with "Show more" button for additional sources
- **Confidence Badges**: Visual indicators for AI response confidence
- **Document Viewer Integration**: Click-to-view functionality for full documents

## Installation

The component is located at:
```
/Users/tamsar/Downloads/nabavkidata/frontend/components/ai/SourceCitation.tsx
```

## Usage

### Basic Usage

```tsx
import { SourceCitation } from "@/components/ai/SourceCitation";

const sources = [
  {
    doc_id: "doc-123",
    file_name: "Teh_specifikacija.pdf",
    excerpt: "ISO 13485 е задолжителна за медицински уреди...",
    similarity: 0.92,
    tender_id: "12345/2024",
    category: "Медицинска опрема"
  },
  {
    doc_id: "doc-456",
    file_name: "Dogovor.docx",
    excerpt: "Гарантен рок од 24 месеци...",
    similarity: 0.87
  }
];

function MyComponent() {
  const handleViewDocument = (docId: string, fileName?: string) => {
    // Open document viewer
    console.log(`View document: ${docId} (${fileName})`);
  };

  return (
    <SourceCitation
      sources={sources}
      onViewDocument={handleViewDocument}
      maxVisible={3}
      showConfidence={true}
      confidence="high"
    />
  );
}
```

### With ChatMessage Component

The `ChatMessage` component has been updated to automatically use `SourceCitation`:

```tsx
import { ChatMessage } from "@/components/chat/ChatMessage";

function ChatInterface() {
  const messages = [
    {
      role: "assistant",
      content: "Според документацијата, ISO 13485 е задолжителна за медицински уреди...",
      sources: [
        {
          doc_id: "doc-123",
          file_name: "Teh_specifikacija.pdf",
          chunk_text: "ISO 13485 е задолжителна за медицински уреди...",
          similarity: 0.92,
          tender_id: "12345/2024",
          category: "Медицинска опрема"
        }
      ],
      confidence: "high"
    }
  ];

  return (
    <div>
      {messages.map((msg, idx) => (
        <ChatMessage
          key={idx}
          role={msg.role}
          content={msg.content}
          sources={msg.sources}
          confidence={msg.confidence}
          onViewDocument={(docId, fileName) => {
            // Handle document viewing
          }}
        />
      ))}
    </div>
  );
}
```

## Props

### SourceCitationProps

| Prop | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `sources` | `Source[]` | Yes | - | Array of source documents |
| `onViewDocument` | `(docId: string, fileName?: string) => void` | No | - | Callback when user clicks "Отвори" button |
| `maxVisible` | `number` | No | `3` | Number of sources to show before "Show more" button |
| `showConfidence` | `boolean` | No | `false` | Whether to display confidence badge |
| `confidence` | `string` | No | - | Confidence level: 'high', 'medium', 'low' |

### Source Interface

```typescript
interface Source {
  doc_id?: string;           // Document ID for viewing
  tender_id?: string;        // Associated tender ID
  file_name?: string;        // Document filename
  excerpt?: string;          // Text excerpt from document
  chunk_text?: string;       // Alternative to excerpt
  similarity?: number;       // Similarity score (0-1 or 0-100)
  relevance?: number;        // Alternative to similarity
  title?: string;            // Tender title
  category?: string;         // Tender category
}
```

## Confidence Levels

The component supports three confidence levels with corresponding badge colors:

| Confidence | Badge Color | Label |
|-----------|-------------|-------|
| `high` / `висока` | Green | Висока сигурност |
| `medium` / `средна` | Yellow | Средна сигурност |
| `low` / `ниска` | Red | Ниска сигурност |

## File Type Icons

The component automatically detects file types and displays appropriate colored icons:

- **PDF**: Red `FileText` icon
- **Word (.doc, .docx)**: Blue `FileType` icon
- **Excel (.xls, .xlsx)**: Green `FileSpreadsheet` icon
- **Other**: Gray `FileText` icon

## Styling

The component uses Tailwind CSS and shadcn/ui components for consistent styling:

- Card with primary-colored border and background (`border-primary/20 bg-primary/5`)
- Hover effects on individual sources (`hover:shadow-md`)
- Responsive design with proper spacing
- Dark mode support

## Examples

### Example 1: Simple Sources (No Document Viewer)

```tsx
<SourceCitation
  sources={[
    {
      file_name: "Tender_123.pdf",
      excerpt: "Техничките барања се наведени во прилог 2...",
      similarity: 0.89
    }
  ]}
  maxVisible={3}
/>
```

### Example 2: With Confidence Badge

```tsx
<SourceCitation
  sources={sources}
  showConfidence={true}
  confidence="high"
  maxVisible={5}
/>
```

### Example 3: With Document Viewer Integration

```tsx
function TenderChatWidget({ tenderId }: { tenderId: string }) {
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null);

  const handleViewDocument = (docId: string, fileName?: string) => {
    setSelectedDoc(docId);
    // Open DocumentViewer modal or navigate to document page
  };

  return (
    <div>
      <SourceCitation
        sources={aiResponse.sources}
        onViewDocument={handleViewDocument}
        maxVisible={3}
        showConfidence={true}
        confidence={aiResponse.confidence}
      />

      {selectedDoc && (
        <DocumentViewer
          docId={selectedDoc}
          fileName="..."
          onClose={() => setSelectedDoc(null)}
        />
      )}
    </div>
  );
}
```

## Integration with Backend

The component works seamlessly with the backend AI chat endpoint:

```typescript
// Backend response format (from /api/ai/chat)
interface ChatResponse {
  response: string;
  sources: Array<{
    tender_id?: string;
    doc_id?: string;
    similarity: number;
    title?: string;
    category?: string;
  }>;
  confidence: string;  // 'high', 'medium', 'low'
}

// Frontend usage
const response = await api.queryRAG(question, tenderId);

<SourceCitation
  sources={response.sources.map(s => ({
    doc_id: s.doc_id,
    tender_id: s.tender_id,
    excerpt: s.chunk_text,
    similarity: s.similarity,
    title: s.title,
    category: s.category
  }))}
  confidence={response.confidence}
  showConfidence={true}
/>
```

## Accessibility

- Uses semantic HTML elements
- Proper ARIA labels for buttons
- Keyboard navigation support
- Focus indicators for interactive elements

## Browser Support

The component works in all modern browsers:
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## Dependencies

- React 18+
- lucide-react (icons)
- @/components/ui/card
- @/components/ui/button
- @/components/ui/badge
- Tailwind CSS

## Testing

To test the component:

1. Create a test page with sample sources
2. Verify file icons display correctly
3. Test expand/collapse functionality
4. Check confidence badges
5. Verify document viewer callback

## Future Enhancements

Potential improvements for future versions:

- [ ] Add pagination for very large source lists
- [ ] Support for audio/video file types
- [ ] Preview thumbnails for documents
- [ ] Search within sources
- [ ] Export sources list
- [ ] Copy source citations to clipboard
