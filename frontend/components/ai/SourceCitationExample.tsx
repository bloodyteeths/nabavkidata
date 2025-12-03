"use client";

/**
 * SourceCitation Component Usage Examples
 *
 * This file demonstrates various ways to use the SourceCitation component
 * in different contexts within the Nabavkidata platform.
 */

import { useState } from "react";
import { SourceCitation, Source } from "./SourceCitation";
import { DocumentViewer } from "@/components/tenders/DocumentViewer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

// ============================================================================
// EXAMPLE 1: Basic Usage with Static Sources
// ============================================================================

export function BasicSourceCitationExample() {
  const sources: Source[] = [
    {
      doc_id: "doc-12345",
      file_name: "Teh_specifikacija.pdf",
      excerpt: "ISO 13485 е задолжителна за сите производители на медицински уреди. Сертификатот мора да биде издаден од акредитирана организација.",
      similarity: 0.92,
      tender_id: "12345/2024",
      category: "Медицинска опрема"
    },
    {
      doc_id: "doc-12346",
      file_name: "Dogovor.docx",
      excerpt: "Гарантен рок од 24 месеци за сите делови и работа. Понудувачот мора да обезбеди сервис во рок од 48 часа.",
      similarity: 0.87,
      tender_id: "12345/2024"
    },
    {
      doc_id: "doc-12347",
      file_name: "Cenovnik.xlsx",
      excerpt: "Единечна цена за артикл А123: 15.000 МКД без ДДВ. Рок на испорака: 30 дена.",
      similarity: 0.81
    }
  ];

  const handleViewDocument = (docId: string, fileName?: string) => {
    console.log(`Opening document: ${docId} (${fileName})`);
    // Navigate to document viewer or open modal
  };

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Basic Source Citation</h2>
      <SourceCitation
        sources={sources}
        onViewDocument={handleViewDocument}
        maxVisible={3}
        showConfidence={true}
        confidence="high"
      />
    </div>
  );
}

// ============================================================================
// EXAMPLE 2: Integration with DocumentViewer
// ============================================================================

