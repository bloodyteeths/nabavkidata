# DocumentViewer Component

## Overview

The DocumentViewer component provides an inline document viewing experience that allows users to read tender documents without downloading them. It includes AI-powered features like summaries, key requirements extraction, and in-document search.

## Location

```
/Users/tamsar/Downloads/nabavkidata/frontend/components/tenders/DocumentViewer.tsx
```

## Features

### 1. Expandable Full Text View
- **Collapsed State**: Shows first 3 lines with "Expand" button
- **Expanded State**: Full document in scrollable container (max 600px)
- Toggle between states with chevron button

### 2. AI Summary Section
- Displays AI-generated summary when available
- Highlighted card with primary color theme
- Sparkles icon for visual distinction
- Auto-loaded from backend `/api/documents/{id}/content`

### 3. Key Requirements Display
- Bullet list of extracted requirements
- Green checkmark icon for visual emphasis
- Auto-extracted from document content by AI

### 4. Items/Products Mentioned
- Badge display of mentioned products/services
- Helps users quickly identify what's being procured
- Color-coded for easy scanning

### 5. In-Document Search
- Real-time search as you type
- Yellow highlighting of matching terms
- Case-insensitive matching
- Accessible via search icon input field

### 6. Interactive Actions
- **Download**: Opens original file in new tab
- **Copy**: Copies full text to clipboard with toast notification
- **Close**: Dismisses viewer and returns to document list
- Success animations for user feedback

## Usage

### Basic Integration

```tsx
import { DocumentViewer } from "@/components/tenders/DocumentViewer";

function MyComponent() {
  const [selectedDoc, setSelectedDoc] = useState<TenderDocument | null>(null);

  return (
    <>
      {selectedDoc && (
        <DocumentViewer
          docId={selectedDoc.doc_id}
          fileName={selectedDoc.file_name || "Unknown Document"}
          fileUrl={selectedDoc.file_url}
          contentText={selectedDoc.content_text}
          onClose={() => setSelectedDoc(null)}
        />
      )}
    </>
  );
}
```

### Props Interface

```typescript
interface DocumentViewerProps {
  docId: string;           // Unique document identifier
  fileName: string;        // Display name of the document
  fileUrl?: string;        // URL for downloading original file
  contentText?: string;    // Pre-loaded text content (optional)
  onClose?: () => void;    // Callback when close button clicked
}
```

## API Integration

### Frontend API Method

```typescript
// In /frontend/lib/api.ts
async getDocumentContent(docId: string) {
  return this.request<{
    doc_id: string;
    content_text: string;
    ai_summary?: string;
    key_requirements?: string[];
    items_mentioned?: string[];
  }>(`/api/documents/${encodeURIComponent(docId)}/content`);
}
```

### Backend Endpoint (To Be Implemented)

```python
# Endpoint: GET /api/documents/{doc_id}/content
# Response:
{
  "doc_id": "abc123",
  "content_text": "Full extracted text...",
  "ai_summary": "This document specifies medical equipment requirements...",
  "key_requirements": [
    "ISO 13485 certification",
    "CE marking required",
    "24-month warranty"
  ],
  "items_mentioned": [
    "CT Scanner 64-slice",
    "X-Ray Machine Digital",
    "Patient Monitors"
  ]
}
```

## Component Structure

```
DocumentViewer
├── Header
│   ├── File Icon + Name
│   └── Action Buttons (Download, Close)
├── AI Summary Section (conditional)
├── Key Requirements List (conditional)
├── Items Mentioned Badges (conditional)
└── Full Text Section
    ├── Header with Copy/Expand buttons
    ├── Search Bar (when expanded)
    └── Content Display
        ├── Loading Spinner
        ├── Text Content (with highlights)
        └── Empty State
```

## State Management

```typescript
const [expanded, setExpanded] = useState(false);
const [searchQuery, setSearchQuery] = useState("");
const [loading, setLoading] = useState(false);
const [documentContent, setDocumentContent] = useState<DocumentContent | null>(null);
const [copied, setCopied] = useState(false);
```

## Styling Features