export function SourceCitationWithViewer() {
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string>("");

  const sources: Source[] = [
    {
      doc_id: "doc-789",
      file_name: "Tender_specifications.pdf",
      excerpt: "Минимални технички барања: процесор Intel i7, RAM 16GB, SSD 512GB.",
      similarity: 0.95,
      tender_id: "67890/2024",
      category: "ИТ Опрема"
    }
  ];

  const handleViewDocument = (docId: string, fileName?: string) => {
    setSelectedDocId(docId);
    setSelectedFileName(fileName || "Документ");
  };

  const handleCloseViewer = () => {
    setSelectedDocId(null);
    setSelectedFileName("");
  };

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Source Citation with Document Viewer</h2>

      <SourceCitation
        sources={sources}
        onViewDocument={handleViewDocument}
        maxVisible={2}
        showConfidence={false}
      />

      {/* Document Viewer Modal */}
      {selectedDocId && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="w-full max-w-4xl max-h-[90vh] overflow-auto">
            <DocumentViewer
              docId={selectedDocId}
              fileName={selectedFileName}
              onClose={handleCloseViewer}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// EXAMPLE 3: AI Chat Response with Sources
// ============================================================================

export function AIChatWithSources() {
  const [messages, setMessages] = useState([
    {
      role: "user" as const,
      content: "Кои се техничките барања за овој тендер?"
    },
    {
      role: "assistant" as const,
      content: "Според техничката спецификација, главните барања се:\n\n1. ISO 13485 сертификација\n2. CE маркирање за ЕУ\n3. Минимум 24 месеци гаранција\n4. Технички сервис достапен во рок од 48 часа\n\nОвие барања се наведени во приложените документи.",
      sources: [
        {
          doc_id: "doc-tech-001",
          file_name: "Tehnichki_baranja.pdf",
          excerpt: "ISO 13485 сертификација е задолжителна. CE маркирање мора да биде приложено.",
          similarity: 0.94,
          category: "Технички документи"
        },
        {
          doc_id: "doc-warranty-002",
          file_name: "Garancija.docx",
          excerpt: "Минимален гарантен рок: 24 месеци за сите компоненти. Сервис: максимум 48 часа.",
          similarity: 0.91,
          category: "Гаранција и сервис"
        }
      ] as Source[],
      confidence: "high" as const
    }
  ]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI Asistent за Тендери</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className="space-y-2">
            {/* User Message */}
            {msg.role === "user" && (
              <div className="flex justify-end">
                <div className="bg-primary text-primary-foreground rounded-lg px-4 py-2 max-w-[80%]">
                  {msg.content}
                </div>
              </div>
            )}

            {/* Assistant Message with Sources */}
            {msg.role === "assistant" && (
              <div className="space-y-2">
                <div className="bg-muted rounded-lg px-4 py-2">
                  {msg.content}
                </div>
                {msg.sources && (
                  <SourceCitation
                    sources={msg.sources}
                    maxVisible={2}
                    showConfidence={true}
                    confidence={msg.confidence}
                    onViewDocument={(docId) => console.log(`View: ${docId}`)}
                  />
                )}
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// EXAMPLE 4: Different Confidence Levels
// ============================================================================

export function ConfidenceLevelsExample() {
  const highConfidenceSources: Source[] = [
    {
      doc_id: "doc-1",
      file_name: "Exact_match.pdf",
      excerpt: "Точен одговор на прашањето...",
      similarity: 0.98
    }
  ];

  const mediumConfidenceSources: Source[] = [
    {
      doc_id: "doc-2",
      file_name: "Related_doc.pdf",
      excerpt: "Поврзани информации...",
      similarity: 0.72
    }
  ];

  const lowConfidenceSources: Source[] = [
    {
      doc_id: "doc-3",
      file_name: "Vague_ref.pdf",
      excerpt: "Можеби релевантни податоци...",
      similarity: 0.55
    }
  ];

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold mb-2">Висока сигурност (95%+)</h3>
        <SourceCitation
          sources={highConfidenceSources}
          showConfidence={true}
          confidence="high"
        />
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-2">Средна сигурност (70-80%)</h3>
        <SourceCitation
          sources={mediumConfidenceSources}
          showConfidence={true}
          confidence="medium"
        />
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-2">Ниска сигурност (&lt;60%)</h3>
        <SourceCitation
          sources={lowConfidenceSources}
          showConfidence={true}
          confidence="low"
        />
      </div>
    </div>
  );
}

// ============================================================================
// EXAMPLE 5: Expandable Long List
// ============================================================================

export function ExpandableLongListExample() {
  // Generate many sources to demonstrate expand/collapse
  const manySources: Source[] = Array.from({ length: 10 }, (_, i) => ({
    doc_id: `doc-${i + 1}`,
    file_name: `Document_${i + 1}.pdf`,
    excerpt: `Релевантна информација од документ ${i + 1}...`,
    similarity: 0.9 - i * 0.05,
    tender_id: "12345/2024"
  }));

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Long List with Expand/Collapse</h2>
      <p className="text-sm text-muted-foreground">
        Shows first 3 sources by default, with "Show more" button
      </p>
      <SourceCitation
        sources={manySources}
        maxVisible={3}
        showConfidence={false}
      />
    </div>
  );
}

// ============================================================================
// EXAMPLE 6: API Integration Pattern
// ============================================================================

export function APIIntegrationExample() {
  const [loading, setLoading] = useState(false);
  const [aiResponse, setAIResponse] = useState<{
    answer: string;
    sources: Source[];
    confidence: string;
  } | null>(null);

  const handleAskQuestion = async () => {
    setLoading(true);

    // Simulate API call
    setTimeout(() => {
      // In real app, this would be: const response = await api.queryRAG(question, tenderId);
      setAIResponse({
        answer: "Според документацијата, минималната вредност на гаранцијата е 5% од вредноста на договорот.",
        sources: [
          {
            doc_id: "doc-garantija",
            file_name: "Garantna_podrska.pdf",
            excerpt: "Гарантна поддршка: минимум 5% од договорната вредност за период од 12 месеци.",
            similarity: 0.93,
            tender_id: "54321/2024",
            category: "Финансиски услови"
          }
        ],
        confidence: "high"
      });
      setLoading(false);
    }, 1000);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>API Integration Example</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button onClick={handleAskQuestion} disabled={loading}>
          {loading ? "Прашување..." : "Прашај за гаранција"}
        </Button>

        {aiResponse && (
          <div className="space-y-4">
            <div className="bg-muted p-4 rounded-lg">
              <p className="text-sm">{aiResponse.answer}</p>
            </div>

            <SourceCitation
              sources={aiResponse.sources}
              showConfidence={true}
              confidence={aiResponse.confidence}
              maxVisible={3}
              onViewDocument={(docId) => {
                console.log(`Opening document: ${docId}`);
                // Open DocumentViewer or navigate
              }}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// COMPLETE DEMO PAGE
// ============================================================================

export default function SourceCitationExamplesPage() {
  return (
    <div className="container mx-auto py-8 space-y-8">
      <div>
        <h1 className="text-3xl font-bold mb-2">SourceCitation Component Examples</h1>
        <p className="text-muted-foreground">
          Comprehensive examples showing various usage patterns for the SourceCitation component.
        </p>
      </div>

      <div className="grid gap-8">
        <BasicSourceCitationExample />
        <SourceCitationWithViewer />
        <AIChatWithSources />
        <ConfidenceLevelsExample />
        <ExpandableLongListExample />
        <APIIntegrationExample />
      </div>
    </div>
  );
}