- **Responsive Design**: Works on mobile, tablet, and desktop
- **Dark Mode Support**: All colors use CSS variables
- **Smooth Animations**: Expand/collapse transitions
- **Hover Effects**: Interactive elements have hover states
- **Color Coding**:
  - AI Summary: Primary color background
  - Key Requirements: Green checkmark icon
  - Search Highlights: Yellow background
  - Success States: Green check icon

## Performance Considerations

1. **Lazy Loading**: Content fetched only when viewer opens
2. **Dynamic Imports**: API module imported when needed
3. **Efficient Highlighting**: Uses string split and map
4. **Scroll Optimization**: Max height with overflow-y-auto
5. **State Cleanup**: Resets on component unmount

## User Experience Flow

1. User clicks "Прегледај" (View) button on document
2. DocumentViewer appears above document list
3. Shows preview or loads full content from API
4. User can:
   - Read AI summary instantly
   - See key requirements at a glance
   - Expand to read full text
   - Search for specific terms
   - Copy text to clipboard
   - Download original file
5. User closes viewer to return to document list

## Accessibility

- **Keyboard Navigation**: All buttons keyboard-accessible
- **Screen Readers**: Semantic HTML with proper labels
- **Focus Management**: Tab order follows logical flow
- **Color Contrast**: Meets WCAG AA standards
- **Alt Text**: Icons have accessible labels

## Dependencies

```json
{
  "@/components/ui/card": "Card components",
  "@/components/ui/button": "Button component",
  "@/components/ui/badge": "Badge component",
  "@/components/ui/input": "Input component",
  "lucide-react": "Icons library",
  "sonner": "Toast notifications"
}
```

## Integration Example (Tender Detail Page)

```tsx
// In /frontend/app/tenders/[id]/page.tsx

// 1. Add state for selected document
const [selectedDocument, setSelectedDocument] = useState<TenderDocument | null>(null);

// 2. Show viewer when document selected
{selectedDocument && (
  <DocumentViewer
    docId={selectedDocument.doc_id}
    fileName={selectedDocument.file_name || "Непознат документ"}
    fileUrl={selectedDocument.file_url}
    contentText={selectedDocument.content_text}
    onClose={() => setSelectedDocument(null)}
  />
)}

// 3. Add view button to document list
<Button
  variant="default"
  size="sm"
  onClick={() => setSelectedDocument(doc)}
>
  <FileText className="h-4 w-4 mr-1" />
  Прегледај
</Button>
```

## Future Enhancements

1. **PDF Rendering**: Direct PDF viewing without extraction
2. **Side-by-Side View**: Original + extracted content
3. **Annotations**: User can highlight and comment
4. **Print View**: Formatted for printing
5. **Export**: Save as different formats
6. **Version History**: Track document changes
7. **Multi-Document Search**: Search across all tender docs
8. **AI Q&A**: Ask questions about document content

## Testing Checklist

- [ ] Opens when view button clicked
- [ ] Closes when X button clicked
- [ ] Expands/collapses on button click
- [ ] Search highlights terms correctly
- [ ] Copy to clipboard works
- [ ] Download opens in new tab
- [ ] Handles missing content gracefully
- [ ] Loading state displays correctly
- [ ] AI summary displays when available
- [ ] Key requirements list renders properly
- [ ] Items badges display correctly
- [ ] Responsive on mobile devices
- [ ] Works in dark mode
- [ ] Keyboard navigation works
- [ ] Screen reader compatible

## Troubleshooting

### Document content not loading
- Check if backend endpoint `/api/documents/{id}/content` is implemented
- Verify API client method is properly configured
- Check browser console for API errors

### Search not highlighting
- Ensure `searchQuery` state is updating
- Check regex pattern in `highlightText` function
- Verify text content is a string

### Copy not working
- Check browser clipboard permissions
- Verify `navigator.clipboard` is available
- Ensure HTTPS in production (clipboard API requirement)

## Related Files

- `/frontend/components/tenders/DocumentViewer.tsx` - Main component
- `/frontend/app/tenders/[id]/page.tsx` - Integration location
- `/frontend/lib/api.ts` - API client with getDocumentContent method
- `/backend/api/documents.py` - Backend endpoint (to be implemented)

## License

Part of nabavkidata platform. All rights reserved.
